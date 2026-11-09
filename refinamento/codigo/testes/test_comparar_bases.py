import numpy as np
import pandas as pd
import pytest

from codigo.bases_gee import MONTHS, SOURCES
from codigo.comparar_bases import add_baselines, build_normals, summarize_extended
from codigo.mapa_piloto import month_weights


def input_series():
    monthly = pd.DataFrame([{"station_id": s, "year": p.year, "month": p.month,
                             "temperature_c": 20.0}
                            for s in ["S1", "S2"] for p in MONTHS])
    grids = pd.concat([monthly.assign(source=source, grid_c=lambda f: 10 + (f.year - 1991))
                       for source in SOURCES], ignore_index=True).drop(columns="temperature_c")
    return grids, monthly


def test_full_and_matched_years_are_different_and_masking_never_becomes_zero():
    grids, monthly = input_series()
    monthly.loc[(monthly.station_id == "S1") & (monthly.year < 1997), "temperature_c"] = np.nan
    grids.loc[(grids.station_id == "S1") & (grids.source == "era5")
              & (grids.month == 1) & (grids.year == 1991), "grid_c"] = np.nan
    normals = build_normals(grids, monthly, ["S1", "S2"])
    x = normals.query("station_id == 'S1' and month == 2 and source == 'era5'").iloc[0]
    assert x.full_c == pytest.approx(24.5)
    assert x.matched_c == pytest.approx(27.5)
    assert x.n_observed == x.n_matched == 24
    masked = normals.query("station_id == 'S1' and month == 1 and source == 'era5'").iloc[0]
    assert np.isnan(masked.full_c)  # Não calcular média de 29 anos como se fossem 30.
    assert masked.matched_c == pytest.approx(27.5)  # Ausência fora dos anos observados.
    grids.loc[(grids.station_id == "S1") & (grids.source == "era5")
              & (grids.month == 1) & (grids.year == 2010), "grid_c"] = np.nan
    masked = build_normals(grids, monthly, ["S1", "S2"]).query(
        "station_id == 'S1' and month == 1 and source == 'era5'").iloc[0]
    assert np.isnan(masked.matched_c)


@pytest.mark.parametrize("damage", ["grid_missing", "duplicate", "obs_missing", "held_station"])
def test_normal_comparison_rejects_wrong_calendar_or_population(damage):
    grids, monthly = input_series()
    if damage == "grid_missing":
        grids = grids.iloc[1:]
    elif damage == "duplicate":
        monthly = pd.concat([monthly, monthly.iloc[:1]])
    elif damage == "obs_missing":
        monthly = monthly.iloc[1:]
    else:
        grids.loc[0, "station_id"] = "HELD_OUT"
    with pytest.raises(ValueError):
        build_normals(grids, monthly, ["S1", "S2"])


def test_annual_metrics_aggregate_predictions_before_errors():
    frame = pd.DataFrame({"station_id": ["S1"] * 12, "month": range(1, 13),
                          "repeat": 0, "method": "M0_chelsa", "elevation_m": 100,
                          "temperature_c": 20.0, "prediction": [22.0] + [20.0] * 11})
    annual = summarize_extended(frame).query("scope == 'annual'").iloc[0]
    assert annual.rmse == pytest.approx(2 * month_weights()[0])
    assert annual.n == annual.n_stations == 1
    with pytest.raises(ValueError, match="12 meses"):
        summarize_extended(frame.iloc[1:])


def test_new_baselines_keep_existing_folds_and_explicit_common_station_set():
    grids, monthly = input_series()
    grids.loc[(grids.station_id == "S1") & (grids.source == "era5")
              & (grids.month == 1) & (grids.year == 1991), "grid_c"] = np.nan
    normals = build_normals(grids, monthly, ["S1", "S2"])
    development = monthly.query("year == 1991").drop(columns="year").assign(chelsa_c=21.)
    predictions = development.assign(method="M0_chelsa", prediction=21., repeat=0,
                                      block="b", fold=0, elevation_m=100.).drop(columns="chelsa_c")
    result, eligible = add_baselines(predictions, normals, development)
    assert eligible == {"S2"}
    assert set(result.method) == {"M0_chelsa", "M0_era5", "M0_xavier", "M0_terraclimate"}
    assert result.fold.eq(0).all() and result.block.eq("b").all()
    assert len(result) == 48
    damaged = predictions.copy()
    damaged.loc[0, "temperature_c"] += 1
    with pytest.raises(ValueError, match="outro alvo"):
        add_baselines(damaged, normals, development)
    with pytest.raises(ValueError, match="holdout"):
        add_baselines(predictions.assign(station_id="HELD"), normals, development)
