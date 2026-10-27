"""Etapa 6a: painel local × ano 1985-2024 com o Köppen móvel de 30 anos (entrada de prever_painel.R e de
prever_painel_gee.py com VAL_*).

Parte do painel do relatório v2 (climas/dados_espaco_tempo/painel_cenarios.parquet, covariáveis da produção
por ano) e acrescenta, para cada local e ano, as dummies do Köppen da janela dos 30 anos anteriores, com os
mesmos nomes da matriz (cenarios_movel30.json; classe ausente = 0). Ponto em pixel sem dado recebe a classe
do pixel válido mais próximo, como na matriz.

Saída (restrita): climas/dados_koppen_movel30/painel_movel30.parquet

Uso: python painel_movel30.py
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

RAIZ = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(RAIZ / 'climas_tempo' / 'codigo'))
from cenarios_tempo import dummies, indices_pixel, niveis  # noqa: E402

DADOS = RAIZ / 'climas' / 'dados_koppen_movel30'
PAINEL_V2 = RAIZ / 'climas' / 'dados_espaco_tempo' / 'painel_cenarios.parquet'
CENARIOS = Path(__file__).with_name('cenarios_movel30.json')


def main():
    g = np.load(DADOS / 'grade.npz')
    k = np.load(DADOS / 'koppen_movel30.npz')
    meta = json.loads(CENARIOS.read_text(encoding='utf-8'))
    p = pd.read_parquet(PAINEL_V2, columns=['ponto_id', 'year', 'longitude', 'latitude'] + meta['base'])
    lin, col, n_fora = indices_pixel(p.longitude.to_numpy(), p.latitude.to_numpy(), g)
    anos = k['anos']
    cod = k['koppen'][np.clip(p.year.to_numpy(), anos[0], anos[-1]) - anos[0], lin, col]
    d = dummies(niveis('koppen', cod), 'xkm').reindex(columns=meta['cenarios']['koppen_movel30'], fill_value=0)
    out = pd.concat([p, d], axis=1)
    out.to_parquet(DADOS / 'painel_movel30.parquet', index=False)
    mudou = pd.Series(cod).groupby(p.ponto_id.to_numpy()).nunique()
    print(f'{len(out)} linhas, {p.ponto_id.nunique()} locais, {n_fora} linhas em pixel sem dado; '
          f'locais com mais de uma classe em 1985-2024: {(mudou > 1).sum()} ({(mudou > 1).mean():.1%})')


if __name__ == '__main__':
    main()
