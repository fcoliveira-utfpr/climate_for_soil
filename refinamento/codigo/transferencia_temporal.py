"""C13: correção do ERA5 treinada em 2001–2010 e avaliada em 2011–2020.

Também ajusta um controle contemporâneo em outras estações de 2011–2020.
As duas condições usam os mesmos blocos; teste reservado original permanece fechado.
Trata-se de hindcast com a grade da década avaliada, não de previsão do tempo.
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd
from sklearn.model_selection import GridSearchCV, GroupKFold

from codigo import modelos
from codigo.bases_gee import sha256
from codigo.comparar_bases import KEY, build_normals, summarize_extended
from codigo.dados_temperatura import safe_path

FEATURES = [x for x in modelos.FEATURES if x != "elevation_m"] + ["dem_elevation_m", "slope_deg", "era5_c"]


def prepare_periods(monthly, grids, normals, minimum_years=8):
    if not 1 <= minimum_years <= 10:
        raise ValueError("Cobertura decenal deve ficar entre 1 e 10 anos por mês.")
    development = normals.loc[~modelos.reserve_test(normals)].copy()
    build_normals(grids, monthly, development.station_id)  # Calendário e população completos.
    observed = monthly[monthly.station_id.isin(development.station_id)]
    joined = observed.merge(grids[grids.source.eq("era5")][KEY + ["grid_c"]],
                            on=KEY, validate="one_to_one")
    metadata = development.drop(columns=["temperature_c", "chelsa_c", "n_years", "coverage"], errors="ignore")
    periods = []
    for start, end in [(2001, 2010), (2011, 2020)]:
        subset = joined[joined.year.between(start, end)].copy()
        subset["observed"] = np.isfinite(subset.temperature_c)
        subset["matched_grid"] = subset.grid_c.where(subset.observed)
        summary = subset.groupby(["station_id", "month"], as_index=False).agg(
            temperature_c=("temperature_c", "mean"), era5_c=("matched_grid", "mean"),
            n_observed=("observed", "sum"), n_grid=("matched_grid", "count"))
        good = (summary.n_observed >= minimum_years) & (summary.n_grid == summary.n_observed)
        summary.loc[~good, ["temperature_c", "era5_c"]] = np.nan
        periods.append(metadata.merge(summary, on=["station_id", "month"], validate="one_to_one"))
    eligible = set(development.station_id)
    for frame in periods:
        counts = frame.dropna(subset=["temperature_c", "era5_c"]).groupby("station_id").month.nunique()
        eligible &= set(counts[counts == 12].index)
    if not eligible:
        raise ValueError("Nenhuma estação elegível nas duas décadas.")
    return tuple(frame[frame.station_id.isin(eligible)].sort_values(["station_id", "month"])
                 .reset_index(drop=True) for frame in periods)


def compare_periods(early, late, block_size=2, repeats=3):
    keys = ["station_id", "month"]
    if not early[keys].equals(late[keys]) or early.duplicated(keys).any():
        raise ValueError("As décadas devem conter as mesmas chaves ordenadas.")
    if not np.isfinite(early[FEATURES + ["temperature_c"]]).all().all() or not np.isfinite(late[FEATURES + ["temperature_c"]]).all().all():
        raise ValueError("Covariáveis/alvos não finitos.")
    groups = modelos.spatial_blocks(early, block_size)
    if not np.array_equal(groups, modelos.spatial_blocks(late, block_size)):
        raise ValueError("Blocos diferentes entre décadas.")
    if len(np.unique(groups)) < 7:
        raise ValueError("Blocos insuficientes para validação aninhada.")
    predictions, settings = [], []
    for repeat in range(repeats):
        outer = GroupKFold(n_splits=5, shuffle=True, random_state=42 + repeat)
        for fold, (train_index, test_index) in enumerate(outer.split(early, groups=groups)):
            test = late.iloc[test_index]
            predicted = {"M0_era5": test.era5_c.to_numpy()}
            for label, frame in [("from_2001_2010", early), ("from_2011_2020", late)]:
                train = frame.iloc[train_index]
                target = train.temperature_c - train.era5_c
                for name, (estimator, parameters) in modelos.model_candidates(42 + repeat).items():
                    best = {}
                    if parameters:
                        estimator = GridSearchCV(estimator, parameters,
                            cv=GroupKFold(n_splits=3), scoring="neg_root_mean_squared_error", n_jobs=1)
                        estimator.fit(train[FEATURES], target, groups=groups[train_index])
                        best = estimator.best_params_
                    else:
                        estimator.fit(train[FEATURES], target)
                    method = f"{name}_{label}"
                    predicted[method] = estimator.predict(test[FEATURES]) + test.era5_c.to_numpy()
                    settings.append({"repeat": repeat, "fold": fold, "method": method, "parameters": best})
            for method, values in predicted.items():
                result = test[["station_id", "month", "temperature_c", "elevation_m"]].copy()
                result["block"], result["fold"], result["repeat"] = groups[test_index], fold, repeat
                result["method"], result["prediction"] = method, values
                predictions.append(result)
            print(f"C13: bloco {block_size}°, repetição {repeat + 1}, dobra {fold + 1}/5", flush=True)
    return pd.concat(predictions, ignore_index=True), settings


def main():
    source = safe_path("dados/processados/normais_covariaveis.csv")
    monthly_path = safe_path("dados/processados/temperatura_mensal.csv")
    grid_path = safe_path("dados/bases/bases_mensais.csv")
    manifest = json.loads(grid_path.with_suffix(".manifesto.json").read_text(encoding="utf-8"))
    if manifest["input_sha256"] != sha256(source) or manifest["output_sha256"] != sha256(grid_path):
        raise ValueError("Extração divergente de seu manifesto.")
    normals = modelos.prepare(pd.read_csv(source, dtype={"station_id": str}))
    early, late = prepare_periods(
        pd.read_csv(monthly_path, dtype={"station_id": str}),
        pd.read_csv(grid_path, dtype={"station_id": str}), normals)
    if set(late.station_id) & set(normals.loc[modelos.reserve_test(normals), "station_id"]):
        raise ValueError("Teste reservado entrou no ensaio.")
    for block in (1, 2):
        predictions, settings = compare_periods(early, late, block_size=block)
        predictions.to_csv(safe_path(f"dados/bases/c13_predicoes_{block}graus.csv"), index=False)
        safe_path(f"dados/bases/c13_parametros_{block}graus.json").write_text(json.dumps(settings, indent=2), encoding="utf-8")
        summarize_extended(predictions).to_csv(safe_path(f"resultados/tabelas/c13_modelos_{block}graus.csv"), index=False)
        comparisons = pd.concat([modelos.paired_intervals(predictions, reference_method=reference)
                                  for reference in ["M0_era5", "M5_lightgbm_from_2011_2020"]], ignore_index=True)
        comparisons.to_csv(safe_path(f"resultados/tabelas/c13_diferencas_{block}graus.csv"), index=False)
    report = {"status": "temporal_and_spatial_hindcast_era5_only", "holdout_scored": False,
              "stations": late.station_id.nunique(), "features": FEATURES, "minimum_years_per_month": 8,
              "train_period": "2001-2010", "test_period": "2011-2020", "control_training_period": "2011-2020",
              "monthly_input_sha256": sha256(monthly_path), "grid_input_sha256": sha256(grid_path),
              "normals_input_sha256": sha256(source), "script_sha256": sha256(__file__),
              "limitations": ["A covariável é ERA5 da década avaliada; isto é hindcast, não previsão futura.",
                              "Controle contemporâneo também mantém estações e blocos de teste fora do treino.",
                              "Compara apenas correção de ERA5; não demonstra transferência da correção de CHELSA.",
                              "Meses decenais admitem 8–10 anos, com referência nos mesmos anos observados.",
                              "O anual usa pesos fixos 1991–2020 apenas para comparabilidade sazonal.",
                              "Não prova validade retrospectiva em 1991–2000 nem independência das grades."]}
    safe_path("resultados/tabelas/c13_transferencia.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
