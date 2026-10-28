"""Etapa 4: painel local × ano 1985-2024 com as colunas de todos os cenários do capítulo 6 (entrada de
prever_painel.R e prever_painel_gee.py com VAL_*).

Parte do painel do relatório v2 (climas/dados_espaco_tempo/painel_cenarios.parquet: covariáveis da produção
por ano, dummies do Köppen IPEF, normais clim_* e decenais dec_*) e acrescenta as variáveis cd_* do relatório v4
de cada local e ano (média dos 10 anos anteriores, no pixel do Xavier; local fora da grade -> pixel válido mais
próximo). Faltas são preenchidas com a mediana da matriz, como no treino.

Saída (restrita): clima_final/dados/painel_final.parquet

Uso: python painel_final.py
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / 'climas_tempo' / 'codigo'))
from cenarios_tempo import indices_pixel  # noqa: E402

DADOS = RAIZ / 'clima_final' / 'dados'
VARIAVEIS = RAIZ / 'clima_decenal' / 'dados' / 'variaveis'
PAINEL_V2 = RAIZ / 'climas' / 'dados_espaco_tempo' / 'painel_cenarios.parquet'


def main():
    meta = json.loads(Path(__file__).with_name('cenarios_final.json').read_text(encoding='utf-8'))
    cols = list(dict.fromkeys(meta['base'] + sum(meta['cenarios'].values(), [])))
    cd = [c for c in cols if c.startswith('cd_')]
    outras = [c for c in cols if c not in cd]
    p = pd.read_parquet(PAINEL_V2, columns=['ponto_id', 'year', 'longitude', 'latitude'] + outras)
    g = np.load(RAIZ / 'climas_tempo' / 'dados' / 'grade.npz')
    lin, col, n_fora = indices_pixel(p.longitude.to_numpy(), p.latitude.to_numpy(), g)
    anos = p.year.to_numpy()
    vals = {v: np.full(len(p), np.nan, np.float32) for v in cd}
    for ano in np.unique(anos):
        d = np.load(VARIAVEIS / f'{ano}.npz')
        sel = anos == ano
        for v in cd:
            vals[v][sel] = d[v][lin[sel], col[sel]]
    v = pd.DataFrame(vals)
    faltas = v.isna().any(axis=1).mean()
    v = v.fillna(pd.read_parquet(DADOS / 'matriz_final.parquet', columns=cd).median())
    out = pd.concat([p, v], axis=1)
    out.to_parquet(DADOS / 'painel_final.parquet', index=False)
    print(f'{len(out)} linhas, {out.ponto_id.nunique()} locais; {n_fora} linhas fora da grade; '
          f'linhas com falta em cd_*: {faltas:.2%}')


if __name__ == '__main__':
    main()
