"""Controle de qualidade: homogeneidade das séries de temperatura (§3.1).

Para cada estação de desenvolvimento, monta a série mensal estação − ERA5-Land no mesmo
pixel (1991-2020, só meses aceitos), tira o ciclo sazonal da diferença e calcula a média de
cada ano com pelo menos 9 meses. Uma quebra (troca de sensor, mudança de local) aparece como
um degrau nessa diferença, porque o ERA5 não muda junto com a estação. A referência é a
grade no próprio pixel, e não as estações vizinhas, para não depender de interpolação.

Testes: Pettitt (não paramétrico) e SNHT de Alexandersson, nas médias anuais. Quebra provável
quando Pettitt p < 0,01, SNHT acima do valor crítico de 95% e degrau de pelo menos 0,3 °C.
As estações marcadas não são retiradas automaticamente: o resultado vai para revisão, e a
tabela pública traz só o resumo. Também compara o erro de validação do modelo candidato nas
estações com e sem quebra provável.

Uso, de dentro de refinamento/:  python -B -m codigo.homogeneidade
"""
import json

import numpy as np
import pandas as pd

from codigo import modelos
from codigo.dados_temperatura import safe_path
from codigo.grade_brasil import digest
from codigo.metricas import metricas

SNHT_CRITICAL_95 = {10: 5.70, 20: 6.95, 30: 7.65, 40: 8.10}  # Khaliq & Ouarda (2007)
MIN_YEARS = 15
MIN_MONTHS = 9
STEP_C = 0.3


def pettitt(series):
    x = np.asarray(series, float)
    n = len(x)
    signs = np.sign(x[:, None] - x[None, :])
    u = np.array([signs[: t + 1, t + 1:].sum() for t in range(n - 1)])
    k = np.abs(u).max()
    position = int(np.abs(u).argmax())
    p = min(1.0, 2 * np.exp(-6 * k ** 2 / (n ** 3 + n ** 2)))
    return position, float(p)


def snht(series):
    x = np.asarray(series, float)
    z = (x - x.mean()) / x.std(ddof=1)
    n = len(z)
    t = np.array([k * z[:k].mean() ** 2 + (n - k) * z[k:].mean() ** 2 for k in range(1, n)])
    return int(t.argmax()) + 1, float(t.max())  # k = tamanho do primeiro trecho


def snht_critical(n):
    keys = sorted(SNHT_CRITICAL_95)
    return float(np.interp(n, keys, [SNHT_CRITICAL_95[k] for k in keys]))


def annual_differences():
    monthly = pd.read_csv(safe_path("dados/processados/temperatura_mensal.csv"), dtype={"station_id": str})
    monthly = monthly[monthly.accepted.astype(str).eq("True") & monthly.temperature_c.notna()]
    era5 = pd.read_csv(safe_path("dados/bases/bases_mensais.csv"), dtype={"station_id": str})
    era5 = era5[era5.source.eq("era5")].rename(columns={"grid_c": "era5_c"})[["station_id", "year", "month", "era5_c"]]
    merged = monthly.merge(era5, on=["station_id", "year", "month"], how="inner").dropna(subset=["era5_c"])
    merged["difference"] = merged.temperature_c - merged.era5_c
    merged["anomaly"] = merged.difference - merged.groupby(["station_id", "month"]).difference.transform("mean")
    annual = merged.groupby(["station_id", "year"]).agg(anomaly=("anomaly", "mean"), months=("anomaly", "size")).reset_index()
    return annual[annual.months >= MIN_MONTHS]


def main():
    annual = annual_differences()
    records = []
    for station, frame in annual.groupby("station_id"):
        frame = frame.sort_values("year")
        n = len(frame)
        if n < MIN_YEARS:
            records.append({"station_id": station, "years": n, "tested": False})
            continue
        values = frame.anomaly.to_numpy()
        position, p_value = pettitt(values)
        k, statistic = snht(values)
        step = float(values[k:].mean() - values[:k].mean())
        records.append({"station_id": station, "years": n, "tested": True,
                        "pettitt_year": int(frame.year.iloc[position + 1]), "pettitt_p": p_value,
                        "snht_year": int(frame.year.iloc[k]), "snht_t": statistic, "snht_critical_95": snht_critical(n),
                        "step_c": step,
                        "probable_break": bool(p_value < 0.01 and statistic > snht_critical(n) and abs(step) >= STEP_C)})
    result = pd.DataFrame(records)
    private = safe_path("dados/modelagem/homogeneidade_temperatura.csv")
    result.to_csv(private, index=False)

    flagged = set(result.loc[result.probable_break.fillna(False).astype(bool), "station_id"])
    stored = pd.read_csv(safe_path("dados/modelagem/predicoes_2graus_grade_correction.csv"), dtype={"station_id": str})
    rows = []
    for method in ("M5_lightgbm", "M0_chelsa"):
        subset = stored[stored.method == method]
        for label, part in (("com_quebra_provavel", subset[subset.station_id.isin(flagged)]),
                            ("sem_quebra_provavel", subset[~subset.station_id.isin(flagged)])):
            if part.station_id.nunique() >= 5:
                rows.append({"method": method, "group": label, "n_stations": int(part.station_id.nunique()),
                             **metricas(part.temperature_c, part.prediction)})
    errors = pd.DataFrame(rows)
    tested = result[result.tested]
    summary = pd.DataFrame([{
        "stations_development": int(result.station_id.nunique()),
        "stations_tested": int(len(tested)),
        "stations_not_tested_short_series": int((~result.tested).sum()),
        "pettitt_p_below_0_01": int((tested.pettitt_p < 0.01).sum()),
        "snht_above_critical_95": int((tested.snht_t > tested.snht_critical_95).sum()),
        "probable_breaks": int(len(flagged)),
        "median_abs_step_c_flagged": float(tested.loc[tested.probable_break, "step_c"].abs().median()) if flagged else float("nan"),
        "max_abs_step_c_flagged": float(tested.loc[tested.probable_break, "step_c"].abs().max()) if flagged else float("nan"),
        "break_years_flagged": ";".join(str(y) for y in sorted(tested.loc[tested.probable_break, "snht_year"].astype(int))),
    }])
    summary.to_csv(safe_path("resultados/tabelas/homogeneidade_temperatura.csv"), index=False)
    errors.to_csv(safe_path("resultados/tabelas/homogeneidade_erros_temperatura.csv"), index=False)
    audit = {"reference": "ERA5-Land monthly at the station pixel", "min_years": MIN_YEARS, "min_months_per_year": MIN_MONTHS,
             "step_threshold_c": STEP_C, "tests": "Pettitt p<0.01 and SNHT>95% critical and |step|>=0.3 C",
             "removed_stations": 0, "private_station_table_sha256": digest(private), "script_sha256": digest(__file__)}
    safe_path("resultados/tabelas/homogeneidade_temperatura.json").write_text(json.dumps(audit, indent=2), encoding="utf-8")
    print(summary.T.to_string(header=False))
    print(errors.round(3).to_string(index=False))


if __name__ == "__main__":
    main()
