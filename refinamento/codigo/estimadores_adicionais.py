"""Estimadores ajustáveis dentro de GridSearchCV, sem acesso a validação externa."""
import numpy as np
from sklearn.base import BaseEstimator, RegressorMixin
from sklearn.linear_model import LinearRegression
from sklearn.preprocessing import StandardScaler
from sklearn.utils.validation import check_is_fitted
from lightgbm import LGBMRegressor


class LinearResidual(RegressorMixin, BaseEstimator):
    """M6: regressão linear seguida de LightGBM nos resíduos do próprio treino."""
    def __init__(self, num_leaves=7, random_state=42, n_estimators=150):
        self.num_leaves=num_leaves
        self.random_state=random_state
        self.n_estimators=n_estimators

    def fit(self,X,y):
        self.linear_=LinearRegression().fit(X,y)
        self.residual_=LGBMRegressor(num_leaves=self.num_leaves,random_state=self.random_state,
            n_estimators=self.n_estimators,learning_rate=.05,min_child_samples=20,n_jobs=1,
            deterministic=True,force_col_wise=True,verbosity=-1)
        self.residual_.fit(X,np.asarray(y)-self.linear_.predict(X))
        self.n_features_in_=self.linear_.n_features_in_
        return self

    def predict(self,X):
        check_is_fitted(self,'residual_')
        return self.linear_.predict(X)+self.residual_.predict(X)


class GeographicalRegression(RegressorMixin, BaseEstimator):
    """M3: regressões locais com kernel gaussiano geodésico e ridge numérico.

    Bandwidth em km ajustado na CV interna. Ridge fixo 1e-6 nas covariáveis
    padronizadas estabiliza colinearidade; intercepto não penalizado.
    """
    def __init__(self, bandwidth_km=750):
        self.bandwidth_km=bandwidth_km

    def fit(self,X,y):
        if self.bandwidth_km<=0:raise ValueError('Bandwidth deve ser positivo.')
        self.coordinates_=np.deg2rad(X[['latitude','longitude']].to_numpy(float))
        self.scaler_=StandardScaler().fit(X)
        self.design_=np.column_stack([np.ones(len(X)),self.scaler_.transform(X)])
        self.response_=np.asarray(y,float)
        if not np.isfinite(self.design_).all() or not np.isfinite(self.response_).all():
            raise ValueError('Treino deve ser finito.')
        self.n_features_in_=X.shape[1]
        return self

    def predict(self,X):
        check_is_fitted(self,'design_')
        design=np.column_stack([np.ones(len(X)),self.scaler_.transform(X)])
        coordinates=np.deg2rad(X[['latitude','longitude']].to_numpy(float))
        result=[]
        penalty=np.eye(self.design_.shape[1])*1e-6;penalty[0,0]=0
        for row,(lat,lon) in zip(design,coordinates):
            a=np.sin((self.coordinates_[:,0]-lat)/2)**2+np.cos(lat)*np.cos(self.coordinates_[:,0])*np.sin((self.coordinates_[:,1]-lon)/2)**2
            distance=6371.0088*2*np.arcsin(np.sqrt(np.clip(a,0,1)))
            logw=-.5*(distance/self.bandwidth_km)**2
            weights=np.exp(logw-logw.max());weights/=weights.sum()
            weighted=self.design_.T*weights
            beta=np.linalg.solve(weighted@self.design_+penalty,weighted@self.response_)
            result.append(row@beta)
        return np.asarray(result)
