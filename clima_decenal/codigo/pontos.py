"""Etapa 4: variáveis decenais (média móvel de 10 anos) nos pontos de SOC.

Parte da matriz do relatório v2 (climas/dados_espaco_tempo/matriz_cenarios.parquet = trainingFinal, com as
covariáveis da produção, as dobras V2/V3/V4 e o CDD decenal dec_cdd) e acrescenta as variáveis cd_* do ano de
cada linha (variaveis.py: média dos 10 anos anteriores), no pixel do Xavier do ponto (ponto do litoral fora da
grade -> pixel válido mais próximo, como no capítulo 3). Valores ainda faltantes são preenchidos com a mediana
da variável.

Saída: clima_decenal/dados/matriz_cd.parquet (restrita) e clima_decenal/resultados/tabelas/variaveis_cd.csv
(resumo de cada variável nas amostras)

Uso: python pontos.py
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / 'climas_tempo' / 'codigo'))
from cenarios_tempo import indices_pixel  # noqa: E402

DADOS = RAIZ / 'clima_decenal' / 'dados'
TAB = RAIZ / 'clima_decenal' / 'resultados' / 'tabelas'
MATRIZ_V2 = RAIZ / 'climas' / 'dados_espaco_tempo' / 'matriz_cenarios.parquet'


def main():
    g = np.load(RAIZ / 'climas_tempo' / 'dados' / 'grade.npz')
    m = pd.read_parquet(MATRIZ_V2)
    lin, col, n_fora = indices_pixel(m.longitude.to_numpy(), m.latitude.to_numpy(), g)
    anos = m.year.to_numpy()
    vals = {}
    for ano in np.unique(anos):
        d = np.load(DADOS / 'variaveis' / f'{ano}.npz')
        sel = anos == ano
        for v in d.files:
            vals.setdefault(v, np.full(len(m), np.nan, np.float32))[sel] = d[v][lin[sel], col[sel]]
    cd = pd.DataFrame(vals)
    faltas = cd.isna().mean()
    cd = cd.fillna(cd.median())
    out = pd.concat([m, cd], axis=1)
    out.to_parquet(DADOS / 'matriz_cd.parquet', index=False)
    TAB.mkdir(parents=True, exist_ok=True)
    resumo = cd.describe().T[['mean', 'std', 'min', '50%', 'max']].assign(faltas_pct=100 * faltas)
    resumo.to_csv(TAB / 'variaveis_cd.csv', float_format='%.4g')
    print(f'{len(m)} linhas, {cd.shape[1]} variáveis cd_; {n_fora} pontos fora da grade (vizinho mais próximo)')
    print(resumo.round(2).to_string())


if __name__ == '__main__':
    main()
