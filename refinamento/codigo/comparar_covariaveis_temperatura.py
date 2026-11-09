"""C5/C6 em amostras pareadas e tuning interno; não altera o produto atual."""
import argparse
import json
import numpy as np
import pandas as pd
from sklearn.model_selection import GroupKFold,GridSearchCV
from codigo import modelos
from codigo.comparar_bases import summarize_extended
from codigo.dados_temperatura import safe_path
from codigo.grade_brasil import digest


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--experiment',choices=['escalas','modis'],required=True)
    args=parser.parse_args()
    source=safe_path('dados/processados/normais_covariaveis.csv')
    data=modelos.prepare(pd.read_csv(source,dtype={'station_id':str}))
    data=data.loc[~modelos.reserve_test(data)].copy()
    initial=data.station_id.nunique()
    extra=safe_path('dados/brasil/relevo_escalas.csv' if args.experiment=='escalas' else 'dados/brasil/modis_temperatura.csv')
    metadata=json.loads(extra.with_suffix('.json').read_text(encoding='utf-8'))
    if metadata['input_sha256']!=digest(source) or metadata['output_sha256']!=digest(extra):raise ValueError('Covariáveis com origem divergente.')
    data=data.merge(pd.read_csv(extra,dtype={'station_id':str}),on=['station_id'] if args.experiment=='escalas' else ['station_id','month'],how='left',validate='many_to_one' if args.experiment=='escalas' else 'one_to_one')
    features=modelos.feature_columns(data)
    if args.experiment=='escalas':
        variants={str(s):[f'elevation_{s}' if c=='dem_elevation_m' else f'slope_{s}' if c=='slope_deg' else c for c in features] for s in (30,90,1000)}
        reference='M5_lightgbm_30'
    else:
        variants={'base':features,'modis':features+['lst_day_c','lst_night_c']}
        reference='M5_lightgbm_base'
    required=sorted(set(sum(variants.values(),[])))
    complete=data.assign(complete=np.isfinite(data[required]).all(axis=1)).groupby('station_id').complete.all()
    data=data.loc[data.station_id.isin(complete[complete].index)].reset_index(drop=True)
    for block in (1,2):
        groups=modelos.spatial_blocks(data,block);records=[];adjustments=[]
        for repeat in range(3):
            outer=GroupKFold(n_splits=5,shuffle=True,random_state=42+repeat)
            for fold,(a,b) in enumerate(outer.split(data,groups=groups)):
                train,test=data.iloc[a],data.iloc[b]
                base=test[['station_id','month','temperature_c','elevation_m']].copy()
                base['block'],base['repeat'],base['fold']=groups[b],repeat,fold
                for variant,columns in variants.items():
                    for method in ('M2_linear','M5_lightgbm'):
                        estimator,grid=modelos.model_candidates(42+repeat)[method]
                        search=GridSearchCV(estimator,grid,cv=GroupKFold(n_splits=3),scoring='neg_root_mean_squared_error',n_jobs=1,error_score='raise')
                        search.fit(train[columns],train.temperature_c-train.chelsa_c,groups=groups[a])
                        name=f'{method}_{variant}'
                        records.append(base.assign(method=name,prediction=search.predict(test[columns])+test.chelsa_c.to_numpy()))
                        adjustments.append({'repeat':repeat,'fold':fold,'method':name,'parameters':search.best_params_})
                print(f'{args.experiment}: {block} graus, repeticao {repeat+1}, dobra {fold+1}',flush=True)
        predictions=pd.concat(records,ignore_index=True)
        path=safe_path(f'dados/modelagem/{args.experiment}_temperatura_{block}graus.csv');predictions.to_csv(path,index=False)
        summarize_extended(predictions).to_csv(safe_path(f'resultados/tabelas/{args.experiment}_temperatura_{block}graus.csv'),index=False)
        modelos.paired_intervals(predictions,reference_method=reference).to_csv(safe_path(f'resultados/tabelas/{args.experiment}_diferencas_{block}graus.csv'),index=False)
        report={'input_sha256':digest(source),'extra_sha256':digest(extra),'script_sha256':digest(__file__),
                'output_sha256':digest(path),'initial_development_stations':int(initial),'paired_stations':int(data.station_id.nunique()),
                'excluded_missing_covariates':int(initial-data.station_id.nunique()),'holdout_scored':False,
                'variants':variants,'outer_folds':5,'inner_folds':3,'repeats':3,
                'limitation':'MODIS descriptor covers 2001-2020 only; DSM aggregation is not proof of predictive skill at 30 m.'}
        safe_path(f'resultados/tabelas/{args.experiment}_auditoria_{block}graus.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
        path.with_suffix('.json').write_text(json.dumps({**report,'settings':adjustments},indent=2),encoding='utf-8')


if __name__=='__main__':main()
