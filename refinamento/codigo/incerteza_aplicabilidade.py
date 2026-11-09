"""§7: calibração da incerteza e área de aplicabilidade (AOA), na validação espacial.

Para cada dobra externa (blocos de 2°, 5 dobras × 3 repetições), refaz o candidato de produção
só com o treino, exatamente como os produtores de mapas: modelo principal e cinco membros
(temperatura: LightGBM corrigindo o CHELSA, membros com os hiperparâmetros escolhidos; chuva:
LightGBM corrigindo log1p(CHELSA), cada membro com a própria escolha interna). Nas estações de
teste guarda a previsão, a dispersão entre membros (SD) e o índice de dissimilaridade (DI).

Incerteza: compara a cobertura do intervalo ingênuo (previsão ± 1,645 SD) com dois intervalos
conformes de 90%: normalizado (± k·SD, k = quantil de |erro|/SD) e de largura constante
(± q, q = quantil de |erro|). A cobertura é honesta: k e q de cada dobra vêm das outras dobras.
O k e o q finais, para os mapas, usam todas as dobras.

AOA (Meyer & Pebesma, 2021): covariáveis padronizadas no treino e pesadas pela importância
(ganho) do modelo; DI = distância ao vizinho de treino mais próximo / distância média entre
pontos de treino; limiar = maior DI de treino (calculado entre dobras internas espaciais) dentro
do bigode superior do boxplot (Q3 + 1,5 IQR). Fora da AOA: DI acima do limiar.

O teste reservado não é usado. Uso, de dentro de refinamento/:
    python -B -m codigo.incerteza_aplicabilidade
"""
import json

import numpy as np
import pandas as pd
from scipy.spatial import cKDTree
from scipy.spatial.distance import pdist
from sklearn.base import clone
from sklearn.model_selection import GridSearchCV, GroupKFold

from codigo import chelsa_bilinear, mapa_chuva, modelos, modelos_chuva
from codigo.dados_temperatura import safe_path
from codigo.grade_brasil import digest
from codigo.metricas import metricas

Z90 = 1.6448536269514722
LEVEL = 0.90


def weighted_space(train_x, other_x, importance):
    mean = train_x.mean()
    scale = train_x.std(ddof=0).replace(0, 1)
    weights = np.asarray(importance, float)
    weights = weights / weights.sum() if weights.sum() > 0 else np.full(len(weights), 1 / len(weights))
    z_train = ((train_x - mean) / scale).to_numpy() * weights
    z_other = ((other_x - mean) / scale).to_numpy() * weights
    return z_train, z_other


def aoa_threshold(z_train, train_folds):
    """DI de treino entre dobras internas e limiar do bigode superior (como o CAST)."""
    mean_distance = pdist(z_train).mean()
    di_train = np.empty(len(z_train))
    for fold in np.unique(train_folds):
        inside = train_folds == fold
        tree = cKDTree(z_train[~inside])
        di_train[inside] = tree.query(z_train[inside])[0] / mean_distance
    q1, q3 = np.percentile(di_train, [25, 75])
    upper = q3 + 1.5 * (q3 - q1)
    threshold = float(di_train[di_train <= upper].max())
    return mean_distance, threshold


def dissimilarity(z_train, z_other, mean_distance):
    return cKDTree(z_train).query(z_other)[0] / mean_distance


def inner_fold_ids(n_rows, groups):
    ids = np.empty(n_rows, int)
    for fold, (_, index) in enumerate(GroupKFold(n_splits=5, shuffle=True, random_state=42).split(np.zeros((n_rows, 1)), groups=groups)):
        ids[index] = fold
    return ids


# ------------------------------------------------------------------- temperatura
def temperature_cv():
    data = modelos.prepare(pd.read_csv(safe_path("dados/processados/normais_covariaveis.csv"), dtype={"station_id": str}))
    if chelsa_bilinear.ativo():
        data = chelsa_bilinear.aplicar(data, "temperatura")
    held = modelos.reserve_test(data)
    development = data.loc[~held].reset_index(drop=True)
    features = modelos.feature_columns(development)
    groups = modelos.spatial_blocks(development, 2)
    rows = []
    for repeat in range(3):
        outer = GroupKFold(n_splits=5, shuffle=True, random_state=42 + repeat)
        for fold, (a, b) in enumerate(outer.split(development, groups=groups)):
            train, test = development.iloc[a], development.iloc[b]
            response = train.temperature_c - train.chelsa_c
            estimator, parameters = modelos.model_candidates(42)["M5_lightgbm"]
            search = GridSearchCV(estimator, parameters, cv=GroupKFold(n_splits=3),
                                  scoring="neg_root_mean_squared_error", n_jobs=1)
            search.fit(train[features], response, groups=groups[a])
            model = search.best_estimator_
            folds_inner = inner_fold_ids(len(train), groups[a])
            members = [clone(model).fit(train[features].iloc[folds_inner != k], response.iloc[folds_inner != k])
                       for k in range(5)]
            prediction = model.predict(test[features]) + test.chelsa_c.to_numpy()
            ensemble = np.stack([m.predict(test[features]) + test.chelsa_c.to_numpy() for m in members])
            z_train, z_test = weighted_space(train[features], test[features], model.booster_.feature_importance("gain"))
            mean_distance, threshold = aoa_threshold(z_train, folds_inner)
            rows.append(test[["station_id", "month", "temperature_c"]].rename(columns={"temperature_c": "observed"}).assign(
                block=groups[b], repeat=repeat, fold=fold, prediction=prediction, sd=ensemble.std(axis=0, ddof=1),
                di=dissimilarity(z_train, z_test, mean_distance), di_threshold=threshold))
            print(f"temperatura: repetição {repeat + 1}, dobra {fold + 1}", flush=True)
    return pd.concat(rows, ignore_index=True)


# ------------------------------------------------------------------------- chuva
def rain_fit(frame, blocks):
    search = GridSearchCV(modelos_chuva.RainRegressor(method="M5", formulation="correction"), {"complexity": [7, 15]},
                          cv=GroupKFold(n_splits=3), scoring="neg_root_mean_squared_error", n_jobs=1, error_score="raise")
    search.fit(frame[mapa_chuva.FEATURES], frame.precipitation_mm, groups=blocks)
    return search.best_estimator_


def rain_cv():
    data, _ = modelos_chuva.prepare()
    development = data.loc[~data.reserved].reset_index(drop=True)
    features = mapa_chuva.FEATURES
    groups = modelos.spatial_blocks(development, 2)
    rows = []
    for repeat in range(3):
        outer = GroupKFold(n_splits=5, shuffle=True, random_state=42 + repeat)
        for fold, (a, b) in enumerate(outer.split(development, groups=groups)):
            train, test = development.iloc[a], development.iloc[b]
            model = rain_fit(train, groups[a])
            folds_inner = inner_fold_ids(len(train), groups[a])
            members = [rain_fit(train.iloc[folds_inner != k], groups[a][folds_inner != k]) for k in range(5)]
            prediction = model.predict(test[features])
            ensemble = np.stack([m.predict(test[features]) for m in members])
            design_train, design_test = model.design(train[features]), model.design(test[features])
            importance = model.estimator_.booster_.feature_importance("gain")
            z_train, z_test = weighted_space(design_train, design_test, importance)
            mean_distance, threshold = aoa_threshold(z_train, folds_inner)
            rows.append(test[["station_id", "month", "precipitation_mm"]].rename(columns={"precipitation_mm": "observed"}).assign(
                block=groups[b], repeat=repeat, fold=fold, prediction=prediction, sd=ensemble.std(axis=0, ddof=1),
                di=dissimilarity(z_train, z_test, mean_distance), di_threshold=threshold))
            print(f"chuva: repetição {repeat + 1}, dobra {fold + 1}", flush=True)
    return pd.concat(rows, ignore_index=True)


RAIN_MONTH_FEATURES = ["latitude", "longitude", "elevation_30", "slope_30", "chelsa_mm"]


def rain_month_fit(frame, blocks, seed=42):
    """Um LightGBM por mês (C7), como em robustez_chuva.py: sem harmônicos, escolha interna por mês."""
    search = GridSearchCV(modelos_chuva.RainRegressor(method="M5", formulation="correction", random_state=seed),
                          {"complexity": [7, 15]}, cv=GroupKFold(n_splits=3), scoring="neg_root_mean_squared_error",
                          n_jobs=1, error_score="raise")
    search.fit(frame[RAIN_MONTH_FEATURES], frame.precipitation_mm, groups=blocks)
    return search.best_estimator_


def rain_month_cv():
    data, _ = modelos_chuva.prepare()
    if chelsa_bilinear.ativo():
        data = chelsa_bilinear.aplicar(data, "chuva")
    development = data.loc[~data.reserved].reset_index(drop=True)
    groups = modelos.spatial_blocks(development, 2)
    rows = []
    for repeat in range(3):
        outer = GroupKFold(n_splits=5, shuffle=True, random_state=42 + repeat)
        for fold, (a, b) in enumerate(outer.split(development, groups=groups)):
            train, test = development.iloc[a], development.iloc[b]
            for month in range(1, 13):
                source, target = train[train.month == month], test[test.month == month]
                blocks = modelos.spatial_blocks(source, 2)
                model = rain_month_fit(source, blocks, 42 + repeat)
                folds_inner = inner_fold_ids(len(source), blocks)
                members = [rain_month_fit(source.iloc[folds_inner != k], blocks[folds_inner != k], 42 + repeat)
                           for k in range(5)]
                prediction = model.predict(target[RAIN_MONTH_FEATURES])
                ensemble = np.stack([m.predict(target[RAIN_MONTH_FEATURES]) for m in members])
                z_train, z_test = weighted_space(model.design(source[RAIN_MONTH_FEATURES]), model.design(target[RAIN_MONTH_FEATURES]),
                                                 model.estimator_.booster_.feature_importance("gain"))
                mean_distance, threshold = aoa_threshold(z_train, folds_inner)
                rows.append(target[["station_id", "month", "precipitation_mm"]].rename(columns={"precipitation_mm": "observed"}).assign(
                    block=modelos.spatial_blocks(target, 2), repeat=repeat, fold=fold, prediction=prediction,
                    sd=ensemble.std(axis=0, ddof=1), di=dissimilarity(z_train, z_test, mean_distance), di_threshold=threshold))
            print(f"chuva por mês: repetição {repeat + 1}, dobra {fold + 1}", flush=True)
    return pd.concat(rows, ignore_index=True)


# -------------------------------------------------------------------- avaliação
def conformal_quantile(values, level=LEVEL):
    values = np.sort(np.asarray(values, float))
    rank = min(len(values), int(np.ceil((len(values) + 1) * level)))
    return float(values[rank - 1])


def evaluate(cv, variable, unit):
    cv = cv.assign(error=lambda x: x.prediction - x.observed,
                   score=lambda x: np.abs(x.prediction - x.observed) / np.maximum(x.sd, 1e-9),
                   outside=lambda x: x.di > x.di_threshold)
    coverage = []
    for repeat, frame in cv.groupby("repeat"):
        naive = np.abs(frame.error) <= Z90 * frame.sd
        normalized, constant, width_k, width_q = [], [], [], []
        for fold, part in frame.groupby("fold"):
            rest = frame[frame.fold != fold]
            k = conformal_quantile(rest.score)
            q = conformal_quantile(np.abs(rest.error))
            normalized.append(np.abs(part.error) <= k * part.sd)
            constant.append(np.abs(part.error) <= q)
            width_k.append(k * part.sd)
            width_q.append(np.full(len(part), q))
        coverage.append({"variable": variable, "repeat": repeat, "n": len(frame),
                         "coverage_naive_1645sd": float(naive.mean()),
                         "coverage_conformal_normalized": float(pd.concat(normalized).mean()),
                         "coverage_conformal_constant": float(pd.concat(constant).mean()),
                         "median_halfwidth_naive": float(np.median(Z90 * frame.sd)),
                         "median_halfwidth_normalized": float(np.median(np.concatenate(width_k))),
                         "median_halfwidth_constant": float(np.median(np.concatenate(width_q))), "unit": unit})
    aoa = []
    for repeat, frame in cv.groupby("repeat"):
        inside, outside = frame[~frame.outside], frame[frame.outside]
        aoa.append({"variable": variable, "repeat": repeat, "fraction_outside": float(frame.outside.mean()),
                    "stations_with_any_month_outside": int(frame[frame.outside].station_id.nunique()),
                    "rmse_inside": metricas(inside.observed, inside.prediction)["rmse"],
                    "rmse_outside": metricas(outside.observed, outside.prediction)["rmse"] if len(outside) else float("nan"),
                    "n_inside": len(inside), "n_outside": len(outside),
                    "median_threshold": float(frame.di_threshold.median()), "unit": unit})
    final = {"k90_normalized": conformal_quantile(cv.score), "q90_constant": conformal_quantile(np.abs(cv.error)),
             "naive_coverage_all": float((np.abs(cv.error) <= Z90 * cv.sd).mean()), "n": len(cv)}
    return pd.DataFrame(coverage), pd.DataFrame(aoa), final


def main():
    import sys
    outputs = {}
    runs = (("temperatura", temperature_cv, "degC"), ("chuva", rain_cv, "mm"), ("chuva_por_mes", rain_month_cv, "mm"))
    if len(sys.argv) > 1:
        runs = [run for run in runs if run[0] in sys.argv[1:]]
        previous = safe_path(f"resultados/tabelas/incerteza_aoa{'_bilinear' if chelsa_bilinear.ativo() else ''}.json")
        if previous.exists():
            outputs = {k: v for k, v in json.loads(previous.read_text(encoding="utf-8")).items() if isinstance(v, dict)}
    suffix = "_bilinear" if chelsa_bilinear.ativo() else ""
    for variable, runner, unit in runs:
        cv = runner()
        variable = variable + suffix
        path = safe_path(f"dados/modelagem/incerteza_aoa_{variable}_2graus.csv")
        cv.to_csv(path, index=False)
        coverage, aoa, final = evaluate(cv, variable, unit)
        coverage.to_csv(safe_path(f"resultados/tabelas/incerteza_cobertura_{variable}_2graus.csv"), index=False)
        aoa.to_csv(safe_path(f"resultados/tabelas/aoa_{variable}_2graus.csv"), index=False)
        outputs[variable] = {**final, "predictions_sha256": digest(path)}
        print(variable, json.dumps(final), "\n", coverage.drop(columns=["variable", "unit"]).round(3).to_string(index=False),
              "\n", aoa.drop(columns=["variable", "unit"]).round(3).to_string(index=False), flush=True)
    outputs.update({"level": LEVEL, "block_degrees": 2, "holdout_scored": False, "script_sha256": digest(__file__),
                    "note": "k90 multiplica a dispersão entre membros; q90 é meia-largura constante"})
    safe_path(f"resultados/tabelas/incerteza_aoa{suffix}.json").write_text(json.dumps(outputs, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
