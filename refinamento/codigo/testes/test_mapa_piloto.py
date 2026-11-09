"""Teste de grade e inferência com covariáveis sintéticas, sem chamar o GEE."""
import calendar

import numpy as np
import pandas as pd
import pytest
import rasterio
from affine import Affine

from codigo import mapa_piloto as pilot
from codigo import modelos


class ConstantModel:
    def __init__(self, value=2.5):
        self.value = value

    def predict(self, features):
        return np.full(len(features), self.value)


class SeasonalMember:
    def __init__(self, weight):
        self.weight = weight

    def predict(self, features):
        return 2.5 + self.weight * features.month_sin.to_numpy()


def cube():
    array = np.empty((15, 2, 2), dtype=float)
    for month in range(12):
        array[month] = 10.0 + month
    array[12], array[13], array[14] = 100.0, 120.0, 5.0
    array[12, 0, 0] = 300.0
    return array


def training_table():
    records = []
    for station in range(24):
        for month in range(1, 13):
            records.append({"station_id": f"S{station:02}", "month": month,
                            "latitude": -30.3 + 2.2 * (station // 6),
                            "longitude": -60.3 + 2.2 * (station % 6),
                            "elevation_m": 100 + station, "dem_elevation_m": 100 + station,
                            "slope_deg": 5.0, "chelsa_c": 10.0 + month,
                            "temperature_c": 12.5 + month})
    return modelos.prepare(pd.DataFrame(records))


def test_pilot_grid_is_metric_and_weights_include_leap_days():
    transform = pilot.pilot_transform()
    pilot.validate_grid(transform, pilot.CRS)
    assert transform.c % 30 == transform.f % 30 == 0
    counts = np.array([sum(calendar.monthrange(year, month)[1] for year in range(1991, 2021))
                       for month in range(1, 13)])
    assert counts[1] == 848
    assert counts.sum() == 10958
    np.testing.assert_allclose(pilot.month_weights(), counts / 10958)


def test_tile_predictions_add_baseline_and_annual_sd_aggregates_members_first():
    covariates, transform = cube(), pilot.pilot_transform()
    development = training_table()
    # Os demais intervalos cobrem o piloto para isolar a flag de elevação.
    development.loc[:, "latitude"] = np.linspace(-90, 90, len(development))
    development.loc[:, "longitude"] = np.linspace(-180, 180, len(development))
    development.loc[:, "latitude_sin"] = np.linspace(-90, 90, len(development))
    development.loc[:, "latitude_cos"] = np.linspace(-90, 90, len(development))
    development.loc[:, "chelsa_c"] = np.linspace(0, 30, len(development))
    members = [SeasonalMember(value) for value in range(-2, 3)]
    temperature, sd, flag = pilot.predict_tile(
        covariates, transform, ConstantModel(), members, development, "correction"
    )
    np.testing.assert_allclose(temperature[:12], covariates[:12] + 2.5)
    np.testing.assert_allclose(temperature[-1], np.tensordot(pilot.month_weights(), temperature[:12], axes=(0, 0)))
    seasonal = np.sin(2 * np.pi * np.arange(12) / 12)
    expected_annual_sd = abs(np.dot(pilot.month_weights(), seasonal)) * np.std(np.arange(-2, 3), ddof=1)
    np.testing.assert_allclose(sd[-1], expected_annual_sd, atol=1e-12)
    assert not np.isclose(sd[-1, 0, 0], np.dot(pilot.month_weights(), sd[:12, 0, 0]))
    assert flag[:, 0, 0].tolist() == [1] * 13
    assert flag[:, 1, 1].tolist() == [0] * 13
    np.testing.assert_array_equal(flag[-1], flag[:12].max(axis=0))


def test_fitting_full_and_fold_models_never_sees_holdout(monkeypatch):
    data = training_table()
    held = modelos.reserve_test(data)
    held_coordinates = set(map(tuple, data.loc[held, ["latitude", "longitude"]].to_numpy()))
    original = modelos.GridSearchCV.fit
    calls = []

    def audit(search, features, target, **kwargs):
        assert held_coordinates.isdisjoint(map(tuple, features[["latitude", "longitude"]].to_numpy()))
        np.testing.assert_allclose(target, 2.5)
        for train_index, valid_index in search.cv.split(features, target, kwargs["groups"]):
            assert set(kwargs["groups"][train_index]).isdisjoint(kwargs["groups"][valid_index])
        calls.append(1)
        return original(search, features, target, **kwargs)

    monkeypatch.setattr(modelos.GridSearchCV, "fit", audit)
    model, members, development, metadata = pilot.fit_development(data, "M5_lightgbm", "correction")
    assert len(calls) == 1
    assert len(members) == 5
    assert set(development.station_id).isdisjoint(data.loc[held, "station_id"])
    assert set(metadata["reserved_unscored_stations"]) == set(data.loc[held, "station_id"])
    for member in [model, *members]:
        np.testing.assert_allclose(member.predict(development[metadata["features"]]), 2.5, atol=1e-8)


def test_covariate_validation_rejects_wrong_grid_and_missing_pixel(tmp_path):
    path, transform = tmp_path / "covariates.tiff", pilot.pilot_transform()

    def write(data):
        with rasterio.open(path, "w", driver="GTiff", width=2, height=2, count=15,
                           dtype="float32", crs=pilot.CRS, transform=transform, nodata=-9999) as target:
            target.write(data.astype("float32"))
            for band, name in enumerate(pilot.BANDS, 1):
                target.set_band_description(band, name)

    data = cube()
    write(data)
    np.testing.assert_array_equal(pilot.validate_covariates(path, transform, size=2), data)
    with pytest.raises(ValueError, match="grade"):
        pilot.validate_covariates(path, Affine(30, 0, transform.c + 30, 0, -30, transform.f), size=2)
    data[0, 0, 0] = -9999
    write(data)
    with pytest.raises(ValueError, match="ausentes"):
        pilot.validate_covariates(path, transform, size=2)


@pytest.mark.parametrize("kind,dtype,nodata", [
    ("sd_between_models", "float32", -9999), ("outside_training_range", "uint8", 255)
])
def test_auxiliary_raster_roundtrip(tmp_path, kind, dtype, nodata):
    path = tmp_path / f"{kind}.tiff"
    pilot.write_auxiliary(path, np.array([[0, 1], [1, 0]]), pilot.pilot_transform(),
                          kind=kind, method="synthetic", period="1991-2020; month=01")
    with rasterio.open(path) as source:
        assert source.dtypes == (dtype,)
        assert source.nodata == nodata
        assert source.tags()["experimental"] == "true"
        assert source.scales == (1.0,)
        assert source.offsets == (0.0,)
        assert source.res == (30.0, 30.0)
        np.testing.assert_array_equal(source.read(1), [[0, 1], [1, 0]])
    with pytest.raises(FileExistsError):
        pilot.write_auxiliary(path, np.zeros((2, 2)), pilot.pilot_transform(),
                              kind=kind, method="synthetic", period="1991-2020; month=01")
