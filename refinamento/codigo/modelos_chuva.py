"""Chuva: validação espacial aninhada em mm, log1p e correção multiplicativa.

Teste espacial reservado antes das perdas por covariáveis. Smearing calculado
somente no treino; nunca usa resíduos da avaliação para corrigir retransposição.
"""
import argparse
import json
import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator,RegressorMixin
from sklearn.linear_model import LinearRegression
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import GroupKFold,GridSearchCV
from lightgbm import LGBMRegressor
from codigo.estimadores_adicionais import LinearResidual
from codigo import modelos
from codigo.metricas import metricas
from codigo.dados_temperatura import safe_path
from codigo.grade_brasil import digest


class RainRegressor(RegressorMixin,BaseEstimator):
    def __init__(self,method='M2',formulation='direct',complexity=7,random_state=42):
        self.method=method;self.formulation=formulation;self.complexity=complexity;self.random_state=random_state

    def design(self,X):
        frame=X.copy()
        for column in ('chelsa_mm','chirps_mm'):
            if column in frame:frame[column]=np.log1p(frame[column])
        return frame

    def offset(self,X):
        return np.log1p(X.chelsa_mm.to_numpy()) if self.formulation=='correction' else np.zeros(len(X))

    def fit(self,X,y):
        if self.formulation not in ('direct','correction'):raise ValueError('Formulação inválida.')
        y=np.asarray(y,float)
        if not np.isfinite(y).all() or np.any(y<0):raise ValueError('Chuva deve ser finita e não negativa.')
        estimators={'M2':LinearRegression(),
                    'M4':RandomForestRegressor(n_estimators=150,min_samples_leaf=self.complexity,random_state=self.random_state,n_jobs=1),
                    'M5':LGBMRegressor(n_estimators=150,learning_rate=.05,num_leaves=self.complexity,
                        min_child_samples=20,n_jobs=1,random_state=self.random_state,verbosity=-1,deterministic=True,force_col_wise=True),
                    'M6':LinearResidual(num_leaves=self.complexity,random_state=self.random_state)}
        if self.method not in estimators:raise ValueError('Método inválido.')
        self.estimator_=estimators[self.method]
        target=np.log1p(y)-self.offset(X)
        self.estimator_.fit(self.design(X),target)
        residual=target-self.estimator_.predict(self.design(X))
        self.smearing_=float(np.exp(residual).mean())
        self.n_features_in_=X.shape[1]
        return self

    def predict(self,X):
        log_prediction=self.estimator_.predict(self.design(X))+self.offset(X)
        result=np.exp(log_prediction)*self.smearing_-1
        if not np.isfinite(result).all():raise ValueError('Previsão não finita; revisar extrapolação.')
        return np.maximum(0,result)


def prepare():
    source=safe_path('dados/processados/normais_precipitacao.csv')
    data=pd.read_csv(source,dtype={'station_id':str})
    ids=set(data.loc[data.month.eq(0)&data.precipitation_mm.notna(),'station_id'])
    data=data.loc[data.station_id.isin(ids)&data.month.ne(0)].copy()
    data['reserved']=modelos.reserve_test(data)
    hashes={'normals':digest(source)}
    for name in ('chelsa','era5','chirps'):
        path=safe_path(f'dados/chuva/{name}_normais.csv')
        metadata=json.loads(path.with_suffix('.json').read_text(encoding='utf-8'))
        if metadata['output_sha256']!=digest(path) or metadata['input_sha256']!=digest(source):raise ValueError('Grade com origem divergente.')
        hashes[name]=digest(path)
        grid=pd.read_csv(path,dtype={'station_id':str}).rename(columns={'grid_mm':f'{name}_mm'})
        data=data.merge(grid,on=['station_id','month'],how='left',validate='one_to_one')
    terrain=safe_path('dados/chuva/relevo_escalas.csv')
    metadata=json.loads(terrain.with_suffix('.json').read_text(encoding='utf-8'))
    if metadata['output_sha256']!=digest(terrain) or metadata['input_sha256']!=digest(source):raise ValueError('Relevo com origem divergente.')
    hashes['terrain']=digest(terrain)
    data=data.merge(pd.read_csv(terrain,dtype={'station_id':str}),on='station_id',how='left',validate='many_to_one')
    required=['chelsa_mm','era5_mm','chirps_mm']+[f'{p}_{s}' for s in (30,90,1000) for p in ('elevation','slope')]
    good=np.isfinite(data[required]).all(axis=1)
    complete=data.assign(good=good).groupby('station_id').good.all()
    eligible=set(complete[complete].index)
    report={'stations_before_covariates':len(ids),'stations_complete_covariates':len(eligible),
            'excluded_missing_covariates':len(ids-eligible),
            'reserved_before_covariates':int(data.loc[data.reserved,'station_id'].nunique()),
            'missing_rows_by_covariate':data[required].isna().sum().to_dict(),'hashes':hashes}
    data=data.loc[data.station_id.isin(eligible)].sort_values(['station_id','month']).reset_index(drop=True)
    angle=2*np.pi*(data.month-1)/12
    data['month_sin'],data['month_cos']=np.sin(angle),np.cos(angle)
    report['development_stations']=int(data.loc[~data.reserved,'station_id'].nunique())
    report['reserved_after_covariates']=int(data.loc[data.reserved,'station_id'].nunique())
    return data,report


def summary(predictions):
    rows=[]
    for (method,repeat),frame in predictions.groupby(['method','repeat']):
        rows.append({'method':method,'repeat':repeat,'scope':'monthly','n_stations':frame.station_id.nunique(),**metricas(frame.precipitation_mm,frame.prediction)})
        if not frame.groupby('station_id').month.nunique().eq(12).all():raise ValueError('Anual exige 12 meses.')
        annual=frame.groupby('station_id')[['precipitation_mm','prediction']].sum()
        rows.append({'method':method,'repeat':repeat,'scope':'annual','n_stations':len(annual),**metricas(annual.precipitation_mm,annual.prediction)})
    return pd.DataFrame(rows)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--method',choices=['M2','M4','M5','M6'],required=True)
    parser.add_argument('--block-size',type=int,choices=[1,2],default=2)
    parser.add_argument('--scale',type=int,choices=[30,90,1000],default=30)
    parser.add_argument('--satellite',action='store_true')
    args=parser.parse_args()
    data,coverage=prepare();development=data.loc[~data.reserved].reset_index(drop=True)
    groups=modelos.spatial_blocks(development,args.block_size)
    features=['latitude','longitude',f'elevation_{args.scale}',f'slope_{args.scale}','month_sin','month_cos','chelsa_mm']
    if args.satellite:features.append('chirps_mm')
    records=[];audit=[]
    for repeat in range(3):
        outer=GroupKFold(n_splits=5,shuffle=True,random_state=42+repeat)
        for fold,(a,b) in enumerate(outer.split(development,groups=groups)):
            train,test=development.iloc[a],development.iloc[b]
            base=test[['station_id','month','precipitation_mm']].copy()
            base['block'],base['repeat'],base['fold']=groups[b],repeat,fold
            for name in ('chelsa','era5','chirps'):
                records.append(base.assign(method=f'M0_{name}',prediction=test[f'{name}_mm'].to_numpy()))
            for formulation in ('direct','correction'):
                estimator=RainRegressor(method=args.method,formulation=formulation,random_state=42+repeat)
                grid={} if args.method=='M2' else {'complexity':[3,10] if args.method=='M4' else [7,15]}
                search=GridSearchCV(estimator,grid,cv=GroupKFold(n_splits=3),scoring='neg_root_mean_squared_error',n_jobs=1,error_score='raise')
                search.fit(train[features],train.precipitation_mm,groups=groups[a])
                records.append(base.assign(method=f'{args.method}_{formulation}',prediction=search.predict(test[features])))
                audit.append({'repeat':repeat,'fold':fold,'formulation':formulation,'parameters':search.best_params_,
                              'smearing':search.best_estimator_.smearing_})
            print(f'Chuva {args.method}: bloco {args.block_size}, repeticao {repeat+1}, dobra {fold+1}',flush=True)
    output=pd.concat(records,ignore_index=True)
    suffix=f'{args.method}_{args.block_size}graus_{args.scale}m_{"satelite" if args.satellite else "base"}'
    path=safe_path(f'dados/chuva/predicoes_{suffix}.csv');output.to_csv(path,index=False)
    summary(output).to_csv(safe_path(f'resultados/tabelas/chuva_{suffix}.csv'),index=False)
    # Bootstrap existente é genérico numericamente; adaptar apenas o nome da variável/unidade.
    paired=output.rename(columns={'precipitation_mm':'temperature_c'})
    diff=modelos.paired_intervals(paired,reference_method='M0_chelsa').rename(columns={'delta_rmse_c':'delta_rmse_mm'})
    diff.to_csv(safe_path(f'resultados/tabelas/chuva_diferencas_{suffix}.csv'),index=False)
    report={**coverage,'configuration':vars(args),'holdout_scored':False,'script_sha256':digest(__file__),
            'output_sha256':digest(path),'outer_folds':5,'inner_folds':3,'repeats':3,
            'retransformation':'training residual smearing, nonnegative predictions; inner scoring in mm',
            'limitation':'independence from climate grids unproven; not final validation','settings':audit}
    path.with_suffix('.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    public={k:v for k,v in report.items() if k!='settings'}
    safe_path(f'resultados/tabelas/chuva_auditoria_{suffix}.json').write_text(json.dumps(public,indent=2),encoding='utf-8')


if __name__=='__main__':main()
