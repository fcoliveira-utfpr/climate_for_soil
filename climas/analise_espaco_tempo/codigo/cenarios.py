"""Etapa 6a: matriz dos cenários de clima e dobras de validação (entrada de validacao.R).

Junta à matriz reconstruída (= trainingFinal) os climas dos locais (climas.py) e monta:
- colunas de cada cenário: dummies das classes (Köppen IPEF = as 13 dummies da produção; nos outros
  sistemas, uma dummy por classe dos níveis usados, descartadas as com menos de 30 ocorrências, como no R
  26) ou variáveis contínuas (CHELSA/BHC e decenais). Clima faltante: dummies 0 e contínuas pela mediana
  (≤ 0,6% das linhas, quase todas no litoral, fora das grades);
- dobras (perfil e réplicas trep sempre juntos):
  V2 espacial: blocos de 2°, 5 dobras equilibradas em linhas, 3 repetições (fold_v2_1..3);
  V3 temporal: 4 períodos de 10 anos pelo ano do perfil original (as réplicas vão com ele);
  V4 espaço-temporal: teste = dobra espacial f (repetição 1) e período p; treino = fora dos dois.

Saídas: climas/dados_espaco_tempo/matriz_cenarios.parquet (restrita) e codigo/cenarios.json (colunas de
cada cenário).

Uso: python cenarios.py
"""
import json
import re

import numpy as np
import pandas as pd

import config as cfg
import covariaveis_c3 as c3
from preparar_dados import ponto_id

COVARIAVEIS = [l for l in (cfg.PASTA / 'codigo' / 'covariaveis_modelo_c3.txt').read_text(encoding='utf-8').splitlines()
               if l and not l.startswith('#')]
BASE = [c for c in COVARIAVEIS if c not in c3.KOPPEN]           # tudo menos o clima
MIN_OCORRENCIAS = 30
PERIODOS = [(1985, 1994), (1995, 2004), (2005, 2014), (2015, 2024)]
N_REP_V2 = 3

CLASSES = {   # cenário: níveis de classe usados (como em climas/reproducao/codigo/config.py)
    'zonas_k10': ['zona_k10'],
    'holdridge_eth': ['holdridge_l1', 'holdridge_eth_l2'],
    'th_cadsolo': ['thsolo_l1', 'thsolo_l2'],
}
CONTINUOS = {
    'cont_chelsa': cfg.CLIMA_CONTINUO,
    'cont_decenal': cfg.CLIMA_DECENAL,
    'cont_ambos': cfg.CLIMA_CONTINUO + cfg.CLIMA_DECENAL,
}


def _nome(s):
    return re.sub(r'[^0-9A-Za-z_]+', '_', str(s)).strip('_')


def dummies(m, niveis, prefixo):
    cols = []
    for nivel in niveis:
        d = pd.get_dummies(m[nivel], prefix=f'{prefixo}_{_nome(nivel)}', prefix_sep='_', dtype=int)
        d.columns = [_nome(c) for c in d.columns]
        d = d.loc[:, d.sum() >= MIN_OCORRENCIAS]
        cols.append(d)
    return pd.concat(cols, axis=1)


def periodo(ano):
    for i, (a, b) in enumerate(PERIODOS, 1):
        if a <= ano <= b:
            return i
    raise ValueError(ano)


def dobras(m, semente=2026):
    m['grupo'] = m.id.str.replace(r'^trep(10|20)-', '', regex=True)
    # ano do perfil original (réplica trepNN tem o ano recuado em NN)
    recuo = m.id.str.extract(r'^trep(10|20)-')[0].fillna(0).astype(int)
    m['ano_original'] = (m.year + recuo).groupby(m.grupo).transform('max')
    m['periodo'] = m.ano_original.clip(lower=1985).map(periodo)
    m['bloco'] = (np.floor(m.longitude / 2).astype(int).astype(str) + '_'
                  + np.floor(m.latitude / 2).astype(int).astype(str))
    tamanho = m.bloco.value_counts().sort_index()
    rng = np.random.default_rng(semente)
    for r in range(1, N_REP_V2 + 1):
        # blocos em ordem aleatória, cada um para a dobra com menos linhas até ali (dobras equilibradas)
        linhas, mapa = np.zeros(5), {}
        for b in rng.permutation(tamanho.index):
            f = int(np.argmin(linhas))
            mapa[b], linhas[f] = f + 1, linhas[f] + tamanho[b]
        m[f'fold_v2_{r}'] = m.bloco.map(mapa)
    return m


def main():
    d = pd.read_parquet(cfg.MATRIZ)
    d['ponto_id'] = ponto_id(d)
    cl = pd.read_parquet(cfg.DADOS / 'climas_locais.parquet')
    dec = pd.read_parquet(cfg.DADOS / 'climas_decenais.parquet').rename(columns={'ano': 'year'})
    m = d.merge(cl, on='ponto_id', how='left').merge(dec, on=['ponto_id', 'year'], how='left')
    assert len(m) == len(d)

    cenarios = {'koppen_ipef': c3.KOPPEN, 'sem_clima': []}
    blocos = [m[BASE + c3.KOPPEN]]
    for nome, niveis in CLASSES.items():
        dm = dummies(m, niveis, nome)
        cenarios[nome] = list(dm.columns)
        blocos.append(dm)
    cont = sorted(set(cfg.CLIMA_CONTINUO + cfg.CLIMA_DECENAL))
    faltas = m[cont].isna().sum()
    blocos.append(m[cont].fillna(m[cont].median()))
    for nome, cols in CONTINUOS.items():
        cenarios[nome] = cols
    m = dobras(m)
    meta = ['id', 'grupo', 'year', 'ano_original', 'periodo', 'bloco', 'longitude', 'latitude',
            'carbono_gm2_qmap'] + [f'fold_v2_{r}' for r in range(1, N_REP_V2 + 1)]
    saida = pd.concat([m[meta]] + blocos, axis=1)
    saida.to_parquet(cfg.DADOS / 'matriz_cenarios.parquet', index=False)
    (cfg.PASTA / 'codigo' / 'cenarios.json').write_text(
        json.dumps({'base': BASE, 'cenarios': cenarios}, indent=1, ensure_ascii=False), encoding='utf-8')

    print(f'{len(saida)} linhas; base {len(BASE)} covariáveis')
    for nome, cols in cenarios.items():
        print(f'  {nome}: {len(cols)} colunas')
    print('faltas preenchidas (contínuas):', faltas[faltas > 0].to_dict())
    print('linhas por período:', m.periodo.value_counts().sort_index().to_dict())
    print('blocos:', m.bloco.nunique(), '| linhas por dobra V2 (rep 1):', m.fold_v2_1.value_counts().sort_index().to_dict())


if __name__ == '__main__':
    main()
