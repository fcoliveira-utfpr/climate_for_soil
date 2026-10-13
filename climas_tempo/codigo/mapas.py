"""Etapa 3: mapas das classificações decenais do Xavier, como os do relatório v1 (§4), e tabelas de apoio.

Figuras (climas_tempo/resultados/figuras/):
    <sistema>_decadas.png          quatro décadas (1985-1994 ... 2015-2024), paletas e legendas do relatório v1
    mudancas_1985_2024.png         pixels que mudaram de classe entre 1985-1994 e 2015-2024
    area_classes_tempo.png         área (%) de cada classe principal em cada década
    conferencia_chelsa.png         Xavier 1991-2020 x CHELSA 1991-2020 (mapas do relatório v1)
Tabelas (climas_tempo/resultados/tabelas/): area_classes_decadas.csv, mudancas.csv, conferencia_chelsa.csv

Todas as classificações com filtro de moda 3 x 3 (classificar.py). Na conferência, os mapas do v1 só têm o
filtro no Holdridge; o k10 do Xavier (reajustado) é comparado ao do CHELSA após o melhor pareamento
de zonas.
Thornthwaite nas figuras: classe de umidade (L1); nas tabelas de mudança, também o L2 (umidade + subtipo).
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
from matplotlib.colors import BoundaryNorm, ListedColormap
from rasterio.enums import Resampling
from rasterio.warp import reproject

from agrometeorologiapy.classificacao_climatica import HOLDRIDGE_ZONAS_EN, KOPPEN_CLASSES, TH_UMIDADE

RAIZ = Path(__file__).resolve().parents[2]
DADOS = RAIZ / 'climas_tempo' / 'dados'
FIG = RAIZ / 'climas_tempo' / 'resultados' / 'figuras'
TAB = RAIZ / 'climas_tempo' / 'resultados' / 'tabelas'
CHELSA = RAIZ / 'climas' / 'dados_chelsa'

# Paletas do relatório v1 (climas/chelsa_climas_brasil: koppen_gee.py, holdridge_gee.py, thornthwaite.py)
PAL_KOPPEN = ["#0000FF", "#0078FF", "#46A0FF", "#96C8FF", "#F5A623", "#FFDA8C", "#FF0000", "#FF9696",
              "#C8FF50", "#64FF50", "#32C800", "#FFFF00", "#C8C800", "#969600", "#C8FFC8", "#96FF96",
              "#64C864", "#B4A0FA", "#8C78F0", "#6450E6", "#3C2CB4", "#E0C8FF", "#C8A0FF", "#B478FF",
              "#9650FF", "#D2D2FF", "#AAAAFF", "#8282FF", "#5A5AFF", "#B4B4B4", "#696969"]
# Holdridge: uma família de cores por faixa térmica (a paleta do relatório v1 repetia os azuis entre
# temperado quente e subtropical). Desertos e estepes em tons claros; florestas do seco ao pluvial.
PAL_HOLDRIDGE = [
    '#ffffff', '#e5e5e5',                                                    # 1-2 polar
    '#d9d9d9', '#bdbdbd', '#969696', '#737373',                              # 3-6 subpolar
    '#efedf5', '#dadaeb', '#bcbddc', '#9e9ac8', '#756bb1',                   # 7-11 boreal
    '#f7f4f9', '#e7e1ef', '#d4b9da', '#c994c7', '#df65b0', '#ce1256',        # 12-17 temperado frio
    '#f7fcb9', '#d9f0a3', '#addd8e', '#78c679', '#41ab5d', '#238443', '#005a32',   # 18-24 temperado quente
    '#f7fbff', '#deebf7', '#c6dbef', '#9ecae1', '#6baed6', '#3182bd', '#08519c',   # 25-31 subtropical
    '#fff5eb', '#fee6ce', '#fdd0a2', '#fdae6b', '#fd8d3c', '#d94801', '#8c2d04',   # 32-38 tropical
]
PAL_UMIDADE = ["#4575b4", "#abd9e9", "#a6d96a", "#fee08b", "#fec44f", "#fe9929", "#ec7014", "#cc4c02",
               "#8c2d04"]
PAL_K10 = [plt.cm.tab10(i) for i in range(10)]

SISTEMAS = {   # nome: (rótulo, legenda {código: texto}, paleta, função que extrai o código do mapa)
    'koppen': ('Köppen-Geiger', KOPPEN_CLASSES, PAL_KOPPEN, lambda x: x),
    'holdridge': ('Holdridge (ETP original)', {k: f'{k} {v}' for k, v in HOLDRIDGE_ZONAS_EN.items()},
                  PAL_HOLDRIDGE, lambda x: x),
    'thornthwaite': ('Thornthwaite, CAD do solo: classe de umidade', TH_UMIDADE, PAL_UMIDADE, lambda x: x // 100),
    'k10': ('Zonas climáticas k10 (reajustadas no Xavier)', {k: f'Zona {k}' for k in range(1, 11)},
            PAL_K10, lambda x: x),
}


def carregar():
    g = np.load(DADOS / 'grade.npz')
    return g, np.load(DADOS / 'classes_decadas.npz'), np.load(DADOS / 'classes_1991_2020.npz')


def area_pct(cls, peso, legenda):
    ok = cls > 0
    tot = peso[ok].sum()
    return {legenda.get(int(c), str(c)): 100 * peso[cls == c].sum() / tot for c in np.unique(cls[ok])}


def mapa(ax, cls, legenda, paleta, ext, titulo, brasil):
    cores = list(paleta) + ['#ffffff'] * (max(legenda) - len(paleta))
    cmap = ListedColormap(cores[:max(legenda)])
    norm = BoundaryNorm(np.arange(0.5, max(legenda) + 1.5), cmap.N)
    ax.imshow(np.ma.masked_where(cls == 0, cls), cmap=cmap, norm=norm, extent=ext, interpolation='nearest')
    ax.contour(brasil.astype(float), levels=[0.5], colors='k', linewidths=0.4, extent=ext, origin='upper')
    ax.set_title(titulo, fontsize=10)
    ax.set_xticks([]), ax.set_yticks([])
    return cores


def figura_decadas(nome, dec, ext, brasil):
    rotulo, leg, pal, cod = SISTEMAS[nome]
    fig, axs = plt.subplots(2, 2, figsize=(13, 12.5))
    presentes = set()
    for ax, cls, (ini, fim), nt in zip(axs.flat, dec[nome], dec['decadas'], dec['n_anos_T']):
        c = cod(cls)
        nota = '' if nt == 10 else f' (temperatura: {nt}-{nt + 1} anos)'
        cores = mapa(ax, c, leg, pal, ext, f'{ini}-{fim}{nota}', brasil)
        presentes |= set(np.unique(c[c > 0]).tolist())
    fig.legend(handles=[mpatches.Patch(color=cores[k - 1], label=leg[k]) for k in sorted(presentes)],
               loc='lower center', ncol=min(6, len(presentes)), fontsize=8, frameon=False)
    fig.suptitle(f'{rotulo}: normais decenais do Xavier (BR-DWGD)', fontsize=13)
    fig.tight_layout(rect=(0, 0.08 if len(presentes) > 12 else 0.05, 1, 0.97))
    fig.savefig(FIG / f'{nome}_decadas.png', dpi=130)
    plt.close(fig)


def figura_mudancas(dec, ext, brasil, peso):
    fig, axs = plt.subplots(1, 4, figsize=(20, 5.5))
    linhas = []
    for ax, (nome, (rotulo, leg, pal, cod)) in zip(axs, SISTEMAS.items()):
        a, b = cod(dec[nome][0]), cod(dec[nome][-1])
        ok = (a > 0) & (b > 0)
        mudou = ok & (a != b)
        pct = 100 * peso[mudou].sum() / peso[ok].sum()
        img = np.where(ok, np.where(mudou, 2, 1), 0)
        ax.imshow(np.ma.masked_where(img == 0, img), cmap=ListedColormap(['#e0e0e0', '#d7301f']),
                  extent=ext, interpolation='nearest', vmin=1, vmax=2)
        ax.contour(brasil.astype(float), levels=[0.5], colors='k', linewidths=0.4, extent=ext, origin='upper')
        ax.set_title(f'{rotulo.split(":")[0].split(" (")[0]}\n{pct:.1f}% da área mudou de classe', fontsize=10)
        ax.set_xticks([]), ax.set_yticks([])
        trans = pd.crosstab(pd.Series(a[mudou]).map(lambda k: leg.get(int(k), k)),
                            pd.Series(b[mudou]).map(lambda k: leg.get(int(k), k)),
                            values=peso[mudou], aggfunc='sum')
        top = trans.stack().sort_values(ascending=False).head(5)
        linhas.append({'sistema': nome, 'area_mudou_pct': pct,
                       'principais_transicoes': '; '.join(f'{i} -> {j}' for (i, j) in top.index)})
        if nome == 'thornthwaite':
            a2, b2 = dec[nome][0], dec[nome][-1]
            ok2 = (a2 > 0) & (b2 > 0)
            linhas.append({'sistema': 'thornthwaite_L2', 'area_mudou_pct':
                           100 * peso[ok2 & (a2 != b2)].sum() / peso[ok2].sum(), 'principais_transicoes': ''})
    fig.suptitle('Mudança de classe entre 1985-1994 e 2015-2024 (vermelho = mudou)', fontsize=13)
    fig.tight_layout(rect=(0, 0, 1, 0.92))
    fig.savefig(FIG / 'mudancas_1985_2024.png', dpi=130)
    plt.close(fig)
    return pd.DataFrame(linhas)


def figura_area_tempo(dec, peso):
    fig, axs = plt.subplots(2, 2, figsize=(15, 10))
    rot = [f'{a}-{b}' for a, b in dec['decadas']]
    for ax, (nome, (rotulo, leg, pal, cod)) in zip(axs.flat, SISTEMAS.items()):
        serie = pd.DataFrame([area_pct(cod(c), peso, leg) for c in dec[nome]], index=rot).fillna(0)
        serie = serie.loc[:, serie.max() >= 2]
        for col in serie:
            k = [k for k, v in leg.items() if v == col][0]
            ax.plot(serie.index, serie[col], 'o-', color=pal[k - 1] if k - 1 < len(pal) else None, lw=2,
                    label=col)
        ax.set_title(rotulo, fontsize=11)
        ax.set_ylabel('% da área')
        ax.legend(fontsize=7, ncol=2)
    fig.suptitle('Área das classes por década (2015-2024: temperatura até 07/2020, chuva até 2022)', fontsize=12)
    fig.tight_layout()
    fig.savefig(FIG / 'area_classes_tempo.png', dpi=130)
    plt.close(fig)


def conferencia(n91, g, peso, ext):
    """Xavier 1991-2020 x mapas do CHELSA 1991-2020 do relatório v1 (reamostrados para 0,1° pela moda)."""
    arqs = {'koppen': CHELSA / 'koppen' / 'Koppen_CHELSA_BR_1991_2020.tif',
            'holdridge': CHELSA / 'holdridge' / 'Holdridge_CHELSA_BR_1991_2020_ETH.tif',
            'thornthwaite': CHELSA / 'thornthwaite' / 'Thornthwaite_CHELSA_BR_1991_2020_CADsolo.tif',
            'k10': CHELSA / 'zonas' / 'zonas_climaticas_k10.tif'}
    h, w = g['brasil'].shape
    transf = rasterio.transform.from_origin(-73.89999847412109, 5.399999902564652, 0.1, 0.09999999586416751)
    linhas, pares = [], {}
    for nome, arq in arqs.items():
        with rasterio.open(arq) as r:
            src = r.read(1).astype(np.float32)
            src = np.where(np.isfinite(src) & (src > 0), src, 0).astype(np.uint16)
            dst = np.zeros((h, w), np.uint16)
            reproject(src, dst, src_transform=r.transform, src_crs=r.crs, dst_transform=transf,
                      dst_crs='EPSG:4326', resampling=Resampling.mode, src_nodata=0, dst_nodata=0)
        x = SISTEMAS[nome][3](n91[nome])
        ok = (x > 0) & (dst > 0)
        if nome == 'k10':
            # zonas reajustadas no Xavier têm numeração própria: compara após o melhor pareamento de zonas
            from scipy.optimize import linear_sum_assignment
            tab = pd.crosstab(pd.Series(dst[ok]), pd.Series(x[ok]), values=peso[ok], aggfunc='sum').fillna(0)
            lin, col = linear_sum_assignment(-tab.to_numpy())
            par = dict(zip(tab.columns[col], tab.index[lin]))
            x = np.vectorize(lambda z: par.get(z, 0))(x).astype(x.dtype)
        igual = 100 * peso[ok & (x == dst)].sum() / peso[ok].sum()
        linhas.append({'sistema': nome, 'concordancia_area_pct': igual, 'pixels_comparados': int(ok.sum())})
        pares[nome] = (dst, x)
    fig, axs = plt.subplots(2, 4, figsize=(20, 10))
    for j, (nome, (chelsa, xav)) in enumerate(pares.items()):
        rotulo, leg, pal, _ = SISTEMAS[nome]
        mapa(axs[0, j], chelsa.astype(np.int64), leg, pal, ext, f'{rotulo.split(":")[0]}\nCHELSA 1991-2020', g['brasil'])
        mapa(axs[1, j], xav.astype(np.int64), leg, pal, ext,
             f'Xavier 1991-2020 ({linhas[j]["concordancia_area_pct"]:.0f}% da área igual)', g['brasil'])
    fig.tight_layout()
    fig.savefig(FIG / 'conferencia_chelsa.png', dpi=120)
    plt.close(fig)
    return pd.DataFrame(linhas)


def main():
    FIG.mkdir(parents=True, exist_ok=True)
    TAB.mkdir(parents=True, exist_ok=True)
    g, dec, n91 = carregar()
    lon, lat, brasil = g['lon'], g['lat'], g['brasil']
    ext = (lon.min() - 0.05, lon.max() + 0.05, lat.min() - 0.05, lat.max() + 0.05)
    peso = np.cos(np.radians(lat)) * brasil
    for nome in SISTEMAS:
        figura_decadas(nome, dec, ext, brasil)
    area = []
    for nome, (rotulo, leg, pal, cod) in SISTEMAS.items():
        for cls, (ini, fim) in zip(dec[nome], dec['decadas']):
            for classe, pct in area_pct(cod(cls), peso, leg).items():
                area.append({'sistema': nome, 'decada': f'{ini}-{fim}', 'classe': classe, 'area_pct': pct})
    pd.DataFrame(area).to_csv(TAB / 'area_classes_decadas.csv', index=False, float_format='%.3f')
    mud = figura_mudancas(dec, ext, brasil, peso)
    mud.to_csv(TAB / 'mudancas.csv', index=False, float_format='%.2f')
    figura_area_tempo(dec, peso)
    conf = conferencia(n91, g, peso, ext)
    conf.to_csv(TAB / 'conferencia_chelsa.csv', index=False, float_format='%.2f')
    pd.set_option('display.width', 200, 'display.max_colwidth', 120)
    print(mud.to_string(index=False))
    print(conf.to_string(index=False))


if __name__ == '__main__':
    main()
