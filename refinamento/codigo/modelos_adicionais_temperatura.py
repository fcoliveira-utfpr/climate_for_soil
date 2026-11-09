"""M3/M6 na temperatura, nas dobras existentes e com tuning espacial interno."""
import json
import pandas as pd
from sklearn.model_selection import GridSearchCV,GroupKFold
from codigo import modelos
from codigo.estimadores_adicionais import GeographicalRegression,LinearResidual
from codigo.comparar_bases import summarize_extended
from codigo.dados_temperatura import safe_path
from codigo.grade_brasil import digest


def main():
    source=safe_path('dados/processados/normais_covariaveis.csv')
    data=modelos.prepare(pd.read_csv(source,dtype={'station_id':str}))
    development=data.loc[~modelos.reserve_test(data)].reset_index(drop=True)
    features=modelos.feature_columns(data)
    for block in (1,2):
        groups=modelos.spatial_blocks(development,block)
        records=[];audit=[]
        for repeat in range(3):
            outer=GroupKFold(n_splits=5,shuffle=True,random_state=42+repeat)
            for fold,(a,b) in enumerate(outer.split(development,groups=groups)):
                train,test=development.iloc[a],development.iloc[b]
                base=test[['station_id','month','temperature_c','elevation_m']].copy()
                base['block'],base['repeat'],base['fold']=groups[b],repeat,fold
                candidates={'M3_GWR':(GeographicalRegression(),{'bandwidth_km':[250,750]}),
                            'M6_linear_residual':(LinearResidual(random_state=42+repeat),{'num_leaves':[7,15]})}
                for name,(model,grid) in candidates.items():
                    search=GridSearchCV(model,grid,cv=GroupKFold(n_splits=3),scoring='neg_root_mean_squared_error',n_jobs=1,error_score='raise')
                    search.fit(train[features],train.temperature_c-train.chelsa_c,groups=groups[a])
                    prediction=search.predict(test[features])+test.chelsa_c.to_numpy()
                    records.append(base.assign(method=name,prediction=prediction))
                    audit.append({'method':name,'repeat':repeat,'fold':fold,'parameters':search.best_params_})
                print(f'M3/M6: {block} graus, repeticao {repeat+1}, dobra {fold+1}',flush=True)
        prior_path=safe_path(f'dados/modelagem/predicoes_{block}graus_grade_correction.csv')
        prior=pd.read_csv(prior_path,dtype={'station_id':str})
        combined=pd.concat([prior,*records],ignore_index=True)
        # paired_intervals também confere mesmas observações, estações, meses e dobras.
        differences=modelos.paired_intervals(combined,reference_method='M5_lightgbm')
        output=safe_path(f'dados/modelagem/m3_m6_temperatura_{block}graus.csv')
        combined.to_csv(output,index=False)
        summarize_extended(combined).to_csv(safe_path(f'resultados/tabelas/m3_m6_temperatura_{block}graus.csv'),index=False)
        differences.to_csv(safe_path(f'resultados/tabelas/m3_m6_diferencas_{block}graus.csv'),index=False)
        output.with_suffix('.json').write_text(json.dumps({'input_sha256':digest(source),
            'prior_predictions_sha256':digest(prior_path),'output_sha256':digest(output),
            'script_sha256':digest(__file__),'estimators_sha256':digest(safe_path('codigo/estimadores_adicionais.py')),
            'holdout_scored':False,'outer_folds':5,'inner_folds':3,'repeats':3,'settings':audit},indent=2),encoding='utf-8')


if __name__=='__main__':main()
