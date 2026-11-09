import numpy as np
import pandas as pd
import pytest
from codigo.dados_precipitacao import monthly_totals, normals


def test_rain_zero_leap_year_and_missing_day():
    dates = pd.date_range('2020-02-01','2020-02-29')
    values = np.ones((29,3))
    values[:,0] = 0
    values[0,2] = np.nan
    months, totals, counts = monthly_totals(values,dates)
    assert totals[0,0] == 0 and totals[0,1] == 29
    assert np.isnan(totals[0,2]) and counts[0,2] == 28


def test_outlier_invalidates_month_instead_of_becoming_zero():
    dates = pd.date_range('2020-01-01','2020-01-31')
    values = np.ones((31,2))
    values[0] = [-1,450]
    _, totals, _ = monthly_totals(values,dates)
    assert np.isnan(totals).all()
    with pytest.raises(ValueError):
        monthly_totals(values,dates[::-1])


def test_annual_is_sum_and_requires_twelve_months():
    months = pd.period_range('1991-01','2020-12',freq='M')
    values = np.full((360,2),100.)
    values[months.month == 2,1] = np.nan
    result, counts = normals(months,values)
    assert result[0,0] == 1200 and counts[0,0] == 30
    assert np.isnan(result[0,1]) and counts[0,1] == 0


def test_normal_threshold_includes_24_and_rejects_23_years():
    months = pd.period_range('1991-01','2020-12',freq='M')
    values = np.full((360,2),10.)
    values[:6*12,0] = np.nan
    values[:7*12,1] = np.nan
    result, _ = normals(months,values)
    assert result[0,0] == 120
    assert np.isnan(result[:,1]).all()
