"""C1 nas mesmas estações do desenvolvimento, com cobertura temporal explícita.

Compara a normal integral de cada grade e, separadamente, a grade nos anos
observados. CHELSA só dispõe da normal integral nesta extração. Não avalia holdout.
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd

from codigo.bases_gee import MONTHS, SOURCES, sha256
from codigo.dados_temperatura import safe_path
from codigo.metricas import metricas
from codigo import modelos
from codigo.mapa_piloto import month_weights

KEY = ["station_id", "year", "month"]
NORMAL_KEY = ["station_id", "month"]


def build_normals(grids, monthly, station_ids):
    """Uma ausência invalida a normal da grade naquele suporte, sem média parcial."""
    station_ids = set(station_ids)
    grids = grids.copy()
    monthly = monthly.loc[monthly.station_id.isin(station_ids)].copy()
    if set(grids.source) != set(SOURCES) or set(grids.station_id) != station_ids:
        raise ValueError("Fontes/estações da extração não correspondem ao desenvolvimento.")
    if grids.duplicated(KEY + ["source"]).any() or monthly.duplicated(KEY).any():
        raise ValueError("Chaves estação/ano/mês duplicadas.")
    expected = pd.MultiIndex.from_tuples(
        [(s, p.year, p.month) for s in sorted(station_ids) for p in MONTHS], names=KEY)
    if not monthly.set_index(KEY).index.sort_values().equals(expected):
        raise ValueError("Calendário observado incompleto; conservar meses inválidos como NaN.")
    for _, group in grids.groupby("source"):
        if not group.set_index(KEY).index.sort_values().equals(expected):
            raise ValueError("Calendário da grade diferente de 1991–2020.")
    if np.isinf(grids.grid_c.to_numpy(float)).any():
        raise ValueError("Grade contém infinitos.")
    obs = monthly[KEY + ["temperature_c"]]
    joined = grids.merge(obs, on=KEY, validate="many_to_one")
    joined["observed"] = np.isfinite(joined.temperature_c)
    joined["matched"] = joined.grid_c.where(joined.observed)
    summary = joined.groupby(NORMAL_KEY + ["source"], as_index=False).agg(
        full_c=("grid_c", "mean"), n_full=("grid_c", "count"),
        matched_c=("matched", "mean"), n_matched=("matched", "count"), n_observed=("observed", "sum"))
    summary.loc[summary.n_full != 30, "full_c"] = np.nan
    summary.loc[(summary.n_matched != summary.n_observed) | (summary.n_observed == 0), "matched_c"] = np.nan
    return summary


def add_baselines(predictions, normals, development):
    if not set(predictions.station_id) == set(development.station_id):
        raise ValueError("Predições não correspondem exatamente ao desenvolvimento; revisar holdout.")
    ref = predictions.loc[predictions.method == "M0_chelsa"].copy()
    key = NORMAL_KEY + ["repeat"]
    if ref.empty or ref.duplicated(key).any():
        raise ValueError("Referência CHELSA ausente/duplicada.")
    check = ref.merge(development[NORMAL_KEY + ["temperature_c", "chelsa_c"]],
                      on=NORMAL_KEY, suffixes=("", "_input"), validate="many_to_one")
    if (len(check) != len(ref)
            or not np.allclose(check.temperature_c, check.temperature_c_input, atol=1e-8, rtol=0)
            or not np.allclose(check.prediction, check.chelsa_c, atol=1e-8, rtol=0)):
        raise ValueError("Predições existentes usam outro alvo ou outra base CHELSA.")
    wide = normals.pivot(index=NORMAL_KEY, columns="source", values="full_c")
    complete_rows = wide.notna().all(axis=1)
    eligible = complete_rows.groupby("station_id").agg(["sum", "count"])
    eligible = set(eligible.index[(eligible["sum"] == 12) & (eligible["count"] == 12)])
    if not eligible:
        raise ValueError("Nenhuma estação com as quatro bases nos 12 meses.")
    rows = [predictions.loc[predictions.station_id.isin(eligible)].copy()]
    for source in SOURCES:
        extra = ref.loc[ref.station_id.isin(eligible)].merge(
            wide[[source]].reset_index(), on=NORMAL_KEY, validate="many_to_one")
        extra["prediction"], extra["method"] = extra[source], f"M0_{source}"
        rows.append(extra.drop(columns=source))
    return pd.concat(rows, ignore_index=True), eligible


def summarize_extended(predictions):
    summary = modelos.summarize(predictions)
    rows = []
    weights = dict(enumerate(month_weights(), start=1))
    for (method, repeat), data in predictions.groupby(["method", "repeat"]):
        if not data.groupby("station_id").month.nunique().eq(12).all():
            raise ValueError("Avaliação anual exige 12 meses por estação.")
        weighted = data.assign(obs=data.temperature_c * data.month.map(weights),
                               pred=data.prediction * data.month.map(weights))
        annual = weighted.groupby("station_id")[["obs", "pred"]].sum()
        rows.append({"method": method, "repeat": repeat, "scope": "annual", "group": "all",
                     "n_stations": len(annual), **metricas(annual.obs, annual.pred)})
        bands = pd.cut(data.elevation_m, [-np.inf, 300, 800, np.inf], right=False,
                       labels=["below_300m", "300_to_800m", "at_least_800m"])
        for group, subset in data.groupby(bands, observed=True):
            rows.append({"method": method, "repeat": repeat, "scope": "elevation", "group": str(group),
                         "n_stations": subset.station_id.nunique(),
                         **metricas(subset.temperature_c, subset.prediction)})
    return pd.concat([summary, pd.DataFrame(rows)], ignore_index=True)


def main():
    input_path = safe_path("dados/processados/normais_covariaveis.csv")
    data = modelos.prepare(pd.read_csv(input_path, dtype={"station_id": str}))
    development = data.loc[~modelos.reserve_test(data)].copy()
    grid_path = safe_path("dados/bases/bases_mensais.csv")
    manifest = json.loads(grid_path.with_suffix(".manifesto.json").read_text(encoding="utf-8"))
    if manifest["output_sha256"] != sha256(grid_path) or manifest["input_sha256"] != sha256(input_path):
        raise ValueError("Extração não confere com os hashes de origem/saída.")
    grids = pd.read_csv(grid_path, dtype={"station_id": str})
    monthly = pd.read_csv(safe_path("dados/processados/temperatura_mensal.csv"), dtype={"station_id": str})
    normals = build_normals(grids, monthly, development.station_id)
    normals.to_csv(safe_path("dados/bases/normais_bases.csv"), index=False)
    coverage, baseline_scores = [], []
    for mode, column in [("full_1991_2020", "full_c"), ("same_observed_years", "matched_c")]:
        wide = normals.pivot(index=NORMAL_KEY, columns="source", values=column).reset_index()
        paired = development.merge(wide, on=NORMAL_KEY, validate="one_to_one")
        names = dict(SOURCES)
        if mode == "full_1991_2020":
            paired["chelsa"] = paired.chelsa_c
            names["chelsa"] = "local"
        for name in names:
            good = paired[name].notna()
            coverage.append({"mode": mode, "source": name, "expected_normals": len(paired),
                             "valid_normals": int(good.sum()),
                             "complete_stations": int(good.groupby(paired.station_id).sum().eq(12).sum())})
        common = paired[list(names)].notna().all(axis=1)
        eligible = common.groupby(paired.station_id).sum().eq(12)
        paired = paired[paired.station_id.isin(eligible[eligible].index)]
        for name in names:
            baseline_scores.append({"mode": mode, "source": name,
                                    "n_stations": paired.station_id.nunique(),
                                    **metricas(paired.temperature_c, paired[name])})
    public = safe_path("resultados/tabelas")
    pd.DataFrame(coverage).to_csv(public / "c1_cobertura_1991_2020.csv", index=False)
    pd.DataFrame(baseline_scores).to_csv(public / "c1_normais_1991_2020.csv", index=False)
    results = {}
    for block in (1, 2):
        path = safe_path(f"dados/modelagem/predicoes_{block}graus_grade_correction.csv")
        predictions = pd.read_csv(path, dtype={"station_id": str})
        all_predictions, eligible = add_baselines(predictions, normals, development)
        all_predictions.to_csv(safe_path(f"dados/bases/predicoes_c1_{block}graus.csv"), index=False)
        summary = summarize_extended(all_predictions)
        summary.to_csv(public / f"c1_modelos_{block}graus.csv", index=False)
        differences = pd.concat([modelos.paired_intervals(all_predictions, reference_method=f"M0_{name}")
                                 for name in ["chelsa", *SOURCES]], ignore_index=True)
        differences.to_csv(public / f"c1_diferencas_{block}graus.csv", index=False)
        results[str(block)] = {"common_stations": len(eligible),
                               "excluded_for_missing_grids": len(set(development.station_id) - eligible),
                               "prediction_input_sha256": sha256(path)}
    report = {"status": "exploratory_not_independent_of_source_grids", "comparisons": results,
              "grid_sha256": sha256(grid_path), "normals_input_sha256": sha256(input_path),
              "script_sha256": sha256(__file__), "holdout_scored": False,
              "limitations": ["C11: definições térmicas diferentes.",
                              "Normal observada usa 24–30 anos por mês; CHELSA só tem normal integral aqui.",
                              "Xavier e outras grades podem ter usado as estações avaliadas: C14 pendente.",
                              "Suporte espacial nativo de cada base; nenhuma correção focal de costa.",
                              "C9 acrescenta altitude; regiões e biomas ainda pendentes."]}
    (public / "c1_1991_2020.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(pd.DataFrame(baseline_scores).to_string(index=False))
    print(json.dumps(results), flush=True)


if __name__ == "__main__":
    main()
