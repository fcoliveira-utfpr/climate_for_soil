"""Etapa 7g: reproduz o mapa oficial de SOC da C3 nos locais do painel, como em carbon/2_model_prediction.

O mapa não usa o ranger da validação (R 28/30, max.depth = 40), e sim o random forest do GEE:
    smileRandomForest({numberOfTrees: 300, variablesPerSplit: 24, minLeafPopulation: 2,
                       bagFraction: 0.632, maxNodes: 40, seed: 2021}), resposta carbono_gm2_qmap
maxNodes = 40 limita cada árvore a 40 folhas (árvores rasas). Emulação no scikit-learn: árvores crescidas
pelo maior ganho primeiro com max_leaf_nodes = 40 (como o Smile), 24 variáveis sorteadas por divisão e 63,2%
das linhas sem reposição em cada árvore.

Pós-processamento do mapa (mascaras_mapa.py): 0 onde o uso do ano é 23, 24 ou 30 ou o grupo textural é 1;
1985-1987 = mediana de 1985-1989 onde o uso foi estável nesses cinco anos; t/ha inteiras. A máscara de areia
(10 t/ha) não é legível: os locais com 10 t/ha no oficial em algum ano ficam fora da comparação.

Compara com o oficial: o modelo do GEE emulado e o ranger da validação, os dois com o mesmo pós-processamento.
Saídas: resultados/tabelas/fidelidade_mapa_oficial.csv; predições em dados_espaco_tempo/painel_gee.parquet.

Uso: python fidelidade_gee.py
"""
import json

import numpy as np
import pandas as pd
from sklearn.ensemble import BaggingRegressor
from sklearn.tree import DecisionTreeRegressor

import config as cfg
from metricas import error_statistics
from trajetorias import inclinacao


def modelo_gee():
    arvore = DecisionTreeRegressor(max_leaf_nodes=40, max_features=24, min_samples_split=2)
    return BaggingRegressor(arvore, n_estimators=300, max_samples=0.632, bootstrap=False,
                            random_state=2021, n_jobs=4)


def pos_processar(d, col):
    """Máscaras de uso e textura, correção de 1985-1987 e arredondamento, como no script do GEE."""
    v = d[col].round()
    v = v.where(~(d.lulc.isin([23, 24, 30]) | (d.textura_grupo == 1)), 0)
    d = d.assign(_v=v)
    ini = d[d.year.between(1985, 1989)]
    estavel = ini.groupby('ponto_id').lulc.std().eq(0)
    mediana = ini.groupby('ponto_id')._v.median().round()
    trocar = d.year.between(1985, 1987) & d.ponto_id.map(estavel).fillna(False).astype(bool)
    return d._v.where(~trocar, d.ponto_id.map(mediana))


def resumo(d, col, rotulo):
    i = pd.DataFrame({'o': inclinacao(d, 'soc_oficial_t_ha'), 'p': inclinacao(d, col)})
    anual = d.groupby('year')[[col, 'soc_oficial_t_ha']].mean()
    var = d.groupby('ponto_id')[[col, 'soc_oficial_t_ha']].agg(lambda s: s.diff().abs().mean()).mean()
    es = error_statistics(d.soc_oficial_t_ha.to_numpy(), d[col].to_numpy())
    return {'modelo': rotulo, 'media_t_ha': d[col].mean(), 'media_oficial': d.soc_oficial_t_ha.mean(),
            'me': es['me'], 'mae': es['mae'], 'rmse': es['rmse'], 'mec': es['mec'],
            'r_local_ano': np.corrcoef(d[col], d.soc_oficial_t_ha)[0, 1],
            'iguais_pct': (d[col] == d.soc_oficial_t_ha).mean() * 100,
            'dif_ate_1_pct': ((d[col] - d.soc_oficial_t_ha).abs() <= 1).mean() * 100,
            'inclinacao_media': i.p.mean(), 'inclinacao_oficial': i.o.mean(), 'r_inclinacao': i.corr().iloc[0, 1],
            'r_media_anual': anual.corr().iloc[0, 1], 'variacao_anual': var[col],
            'variacao_anual_oficial': var.soc_oficial_t_ha}


def main():
    meta = json.loads((cfg.PASTA / 'codigo' / 'cenarios.json').read_text(encoding='utf-8'))
    cols = meta['base'] + meta['cenarios']['koppen_ipef']
    m = pd.read_parquet(cfg.DADOS / 'matriz_cenarios.parquet', columns=cols + ['carbono_gm2_qmap'])
    p = pd.read_parquet(cfg.DADOS / 'painel_cenarios.parquet', columns=['ponto_id', 'year'] + cols)

    rf = modelo_gee().fit(m[cols].to_numpy(), m.carbono_gm2_qmap.to_numpy())
    X = p[cols].to_numpy(np.float32)
    p['gee'] = np.concatenate([rf.predict(X[i:i + 50000]) for i in range(0, len(X), 50000)]) / 100
    rang = pd.read_parquet(cfg.DADOS / 'painel_predicoes.parquet', columns=['ponto_id', 'year', 'koppen_ipef'])
    d = (p[['ponto_id', 'year', 'gee']].merge(rang, on=['ponto_id', 'year'])
         .merge(pd.read_parquet(cfg.DADOS / 'mascaras_mapa.parquet'), on=['ponto_id', 'year'])
         .merge(pd.read_parquet(cfg.DADOS / 'soc_oficial_c3.parquet'), on=['ponto_id', 'year'])
         .sort_values(['ponto_id', 'year']).reset_index(drop=True))
    d.to_parquet(cfg.DADOS / 'painel_gee.parquet', index=False)

    areia = d.groupby('ponto_id').soc_oficial_t_ha.transform(lambda s: (s == 10).any())
    print(f'locais com 10 t/ha no oficial (máscara de areia provável), fora da comparação: '
          f'{d[areia].ponto_id.nunique()}')
    d = d[~areia].copy()
    d['gee_pp'] = pos_processar(d, 'gee')
    d['ranger_pp'] = pos_processar(d, 'koppen_ipef')
    tab = pd.DataFrame([resumo(d, 'gee_pp', 'GEE emulado (maxNodes 40) + pós-processamento'),
                        resumo(d, 'ranger_pp', 'ranger da validação (max.depth 40) + pós-processamento'),
                        resumo(d, 'gee', 'GEE emulado, sem pós-processamento'),
                        resumo(d, 'koppen_ipef', 'ranger, sem pós-processamento')])
    tab.to_csv(cfg.TABELAS / 'fidelidade_mapa_oficial.csv', index=False, float_format='%.4g')
    pd.set_option('display.width', 250)
    print(tab.round(3).T.to_string())
    print(d.groupby('year')[['soc_oficial_t_ha', 'gee_pp', 'ranger_pp']].mean().iloc[::5].round(2))


if __name__ == '__main__':
    main()
