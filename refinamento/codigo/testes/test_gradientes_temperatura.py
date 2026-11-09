import numpy as np
import pandas as pd
import pytest
from codigo.gradientes_temperatura import slope, predict, FIXED


def sample(prefix, gamma=-.004):
    rows = []
    for i in range(6):
        for month in range(1, 13):
            dz = 10*(i+1)
            rows.append(dict(station_id=f'{prefix}{i}', month=month, region='Sul',
                             dem_elevation_m=100+dz, coarse_elevation_m=100,
                             chelsa_c=20, temperature_c=20+gamma*dz))
    return pd.DataFrame(rows)


def test_recovers_known_gradient_and_does_not_read_test_response():
    train, test = sample('train'), sample('test')
    gamma, fallback = slope(train)
    assert gamma == pytest.approx(-.004) and not fallback
    first, _ = predict(train, test)
    test.temperature_c = 9999
    second, _ = predict(train, test)
    for method in first:
        np.testing.assert_array_equal(first[method], second[method])
    np.testing.assert_allclose(first['M1_mensal_regional'], sample('test').temperature_c)


def test_fallback_counts_stations_not_monthly_rows():
    train = sample('train')
    train = train.loc[train.station_id.eq('train0')]
    assert slope(train) == (FIXED, True)
    train = sample('train')
    train.dem_elevation_m = train.coarse_elevation_m
    assert slope(train, -.003) == (-.003, True)


def test_rejects_station_leakage_and_nonfinite_fit():
    train = sample('train')
    with pytest.raises(ValueError, match='distintas'):
        predict(train, train)
    train.loc[0, 'temperature_c'] = np.nan
    with pytest.raises(ValueError, match='finitos'):
        slope(train)


def test_unseen_region_uses_monthly_fallback():
    train, test = sample('train'), sample('test')
    test.region = 'Norte'
    values, audit = predict(train, test)
    np.testing.assert_array_equal(values['M1_mensal'], values['M1_mensal_regional'])
    assert all(row['fallback'] for row in audit if row['level'] == 'month_region')
