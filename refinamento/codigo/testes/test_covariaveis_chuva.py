import numpy as np
import pytest
from codigo.covariaveis_chuva_gee import decode


def test_preserve_zero_and_missing():
    result=decode([{'properties':{'station_id':'001','m01':0,'m02':None}}],['001'])
    assert len(result)==12 and result.iloc[0].grid_mm==0
    assert np.isnan(result.iloc[1].grid_mm)


def test_refuse_changed_stations_and_negative_rain():
    with pytest.raises(ValueError):decode([{'properties':{'station_id':'002'}}],['001'])
    with pytest.raises(ValueError):decode([{'properties':{'station_id':'001','m01':-1}}],['001'])
