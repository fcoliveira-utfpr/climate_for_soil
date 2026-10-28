"""Figura do capítulo 6: ganho de MEC de cada cenário sobre o Köppen IPEF nas partições novas (amostras reais,
0-30 cm; barra = média das 3 repetições, traço = mínimo a máximo), com o conjunto curto em destaque.

Saída: resultados/figuras/ganhos_final.png

Uso: python figura_ganhos.py      (depois de metricas_final.py)
"""
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

PASTA = Path(__file__).resolve().parents[1] / 'resultados'
ROTULOS = {'curto': 'Conjunto curto\n(temperatura + CDD + ARM)', 'temperatura': 'Temperatura decenal',
           'hibrido_curto': 'Híbrido curto', 'hibrido': 'Híbrido\n(temperatura + hídrico estático)',
           'cont_decenal': 'Contínuo decenal (v2)', 'sem_clima': 'Sem clima'}
CORES = {'curto': '#eb6834', 'temperatura': '#1baf7a', 'cont_decenal': '#2a78d6'}
MODELOS = {'ranger': 'Ranger (modelo validado)', 'mapa': 'Modelo do mapa (GEE)'}
ESQUEMAS = {'v2': 'V2 espacial', 'v3': 'V3 temporal', 'v4': 'V4 espaço-temporal'}
CINZA, TINTA, TINTA2, GRADE = '#b9b8b2', '#0b0b0b', '#52514e', '#e4e3df'


def main():
    r = pd.read_csv(PASTA / 'tabelas' / 'final_resumo.csv')
    r = r[(r.recorte == '0-30 cm, amostras reais') & r.cenario.isin(ROTULOS)]
    ordem = list(ROTULOS)[::-1]
    y = np.arange(len(ordem))
    fig, axs = plt.subplots(2, 3, figsize=(15, 7.6), sharey=True, sharex=True)
    for i, (modelo, nome_m) in enumerate(MODELOS.items()):
        for j, (esq, nome_e) in enumerate(ESQUEMAS.items()):
            ax = axs[i, j]
            x = r[(r.modelo == modelo) & (r.esquema == esq)].set_index('cenario').loc[ordem]
            ax.barh(y, x.ganho_koppen, height=0.66, color=[CORES.get(c, CINZA) for c in ordem], edgecolor='white')
            ax.hlines(y, x.min_koppen, x.max_koppen, color=TINTA2, lw=1)
            ax.axvline(0, color=TINTA, lw=1)
            for k, c in enumerate(ordem):
                if c in CORES:
                    ax.text(max(x.ganho_koppen[c], x.max_koppen[c]) + 0.0015, k, f'{x.ganho_koppen[c]:+.3f}',
                            va='center', fontsize=9.5, fontweight='bold' if c == 'curto' else 'normal', color=TINTA)
            for lado in ('top', 'right', 'left'):
                ax.spines[lado].set_visible(False)
            ax.spines['bottom'].set_color(GRADE)
            ax.tick_params(colors=TINTA2, labelsize=9, length=0)
            ax.grid(axis='x', color=GRADE, lw=0.8)
            ax.set_axisbelow(True)
            ax.set_xlim(-0.012, 0.047)
            if i == 0:
                ax.set_title(nome_e, fontsize=12, color=TINTA, pad=8)
            if j == 0:
                ax.set_ylabel(nome_m, fontsize=11, color=TINTA, labelpad=8)
            if i == 1:
                ax.set_xlabel('ganho de MEC sobre o Köppen IPEF', fontsize=9, color=TINTA2)
    axs[0, 0].set_yticks(y, [ROTULOS[c] for c in ordem])
    for ax in axs[:, 0]:
        for lab in ax.get_yticklabels():
            if lab.get_text().startswith('Conjunto curto'):
                lab.set_fontweight('bold')
    fig.suptitle('Validação em partições novas: ganho de cada conjunto de clima sobre o Köppen IPEF', fontsize=14,
                 color=TINTA, x=0.01, ha='left')
    fig.text(0.01, 0.93, 'Amostras reais de 0-30 cm; barra = média das 3 repetições, traço = mínimo a máximo.',
             fontsize=10, color=TINTA2)
    fig.tight_layout(rect=(0, 0, 1, 0.92))
    fig.savefig(PASTA / 'figuras' / 'ganhos_final.png', dpi=150)
    plt.close(fig)


if __name__ == '__main__':
    main()
