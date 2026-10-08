"""Etapa 7b: painel local × ano com as colunas de todos os cenários (entrada de prever_painel.R).

As colunas são as mesmas de matriz_cenarios.parquet (cenarios.json): as dummies de classe recebem os
mesmos nomes (classes ausentes no painel = 0); as contínuas faltantes são preenchidas com a mediana da
matriz, como no treino; as decenais entram pelo ano de cada linha.

Saída (restrita): climas/dados_espaco_tempo/painel_cenarios.parquet

Uso: python painel_cenarios.py
"""
import json

import pandas as pd

import config as cfg
from cenarios import CLASSES, _nome


def main():
    meta = json.loads((cfg.PASTA / 'codigo' / 'cenarios.json').read_text(encoding='utf-8'))
    p = pd.read_parquet(cfg.PAINEL)
    cl = pd.read_parquet(cfg.DADOS / 'climas_locais.parquet')
    dec = pd.read_parquet(cfg.DADOS / 'climas_decenais.parquet').rename(columns={'ano': 'year'})
    n = len(p)
    p = p.merge(cl, on='ponto_id', how='left').merge(dec, on=['ponto_id', 'year'], how='left')
    assert len(p) == n

    blocos = [p[['ponto_id', 'year', 'longitude', 'latitude'] + meta['base'] + meta['cenarios']['koppen_ipef']]]
    for nome, niveis in CLASSES.items():
        partes = []
        for nivel in niveis:
            d = pd.get_dummies(p[nivel], prefix=f'{nome}_{_nome(nivel)}', prefix_sep='_', dtype=int)
            d.columns = [_nome(c) for c in d.columns]
            partes.append(d)
        blocos.append(pd.concat(partes, axis=1).reindex(columns=meta['cenarios'][nome], fill_value=0))
    cont = sorted(set(cfg.CLIMA_CONTINUO + cfg.CLIMA_DECENAL))
    mediana = pd.read_parquet(cfg.DADOS / 'matriz_cenarios.parquet', columns=cont).median()
    blocos.append(p[cont].fillna(mediana))
    out = pd.concat(blocos, axis=1)
    faltam = [c for c in meta['base'] + sum(meta['cenarios'].values(), []) if c not in out.columns]
    assert not faltam, faltam
    out.to_parquet(cfg.DADOS / 'painel_cenarios.parquet', index=False)
    print(f'{len(out)} linhas, {out.shape[1]} colunas; faltas nas contínuas preenchidas: '
          f'{p[cont].isna().any(axis=1).mean():.2%} das linhas')


if __name__ == '__main__':
    main()
