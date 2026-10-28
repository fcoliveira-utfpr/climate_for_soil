"""Figuras da presentation.md: ganho de MEC de cada clima sobre o Köppen IPEF (relatórios v2 a v5).

Junta os resumos de validação (amostras reais, 0-30 cm; média e mínimo/máximo nas 3 repetições) dos
dois modelos (ranger validado e modelo do mapa) e dos três esquemas (V2 espacial, V3 temporal, V4
espaço-temporal). A família decenal (média móvel de 10 anos) é destacada: contínuo decenal do v2 (3
variáveis) em azul e temperatura decenal do v4 em azul claro; os demais ficam em cinza.

Saídas: relatorios/figuras/ganho_clima_barras.png, ganho_clima_mapa_calor.png e ganho_clima.csv

Uso: python figuras_apresentacao.py
"""
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.colors import LinearSegmentedColormap, TwoSlopeNorm

RAIZ = Path(__file__).resolve().parents[2]
FIG = Path(__file__).resolve().parents[1] / 'figuras'
REAIS = '0-30 cm, amostras reais'
DESTAQUE = {'Contínuo decenal (v2)': '#2a78d6', 'Temperatura decenal (v4)': '#86b6ef'}

# rótulo: (relatório, nome no resumo)
CENARIOS = {
    'Contínuo decenal (v2)': ('v2', 'cont_decenal'),
    'Contínuo selecionado (v2)': ('v2', 'cont_sel'),
    'Contínuo CHELSA estático (v2)': ('v2', 'cont_chelsa'),
    'CHELSA + decenal (v2)': ('v2', 'cont_ambos'),
    'Temperatura decenal (v4)': ('v4', 'cd_temperatura'),
    '39 variáveis decenais (v4)': ('v4', 'cd_todas'),
    'Holdridge Xavier (v3)': ('v3', 'holdridge_est'),
    'Thornthwaite CAD solo (v2)': ('v2', 'th_cadsolo'),
    'Holdridge CHELSA (v2)': ('v2', 'holdridge_eth'),
    'Zonas k10 (v2)': ('v2', 'zonas_k10'),
    'Köppen decenal (v3)': ('v3', 'koppen_dec'),
    'Köppen móvel 30 anos (v5)': ('v5', 'koppen_movel30'),
    'Sem clima (v2)': ('v2', 'sem_clima'),
}
MODELOS = {'ranger': 'Ranger (modelo validado)', 'mapa': 'Modelo do mapa (GEE)'}
ESQUEMAS = {'v2': 'V2 espacial', 'v3': 'V3 temporal', 'v4': 'V4 espaço-temporal'}

CINZA, TINTA, TINTA2, GRADE = '#b9b8b2', '#0b0b0b', '#52514e', '#e4e3df'


def carregar():
    v2 = RAIZ / 'climas' / 'analise_espaco_tempo' / 'resultados' / 'tabelas'
    partes = []
    for modelo, suf in (('ranger', ''), ('mapa', '_gee')):
        d = pd.read_csv(v2 / f'validacao_ganhos{suf}.csv')
        d = d[d.camadas == REAIS].rename(columns={'ganho_mec': 'ganho', 'ganho_mec_min': 'gmin', 'ganho_mec_max': 'gmax'})
        partes.append(d.assign(rel='v2', modelo=modelo))
    d = pd.read_csv(RAIZ / 'climas_tempo' / 'resultados' / 'tabelas' / 'cap3_resumo.csv')
    partes.append(d[d.recorte == REAIS].rename(columns={'ganho_vs_koppen': 'ganho', 'ganho_min': 'gmin',
                                                        'ganho_max': 'gmax'}).assign(rel='v3'))
    d = pd.read_csv(RAIZ / 'clima_decenal' / 'resultados' / 'tabelas' / 'cd_resumo.csv')
    partes.append(d[d.recorte == REAIS].rename(columns={'ganho_vs_koppen': 'ganho', 'gk_min': 'gmin',
                                                        'gk_max': 'gmax'}).assign(rel='v4'))
    d = pd.read_csv(RAIZ / 'climas' / 'koppen_movel30' / 'resultados' / 'tabelas' / 'movel30_resumo.csv')
    partes.append(d[d.recorte == REAIS].rename(columns={'ganho_vs_ipef': 'ganho', 'ganho_min': 'gmin',
                                                        'ganho_max': 'gmax'}).assign(rel='v5'))
    t = pd.concat(partes, ignore_index=True)
    linhas = []
    for rotulo, (rel, cen) in CENARIOS.items():
        x = t[(t.rel == rel) & (t.cenario == cen)]
        assert len(x) == 6, (rotulo, len(x))
        linhas.append(x.assign(rotulo=rotulo)[['rotulo', 'modelo', 'esquema', 'mec', 'ganho', 'gmin', 'gmax']])
    return pd.concat(linhas, ignore_index=True)


def estilo(ax):
    for lado in ('top', 'right', 'left'):
        ax.spines[lado].set_visible(False)
    ax.spines['bottom'].set_color(GRADE)
    ax.tick_params(colors=TINTA2, labelsize=9, length=0)
    ax.grid(axis='x', color=GRADE, lw=0.8)
    ax.set_axisbelow(True)


def barras(g):
    ordem = g.groupby('rotulo').ganho.mean().sort_values().index.tolist()     # melhor média no topo
    y = np.arange(len(ordem))
    lim = (min(g.gmin.min(), g.ganho.min()) - 0.004, max(g.gmax.max(), g.ganho.max()) + 0.012)
    fig, axs = plt.subplots(2, 3, figsize=(15, 9.2), sharey=True, sharex=True)
    for i, (modelo, nome_m) in enumerate(MODELOS.items()):
        for j, (esq, nome_e) in enumerate(ESQUEMAS.items()):
            ax = axs[i, j]
            estilo(ax)
            x = g[(g.modelo == modelo) & (g.esquema == esq)].set_index('rotulo').loc[ordem]
            cores = [DESTAQUE.get(r, CINZA) for r in ordem]
            ax.barh(y, x.ganho, height=0.68, color=cores, edgecolor='white', linewidth=1)
            ax.hlines(y, x.gmin, x.gmax, color=TINTA2, lw=1)
            ax.axvline(0, color=TINTA, lw=1)
            for r in DESTAQUE:
                k = ordem.index(r)
                v = x.ganho.iloc[k]
                ax.text(max(v, x.gmax.iloc[k]) + 0.002, k, f'{v:+.3f}', va='center', ha='left', fontsize=10,
                        fontweight='bold', color=TINTA)
            ax.set_xlim(*lim)
            if i == 0:
                ax.set_title(nome_e, fontsize=12, color=TINTA, pad=10)
            if j == 0:
                ax.set_ylabel(nome_m, fontsize=11, color=TINTA, labelpad=10)
            if i == 1:
                ax.set_xlabel('ganho de MEC sobre o Köppen IPEF', fontsize=9, color=TINTA2)
    axs[0, 0].set_yticks(y, ordem)
    for lab in axs[0, 0].get_yticklabels() + axs[1, 0].get_yticklabels():
        if lab.get_text() in DESTAQUE:
            lab.set_fontweight('bold')
            lab.set_color(TINTA)
    fig.suptitle('Quanto cada clima melhora o modelo de SOC em relação ao Köppen IPEF', fontsize=14,
                 color=TINTA, x=0.01, ha='left', y=0.995)
    fig.text(0.01, 0.955, 'MEC fora da amostra, amostras reais de 0-30 cm; barra = média das 3 repetições, '
             'traço = mínimo a máximo. À direita do zero, melhor que o Köppen.', fontsize=10, color=TINTA2)
    fig.tight_layout(rect=(0, 0, 1, 0.945))
    fig.savefig(FIG / 'ganho_clima_barras.png', dpi=150)
    plt.close(fig)


def mapa_calor(g):
    g = g.assign(col=g.modelo.map({'ranger': 'Ranger', 'mapa': 'Mapa'}) + '\n' + g.esquema.str.upper())
    cols = [f'{m}\n{e}' for m in ('Ranger', 'Mapa') for e in ('V2', 'V3', 'V4')]
    v = g.pivot(index='rotulo', columns='col', values='ganho')[cols]
    consist = g.assign(c=(np.sign(g.gmin) == np.sign(g.gmax)) & (g.gmin != 0)).pivot(
        index='rotulo', columns='col', values='c')[cols]
    vence = (v > 0).sum(axis=1)
    v = v.loc[v.mean(axis=1).sort_values(ascending=False).index]
    consist = consist.loc[v.index]
    cmap = LinearSegmentedColormap.from_list('div', ['#c23b3a', '#f0efec', '#1c5cab'])
    m = np.abs(v.values).max()
    fig, ax = plt.subplots(figsize=(10.5, 7.6))
    ax.imshow(v.values, cmap=cmap, norm=TwoSlopeNorm(0, -m, m), aspect='auto')
    for a in range(v.shape[0]):
        for b in range(v.shape[1]):
            val = v.values[a, b]
            forte = abs(val) > 0.55 * m
            txt = f'{val:+.3f}' + ('*' if consist.values[a, b] else '')
            ax.text(b, a, txt, ha='center', va='center', fontsize=9.5, color='white' if forte else TINTA,
                    fontweight='bold' if v.index[a] in DESTAQUE else 'normal')
    ax.set_xticks(range(len(cols)), cols, fontsize=10, color=TINTA)
    ax.set_yticks(range(len(v)), [f'{r}  ({vence[r]}/6)' for r in v.index], fontsize=10, color=TINTA)
    for r in DESTAQUE:
        k = list(v.index).index(r)
        ax.add_patch(plt.Rectangle((-0.5, k - 0.5), len(cols), 1, fill=False, ec=TINTA, lw=2))
    ax.axvline(2.5, color='white', lw=4)
    ax.tick_params(length=0)
    ax.xaxis.tick_top()
    for s in ax.spines.values():
        s.set_visible(False)
    ax.set_title('Ganho de MEC sobre o Köppen IPEF (azul = melhor, vermelho = pior)', fontsize=13,
                 color=TINTA, loc='left', pad=48)
    fig.text(0.01, 0.015, '* mesmo sinal nas 3 repetições.  (n/6) = em quantas das 6 combinações '
             'modelo × esquema o clima ganha do Köppen.  Amostras reais, 0-30 cm.', fontsize=9, color=TINTA2)
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    fig.savefig(FIG / 'ganho_clima_mapa_calor.png', dpi=150)
    plt.close(fig)


def main():
    FIG.mkdir(parents=True, exist_ok=True)
    g = carregar()
    g.to_csv(FIG / 'ganho_clima.csv', index=False, float_format='%.4f')
    barras(g)
    mapa_calor(g)
    print(g[g.rotulo.isin(list(DESTAQUE))].round(3).to_string(index=False))


if __name__ == '__main__':
    main()
