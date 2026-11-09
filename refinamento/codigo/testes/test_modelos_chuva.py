import numpy as np
import pandas as pd
import pytest
from sklearn.base import clone
from codigo.modelos_chuva import RainRegressor,summary


@pytest.mark.parametrize('formulation',['direct','correction'])
def test_zero_and_constant_are_preserved(formulation):
    x=pd.DataFrame({'latitude':np.arange(30),'longitude':np.arange(30),'chelsa_mm':np.full(30,50.)})
    for value in (0,100):
        model=clone(RainRegressor(formulation=formulation)).fit(x,np.full(30,value))
        np.testing.assert_allclose(model.predict(x),value,atol=1e-8)


def test_annual_rain_is_sum_not_temperature_weighted_mean():
    frame=pd.DataFrame({'station_id':['a']*12,'month':range(1,13),'method':['M2']*12,
                        'repeat':[0]*12,'precipitation_mm':[10.]*12,'prediction':[11.]*12})
    stats=summary(frame).set_index('scope')
    assert stats.loc['monthly','bias']==1 and stats.loc['annual','bias']==12
