import numpy as np
import pandas as pd
import pytest
from affine import Affine
from codigo.mapa_chuva import predict,FEATURES

class Constant:
    def __init__(self,value):self.value=value
    def predict(self,frame):return np.full(len(frame),self.value)

def test_rain_annual_sum_nodata_and_correlated_uncertainty():
    cov=np.ones((14,2,2));cov[:,0,1]=np.nan
    inside=np.array([[True,True],[False,True]])
    development=pd.DataFrame([[0]*7,[1000]*7],columns=FEATURES)
    arrays,count=predict(cov,Affine(30,0,500010,0,-30,7200000),'EPSG:32722',inside,
        Constant(10.4),[Constant(9),Constant(11)],development)
    assert count==2
    assert arrays['precipitacao'][0,0,0]==10
    assert arrays['precipitacao'][12,0,0]==125
    assert (arrays['precipitacao'][:,0,1]==65535).all()
    assert (arrays['precipitacao'][:,1,0]==65535).all()
    np.testing.assert_allclose(arrays['dispersao_chuva'][12,0,0],12*np.sqrt(2),rtol=1e-6)

def test_rain_uint16_overflow_is_not_silently_clipped():
    with pytest.raises(ValueError,match='Anual excede'):
        predict(np.ones((14,1,1)),Affine(30,0,500010,0,-30,7200000),'EPSG:32722',
            np.ones((1,1),bool),Constant(6000),[Constant(5999),Constant(6001)],
            pd.DataFrame([[0]*7,[1000]*7],columns=FEATURES))
