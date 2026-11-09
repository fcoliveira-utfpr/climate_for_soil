"""C2: gradiente efetivo de correção CHELSA, ajustado somente no treino.

OLS pela origem: Tobs - CHELSA = gamma * (DEM30 - DEMgrosseiro).
Não estima diretamente o gradiente atmosférico. Sem intercepto, clipping ou
seleção de hiperparâmetros. Grupos com menos de cinco estações usam fallback.
"""
import json
import numpy as np
import pandas as pd
from sklearn.model_selection import GroupKFold
from codigo import modelos
from codigo.comparar_bases import summarize_extended
from codigo.dados_temperatura import safe_path
from codigo.grade_brasil import digest

FIXED = -.0065
UNKNOWN = 'sem_atribuicao_univoca'


def slope(train, fallback=FIXED):
    x = (train.dem_elevation_m - train.coarse_elevation_m).to_numpy(float)
    y = (train.temperature_c - train.chelsa_c).to_numpy(float)
    if not np.isfinite(x).all() or not np.isfinite(y).all():
        raise ValueError('Ajuste exige valores finitos.')
    if train.station_id.nunique() < 5 or np.dot(x, x) <= 1e-12:
        return fallback, True
    return float(np.dot(x, y) / np.dot(x, x)), False


def predict(train, test):
    if set(train.station_id) & set(test.station_id):
        raise ValueError('Estações de treino e avaliação devem ser distintas.')
    global_slope, fallback = slope(train)
    audit = [{'level':'global', 'gamma_c_per_m':global_slope, 'fallback':fallback}]
    slopes = {name:np.full(len(test), value) for name, value in
              [('M1_fixo', FIXED), ('M1_global', global_slope),
               ('M1_mensal', global_slope), ('M1_mensal_regional', global_slope)]}
    for month in range(1, 13):
        source = train.loc[train.month.eq(month)]
        monthly, fallback = slope(source, global_slope)
        mask = test.month.eq(month).to_numpy()
        slopes['M1_mensal'][mask] = monthly
        slopes['M1_mensal_regional'][mask] = monthly
        audit.append({'level':'month', 'month':month, 'gamma_c_per_m':monthly, 'fallback':fallback})
        for region in sorted(test.loc[mask, 'region'].unique()):
            if region == UNKNOWN:
                continue
            regional, fallback = slope(source.loc[source.region.eq(region)], monthly)
            subset = mask & test.region.eq(region).to_numpy()
            slopes['M1_mensal_regional'][subset] = regional
            audit.append({'level':'month_region', 'month':month, 'region':region,
                          'gamma_c_per_m':regional, 'fallback':fallback})
    delta = (test.dem_elevation_m - test.coarse_elevation_m).to_numpy()
    values = {name:test.chelsa_c.to_numpy() + gamma*delta for name, gamma in slopes.items()}
    values['M0_chelsa'] = test.chelsa_c.to_numpy()
    return values, audit


def main():
    source = safe_path('dados/processados/normais_covariaveis.csv')
    regions_path = safe_path('dados/brasil/regioes_estacoes.csv')
    data = modelos.prepare(pd.read_csv(source, dtype={'station_id':str}))
    development = data.loc[~modelos.reserve_test(data)].copy()
    regions = pd.read_csv(regions_path, dtype={'station_id':str})
    development = development.merge(regions, on='station_id', how='left', validate='many_to_one')
    if development.region.isna().any():
        raise ValueError('Auditoria regional incompleta.')
    for block in (1, 2):
        groups = modelos.spatial_blocks(development, block)
        records, adjustments = [], []
        for repeat in range(3):
            folds = GroupKFold(n_splits=5, shuffle=True, random_state=42+repeat)
            for fold, (a, b) in enumerate(folds.split(development, groups=groups)):
                train, test = development.iloc[a], development.iloc[b]
                values, audit = predict(train, test)
                base = test[['station_id','month','temperature_c','elevation_m']].copy()
                base['block'], base['repeat'], base['fold'] = groups[b], repeat, fold
                records.extend(base.assign(method=method, prediction=value) for method, value in values.items())
                adjustments.append({'repeat':repeat, 'fold':fold, 'coefficients':audit,
                                    'training_stations':sorted(train.station_id.unique().tolist()),
                                    'evaluation_stations':sorted(test.station_id.unique().tolist())})
        predictions = pd.concat(records, ignore_index=True)
        path = safe_path(f'dados/modelagem/c2_gradientes_{block}graus.csv')
        predictions.to_csv(path, index=False)
        path.with_suffix('.ajustes.json').write_text(json.dumps(adjustments, indent=2), encoding='utf-8')
        summarize_extended(predictions).to_csv(safe_path(f'resultados/tabelas/c2_gradientes_{block}graus.csv'), index=False)
        modelos.paired_intervals(predictions, reference_method='M0_chelsa').to_csv(
            safe_path(f'resultados/tabelas/c2_gradientes_diferencas_{block}graus.csv'), index=False)
        report = {'input_sha256':digest(source), 'regions_sha256':digest(regions_path),
                  'script_sha256':digest(__file__), 'modelos_sha256':digest(modelos.__file__),
                  'output_sha256':digest(path), 'holdout_scored':False,
                  'development_stations':int(development.station_id.nunique()),
                  'minimum_training_stations_per_group':5, 'outer_folds':5, 'repeats':3,
                  'method':'OLS through origin, no hyperparameter tuning; monthly regional -> monthly -> global -> fixed fallback',
                  'limitation':'Effective CHELSA correction coefficient; not an atmospheric lapse-rate measurement.'}
        path.with_suffix('.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
        print(f'C2: {block} graus concluido', flush=True)


if __name__ == '__main__':
    main()
