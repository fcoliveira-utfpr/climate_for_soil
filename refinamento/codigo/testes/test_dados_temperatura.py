"""Casos sintéticos explícitos; não são dados climáticos nem resultados reais."""

import importlib.util
from pathlib import Path
import sys

import numpy as np
import pandas as pd
import pytest


MODULE_PATH = Path(__file__).resolve().parents[1] / "dados_temperatura.py"
SPEC = importlib.util.spec_from_file_location("dados_temperatura", MODULE_PATH)
dt = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = dt
SPEC.loader.exec_module(dt)


def observations(maximum=30.0, minimum=10.0, stations=1):
    dates = pd.date_range("1991-01-01", "2020-12-31")
    metadata = pd.DataFrame({
        "station_id": [f"S{i}" for i in range(stations)],
        "latitude": -20.0 - np.arange(stations),
        "longitude": -40.0 - np.arange(stations),
        "elevation_m": 100.0 + np.arange(stations),
    })
    return (
        dt.Observations(np.full((len(dates), stations), maximum), metadata.copy(), dates),
        dt.Observations(np.full((len(dates), stations), minimum), metadata.copy(), dates),
    )


def month(result, year, number):
    return result.monthly.loc[(result.monthly.year == year) & (result.monthly.month == number)].iloc[0]


def write_archive(tmp_path, **overrides):
    path = tmp_path / "observations.npz"
    arrays = {"data": np.ones((3, 1)), "lat_lon_alt": np.array([[-20, -40, 100]]), "ID": np.array(["A001"])}
    arrays.update(overrides)
    np.savez(path, **arrays)
    return path


def test_only_paired_days_enter_monthly_mean():
    tmax, tmin = observations()
    tmax.data[0, 0] = np.nan
    tmin.data[1, 0] = np.nan
    tmax.data[1, 0] = 49.0  # Seria viés se Tmax e Tmin fossem agregadas separadamente.
    result = dt.prepare_temperature(tmax, tmin)
    january = month(result, 1991, 1)
    assert january.valid_days == 29
    assert january.temperature_c == 20


def test_month_threshold_uses_calendar_and_leap_year():
    tmax, tmin = observations()
    for year in [1991, 1992]:
        rows = np.flatnonzero((tmax.dates.year == year) & (tmax.dates.month == 2))
        tmin.data[rows[23:], 0] = np.nan
    result = dt.prepare_temperature(tmax, tmin, minimum_day_fraction=0.8)
    assert month(result, 1991, 2).expected_days == 28
    assert month(result, 1991, 2).accepted
    assert month(result, 1992, 2).expected_days == 29
    assert not month(result, 1992, 2).accepted
    assert pd.isna(month(result, 1992, 2).temperature_c)


def test_coverage_is_required_for_each_month_and_annual_needs_all_twelve():
    tmax, tmin = observations()
    tmin.data[(tmin.dates.month == 1) & (tmin.dates.year <= 1997), 0] = np.nan
    result = dt.prepare_temperature(tmax, tmin)
    january = result.normals.loc[result.normals.month == 1].iloc[0]
    assert january.n_years == 23
    assert january.coverage == pytest.approx(23 / 30)
    assert pd.isna(january.temperature_c)
    assert 0 not in result.normals.month.to_list()
    annual_sensitivity = result.sensitivity.loc[result.sensitivity.month == 0]
    assert annual_sensitivity.stations_eligible.to_list() == [1, 0, 0]


def test_annual_weights_include_the_eight_leap_days_in_1991_2020():
    tmax, tmin = observations(maximum=0.0, minimum=0.0)
    tmax.data[tmax.dates.month == 2] = 40.0
    result = dt.prepare_temperature(tmax, tmin)
    annual = result.normals.loc[result.normals.month == 0].iloc[0]
    assert annual.temperature_c == pytest.approx(20 * (28 * 30 + 8) / (365 * 30 + 8))
    assert annual.n_years == 30


def test_physical_limits_and_inversion_exclude_pairs_but_flags_only_audit():
    tmax, tmin = observations()
    tmax.data[0, 0] = 50
    tmin.data[1, 0] = -30
    tmax.data[2, 0] = 5
    tmin.data[3, 0] = np.inf
    result = dt.prepare_temperature(tmax, tmin)
    assert month(result, 1991, 1).valid_days == 27
    audit = result.stations.iloc[0]
    assert audit.tmax_invalid_days == 1
    assert audit.tmin_invalid_days == 2
    assert audit.inverted_days == 1
    assert audit.tmax_constant_flag
    assert audit.annual_normal_eligible  # Flag não elimina a série sem revisão.


def test_station_alignment_uses_ids_and_checks_coordinates():
    tmax, tmin = observations(stations=2)
    tmin.data[:, 1] = 0
    tmin.data = tmin.data[:, ::-1]
    tmin.stations = tmin.stations.iloc[::-1].reset_index(drop=True)
    _, order, excluded = dt.align_observations(tmax, tmin)
    aligned = tmin.data[:, order]
    assert aligned[0].tolist() == [10, 0]
    assert excluded.empty
    tmin.stations.loc[0, "latitude"] += 0.01
    with pytest.raises(ValueError, match="divergentes"):
        dt.align_observations(tmax, tmin)


def test_archive_length_is_checked_against_explicit_calendar(tmp_path):
    path = write_archive(tmp_path)
    loaded = dt.load_observations(path, "2000-01-01", "2000-01-03")
    assert loaded.stations.station_id.to_list() == ["A001"]
    with pytest.raises(ValueError, match="Confirme as datas"):
        dt.load_observations(path)


def test_legacy_object_ids_are_read_only_by_restricted_unpickler(tmp_path):
    path = write_archive(tmp_path, ID=np.array(["A001"], dtype=object))
    loaded = dt.load_observations(path, "2000-01-01", "2000-01-03")
    assert loaded.stations.station_id.to_list() == ["A001"]


def test_legacy_object_ids_reject_unapproved_global_without_executing_it(tmp_path):
    class Malicious:
        def __reduce__(self):
            return (eval, ("1 + 1",))

    path = write_archive(tmp_path, ID=np.array([Malicious()], dtype=object))
    with pytest.raises(ValueError, match="global proibido: builtins.eval"):
        dt.load_observations(path, "2000-01-01", "2000-01-03")


def test_unpaired_ids_are_audited_and_excluded_without_losing_common_stations():
    tmax, tmin = observations(stations=2)
    tmin.stations = tmin.stations.iloc[1:].reset_index(drop=True)
    tmin.data = tmin.data[:, 1:]
    result = dt.prepare_temperature(tmax, tmin)
    assert result.stations.station_id.to_list() == ["S1"]
    assert result.unpaired_stations.station_id.to_list() == ["S0"]
    assert result.unpaired_stations.available_variable.to_list() == ["tmax"]


@pytest.mark.parametrize("coords", [[[91, 0, 10]], [[-20, np.nan, 10]], [[-20, -40, np.inf]]])
def test_invalid_coordinates_rejected(tmp_path, coords):
    path = write_archive(tmp_path, lat_lon_alt=np.array(coords))
    with pytest.raises(ValueError, match="coordenadas inválidas"):
        dt.load_observations(path, "2000-01-01", "2000-01-03")


def test_path_boundary_cannot_escape_refinement():
    assert dt.safe_path("dados/a.csv").is_relative_to(dt.ROOT)
    with pytest.raises(ValueError, match="fora de refinamento"):
        dt.safe_path("../a.csv")
    with pytest.raises(ValueError, match="fora de refinamento"):
        dt.safe_path(dt.ROOT.parent / "refinamento_fake" / "a.csv")


def test_source_must_include_full_normal_period():
    tmax, tmin = observations()
    for source in [tmax, tmin]:
        source.data = source.data[:-1]
        source.dates = source.dates[:-1]
    with pytest.raises(ValueError, match="todos os dias de 1991"):
        dt.prepare_temperature(tmax, tmin)


@pytest.mark.parametrize("fraction", [0, 1.1, float("nan")])
def test_invalid_coverage_threshold_rejected(fraction):
    tmax, tmin = observations()
    with pytest.raises(ValueError, match="intervalo"):
        dt.prepare_temperature(tmax, tmin, minimum_day_fraction=fraction)
