"""Ensaios sintéticos de isolamento espacial; não medem qualidade climática real."""

import numpy as np
import pandas as pd
import pytest

from codigo import modelos


def synthetic_normals(n_stations=24):
    rows = []
    for station in range(n_stations):
        latitude = -30.3 + 2.2 * (station // 6)
        longitude = -60.3 + 2.2 * (station % 6)
        elevation = 50.0 + 40 * station
        for month in range(1, 13):
            temperature = 24 - 0.006 * elevation + 2 * np.sin(2 * np.pi * (month - 1) / 12)
            rows.append({"station_id": f"S{station:02d}", "latitude": latitude,
                         "longitude": longitude, "elevation_m": elevation,
                         "month": month, "temperature_c": temperature})
    return pd.DataFrame(rows)


@pytest.mark.parametrize("column", ["latitude", "longitude", "elevation_m"])
def test_prepare_rejects_station_relocation(column):
    data = synthetic_normals(2)
    data.loc[0, column] += 0.1
    with pytest.raises(ValueError, match="Metadados|relocação"):
        modelos.prepare(data)


def test_prepare_rejects_duplicate_months():
    data = synthetic_normals(2)
    with pytest.raises(ValueError, match="duplicad"):
        modelos.prepare(pd.concat([data, data.iloc[[0]]], ignore_index=True))


def test_prepare_retains_complete_stations_without_treating_annual_as_month():
    data = synthetic_normals(3)
    data.loc[(data.station_id == "S01") & (data.month == 4), "temperature_c"] = np.nan
    data = data[~((data.station_id == "S02") & (data.month == 12))]
    annual = data.iloc[[0]].assign(month=0)
    result = modelos.prepare(pd.concat([data, annual], ignore_index=True))
    assert set(result.station_id) == {"S00"}
    assert result.month.tolist() == list(range(1, 13))
    assert np.isfinite(result[modelos.FEATURES]).all().all()


def test_reserved_blocks_and_all_months_are_kept_together():
    data = modelos.prepare(synthetic_normals())
    held = modelos.reserve_test(data)
    blocks = modelos.spatial_blocks(data, 2)
    assert set(blocks[held]).isdisjoint(blocks[~held])
    assert data.assign(held=held).groupby("station_id").held.nunique().eq(1).all()
    reordered = data.sample(frac=1, random_state=77).reset_index(drop=True)
    reserved_ids = set(data.loc[held, "station_id"])
    assert set(reordered.loc[modelos.reserve_test(reordered), "station_id"]) == reserved_ids
    # Blocos de 1° estão aninhados na partição reservada de 2°.
    one_degree = modelos.spatial_blocks(data, 1)
    assert set(one_degree[held]).isdisjoint(one_degree[~held])


def mx_inputs():
    # Os cinco vizinhos próximos têm o mesmo valor; o sexto é um outlier distante.
    train = pd.DataFrame({
        "station_id": [f"T{i}" for i in range(6)], "month": [1] * 6,
        "latitude": [0.0] * 6, "longitude": [0.1, 0.2, 0.3, 0.4, 0.5, 1.0],
        "elevation_m": [0.0] * 6, "temperature_c": [20.0] * 5 + [100000.0],
    })
    test = pd.DataFrame({"station_id": ["UNSEEN"], "month": [1], "latitude": [0.0],
                         "longitude": [0.0], "elevation_m": [1000.0], "temperature_c": [-99.0]})
    return train, test


def test_mx_uses_five_nearest_training_stations_and_correct_lapse_sign():
    train, test = mx_inputs()
    np.testing.assert_allclose(modelos.predict_mx(train, test), [14.0], atol=1e-10)
    lower = test.assign(elevation_m=-1000.0)
    np.testing.assert_allclose(modelos.predict_mx(train, lower), [26.0], atol=1e-10)


def test_mx_uses_same_month_and_ignores_test_responses():
    train, test = mx_inputs()
    other_month = train.assign(month=2, latitude=0.0, longitude=0.0, temperature_c=-100000.0)
    train = pd.concat([train, other_month], ignore_index=True)
    expected = modelos.predict_mx(train, test)
    np.testing.assert_allclose(expected, [14.0], atol=1e-10)
    np.testing.assert_array_equal(expected, modelos.predict_mx(train, test.assign(temperature_c=1e9)))


def test_mx_rejects_fewer_than_five_training_stations_in_month():
    train, test = mx_inputs()
    with pytest.raises(ValueError, match="cinco"):
        modelos.predict_mx(train.iloc[:4], test)


def test_real_model_comparison_keeps_holdout_blocks_and_station_months_isolated(monkeypatch):
    data = modelos.prepare(synthetic_normals())
    held = modelos.reserve_test(data)
    held_ids = set(data.loc[held, "station_id"])
    development_ids = set(data.loc[~held, "station_id"])
    held_coordinates = set(map(tuple, data.loc[held, ["latitude", "longitude"]].to_numpy()))
    original_mx = modelos.predict_mx
    original_grid_fit = modelos.GridSearchCV.fit
    calls = []
    inner_calls = []

    def audited_mx(train, test):
        assert set(train.station_id).isdisjoint(test.station_id)
        assert set(modelos.spatial_blocks(train, 2)).isdisjoint(modelos.spatial_blocks(test, 2))
        assert held_ids.isdisjoint(train.station_id)
        assert held_ids.isdisjoint(test.station_id)
        assert train.groupby("month").station_id.nunique().min() >= 5
        calls.append((len(train), len(test)))
        return original_mx(train, test)

    def audited_grid_fit(search, features, target, **kwargs):
        assert held_coordinates.isdisjoint(map(tuple, features[["latitude", "longitude"]].to_numpy()))
        groups = kwargs["groups"]
        for train_index, validation_index in search.cv.split(features, target, groups):
            assert set(groups[train_index]).isdisjoint(groups[validation_index])
            train_coordinates = set(map(tuple, features.iloc[train_index][["latitude", "longitude"]].to_numpy()))
            validation_coordinates = set(map(tuple, features.iloc[validation_index][["latitude", "longitude"]].to_numpy()))
            assert train_coordinates.isdisjoint(validation_coordinates)
            inner_calls.append(1)
        return original_grid_fit(search, features, target, **kwargs)

    monkeypatch.setattr(modelos, "predict_mx", audited_mx)
    monkeypatch.setattr(modelos.GridSearchCV, "fit", audited_grid_fit)
    predictions, partition, settings = modelos.compare(data, block_size=2, repeats=1, folds=3)
    assert len(calls) == 3
    assert len(inner_calls) == 3 * 2 * 3
    assert held_ids == set(partition.loc[partition.reserved_test, "station_id"])
    assert set(predictions.station_id) == development_ids
    assert set(predictions.method) == {
        "MX_mensal_referencia", "M2_linear", "M4_random_forest", "M5_lightgbm"
    }
    assert np.isfinite(predictions.prediction).all()
    assert not predictions.duplicated(["station_id", "month", "method", "repeat"]).any()
    assert predictions.groupby(["station_id", "repeat"]).fold.nunique().eq(1).all()
    assert predictions.groupby(["block", "repeat"]).fold.nunique().eq(1).all()
    assert predictions.groupby(["method", "station_id"]).month.nunique().eq(12).all()
    assert len(predictions) == len(development_ids) * 12 * 4
    assert len(settings) == 3 * 3
    summary = modelos.summarize(predictions)
    assert summary[summary.scope == "global"].n_stations.eq(len(development_ids)).all()
    intervals = modelos.paired_intervals(predictions, n_bootstrap=20)
    reference = intervals[intervals.method == "MX_mensal_referencia"].iloc[0]
    np.testing.assert_array_equal(reference[["delta_rmse_c", "ci025", "ci975"]].to_numpy(float), 0)


def paired_predictions():
    records = []
    for block in range(4):
        for month in (1, 2):
            for method, error in [("MX_mensal_referencia", 2.0), ("candidate", 1.0)]:
                records.append({"block": str(block), "station_id": f"S{block}", "month": month,
                                "repeat": 0, "fold": block, "method": method,
                                "temperature_c": 10.0, "prediction": 10.0 + error})
    return pd.DataFrame(records)


def test_paired_bootstrap_has_known_negative_delta_for_better_candidate():
    intervals = modelos.paired_intervals(paired_predictions(), n_bootstrap=30)
    candidate = intervals[intervals.method == "candidate"].iloc[0]
    np.testing.assert_allclose(candidate[["delta_rmse_c", "ci025", "ci975"]].to_numpy(float), -1.0)


def test_paired_bootstrap_reference_can_be_a_competing_model():
    intervals = modelos.paired_intervals(paired_predictions(), n_bootstrap=30,
                                        reference_method="candidate")
    worse = intervals[intervals.method == "MX_mensal_referencia"].iloc[0]
    np.testing.assert_allclose(worse[["delta_rmse_c", "ci025", "ci975"]].to_numpy(float), 1.0)
    with pytest.raises(ValueError, match="referência"):
        modelos.paired_intervals(paired_predictions(), reference_method="unknown")


@pytest.mark.parametrize("damage", ["missing", "duplicate", "different_observation", "different_fold"])
def test_paired_bootstrap_rejects_unmatched_comparisons(damage):
    data = paired_predictions()
    if damage == "missing":
        data = data.iloc[1:]
    elif damage == "duplicate":
        data = pd.concat([data, data.iloc[[0]]], ignore_index=True)
    elif damage == "different_observation":
        data.loc[0, "temperature_c"] += 2
    else:
        data.loc[0, "fold"] += 1
    with pytest.raises(ValueError):
        modelos.paired_intervals(data, n_bootstrap=10)


def synthetic_grid_normals():
    data = modelos.prepare(synthetic_normals())
    data["chelsa_c"] = data.temperature_c - 2.5
    data["dem_elevation_m"] = data.elevation_m + 50.0
    data["slope_deg"] = 5.0
    sign = np.where(data.station_id.str[1:].astype(int) % 2, -1.0, 1.0)
    data["coarse_elevation_m"] = data.dem_elevation_m - sign * 100.0
    return data


def test_grid_features_use_dem_instead_of_station_elevation():
    data = synthetic_grid_normals()
    features = modelos.feature_columns(data)
    assert "elevation_m" not in features
    assert {"dem_elevation_m", "chelsa_c", "slope_deg"}.issubset(features)
    assert "temperature_c" not in features


def test_grid_correction_real_models_add_offset_and_keep_direct_partitions(monkeypatch):
    data = synthetic_grid_normals()
    original_fit = modelos.GridSearchCV.fit
    audited_fits = []

    def audit_residual_target(search, features, target, **kwargs):
        assert "elevation_m" not in features
        assert "dem_elevation_m" in features
        np.testing.assert_allclose(target.to_numpy(), 2.5, atol=1e-12)
        audited_fits.append(1)
        return original_fit(search, features, target, **kwargs)

    monkeypatch.setattr(modelos.GridSearchCV, "fit", audit_residual_target)
    correction, correction_partition, _ = modelos.compare(
        data, repeats=1, folds=3, formulation="correction"
    )
    assert len(audited_fits) == 6
    learned = correction[correction.method.isin(["M2_linear", "M4_random_forest", "M5_lightgbm"])]
    np.testing.assert_allclose(learned.prediction, learned.temperature_c, atol=1e-8)
    joined = correction.merge(
        data[["station_id", "month", "chelsa_c", "dem_elevation_m", "coarse_elevation_m"]],
        on=["station_id", "month"], validate="many_to_one",
    )
    baseline = joined[joined.method == "M0_chelsa"]
    np.testing.assert_allclose(baseline.prediction, baseline.chelsa_c)
    lapse = joined[joined.method == "M1_lapse_fixo"]
    delta_height = lapse.dem_elevation_m - lapse.coarse_elevation_m
    np.testing.assert_allclose(lapse.prediction - lapse.chelsa_c, -0.0065 * delta_height)
    assert (lapse.loc[delta_height > 0, "prediction"] < lapse.loc[delta_height > 0, "chelsa_c"]).all()
    assert (lapse.loc[delta_height < 0, "prediction"] > lapse.loc[delta_height < 0, "chelsa_c"]).all()
    # Uma regressão basta para verificar partições da outra formulação; os três
    # estimadores reais já foram exercitados acima, inclusive ajuste aninhado.
    monkeypatch.setattr(modelos, "model_candidates", lambda seed: {
        "M2_linear": (modelos.LinearRegression(), {})
    })
    direct, direct_partition, _ = modelos.compare(data, repeats=1, folds=3, formulation="direct")
    pd.testing.assert_frame_equal(correction_partition, direct_partition)
    columns = ["station_id", "month", "repeat", "fold", "block"]
    correction_keys = correction[correction.method == "M2_linear"][columns].reset_index(drop=True)
    direct_keys = direct[direct.method == "M2_linear"][columns].reset_index(drop=True)
    pd.testing.assert_frame_equal(correction_keys, direct_keys)
    held_ids = set(correction_partition.loc[correction_partition.reserved_test, "station_id"])
    assert held_ids.isdisjoint(correction.station_id)
    assert correction.groupby(["station_id", "repeat"]).fold.nunique().eq(1).all()


def test_grid_rejects_missing_coarse_elevation_before_modeling():
    data = synthetic_grid_normals()
    data.loc[0, "coarse_elevation_m"] = np.nan
    with pytest.raises(ValueError):
        modelos.compare(data, repeats=1, folds=3, formulation="correction")


def test_grid_correction_requires_baseline():
    data = modelos.prepare(synthetic_normals())
    with pytest.raises(ValueError, match="CHELSA"):
        modelos.compare(data, repeats=1, folds=3, formulation="correction")
