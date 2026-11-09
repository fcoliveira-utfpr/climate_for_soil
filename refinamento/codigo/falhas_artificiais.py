"""C12 parcial: retira anos de séries mensais completas do desenvolvimento.

Compara média dos anos retidos, método das diferenças e regressão com grade.
Não testa lacunas diárias, não muda as normais usadas no piloto e não usa holdout.
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd

from codigo.bases_gee import sha256
from codigo.comparar_bases import KEY, build_normals
from codigo.dados_temperatura import safe_path
from codigo.metricas import metricas
from codigo import modelos

SEED = 20261103
REPETITIONS = 30
REFERENCES = ["era5", "terraclimate"]


def estimate_normal(observed, reference, retained):
    """Valores observados retirados nunca entram em nenhuma das três estimativas."""
    observed, reference = np.asarray(observed, float), np.asarray(reference, float)
    retained = np.asarray(retained)
    if (observed.ndim != 1 or reference.shape != observed.shape or retained.shape != observed.shape
            or retained.dtype != bool or retained.sum() < 3 or retained.all()
            or not np.isfinite(reference).all() or not np.isfinite(observed[retained]).all()):
        raise ValueError("Exige referência completa, máscara booleana e pelo menos três anos retidos.")
    kept_mean = observed[retained].mean()
    reference_mean = reference[retained].mean()
    x = reference[retained] - reference_mean
    variance = np.dot(x, x)
    if variance <= 1e-12:
        raise ValueError("Referência constante nos anos retidos: regressão não identificável.")
    slope = np.dot(x, observed[retained] - kept_mean) / variance
    filled = kept_mean + slope * (reference[~retained] - reference_mean)
    return {
        "available_years": float(kept_mean),
        "difference": float(kept_mean + reference.mean() - reference_mean),
        "regression_fill": float((observed[retained].sum() + filled.sum()) / len(observed)),
    }


def scenarios(rng):
    for n in (21, 24, 27):
        for repeat in range(REPETITIONS):
            retained = np.zeros(30, dtype=bool)
            retained[rng.choice(30, n, replace=False)] = True
            yield f"random_{n}", repeat, retained
    years = np.arange(1991, 2021)
    yield "recent_10", 0, years >= 2011
    yield "first_10", 0, years <= 2000
    yield "recent_24", 0, years >= 1997


def run_experiment(monthly, grids, development):
    # Reutiliza os controles de chaves, calendário e população da comparação C1.
    normals = build_normals(grids, monthly, development.station_id)
    complete = normals.query("n_observed == 30 and source in @REFERENCES").copy()
    eligible = complete.pivot(index=["station_id", "month"], columns="source", values="full_c")
    eligible = eligible.reindex(columns=REFERENCES).dropna()
    if eligible.empty:
        raise ValueError("Nenhuma série estação-mês completa nas observações e referências.")
    observations = monthly.set_index(KEY).temperature_c
    references = grids.set_index(KEY + ["source"]).grid_c
    metadata = development[["station_id", "latitude", "longitude"]].drop_duplicates("station_id")
    metadata["block"] = modelos.spatial_blocks(metadata, 2)
    blocks = metadata.set_index("station_id").block
    rng = np.random.default_rng(SEED)
    records = []
    for station, month in eligible.sort_index().index:
        keys = [(station, year, month) for year in range(1991, 2021)]
        observed = observations.loc[keys].to_numpy(float)
        if not np.isfinite(observed).all():
            raise ValueError("Série declarada completa contém ausência.")
        truth = observed.mean()
        series = {source: references.loc[[(s, y, m, source) for s, y, m in keys]].to_numpy(float)
                  for source in REFERENCES}
        for scenario, repeat, retained in scenarios(rng):
            # As duas grades e todos os métodos recebem exatamente a mesma máscara.
            for source, reference in series.items():
                for method, prediction in estimate_normal(observed, reference, retained).items():
                    records.append({"station_id": station, "month": month, "block": blocks.loc[station],
                                    "source": source, "scenario": scenario, "repeat": repeat,
                                    "retained_years": int(retained.sum()), "method": method,
                                    "observed": truth, "prediction": prediction})
    return pd.DataFrame(records)


def summarize(records):
    rows = []
    for keys, group in records.groupby(["source", "scenario", "method"]):
        rows.append(dict(zip(["source", "scenario", "method"], keys)) | {
            "n_stations": group.station_id.nunique(), "n_station_months": len(group[["station_id", "month"]].drop_duplicates()),
            "n_blocks": group.block.nunique(), "repetitions": group.repeat.nunique(),
            **metricas(group.observed, group.prediction)})
    return pd.DataFrame(rows)


def main():
    source = safe_path("dados/processados/normais_covariaveis.csv")
    monthly_path = safe_path("dados/processados/temperatura_mensal.csv")
    grid_path = safe_path("dados/bases/bases_mensais.csv")
    grid_manifest = json.loads(grid_path.with_suffix(".manifesto.json").read_text(encoding="utf-8"))
    if grid_manifest["input_sha256"] != sha256(source) or grid_manifest["output_sha256"] != sha256(grid_path):
        raise ValueError("Extração de referência divergente de seu manifesto.")
    data = modelos.prepare(pd.read_csv(source, dtype={"station_id": str}))
    development = data.loc[~modelos.reserve_test(data)].copy()
    monthly = pd.read_csv(monthly_path, dtype={"station_id": str})
    grids = pd.read_csv(grid_path, dtype={"station_id": str})
    records = run_experiment(monthly, grids, development)
    summary = summarize(records)
    private = safe_path("dados/bases/c12_falhas_artificiais.csv")
    records.to_csv(private, index=False)
    summary.to_csv(safe_path("resultados/tabelas/c12_falhas_artificiais.csv"), index=False)
    manifest = {
        "status": "partial_C12_artificial_missing_years_only", "seed": SEED, "random_repetitions": REPETITIONS,
        "n_stations": records.station_id.nunique(),
        "n_station_months": len(records[["station_id", "month"]].drop_duplicates()),
        "holdout_scored": False, "monthly_input_sha256": sha256(monthly_path),
        "grid_input_sha256": sha256(grid_path), "normals_input_sha256": sha256(source),
        "script_sha256": sha256(__file__), "private_output_sha256": sha256(private),
        "limitations": ["Elegibilidade é 30 meses-ano aprovados pelo QC diário de 80%, não 100% dos dias.",
                        "Amostra de séries longas, não representativa de todas as estações curtas.",
                        "Não testa falhas diárias, média compensada ou transferência de modelo espacial.",
                        "Métricas agrupam máscaras repetidas; não são 30 amostras independentes.",
                        "Nenhuma regra de preenchimento foi promovida ao pipeline de produção."]}
    safe_path("resultados/tabelas/c12_falhas_artificiais.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    print(summary[["source", "scenario", "method", "n_stations", "n_station_months", "rmse", "bias"]].to_string(index=False))


if __name__ == "__main__":
    main()
