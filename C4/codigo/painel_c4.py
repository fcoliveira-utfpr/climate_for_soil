"""Etapa 7: painel local × ano 1985-2024 com as variáveis do Xavier v3.2.4 (entrada de prever_painel.R e
prever_painel_gee.py com VAL_*).

Parte do painel do v6 (clima_final/dados/painel_final.parquet: covariáveis da produção por ano e as cd_* do
Xavier v3.2.2) e troca as cd_* pelas da v3.2.4 do ano de cada linha (mesma extração de pontos.py); faltas são
preenchidas com a mediana da matriz do C4, como no treino.

Saída (restrita): C4/dados/painel_c4.parquet

Uso: python painel_c4.py
"""
from pathlib import Path

import pandas as pd

from pontos import DADOS, RAIZ, extrair

PAINEL_V6 = RAIZ / 'clima_final' / 'dados' / 'painel_final.parquet'


def main():
    p = pd.read_parquet(PAINEL_V6)
    p = p.drop(columns=[c for c in p.columns if c.startswith('cd_')])
    cd, n_fora = extrair(p)
    faltas = cd.isna().any(axis=1).mean()
    cd = cd.fillna(pd.read_parquet(DADOS / 'matriz_c4.parquet', columns=list(cd.columns)).median())
    out = pd.concat([p, cd], axis=1)
    out.to_parquet(DADOS / 'painel_c4.parquet', index=False)
    print(f'{len(out)} linhas, {out.ponto_id.nunique()} locais; {n_fora} linhas fora da grade; '
          f'linhas com falta em cd_*: {faltas:.2%}')


if __name__ == '__main__':
    main()
