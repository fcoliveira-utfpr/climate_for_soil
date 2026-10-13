"""Etapa 5a: cenários da avaliação das variáveis decenais e matriz de correlação entre elas.

Cenários (as 118 covariáveis da produção + o grupo de clima decenal), para validacao.R:
    cd_temperatura  7 variáveis de temperatura
    cd_chuva        5 de chuva + o CDD decenal
    cd_energia      Rs, Rn, ETo, UR, DPV, vento e as razões ETo/P, P - ETo
    cd_bh_c100      balanço hídrico com CAD 100 mm (9)
    cd_bh_csolo     balanço hídrico com a CAD do solo (9)
    cont_ambos      todas as 39 (o nome é o que validacao.R usa como candidatas da seleção aninhada)
    cont_sel        as 39 com seleção aninhada em cada dobra (pares |r de Spearman| > 0,9, fica a mais
                    importante; selecao_continuas.R)
Referências (relatório v2): Köppen IPEF e contínuo decenal (temperatura, chuva e CDD do GT de clima).

Saídas: clima_decenal/codigo/cenarios_cd.json, resultados/figuras/correlacao_cd.png,
resultados/tabelas/correlacao_cd.csv e pares_redundantes_cd.csv

Uso: python cenarios_cd.py
"""
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

RAIZ = Path(__file__).resolve().parents[2]
DADOS = RAIZ / 'clima_decenal' / 'dados'
RES = RAIZ / 'clima_decenal' / 'resultados'
CENARIOS_V2 = RAIZ / 'climas' / 'analise_espaco_tempo' / 'codigo' / 'cenarios.json'

GRUPOS = {
    'cd_temperatura': ['cd_t_media', 'cd_tmax_media', 'cd_tmin_media', 'cd_t_mes_quente', 'cd_t_mes_frio',
                       'cd_amplitude', 'cd_biotemp'],
    'cd_chuva': ['cd_p_anual', 'cd_p_mes_seco', 'cd_p_mes_chuvoso', 'cd_p_sazonalidade', 'cd_meses_secos',
                 'dec_cdd'],
    'cd_energia': ['cd_rs', 'cd_rn', 'cd_eto', 'cd_ur', 'cd_dpv', 'cd_u2', 'cd_eto_p', 'cd_p_menos_eto'],
    'cd_bh_c100': ['cd_def_c100', 'cd_exc_c100', 'cd_etr_c100', 'cd_etr_eto_c100', 'cd_ih_c100', 'cd_ia_c100',
                   'cd_im_c100', 'cd_meses_def_c100', 'cd_arm_c100'],
    'cd_bh_csolo': ['cd_def_csolo', 'cd_exc_csolo', 'cd_etr_csolo', 'cd_etr_eto_csolo', 'cd_ih_csolo',
                    'cd_ia_csolo', 'cd_im_csolo', 'cd_meses_def_csolo', 'cd_arm_csolo'],
}
TODAS = [v for g in GRUPOS.values() for v in g]


def main():
    meta = json.loads(CENARIOS_V2.read_text(encoding='utf-8'))
    cenarios = dict(GRUPOS, cont_ambos=TODAS, cont_sel=TODAS)
    (Path(__file__).with_name('cenarios_cd.json')).write_text(
        json.dumps({'base': meta['base'], 'cenarios': cenarios}, indent=1, ensure_ascii=False), encoding='utf-8')

    m = pd.read_parquet(DADOS / 'matriz_cd.parquet', columns=['id', 'PSEUDOROCK_index', 'PSEUDOSAND_index'] + TODAS)
    real = ~m.id.str.startswith('trep') & (m.PSEUDOROCK_index == 0) & (m.PSEUDOSAND_index == 0)
    c = m.loc[real, TODAS].corr(method='spearman')
    (RES / 'tabelas').mkdir(parents=True, exist_ok=True)
    (RES / 'figuras').mkdir(parents=True, exist_ok=True)
    c.to_csv(RES / 'tabelas' / 'correlacao_cd.csv', float_format='%.3f')
    pares = [(a, b, c.loc[a, b]) for i, a in enumerate(TODAS) for b in TODAS[i + 1:] if abs(c.loc[a, b]) > 0.9]
    pd.DataFrame(pares, columns=['var_a', 'var_b', 'r_spearman']).sort_values(
        'r_spearman', key=abs, ascending=False).to_csv(RES / 'tabelas' / 'pares_redundantes_cd.csv',
                                                       index=False, float_format='%.3f')
    fig, ax = plt.subplots(figsize=(13, 11))
    im = ax.imshow(c, cmap='RdBu_r', vmin=-1, vmax=1)
    ax.set_xticks(range(len(TODAS)), [v.replace('cd_', '') for v in TODAS], rotation=90, fontsize=7)
    ax.set_yticks(range(len(TODAS)), [v.replace('cd_', '') for v in TODAS], fontsize=7)
    lim = np.cumsum([len(g) for g in GRUPOS.values()])[:-1] - 0.5
    for x in lim:
        ax.axhline(x, color='k', lw=0.8), ax.axvline(x, color='k', lw=0.8)
    fig.colorbar(im, ax=ax, shrink=0.7, label='r de Spearman')
    ax.set_title('Correlação entre as variáveis decenais (amostras reais)')
    fig.tight_layout()
    fig.savefig(RES / 'figuras' / 'correlacao_cd.png', dpi=130)
    print(f'{len(TODAS)} variáveis; {len(pares)} pares com |r| > 0,9; cenários: {list(cenarios)}')


if __name__ == '__main__':
    main()
