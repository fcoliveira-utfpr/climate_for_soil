import numpy as np
import pandas as pd
import pytest
from codigo.definicoes_temperatura_inmet import daily_means


def example():
    times=pd.date_range('2020-01-01 01:00',periods=24,freq='h')
    return pd.DataFrame({'air':np.arange(24,dtype=float),'maximum':np.arange(24)+1.,'minimum':np.arange(24)-1.},index=times)


def test_24utc_belongs_to_previous_day_and_formula():
    result=daily_means(example()).iloc[0]
    assert result.date==pd.Timestamp('2020-01-01')
    assert result.mean_24h==11.5 and result.mean_extremes==11.5
    assert result.mean_compensated==(24-1+11+2*23)/5


def test_missing_hour_or_extreme_invalidates_all_methods():
    frame=example()
    empty=daily_means(frame.iloc[:-1])
    assert empty.empty and empty.date.dt.year.empty
    frame.iloc[5,1]=np.nan
    assert daily_means(frame).empty
    with pytest.raises(ValueError):daily_means(pd.concat([example(),example().iloc[:1]]))
