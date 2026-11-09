import numpy as np
import pandas as pd
import pytest

from codigo.robustez_temperatura import features_for, subsample_stations
from codigo import modelos


def population():
    rows = [{'station_id': str(i), 'month': m, 'latitude': -10-i, 'longitude': -40-i,
             'elevation_m': i*100, 'temperature_c': 20+m/12, 'chelsa_c': 19+m/12,
             'dem_elevation_m': i*100, 'slope_deg': 2} for i in range(20) for m in range(1,13)]
    return modelos.prepare(pd.DataFrame(rows))


def test_subsamples_nested_complete_and_repeatable():
    data = population()
    small = subsample_stations(data, .25, 42)
    large = subsample_stations(data, .5, 42)
    assert small.station_id.nunique() == 5
    assert set(small.station_id) <= set(large.station_id)
    assert small.groupby('station_id').month.nunique().eq(12).all()
    pd.testing.assert_frame_equal(small, subsample_stations(data, .25, 42))
    pd.testing.assert_frame_equal(data, subsample_stations(data, 1, 42))


def test_month_categories_consistent_in_separate_months():
    data = population()
    january = features_for(data[data.month == 1], 'categorical')
    december = features_for(data[data.month == 12], 'categorical')
    assert list(january) == list(december)
    assert january.filter(like='month_').to_numpy().sum() == 0
    assert december.month_12.eq(1).all()
    assert 'temperature_c' not in january
    assert 'month_sin' not in features_for(data, 'none')
    assert 'month_sin' in features_for(data, 'harmonics')


@pytest.mark.parametrize('fraction', [0, -1, 1.1, np.nan])
def test_reject_invalid_fraction(fraction):
    with pytest.raises(ValueError):
        subsample_stations(population(), fraction, 42)
