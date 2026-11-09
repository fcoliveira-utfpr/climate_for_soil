"""Avaliação final, uma única vez, no teste reservado (estações nunca usadas em nenhuma escolha).

O método está congelado no preparo do Paraná (dados/parana/preparo.joblib): LightGBM corrigindo o
CHELSA para a temperatura e um LightGBM por mês corrigindo log1p(CHELSA) para a chuva, ajustados
em todas as estações de desenvolvimento. Aqui eles são aplicados às estações reservadas
(15% dos blocos de 2°, sorteados em 18/10/2026 antes de qualquer modelo) e comparados com:
- temperatura: CHELSA, gradiente fixo (M1) e o método do Xavier (MX, IDW de 5 vizinhos com
  gradiente recalibrado em pares de estações a até 90 km fora dos blocos reservados);
- chuva: CHELSA, CHIRPS, ERA5-Land e o método do Xavier (IDW e ADW de 5 vizinhos).
Os vizinhos do MX são as estações de desenvolvimento. Também mede a cobertura real do intervalo
de 90% calibrado e a fração fora da área de aplicabilidade, e calcula intervalos de 95% para as
diferenças de RMSE reamostrando blocos de 2°.

Uso, de dentro de refinamento/:  python -B -m codigo.teste_reservado --confirmo-uso-unico
"""
import argparse
import json

import joblib
import numpy as np
import pandas as pd

from codigo import chelsa_bilinear, mapa_parana, mapa_piloto, modelos, modelos_chuva, mx_completo
from codigo.dados_temperatura import safe_path
from codigo.grade_brasil import digest
from codigo.metricas import metricas

GUARD = "resultados/tabelas/teste_reservado.json"


def block_bootstrap(frame, observed, methods, reference, n=2000, seed=42):
    blocks = frame.block.unique()
    rng = np.random.default_rng(seed)
    sums = {m: frame.assign(e=(frame[m] - frame[observed]) ** 2).groupby("block").e.agg(["sum", "count"]) for m in methods}
    rows = []
    draws = rng.integers(0, len(blocks), (n, len(blocks)))
    for method in methods:
        point = np.sqrt(sums[method]["sum"].sum() / sums[method]["count"].sum()) - \
            np.sqrt(sums[reference]["sum"].sum() / sums[reference]["count"].sum())
        a = sums[method].loc[blocks].to_numpy()
        b = sums[reference].loc[blocks].to_numpy()
        diff = np.sqrt(a[draws, 0].sum(1) / a[draws, 1].sum(1)) - np.sqrt(b[draws, 0].sum(1) / b[draws, 1].sum(1))
        rows.append({"method": method, "reference": reference, "delta_rmse": float(point),
                     "ci025": float(np.quantile(diff, 0.025)), "ci975": float(np.quantile(diff, 0.975)),
                     "n_blocks": int(len(blocks))})
    return pd.DataFrame(rows)


def metrics_table(frame, observed, methods, annual_weights=None):
    rows = []
    for method in methods:
        rows.append({"method": method, "scope": "mensal", "n_stations": frame.station_id.nunique(),
                     **metricas(frame[observed], frame[method])})
        if annual_weights is None:
            annual = frame.groupby("station_id")[[observed, method]].sum()
        else:
            w = np.asarray(annual_weights)[frame.month - 1]
            annual = frame.assign(**{observed: frame[observed] * w, method: frame[method] * w}).groupby("station_id")[[observed, method]].sum()
        rows.append({"method": method, "scope": "anual", "n_stations": len(annual), **metricas(annual[observed], annual[method])})
    return pd.DataFrame(rows)


def temperature(preparo):
    part = preparo["temperatura"]
    data = modelos.prepare(pd.read_csv(safe_path(mapa_parana.TEMP_INPUT), dtype={"station_id": str}))
    if preparo["chelsa_bilinear"]:
        data = chelsa_bilinear.aplicar(data, "temperatura")
    held = modelos.reserve_test(data)
    development, test = data.loc[~held].reset_index(drop=True), data.loc[held].reset_index(drop=True)
    features = part["features"]
    frame = test[["station_id", "month", "temperature_c", "latitude", "longitude"]].copy()
    frame["block"] = modelos.spatial_blocks(test, 2)
    frame["modelo"] = part["model"].predict(test[features]) + test.chelsa_c.to_numpy()
    spread = np.stack([m.predict(test[features]) + test.chelsa_c.to_numpy() for m in part["members"]]).std(axis=0, ddof=1)
    frame["CHELSA"] = test.chelsa_c.to_numpy()
    frame["M1_gradiente_fixo"] = (test.chelsa_c - 0.0065 * (test.dem_elevation_m - test.coarse_elevation_m)).to_numpy()
    pairs, auxiliary = mx_completo.auxiliary_pairs()
    reserved_blocks = set(modelos.spatial_blocks(test, 2))
    excluded = set(test.station_id) | set(auxiliary.index[np.isin(modelos.spatial_blocks(auxiliary, 2), list(reserved_blocks))])
    pooled, monthly, n_pairs = mx_completo.gamma_from_pairs(pairs, excluded)
    frame["MX_xavier"] = mx_completo.mx_temperature(development, test, np.full(12, pooled))
    di = mapa_parana.dissimilarity(test[features], part["aoa"])
    methods = ["modelo", "CHELSA", "M1_gradiente_fixo", "MX_xavier"]
    table = metrics_table(frame, "temperature_c", methods, mapa_piloto.month_weights())
    diffs = pd.concat([block_bootstrap(frame, "temperature_c", methods, ref) for ref in ("CHELSA", "MX_xavier")])
    half = part["k90_monthly"] * spread
    extra = {"coverage_90_monthly": float((np.abs(frame.modelo - frame.temperature_c) <= half).mean()),
             "median_halfwidth_monthly_c": float(np.median(half)),
             "fraction_outside_aoa": float((di > part["aoa"]["threshold"]).mean()),
             "reserved_stations": int(test.station_id.nunique()), "gamma_c_per_km": 1000 * pooled, "gamma_pairs": n_pairs}
    annual = frame.assign(w=np.asarray(mapa_piloto.month_weights())[frame.month - 1])
    annual = annual.assign(o=annual.temperature_c * annual.w, p=annual.modelo * annual.w).groupby("station_id")[["o", "p"]].sum()
    extra["coverage_90_annual"] = float((np.abs(annual.p - annual.o) <= part["q90_annual"]).mean())
    return table, diffs, extra


def rain(preparo):
    part = preparo["chuva"]
    data, _ = modelos_chuva.prepare()
    if preparo["chelsa_bilinear"]:
        data = chelsa_bilinear.aplicar(data, "chuva")
    development, test = data.loc[~data.reserved].reset_index(drop=True), data.loc[data.reserved].reset_index(drop=True)
    frame = test[["station_id", "month", "precipitation_mm", "latitude", "longitude"]].copy()
    frame["block"] = modelos.spatial_blocks(test, 2)
    frame["modelo"] = np.nan
    half = np.full(len(test), np.nan)
    outside = np.zeros(len(test), bool)
    for month in range(1, 13):
        unit = part["months"][month]
        rows = np.flatnonzero(test.month.to_numpy() == month)
        x = test.iloc[rows][part["features"]]
        frame.loc[rows, "modelo"] = unit["model"].predict(x)
        half[rows] = part["k90_monthly"] * np.stack([m.predict(x) for m in unit["members"]]).std(axis=0, ddof=1)
        outside[rows] = mapa_parana.dissimilarity(unit["model"].design(x), unit["aoa"]) > unit["aoa"]["threshold"]
    frame["CHELSA"], frame["CHIRPS"], frame["ERA5_Land"] = test.chelsa_mm.to_numpy(), test.chirps_mm.to_numpy(), test.era5_mm.to_numpy()
    stations = development.groupby("station_id")[["latitude", "longitude"]].first()
    correlation = mx_completo.anomaly_correlations(list(stations.index))
    cdd, _ = mx_completo.cdd_from_pairs(stations, correlation)
    idw, adw = mx_completo.mx_rain(development, test, cdd)
    frame["MX_idw"], frame["MX_adw"] = idw, adw
    methods = ["modelo", "CHELSA", "CHIRPS", "ERA5_Land", "MX_idw", "MX_adw"]
    table = metrics_table(frame, "precipitation_mm", methods)
    diffs = pd.concat([block_bootstrap(frame, "precipitation_mm", methods, ref) for ref in ("CHELSA", "CHIRPS", "MX_adw")])
    annual = frame.groupby("station_id")[["precipitation_mm", "modelo"]].sum()
    extra = {"coverage_90_monthly": float((np.abs(frame.modelo - frame.precipitation_mm) <= half).mean()),
             "coverage_90_annual": float((np.abs(annual.modelo - annual.precipitation_mm) <= part["q90_annual"]).mean()),
             "median_halfwidth_monthly_mm": float(np.median(half)), "fraction_outside_aoa": float(outside.mean()),
             "reserved_stations": int(test.station_id.nunique()), "cdd_km": cdd}
    return table, diffs, extra


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--confirmo-uso-unico", action="store_true", required=True)
    parser.parse_args()
    if safe_path(GUARD).exists():
        raise SystemExit("O teste reservado já foi avaliado; não reabrir (ver resultados/tabelas/teste_reservado.json).")
    preparo_path = safe_path(mapa_parana.PREP)
    preparo = joblib.load(preparo_path)
    t_table, t_diff, t_extra = temperature(preparo)
    r_table, r_diff, r_extra = rain(preparo)
    t_table.to_csv(safe_path("resultados/tabelas/teste_reservado_temperatura.csv"), index=False)
    t_diff.to_csv(safe_path("resultados/tabelas/teste_reservado_diferencas_temperatura.csv"), index=False)
    r_table.to_csv(safe_path("resultados/tabelas/teste_reservado_chuva.csv"), index=False)
    r_diff.to_csv(safe_path("resultados/tabelas/teste_reservado_diferencas_chuva.csv"), index=False)
    report = {"evaluated_once": True, "frozen_preparo_sha256": digest(preparo_path),
              "chelsa_bilinear": preparo["chelsa_bilinear"], "temperature": t_extra, "rain": r_extra,
              "script_sha256": digest(__file__)}
    safe_path(GUARD).write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(t_table[["method", "scope", "n_stations", "bias", "rmse"]].round(3).to_string(index=False))
    print(t_diff.round(3).to_string(index=False))
    print(r_table[["method", "scope", "n_stations", "bias", "rmse"]].round(3).to_string(index=False))
    print(r_diff.round(3).to_string(index=False))
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
