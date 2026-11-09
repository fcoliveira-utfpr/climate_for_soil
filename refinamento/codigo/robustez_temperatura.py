"""C7/C8: sazonalidade e densidade com avaliação espacial fixa, sem holdout.

Compara LightGBM e regressão linear corrigindo CHELSA. Subamostragem ocorre
somente no treino externo, por estação inteira; tuning usa apenas esse treino.
"""
from __future__ import annotations

import json
import numpy as np
import pandas as pd
from sklearn.model_selection import GroupKFold, GridSearchCV

from codigo import modelos
from codigo.bases_gee import sha256
from codigo.comparar_bases import summarize_extended
from codigo.dados_temperatura import safe_path

SEASONAL = ['month_sin', 'month_cos', 'latitude_sin', 'latitude_cos']


def features_for(data, strategy):
    if strategy not in ('harmonics', 'none', 'categorical', 'per_month'):
        raise ValueError('Estratégia sazonal inválida.')
    features = modelos.feature_columns(data)
    if strategy != 'harmonics':
        features = [x for x in features if x not in SEASONAL]
    frame = data[features].copy()
    if strategy == 'categorical':
        for month in range(2, 13):
            frame[f'month_{month:02d}'] = (data.month == month).astype(float)
    return frame


def subsample_stations(train, fraction, seed):
    if not 0 < fraction <= 1:
        raise ValueError('Fração deve ficar em (0, 1].')
    ids = np.sort(train.station_id.unique())
    # O mesmo sorteio permite comparar subconjuntos aninhados entre frações.
    selected = np.random.default_rng(seed).permutation(ids)[:max(1, int(np.ceil(len(ids) * fraction)))]
    return train.loc[train.station_id.isin(selected)].copy()


def predict(train, test, strategy, method, block_size, seed):
    prediction = np.empty(len(test))
    settings = []
    subsets = list(range(1, 13)) if strategy == 'per_month' else [None]
    for month in subsets:
        source = train if month is None else train.loc[train.month == month]
        positions = np.arange(len(test)) if month is None else np.flatnonzero(test.month.to_numpy() == month)
        target = test.iloc[positions]
        groups = modelos.spatial_blocks(source, block_size)
        if len(np.unique(groups)) < 3:
            raise ValueError('Subamostra sem três blocos para tuning espacial.')
        estimator, parameters = modelos.model_candidates(seed)[method]
        x, y = features_for(source, strategy), source.temperature_c - source.chelsa_c
        best = {}
        if parameters:
            estimator = GridSearchCV(estimator, parameters, cv=GroupKFold(n_splits=3),
                                     scoring='neg_root_mean_squared_error', n_jobs=1)
            estimator.fit(x, y, groups=groups)
            best = estimator.best_params_
        else:
            estimator.fit(x, y)
        prediction[positions] = estimator.predict(features_for(target, strategy)) + target.chelsa_c.to_numpy()
        settings.append({'month': month, 'parameters': best, 'training_stations': int(source.station_id.nunique())})
    return prediction, settings


def compare(data, block_size=2, repeats=3):
    development = data.loc[~modelos.reserve_test(data)].reset_index(drop=True)
    groups = modelos.spatial_blocks(development, block_size)
    scenarios = [(s, 1.0) for s in ('harmonics', 'none', 'categorical', 'per_month')]
    scenarios += [('harmonics', f) for f in (0.25, 0.5, 0.75)]
    predictions, audit = [], []
    for repeat in range(repeats):
        splitter = GroupKFold(n_splits=5, shuffle=True, random_state=42 + repeat)
        for fold, (train_idx, test_idx) in enumerate(splitter.split(development, groups=groups)):
            full_train, test = development.iloc[train_idx], development.iloc[test_idx]
            base = test[['station_id', 'month', 'temperature_c', 'elevation_m']].copy()
            base['block'], base['fold'], base['repeat'] = groups[test_idx], fold, repeat
            predictions.append(base.assign(method='M0_chelsa', prediction=test.chelsa_c.to_numpy()))
            for strategy, fraction in scenarios:
                train = subsample_stations(full_train, fraction, 42000 + 100 * repeat + fold)
                if set(train.station_id) & set(test.station_id):
                    raise ValueError('Vazamento de estação entre treino e avaliação.')
                for method in ('M2_linear', 'M5_lightgbm'):
                    label = f'{method}_{strategy}_{int(100*fraction):03d}pct'
                    values, settings = predict(train, test, strategy, method, block_size, 42 + repeat)
                    predictions.append(base.assign(method=label, prediction=values))
                    audit.append({'repeat': repeat, 'fold': fold, 'method': label,
                                  'training_stations': sorted(train.station_id.unique().tolist()),
                                  'evaluation_stations': sorted(test.station_id.unique().tolist()),
                                  'settings': settings})
            print(f'C7/C8: {block_size} graus; repeticao {repeat+1}; dobra {fold+1}/5', flush=True)
    return pd.concat(predictions, ignore_index=True), audit


def main():
    source = safe_path('dados/processados/normais_covariaveis.csv')
    data = modelos.prepare(pd.read_csv(source, dtype={'station_id': str}))
    for block in (1, 2):
        destination = safe_path(f'dados/modelagem/c7_c8_predicoes_{block}graus.csv')
        manifest_path = destination.with_suffix('.json')
        signature = {'input_sha256': sha256(source), 'script_sha256': sha256(__file__),
                     'modelos_sha256': sha256(modelos.__file__), 'block_size': block}
        if destination.exists() and manifest_path.exists():
            previous = json.loads(manifest_path.read_text(encoding='utf-8'))
            if previous.get('signature') == signature and previous.get('output_sha256') == sha256(destination):
                print(f'C7/C8: {block} graus ja conferido.', flush=True)
                continue
            raise ValueError('Resultado existente incompatível; não sobrescrever silenciosamente.')
        predictions, audit = compare(data, block)
        predictions.to_csv(destination, index=False)
        safe_path(f'dados/modelagem/c7_c8_ajustes_{block}graus.json').write_text(json.dumps(audit, indent=2), encoding='utf-8')
        summarize_extended(predictions).to_csv(safe_path(f'resultados/tabelas/c7_c8_metricas_{block}graus.csv'), index=False)
        modelos.paired_intervals(predictions, reference_method='M5_lightgbm_harmonics_100pct').to_csv(
            safe_path(f'resultados/tabelas/c7_c8_diferencas_{block}graus.csv'), index=False)
        manifest = {'signature': signature, 'output_sha256': sha256(destination), 'holdout_scored': False,
                    'development_stations': int(data.loc[~modelos.reserve_test(data)].station_id.nunique()),
                    'repeats': 3, 'outer_folds': 5, 'inner_folds': 3,
                    'limitation': 'CHELSA e alvo atuais; sem escolha final nem prova de habilidade a 30 m.'}
        manifest_path.write_text(json.dumps(manifest, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
