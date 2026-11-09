"""Ensaio exploratório: normais observadas, blocos espaciais e teste reservado.

Não seleciona produto nacional e não usa o teste reservado para comparação.
MX é uma referência mensal inspirada no Xavier, não reprodução diária exata.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
from lightgbm import LGBMRegressor
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import LinearRegression
from sklearn.model_selection import GridSearchCV, GroupKFold
from sklearn.neighbors import BallTree

from codigo.metricas import metricas

ROOT = Path(__file__).resolve().parents[1]
FEATURES = ["latitude", "longitude", "elevation_m", "month_sin", "month_cos",
            "latitude_sin", "latitude_cos"]


def local_path(path):
    path = Path(path).resolve()
    if not path.is_relative_to(ROOT):
        raise ValueError("O caminho deve permanecer dentro de refinamento.")
    return path


def prepare(data):
    data = data.copy()
    required = ["station_id", "latitude", "longitude", "elevation_m", "month", "temperature_c"]
    if not set(required).issubset(data.columns):
        raise ValueError(f"Colunas obrigatórias: {required}")
    data = data.loc[data.month != 0].copy()
    if data.empty or data.station_id.isna().any():
        raise ValueError("Normais mensais vazias ou sem identificador de estação.")
    if not data.month.isin(range(1, 13)).all():
        raise ValueError("Mês deve estar entre 1 e 12.")
    if not data.latitude.between(-90, 90).all() or not data.longitude.between(-180, 180).all():
        raise ValueError("Coordenadas fora dos limites geográficos.")
    if data.duplicated(["station_id", "month"]).any():
        raise ValueError("Normais duplicadas por estação/mês.")
    if (data.groupby("station_id")[["latitude", "longitude", "elevation_m"]].nunique() > 1).any().any():
        raise ValueError("Metadados variam dentro da estação; auditar relocação.")
    # O arquivo de QC conserva NaN para normais sem cobertura. Essas estações
    # ficam auditadas na ingestão, mas não participam do ensaio balanceado.
    data = data.loc[np.isfinite(data.temperature_c)].copy()
    counts = data.groupby("station_id").month.nunique()
    data = data[data.station_id.isin(counts[counts == 12].index)].copy()
    if data.empty:
        raise ValueError("Nenhuma estação com 12 normais mensais válidas.")
    if not np.isfinite(data[required[1:]].to_numpy(float)).all():
        raise ValueError("As entradas das estações elegíveis devem ser finitas.")
    angle = 2 * np.pi * (data.month - 1) / 12
    data["month_sin"], data["month_cos"] = np.sin(angle), np.cos(angle)
    data["latitude_sin"] = data.latitude * data.month_sin
    data["latitude_cos"] = data.latitude * data.month_cos
    return data.sort_values(["station_id", "month"]).reset_index(drop=True)


def spatial_blocks(data, degrees):
    if degrees <= 0:
        raise ValueError("Tamanho do bloco deve ser positivo.")
    x = np.floor((data.longitude.to_numpy() + 180) / degrees).astype(int)
    y = np.floor((data.latitude.to_numpy() + 90) / degrees).astype(int)
    return np.array([f"{a}_{b}" for a, b in zip(x, y)])


def reserve_test(data, fraction=0.15, seed=20261018):
    # Partição fixa em blocos de 2° para todos os ensaios 1°/2°.
    groups = spatial_blocks(data, 2)
    unique = np.unique(groups)
    if len(unique) < 8:
        raise ValueError("Poucos blocos para teste reservado e CV espacial.")
    rng = np.random.default_rng(seed)
    held = rng.choice(unique, max(1, int(np.ceil(fraction * len(unique)))), replace=False)
    return np.isin(groups, held)


def model_candidates(seed):
    return {
        "M2_linear": (LinearRegression(), {}),
        "M4_random_forest": (RandomForestRegressor(n_estimators=150, random_state=seed, n_jobs=1),
                             {"min_samples_leaf": [3, 10], "max_features": [1.0]}),
        "M5_lightgbm": (LGBMRegressor(n_estimators=150, learning_rate=0.05,
                                      min_child_samples=20, random_state=seed, n_jobs=1,
                                      verbosity=-1, deterministic=True, force_col_wise=True),
                        {"num_leaves": [7, 15]}),
    }


def predict_mx(train, test):
    """IDW de cinco estações do TREINO, distâncias geodésicas e ajuste -6°C/km."""
    prediction = np.empty(len(test))
    for month in sorted(test.month.unique()):
        source = train[train.month == month]
        target_positions = np.flatnonzero(test.month.to_numpy() == month)
        target = test.iloc[target_positions]
        if len(source) < 5:
            raise ValueError("MX requer pelo menos cinco estações de treino por mês.")
        tree = BallTree(np.deg2rad(source[["latitude", "longitude"]]), metric="haversine")
        distances, indices = tree.query(np.deg2rad(target[["latitude", "longitude"]]), k=5)
        adjusted = (source.temperature_c.to_numpy()[indices]
                    - 0.006 * (target.elevation_m.to_numpy()[:, None]
                               - source.elevation_m.to_numpy()[indices]))
        weights = np.maximum(distances, 1e-12) ** -2
        prediction[target_positions] = (adjusted * weights).sum(axis=1) / weights.sum(axis=1)
    return prediction


def compare(data, block_size=2, repeats=3, folds=5, formulation="direct"):
    if formulation not in {"direct", "correction"}:
        raise ValueError("Formulação deve ser direct ou correction.")
    with_grid = "chelsa_c" in data.columns
    if formulation == "correction" and not with_grid:
        raise ValueError("Correção requer CHELSA nas estações.")
    features = feature_columns(data)
    checked = features + (["coarse_elevation_m"] if with_grid and "coarse_elevation_m" in data else [])
    if not set(checked).issubset(data.columns):
        raise ValueError("Covariáveis ausentes: CHELSA exige dem_elevation_m.")
    if not np.isfinite(data[checked]).all().all():
        raise ValueError("Covariáveis ausentes: não reduzir silenciosamente a amostra pareada.")
    held = reserve_test(data)
    development = data.loc[~held].reset_index(drop=True)
    groups = spatial_blocks(development, block_size)
    if len(np.unique(groups)) < folds + 2:
        raise ValueError("Blocos insuficientes para validação aninhada.")
    all_predictions, settings = [], []
    for repeat in range(repeats):
        outer = GroupKFold(n_splits=folds, shuffle=True, random_state=42 + repeat)
        for fold, (train_index, test_index) in enumerate(outer.split(development, groups=groups)):
            train, test = development.iloc[train_index], development.iloc[test_index]
            inner_groups = groups[train_index]
            inner = GroupKFold(n_splits=min(3, len(np.unique(inner_groups))))
            predicted = {"MX_mensal_referencia": predict_mx(train, test)}
            if with_grid:
                predicted["M0_chelsa"] = test.chelsa_c.to_numpy()
                if "coarse_elevation_m" in data:
                    predicted["M1_lapse_fixo"] = (
                        test.chelsa_c - 0.0065 * (test.dem_elevation_m - test.coarse_elevation_m)
                    ).to_numpy()
            response = train.temperature_c.copy()
            offset = 0
            if formulation == "correction":
                response -= train.chelsa_c
                offset = test.chelsa_c.to_numpy()
            for method, (estimator, parameters) in model_candidates(42 + repeat).items():
                if parameters:
                    estimator = GridSearchCV(estimator, parameters, cv=inner,
                                             scoring="neg_root_mean_squared_error", n_jobs=1)
                    estimator.fit(train[features], response, groups=inner_groups)
                    best = estimator.best_params_
                else:
                    estimator.fit(train[features], response)
                    best = {}
                predicted[method] = estimator.predict(test[features]) + offset
                settings.append({"repeat": repeat, "fold": fold, "method": method, "parameters": best})
            for method, values in predicted.items():
                rows = test[["station_id", "month", "temperature_c", "elevation_m"]].copy()
                rows["block"] = groups[test_index]
                rows["prediction"] = values
                rows["method"], rows["repeat"], rows["fold"] = method, repeat, fold
                all_predictions.append(rows)
            print(f"Bloco {block_size} graus; repetição {repeat + 1}; dobra {fold + 1}/{folds}", flush=True)
    partition = data[["station_id", "latitude", "longitude"]].drop_duplicates().copy()
    partition["reserved_test"] = reserve_test(partition)
    return pd.concat(all_predictions, ignore_index=True), partition, settings


def feature_columns(data):
    if "chelsa_c" not in data.columns:
        return FEATURES
    # Ao gerar mapas, altitude vem do mesmo MDS amostrado no treino.
    features = [item for item in FEATURES if item != "elevation_m"]
    features += ["dem_elevation_m", "chelsa_c"]
    if "slope_deg" in data:
        features.append("slope_deg")
    return features


def summarize(predictions):
    records = []
    # Cada repetição tem exatamente uma previsão fora da amostra por linha.
    for (method, repeat), rows in predictions.groupby(["method", "repeat"]):
        records.append({"method": method, "repeat": repeat, "scope": "global", "group": "all",
                        "n_stations": rows.station_id.nunique(),
                        **metricas(rows.temperature_c, rows.prediction)})
        for month, subset in rows.groupby("month"):
            if subset.station_id.nunique() >= 5:
                records.append({"method": method, "repeat": repeat, "scope": "month", "group": month,
                                "n_stations": subset.station_id.nunique(),
                                **metricas(subset.temperature_c, subset.prediction)})
    return pd.DataFrame(records)


def paired_intervals(predictions, n_bootstrap=1000, reference_method="MX_mensal_referencia"):
    # Reamostrar blocos, mantendo meses/estações/repetições juntos.
    key = ["station_id", "month", "repeat"]
    if predictions.empty or predictions.duplicated(key + ["method"]).any():
        raise ValueError("Predições vazias ou duplicadas para o pareamento.")
    methods = predictions.method.unique()
    if reference_method not in methods or n_bootstrap < 1:
        raise ValueError("Bootstrap requer a referência informada e pelo menos uma reamostragem.")
    paired = predictions.groupby(key)
    if (paired.size() != len(methods)).any():
        raise ValueError("Todos os métodos devem ter as mesmas estações/meses/repetições.")
    if (paired[["temperature_c", "block", "fold"]].nunique(dropna=False) != 1).any().any():
        raise ValueError("Observações, blocos e dobras devem ser idênticos entre métodos.")
    if not np.isfinite(predictions[["temperature_c", "prediction"]]).all().all():
        raise ValueError("As previsões pareadas devem ser finitas.")
    work = predictions.assign(squared_error=lambda x: (x.prediction - x.temperature_c) ** 2)
    sums = work.groupby(["block", "method"]).squared_error.agg(["sum", "count"])
    squared = sums["sum"].unstack("method")
    counts = sums["count"].unstack("method")
    rng = np.random.default_rng(42)
    draws = rng.integers(0, len(squared), (n_bootstrap, len(squared)))
    estimates = np.sqrt(squared.to_numpy()[draws].sum(axis=1) / counts.to_numpy()[draws].sum(axis=1))
    point = np.sqrt(squared.sum(axis=0) / counts.sum(axis=0))
    reference = squared.columns.get_loc(reference_method)
    output = []
    for index, method in enumerate(squared.columns):
        difference = estimates[:, index] - estimates[:, reference]
        output.append({"method": method, "reference": reference_method,
                       "delta_rmse_c": point.iloc[index] - point.iloc[reference],
                       "ci025": np.quantile(difference, 0.025), "ci975": np.quantile(difference, 0.975),
                       "n_blocks": len(squared), "bootstrap": n_bootstrap})
    return pd.DataFrame(output)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("normals", type=local_path)
    parser.add_argument("--block-size", type=float, choices=[1, 2], default=2)
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--formulation", choices=["direct", "correction"], default="direct")
    args = parser.parse_args()
    if args.repeats < 1:
        parser.error("repeats deve ser positivo")
    source = pd.read_csv(args.normals, dtype={"station_id": str})
    data = prepare(source)
    predictions, partition, settings = compare(data, args.block_size, args.repeats,
                                               formulation=args.formulation)
    private = ROOT / "dados" / "modelagem"
    public = ROOT / "resultados" / "tabelas"
    private.mkdir(parents=True, exist_ok=True)
    public.mkdir(parents=True, exist_ok=True)
    suffix = f"{int(args.block_size)}graus"
    with_grid = "chelsa_c" in data.columns
    if with_grid:
        suffix += f"_grade_{args.formulation}"
    predictions.to_csv(private / f"predicoes_{suffix}.csv", index=False)
    partition.to_csv(private / f"particao_reservada_{suffix}.csv", index=False)
    (private / f"parametros_{suffix}.json").write_text(json.dumps(settings, indent=2), encoding="utf-8")
    summarize(predictions).to_csv(public / f"modelos_exploratorios_{suffix}.csv", index=False)
    paired_intervals(predictions).to_csv(public / f"diferencas_mx_{suffix}.csv", index=False)
    comparisons = pd.concat([
        paired_intervals(predictions, reference_method=reference)
        for reference in ("M0_chelsa", "M2_linear", "M4_random_forest")
        if reference in predictions.method.unique()
    ], ignore_index=True)
    comparisons.to_csv(public / f"diferencas_pareadas_{suffix}.csv", index=False)
    manifest = {"status": "exploratorio_C11_C12_C13_pendentes", "features": feature_columns(data),
                "with_grid": with_grid, "formulation": args.formulation, "normal_period": "1991-2020",
                "input_sha256": hashlib.sha256(args.normals.read_bytes()).hexdigest(),
                "stations_complete": data.station_id.nunique(),
                "stations_development": int((~partition.reserved_test).sum()),
                "stations_reserved_unscored": int(partition.reserved_test.sum()),
                "block_size_degrees": args.block_size, "repeats": args.repeats,
                "folds_outer": 5, "folds_inner": 3, "test_seed": 20261018,
                "mx": "IDW mensal; 5 vizinhos treino; gamma=-0.006 C/m; não reprodução diária"}
    (public / f"ensaio_{suffix}.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
