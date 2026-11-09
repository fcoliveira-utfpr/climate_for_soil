"""C12 com falhas diárias: quanto erram a média mensal (temperatura) e a soma mensal (chuva).

Toma meses completos (todos os dias válidos) das estações de desenvolvimento em 1991-2020,
apaga dias de propósito e compara com o valor verdadeiro do mês:

- temperatura, média de (Tmax + Tmin)/2: 10% e 20% dos dias faltando (o limite da regra de
  80%), sorteados ou num bloco contínuo (no começo, no fim ou em posição sorteada);
- chuva, soma do mês: 1 dia, 10% e 20% faltando, sorteados; compara a soma simples dos dias
  restantes (o que aconteceria sem a regra de mês completo) com a soma reescalada pelo número
  de dias.

Até 60 meses completos por estação, 10 sorteios por mês e cenário, semente fixa.
O teste reservado não é usado. Uso, de dentro de refinamento/:  python -B -m codigo.falhas_diarias
"""
import json

import numpy as np
import pandas as pd

from codigo import modelos, modelos_chuva
from codigo.dados_temperatura import align_observations, load_observations, safe_path
from codigo.grade_brasil import digest

RNG = np.random.default_rng(20261108)
MONTHS_PER_STATION = 60
DRAWS = 10


_CALENDAR = {}


def complete_months(series, dates):
    """Valores diários de cada mês de 1991-2020 com todos os dias válidos."""
    key = (dates[0], len(dates))
    if key not in _CALENDAR:
        inside = (dates >= "1991-01-01") & (dates <= "2020-12-31")
        periods = dates[inside].to_period("M")
        starts = np.flatnonzero(np.r_[True, periods[1:] != periods[:-1]])
        _CALENDAR[key] = (inside, starts, np.diff(np.r_[starts, len(periods)]))
    inside, starts, lengths = _CALENDAR[key]
    values = series[inside]
    counts = np.add.reduceat(np.isfinite(values).astype(int), starts)
    return [values[s:s + n] for s, n, c in zip(starts, lengths, counts) if c == n]


def remove_days(n_days, fraction, mode):
    k = max(1, int(round(n_days * fraction))) if fraction < 1 else int(fraction)
    if mode == "sorteados":
        return RNG.choice(n_days, k, replace=False)
    start = {"inicio": 0, "fim": n_days - k, "bloco": int(RNG.integers(0, n_days - k + 1))}[mode]
    return np.arange(start, start + k)


def temperature():
    data = modelos.prepare(pd.read_csv(safe_path("dados/processados/normais_covariaveis.csv"), dtype={"station_id": str}))
    stations = set(data.loc[~modelos.reserve_test(data), "station_id"])
    tmax, tmin = load_observations("dados/brutos/Tmax.npz"), load_observations("dados/brutos/Tmin.npz")
    max_order, min_order, _ = align_observations(tmax, tmin)
    ids = tmax.stations.station_id.to_numpy()[max_order]
    rows = []
    for column, station in enumerate(ids):
        if station not in stations:
            continue
        mean = (tmax.data[:, max_order[column]] + tmin.data[:, min_order[column]]) / 2
        spans = complete_months(mean, tmax.dates)
        if not spans:
            continue
        chosen = RNG.choice(len(spans), min(MONTHS_PER_STATION, len(spans)), replace=False)
        for index in chosen:
            values = spans[index]
            truth = values.mean()
            for fraction in (0.1, 0.2):
                for mode in ("sorteados", "bloco", "inicio", "fim"):
                    draws = DRAWS if mode in ("sorteados", "bloco") else 1
                    for _ in range(draws):
                        keep = np.setdiff1d(np.arange(len(values)), remove_days(len(values), fraction, mode))
                        rows.append((station, fraction, mode, values[keep].mean() - truth))
    errors = pd.DataFrame(rows, columns=["station_id", "fraction_missing", "mode", "error_c"])
    summary = (errors.groupby(["fraction_missing", "mode"]).error_c
               .agg(n="size", bias_c="mean", rmse_c=lambda e: float(np.sqrt(np.mean(e ** 2))),
                    p95_abs_c=lambda e: float(np.quantile(np.abs(e), 0.95)))
               .reset_index())
    summary["stations"] = errors.station_id.nunique()
    return summary


def rain():
    data, _ = modelos_chuva.prepare()
    stations = set(data.loc[~data.reserved, "station_id"])
    observations = load_observations("dados/brutos/pr.npz")
    rows = []
    for column, station in enumerate(observations.stations.station_id):
        if station not in stations:
            continue
        spans = complete_months(observations.data[:, column], observations.dates)
        spans = [s for s in spans if s.sum() > 0]
        if not spans:
            continue
        chosen = RNG.choice(len(spans), min(MONTHS_PER_STATION, len(spans)), replace=False)
        for index in chosen:
            values = spans[index]
            truth = values.sum()
            for fraction in (1, 0.1, 0.2):
                for _ in range(DRAWS):
                    removed = remove_days(len(values), fraction, "sorteados")
                    keep = np.setdiff1d(np.arange(len(values)), removed)
                    simple = values[keep].sum()
                    scaled = simple * len(values) / len(keep)
                    rows.append((station, "1 dia" if fraction == 1 else f"{int(fraction * 100)}%",
                                 truth, simple - truth, scaled - truth))
    errors = pd.DataFrame(rows, columns=["station_id", "missing", "truth_mm", "error_simple_mm", "error_scaled_mm"])
    summary = errors.groupby("missing").apply(lambda e: pd.Series({
        "n": len(e), "stations": e.station_id.nunique(),
        "bias_simple_pct": 100 * e.error_simple_mm.sum() / e.truth_mm.sum(),
        "rmse_simple_mm": float(np.sqrt(np.mean(e.error_simple_mm ** 2))),
        "bias_scaled_pct": 100 * e.error_scaled_mm.sum() / e.truth_mm.sum(),
        "rmse_scaled_mm": float(np.sqrt(np.mean(e.error_scaled_mm ** 2))),
        "p95_abs_scaled_mm": float(np.quantile(np.abs(e.error_scaled_mm), 0.95)),
    }), include_groups=False).reset_index()
    return summary


def main():
    t = temperature()
    t.to_csv(safe_path("resultados/tabelas/c12_falhas_diarias_temperatura.csv"), index=False)
    print(t.round(4).to_string(index=False), flush=True)
    r = rain()
    r.to_csv(safe_path("resultados/tabelas/c12_falhas_diarias_chuva.csv"), index=False)
    print(r.round(3).to_string(index=False))
    report = {"months_per_station": MONTHS_PER_STATION, "draws": DRAWS, "seed": 20261108, "period": "1991-2020",
              "complete_month": "all days valid", "holdout_scored": False, "script_sha256": digest(__file__)}
    safe_path("resultados/tabelas/c12_falhas_diarias.json").write_text(json.dumps(report, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
