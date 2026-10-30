"""Etapa 4: variáveis do Xavier v3.2.4 nos pontos de SOC e cenários do C4.

Parte da matriz do relatório v6 (clima_final/dados/matriz_final.parquet: trainingFinal reconstruída, partição
nova das dobras V2/V4 com semente 2027) e troca as variáveis cd_* (Xavier v3.2.2 do v4) pelas calculadas aqui
com a v3.2.4 (variaveis.py), no ano de cada linha e no pixel do Xavier do ponto (fora da grade -> pixel válido
mais próximo; faltas -> mediana). O CDD decenal novo entra como cd_cdd.

Só os cenários que dependem do Xavier são refeitos (temperatura e conjunto curto); as referências (Köppen IPEF,
sem clima e contínuo decenal do GT de clima) não mudam e as predições delas são as do v6, nas mesmas dobras e
sementes, o que deixa a comparação v6 x C4 pareada.

Saídas: C4/dados/matriz_c4.parquet (restrita), codigo/cenarios_c4.json e resultados/tabelas/variaveis_c4.csv
(comparação das variáveis do conjunto curto entre as duas versões do Xavier, nas amostras)

Uso: python pontos.py
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / 'climas_tempo' / 'codigo'))
from cenarios_tempo import indices_pixel  # noqa: E402

DADOS = RAIZ / 'C4' / 'dados'
TAB = RAIZ / 'C4' / 'resultados' / 'tabelas'
MATRIZ_V6 = RAIZ / 'clima_final' / 'dados' / 'matriz_final.parquet'
CENARIOS_V6 = RAIZ / 'clima_final' / 'codigo' / 'cenarios_final.json'
TEMPERATURA = ['cd_t_media', 'cd_tmax_media', 'cd_tmin_media', 'cd_t_mes_quente', 'cd_t_mes_frio', 'cd_amplitude',
               'cd_biotemp']


def extrair(df, anos_col='year'):
    """Variáveis cd_* do ano de cada linha (DataFrame com longitude, latitude e year)."""
    g = np.load(RAIZ / 'climas_tempo' / 'dados' / 'grade.npz')
    lin, col, n_fora = indices_pixel(df.longitude.to_numpy(), df.latitude.to_numpy(), g)
    anos = df[anos_col].to_numpy()
    vals = {}
    for ano in np.unique(anos):
        d = np.load(DADOS / 'variaveis' / f'{ano}.npz')
        sel = anos == ano
        for v in d.files:
            vals.setdefault(v, np.full(len(df), np.nan, np.float32))[sel] = d[v][lin[sel], col[sel]]
    return pd.DataFrame(vals, index=df.index), n_fora


def main():
    TAB.mkdir(parents=True, exist_ok=True)
    m = pd.read_parquet(MATRIZ_V6)
    antigo = m[TEMPERATURA + ['dec_cdd', 'cd_arm_csolo']].copy()
    cd, n_fora = extrair(m)
    faltas = cd.isna().mean()
    cd = cd.fillna(cd.median())
    m = pd.concat([m.drop(columns=[c for c in m.columns if c.startswith('cd_')]), cd], axis=1)
    m.to_parquet(DADOS / 'matriz_c4.parquet', index=False)

    v6 = json.loads(CENARIOS_V6.read_text(encoding='utf-8'))
    cenarios = {'temperatura': TEMPERATURA, 'curto': TEMPERATURA + ['cd_cdd', 'cd_arm_csolo']}
    Path(__file__).with_name('cenarios_c4.json').write_text(
        json.dumps({'base': v6['base'], 'cenarios': cenarios}, indent=1, ensure_ascii=False), encoding='utf-8')

    linhas = []
    for v_novo, v_antigo in [(c, c) for c in TEMPERATURA] + [('cd_cdd', 'dec_cdd'), ('cd_arm_csolo', 'cd_arm_csolo')]:
        a, b = m[v_novo].to_numpy(), antigo[v_antigo].to_numpy()
        linhas.append({'variavel': v_novo, 'media_v3_2_4': a.mean(), 'media_v3_2_2': b.mean(),
                       'dif_media': (a - b).mean(), 'r': np.corrcoef(a, b)[0, 1], 'faltas_pct': 100 * faltas[v_novo]})
    t = pd.DataFrame(linhas)
    t.to_csv(TAB / 'variaveis_c4.csv', index=False, float_format='%.4g')
    print(f'{len(m)} linhas; {n_fora} pontos fora da grade (vizinho mais próximo)')
    print(t.round(3).to_string(index=False))


if __name__ == '__main__':
    main()
