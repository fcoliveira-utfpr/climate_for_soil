import numpy as np
import pandas as pd
import pytest
from sklearn.base import clone
from codigo.estimadores_adicionais import LinearResidual,GeographicalRegression


@pytest.mark.parametrize('estimator',[LinearResidual(n_estimators=5),GeographicalRegression()])
def test_clone_constant_response_and_unfitted(estimator):
    x=pd.DataFrame({'latitude':np.linspace(-30,-20,30),'longitude':np.linspace(-50,-40,30),'elevation':np.arange(30)})
    with pytest.raises(Exception):estimator.predict(x)
    fitted=clone(estimator).fit(x,np.full(30,7.))
    np.testing.assert_allclose(fitted.predict(x.iloc[:3]),7,atol=1e-7)
    shifted=clone(estimator).fit(x,np.full(30,10.))
    np.testing.assert_allclose(shifted.predict(x.iloc[:3])-fitted.predict(x.iloc[:3]),3,atol=1e-7)


def test_gwr_collinear_features_are_finite():
    x=pd.DataFrame({'latitude':[-25.]*10,'longitude':[-50.]*10,'z':np.arange(10),'twice_z':np.arange(10)*2})
    model=GeographicalRegression().fit(x,np.arange(10)*.1)
    np.testing.assert_allclose(model.predict(x),np.arange(10)*.1,atol=1e-5)
