"""Regressoes associativas, pareadas por perfil, com validacao aleatoria e espacial."""
import json

import numpy as np
import pandas as pd
import statsmodels.api as sm
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import LinearRegression, LogisticRegression
from sklearn.metrics import accuracy_score, balanced_accuracy_score, mean_squared_error, r2_score
from sklearn.model_selection import GroupKFold, KFold, StratifiedKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from analise_solo_clima import SOC, selecionar
from preparar_dados import RES, carregar_bases

TEXTURA_REG=['areia','argila']  # silte = 100 - areia - argila


def montar():
    df=carregar_bases()[2]
    valid=selecionar(df,SOC,'koppen_l2').index
    return df.loc[valid].dropna(subset=['elevation','latitude','longitude']).reset_index(drop=True)


def dummies_clima(df,nivel='koppen_l2'):
    base=df[nivel].value_counts().index[0]
    dummy=pd.get_dummies(df[nivel],prefix=nivel,dtype=float)
    return dummy.drop(columns=[nivel+'_'+base]),base


def ajustar(y,X,nome):
    X=sm.add_constant(X.astype(float),has_constant='add')
    if np.linalg.matrix_rank(X.to_numpy())!=X.shape[1]:
        raise ValueError('Matriz de regressao sem posto completo')
    m=sm.OLS(y,X).fit(cov_type='HC3')
    return {'modelo':nome,'n':int(m.nobs),'k':X.shape[1]-1,'R2':m.rsquared,
            'R2_aj':m.rsquared_adj,'AIC':m.aic},m


def grupos_espaciais(df,tamanho=2):
    # Grades geograficas: tamanho em graus, nao distancia constante em km.
    return (np.floor((df.longitude+180)/tamanho).astype(int).astype(str)+'_'+
            np.floor((df.latitude+90)/tamanho).astype(int).astype(str))


def validar(df,X,y,alvo):
    rows=[]
    predictions=[]
    for scheme,size in [('aleatoria',None),('espacial_1grau',1),('espacial_2graus',2),('espacial_5graus',5)]:
        groups=grupos_espaciais(df,size) if size else None
        splitter=GroupKFold(n_splits=5) if size else KFold(n_splits=5,shuffle=True,random_state=42)
        splits=list(splitter.split(X,y,groups))
        for model_name in ['OLS','RandomForest']:
            pred=np.full(len(df),np.nan)
            baseline=np.full(len(df),np.nan)
            for fold,(train,test) in enumerate(splits,1):
                if groups is not None:
                    assert set(groups.iloc[train]).isdisjoint(groups.iloc[test])
                model=(make_pipeline(StandardScaler(),LinearRegression()) if model_name=='OLS' else
                       RandomForestRegressor(n_estimators=200,min_samples_leaf=5,random_state=42,n_jobs=2))
                model.fit(X.iloc[train],y.iloc[train])
                pred[test]=model.predict(X.iloc[test])
                baseline[test]=y.iloc[train].mean()
                rows.append({'alvo':alvo,'esquema':scheme,'modelo':model_name,'fold':fold,
                             'n_treino':len(train),'n_teste':len(test),
                             'R2':r2_score(y.iloc[test],pred[test]),
                             'RMSE_log':float(np.sqrt(mean_squared_error(y.iloc[test],pred[test]))),
                             'blocos_treino':int(groups.iloc[train].nunique()) if size else None,
                             'blocos_teste':int(groups.iloc[test].nunique()) if size else None})
            predictions.append({'alvo':alvo,'esquema':scheme,'modelo':model_name,'n':len(df),
                                'R2_oof':r2_score(y,pred),'R2_baseline_oof':r2_score(y,baseline),
                                'RMSE_log_oof':float(np.sqrt(mean_squared_error(y,pred)))})
            print(alvo,scheme,model_name,'R2 OOF',round(r2_score(y,pred),4),flush=True)
    return rows,predictions


def main():
    df=montar()
    models,coefficients=[],[]
    sub=df[df[SOC]>0].reset_index(drop=True)
    counts={'SOC':{'n':len(sub),'soc_nao_positivo_excluido':int((df[SOC]<=0).sum())}}
    y=np.log(sub[SOC])
    dummy,base=dummies_clima(sub)
    tex=sub[TEXTURA_REG]
    relief=sub[['elevation','latitude']]
    full=pd.concat([tex,dummy,relief],axis=1)
    for name,X in [('M1 clima',dummy),('M2 textura',tex),
                   ('M3 textura+clima',pd.concat([tex,dummy],axis=1)),
                   ('M4 textura+clima+relevo',full),
                   ('M5 clima+relevo',pd.concat([dummy,relief],axis=1))]:
        row,fit=ajustar(y,X,name)
        models.append({**row,'alvo':'SOC','referencia_clima':base})
        if name=='M4 textura+clima+relevo':
            ci=fit.conf_int()
            for term in fit.params.index:
                coefficients.append({'alvo':'SOC','termo':term,'coef_log':fit.params[term],
                                     'p_HC3':fit.pvalues[term],'ic95_inf':ci.loc[term,0],
                                     'ic95_sup':ci.loc[term,1],
                                     'variacao_condicional_pct':100*np.expm1(fit.params[term])})
    folds,summaries=validar(sub,full,y,'SOC')
    pd.DataFrame(models).to_csv(RES/'regressao_modelos.csv',index=False)
    pd.DataFrame(coefficients).to_csv(RES/'regressao_coeficientes.csv',index=False)
    pd.DataFrame(folds).to_csv(RES/'validacao_folds.csv',index=False)
    pd.DataFrame(summaries).to_csv(RES/'validacao_modelos.csv',index=False)
    sub=df[df[SOC]>0].reset_index(drop=True)
    X=sub[TEXTURA_REG].assign(log_soc=np.log(sub[SOC]))
    y=sub.koppen_l2
    acc=[]
    for name,groups in [('aleatoria',None),('espacial_2graus',grupos_espaciais(sub,2))]:
        splits=(StratifiedKFold(5,shuffle=True,random_state=42).split(X,y) if groups is None else
                GroupKFold(5).split(X,y,groups))
        pred=np.empty(len(y),dtype=object)
        base_pred=np.empty(len(y),dtype=object)
        for train,test in splits:
            model=make_pipeline(StandardScaler(),LogisticRegression(max_iter=3000))
            model.fit(X.iloc[train],y.iloc[train])
            pred[test]=model.predict(X.iloc[test])
            base_pred[test]=y.iloc[train].value_counts().index[0]
        acc.append({'esquema':name,'n':len(y),'acuracia_oof':accuracy_score(y,pred),
                    'acuracia_balanceada_oof':balanced_accuracy_score(y,pred),
                    'baseline_treino_oof':accuracy_score(y,base_pred)})
    pd.DataFrame(acc).to_csv(RES/'logistica_validacao.csv',index=False)
    (RES/'regressao_amostra.json').write_text(json.dumps(counts,indent=2),encoding='utf-8')


if __name__=='__main__':
    main()
