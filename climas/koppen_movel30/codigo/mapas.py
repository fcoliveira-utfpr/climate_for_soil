"""Etapa 3: mapas e conferências do Köppen móvel de 30 anos (reaproveita as funções do capítulo 3).

Figuras (climas/koppen_movel30/resultados/figuras/):
    koppen_movel30_anos.png     1985, 1991, 2000, 2010, 2021 e 2024
    mudancas_movel30.png        classe de 1985 x 2024 e número de trocas de classe ao longo de 1985-2024
    area_classes_movel30.png    área (%) de cada classe, ano a ano
    conferencia_chelsa.png      2021 (janela 1991-2020) x Köppen do CHELSA 1991-2020 (relatório v1)
Tabelas (climas/koppen_movel30/resultados/tabelas/):
    area_classes_anos.csv, janelas.csv (anos com dado por janela), mudancas.csv, conferencia_chelsa.csv

Área: pixels de 0,1° ponderados por cos(latitude).

Uso: python mapas.py
"""
import sys
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import rasterio
from matplotlib.colors import ListedColormap
from rasterio.enums import Resampling
from rasterio.warp import reproject

from agrometeorologiapy.classificacao_climatica import KOPPEN_CLASSES

RAIZ = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(RAIZ / 'climas_tempo' / 'codigo'))
import mapas as m3  # noqa: E402  (mapa, area_pct, PAL_KOPPEN)

DADOS = RAIZ / 'climas' / 'dados_koppen_movel30'
PASTA = Path(__file__).resolve().parents[1] / 'resultados'
FIG, TAB = PASTA / 'figuras', PASTA / 'tabelas'
CHELSA = RAIZ / 'climas' / 'dados_chelsa' / 'koppen' / 'Koppen_CHELSA_BR_1991_2020.tif'
ANOS_FIGURA = [1985, 1991, 2000, 2010, 2021, 2024]


def carregar():
    g, k = np.load(DADOS / 'grade.npz'), np.load(DADOS / 'koppen_movel30.npz')
    lon, lat = g['lon'], g['lat']
    ext = [lon.min() - 0.05, lon.max() + 0.05, lat.min() - 0.05, lat.max() + 0.05]
    peso = np.cos(np.radians(lat))
    return g, k, ext, peso


def figura_anos(k, ext, brasil):
    anos = list(k['anos'])
    fig, axs = plt.subplots(2, 3, figsize=(18, 14))
    presentes = set()
    for ax, ano in zip(axs.flat, ANOS_FIGURA):
        i = anos.index(ano)
        c = k['koppen'][i].astype(np.int64)
        nt, npr = k['n_anos_T'][i], k['n_anos_P'][i]
        nota = '' if nt == 30 and npr == 30 else f'\n(anos na janela: temperatura {nt}, chuva {npr})'
        cores = m3.mapa(ax, c, KOPPEN_CLASSES, m3.PAL_KOPPEN, ext, f'{ano}: normal {ano - 30}-{ano - 1}{nota}',
                        brasil)
        presentes |= set(np.unique(c[c > 0]).tolist())
    fig.legend(handles=[mpatches.Patch(color=cores[c - 1], label=KOPPEN_CLASSES[c]) for c in sorted(presentes)],
               loc='lower center', ncol=len(presentes), fontsize=9, frameon=False)
    fig.suptitle('Köppen-Geiger por média móvel de 30 anos (Xavier, BR-DWGD)', fontsize=14)
    fig.tight_layout(rect=(0, 0.04, 1, 0.97), h_pad=3)
    fig.savefig(FIG / 'koppen_movel30_anos.png', dpi=120)
    plt.close(fig)


def figura_mudancas(k, ext, brasil, peso):
    K = k['koppen'].astype(np.int64)
    a, b = K[0], K[-1]
    ok = (a > 0) & (b > 0)
    mudou = ok & (a != b)
    trocas = np.where(ok, (np.diff(K, axis=0) != 0).sum(axis=0), -1)
    pct = 100 * peso[mudou].sum() / peso[ok].sum()
    fig, axs = plt.subplots(1, 2, figsize=(14, 6.5))
    img = np.where(ok, np.where(mudou, 2, 1), 0)
    axs[0].imshow(np.ma.masked_where(img == 0, img), cmap=ListedColormap(['#e0e0e0', '#d7301f']), extent=ext,
                  interpolation='nearest', vmin=1, vmax=2)
    axs[0].set_title(f'Classe de 2024 diferente da de 1985 (vermelho)\n{pct:.1f}% da área', fontsize=11)
    im = axs[1].imshow(np.ma.masked_where(trocas < 1, trocas), cmap='magma_r', extent=ext, interpolation='nearest',
                       vmin=1, vmax=max(2, int(trocas.max())))
    axs[1].set_title('Número de trocas de classe entre anos consecutivos, 1985-2024\n(cinza = nunca trocou)',
                     fontsize=11)
    axs[1].imshow(np.ma.masked_where(trocas != 0, np.ones_like(trocas)), cmap=ListedColormap(['#e0e0e0']),
                  extent=ext, interpolation='nearest')
    fig.colorbar(im, ax=axs[1], shrink=0.7, label='trocas')
    for ax in axs:
        ax.contour(brasil.astype(float), levels=[0.5], colors='k', linewidths=0.4, extent=ext, origin='upper')
        ax.set_xticks([]), ax.set_yticks([])
    fig.tight_layout()
    fig.savefig(FIG / 'mudancas_movel30.png', dpi=120)
    plt.close(fig)
    leg = KOPPEN_CLASSES
    trans = pd.crosstab(pd.Series(a[mudou]).map(leg), pd.Series(b[mudou]).map(leg), values=peso[mudou],
                        aggfunc='sum')
    top = (100 * trans.stack() / peso[ok].sum()).sort_values(ascending=False).head(8)
    linhas = [{'transicao': f'{i} -> {j}', 'area_pct': v} for (i, j), v in top.items()]
    por_ano = [{'ano': int(k['anos'][i + 1]), 'area_mudou_pct': 100 * peso[ok & (K[i + 1] != K[i])].sum()
                / peso[ok].sum()} for i in range(len(K) - 1)]
    return pct, pd.DataFrame(linhas), pd.DataFrame(por_ano)


def figura_area(k, peso):
    serie = pd.DataFrame([m3.area_pct(c.astype(np.int64), peso, KOPPEN_CLASSES) for c in k['koppen']],
                         index=k['anos']).fillna(0)
    serie.index.name = 'ano'
    serie.to_csv(TAB / 'area_classes_anos.csv', float_format='%.3f')
    principais = serie.loc[:, serie.max() >= 1]
    fig, ax = plt.subplots(figsize=(12, 6))
    for col in principais:
        c = [c for c, v in KOPPEN_CLASSES.items() if v == col][0]
        ax.plot(principais.index, principais[col], '-', color=m3.PAL_KOPPEN[c - 1], lw=2.2, label=col)
    ax.axvline(2020.5, color='0.5', ls=':', lw=1)
    ax.text(2020.7, ax.get_ylim()[1] * 0.95, 'janelas com\ntemperatura\nincompleta', fontsize=8, color='0.4',
            va='top')
    ax.set_xlabel('ano (normal dos 30 anos anteriores)'), ax.set_ylabel('% da área do Brasil')
    ax.set_title('Área de cada classe de Köppen, média móvel de 30 anos (classes com ≥ 1% em algum ano)')
    ax.legend(ncol=5, fontsize=9)
    fig.tight_layout()
    fig.savefig(FIG / 'area_classes_movel30.png', dpi=130)
    plt.close(fig)
    return serie


def conferencia(k, g, peso, ext):
    """2021 (janela 1991-2020) x Köppen do CHELSA 1991-2020 do relatório v1, reamostrado para 0,1° pela moda."""
    h, w = g['brasil'].shape
    t = g['transf']
    transf = rasterio.Affine(*t)
    with rasterio.open(CHELSA) as r:
        src = r.read(1).astype(np.float32)
        src = np.where(np.isfinite(src) & (src > 0), src, 0).astype(np.uint16)
        dst = np.zeros((h, w), np.uint16)
        reproject(src, dst, src_transform=r.transform, src_crs=r.crs, dst_transform=transf, dst_crs='EPSG:4326',
                  resampling=Resampling.mode, src_nodata=0, dst_nodata=0)
    x = k['koppen'][list(k['anos']).index(2021)].astype(np.uint16)
    ok = (x > 0) & (dst > 0)
    igual = 100 * peso[ok & (x == dst)].sum() / peso[ok].sum()
    fig, axs = plt.subplots(1, 2, figsize=(14, 6.5))
    m3.mapa(axs[0], dst.astype(np.int64), KOPPEN_CLASSES, m3.PAL_KOPPEN, ext, 'CHELSA 1991-2020 (relatório v1)',
            g['brasil'])
    m3.mapa(axs[1], x.astype(np.int64), KOPPEN_CLASSES, m3.PAL_KOPPEN, ext,
            f'Xavier, janela 1991-2020 (ano 2021): {igual:.0f}% da área igual', g['brasil'])
    fig.tight_layout()
    fig.savefig(FIG / 'conferencia_chelsa.png', dpi=120)
    plt.close(fig)
    return pd.DataFrame([{'comparacao': 'Xavier 2021 (1991-2020) x CHELSA 1991-2020', 'concordancia_area_pct': igual,
                          'pixels': int(ok.sum())}])


def main():
    FIG.mkdir(parents=True, exist_ok=True), TAB.mkdir(parents=True, exist_ok=True)
    g, k, ext, peso = carregar()
    brasil = g['brasil']
    pd.DataFrame({'ano': k['anos'], 'janela_ini': k['anos'] - 30, 'janela_fim': k['anos'] - 1,
                  'anos_com_T': k['n_anos_T'], 'anos_com_chuva': k['n_anos_P']}).to_csv(TAB / 'janelas.csv',
                                                                                       index=False)
    figura_anos(k, ext, brasil)
    pct, trans, por_ano = figura_mudancas(k, ext, brasil, peso)
    figura_area(k, peso)
    conf = conferencia(k, g, peso, ext)
    resumo = pd.concat([pd.DataFrame([{'transicao': 'TOTAL (2024 diferente de 1985)', 'area_pct': pct}]), trans])
    resumo.to_csv(TAB / 'mudancas.csv', index=False, float_format='%.3f')
    por_ano.to_csv(TAB / 'mudancas_por_ano.csv', index=False, float_format='%.3f')
    conf.to_csv(TAB / 'conferencia_chelsa.csv', index=False, float_format='%.2f')
    print(resumo.round(2).to_string(index=False))
    print(conf.round(1).to_string(index=False))
    print('maior troca anual:', por_ano.sort_values('area_mudou_pct').tail(3).round(2).to_string(index=False))


if __name__ == '__main__':
    main()
