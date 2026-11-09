"""C7/C8 chuva: sazonalidade e densidade, com avaliação espacial fixa."""
import argparse
import json
import numpy as np
import pandas as pd
from sklearn.model_selection import GroupKFold,GridSearchCV
from codigo import modelos
from codigo.modelos_chuva import RainRegressor,prepare,summary
from codigo.robustez_temperatura import subsample_stations
from codigo.dados_temperatura import safe_path
from codigo.grade_brasil import digest


def features(data,strategy):
    names=['latitude','longitude','elevation_30','slope_30','chelsa_mm']
    if strategy=='harmonics':names+=['month_sin','month_cos']
    frame=data[names].copy()
    if strategy=='categorical':
        for month in range(2,13):frame[f'month_{month}']=data.month.eq(month).astype(float)
    return frame


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--block-size',type=int,choices=[1,2],required=True)
    args=parser.parse_args()
    data,coverage=prepare();data=data.loc[~data.reserved].reset_index(drop=True)
    groups=modelos.spatial_blocks(data,args.block_size)
    records=[];settings=[]
    scenarios=[(s,1.) for s in ('harmonics','none','categorical','per_month')]+[('harmonics',f) for f in (.25,.5,.75)]
    for repeat in range(3):
        for fold,(a,b) in enumerate(GroupKFold(n_splits=5,shuffle=True,random_state=42+repeat).split(data,groups=groups)):
            full,test=data.iloc[a],data.iloc[b]
            base=test[['station_id','month','precipitation_mm']].copy()
            base['block'],base['repeat'],base['fold']=groups[b],repeat,fold
            records.append(base.assign(method='M0_chelsa',prediction=test.chelsa_mm.to_numpy()))
            for strategy,fraction in scenarios:
                train=subsample_stations(full,fraction,42000+100*repeat+fold)
                if set(train.station_id)&set(test.station_id):raise ValueError('Vazamento de estação.')
                for method in ('M2','M5'):
                    label=f'{method}_{strategy}_{int(fraction*100):03d}pct'
                    values=np.empty(len(test))
                    for month in range(1,13) if strategy=='per_month' else [None]:
                        source=train if month is None else train.loc[train.month.eq(month)]
                        positions=np.arange(len(test)) if month is None else np.flatnonzero(test.month.to_numpy()==month)
                        inner_groups=modelos.spatial_blocks(source,args.block_size)
                        search=GridSearchCV(RainRegressor(method=method,formulation='correction',random_state=42+repeat),
                            {} if method=='M2' else {'complexity':[7,15]},cv=GroupKFold(n_splits=3),
                            scoring='neg_root_mean_squared_error',n_jobs=1,error_score='raise')
                        search.fit(features(source,strategy),source.precipitation_mm,groups=inner_groups)
                        values[positions]=search.predict(features(test.iloc[positions],strategy))
                        settings.append({'repeat':repeat,'fold':fold,'method':label,'month':month,
                            'training_stations':source.station_id.nunique(),'parameters':search.best_params_})
                    records.append(base.assign(method=label,prediction=values))
            print(f'Robustez chuva {args.block_size}°: repetição {repeat+1}, dobra {fold+1}',flush=True)
    output=pd.concat(records,ignore_index=True)
    path=safe_path(f'dados/chuva/predicoes_c7_c8_{args.block_size}graus.csv');output.to_csv(path,index=False)
    summary(output).to_csv(safe_path(f'resultados/tabelas/chuva_c7_c8_{args.block_size}graus.csv'),index=False)
    differences=modelos.paired_intervals(output.rename(columns={'precipitation_mm':'temperature_c'}),reference_method='M5_harmonics_100pct')
    differences.rename(columns={'delta_rmse_c':'delta_rmse_mm'}).to_csv(
        safe_path(f'resultados/tabelas/chuva_c7_c8_diferencas_{args.block_size}graus.csv'),index=False)
    audit={**coverage,'block_size':args.block_size,'script_sha256':digest(__file__),'output_sha256':digest(path),
        'holdout_scored':False,'outer_folds':5,'inner_folds':3,'repeats':3,'subsample_unit':'station, training only'}
    path.with_suffix('.json').write_text(json.dumps({**audit,'settings':settings},indent=2),encoding='utf-8')
    safe_path(f'resultados/tabelas/chuva_c7_c8_{args.block_size}graus.json').write_text(json.dumps(audit,indent=2),encoding='utf-8')


if __name__=='__main__':main()
