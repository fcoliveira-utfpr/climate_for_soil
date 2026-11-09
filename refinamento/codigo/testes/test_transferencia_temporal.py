import numpy as np
import pandas as pd
import pytest

from codigo import modelos
from codigo.bases_gee import MONTHS, SOURCES
from codigo.transferencia_temporal import compare_periods, prepare_periods


def inputs():
    normals, monthly = [], []
    for i in range(16):
        for month in range(1, 13):
            normals.append({"station_id": f"S{i:02d}", "month": month, "latitude": -30 + 2.1 * (i // 4),
                            "longitude": -60 + 2.1 * (i % 4), "elevation_m": 100 + i * 30,
                            "dem_elevation_m": 100 + i * 30, "slope_deg": 3.,
                            "temperature_c": 22., "chelsa_c": 20.})
        for p in MONTHS:
            base = 20 + 0.05 * (p.year - 1991) + np.sin(2 * np.pi * p.month / 12)
            monthly.append({"station_id": f"S{i:02d}", "year": p.year, "month": p.month,
                            "temperature_c": base + 2, "grid_c": base})
    normals = modelos.prepare(pd.DataFrame(normals))
    series = pd.DataFrame(monthly)
    held = set(normals.loc[modelos.reserve_test(normals), "station_id"])
    grids = pd.concat([series[~series.station_id.isin(held)].assign(source=s) for s in SOURCES], ignore_index=True)
    return series.drop(columns="grid_c"), grids.drop(columns="temperature_c"), normals, held


def test_periods_exclude_original_holdout_and_require_each_month_in_both_decades():
    monthly, grids, normals, held = inputs()
    early, late = prepare_periods(monthly, grids, normals)
    assert held.isdisjoint(early.station_id) and held.isdisjoint(late.station_id)
    assert early[['station_id', 'month']].equals(late[['station_id', 'month']])
    station = early.station_id.iloc[0]
    monthly.loc[(monthly.station_id == station) & (monthly.month == 3)
                & monthly.year.between(2001, 2003), "temperature_c"] = np.nan
    early, late = prepare_periods(monthly, grids, normals)
    assert station not in set(early.station_id) | set(late.station_id)


def test_future_responses_do_not_enter_earlier_training_and_spatial_groups_stay_together(monkeypatch):
    monthly, grids, normals, _ = inputs()
    early, late = prepare_periods(monthly, grids, normals)
    monkeypatch.setattr(modelos, 'model_candidates', lambda seed: {'M2_linear': (modelos.LinearRegression(), {})})
    first, _ = compare_periods(early, late, repeats=1)
    second, _ = compare_periods(early, late.assign(temperature_c=late.temperature_c + 100), repeats=1)
    target_method = 'M2_linear_from_2001_2010'
    a = first[first.method.eq(target_method)]
    b = second[second.method.eq(target_method)]
    np.testing.assert_allclose(a.prediction, a.temperature_c, atol=1e-10)
    np.testing.assert_allclose(a.prediction, b.prediction, atol=1e-10)
    assert first.groupby(['station_id', 'repeat']).fold.nunique().eq(1).all()
    assert first.groupby(['block', 'repeat']).fold.nunique().eq(1).all()
    assert not first.duplicated(['station_id', 'month', 'repeat', 'method']).any()
    with pytest.raises(ValueError, match='chaves ordenadas'):
        compare_periods(early, late.iloc[::-1], repeats=1)
