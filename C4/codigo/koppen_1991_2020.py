"""Köppen-Geiger do Xavier v3.2.4 com a normal 1991-2020, em GeoTIFF para subir no GEE.

Normal mensal de 1991 a 2020 (30 anos completos de todas as variáveis na v3.2.4; na v3.2.2 do capítulo 3 a
temperatura ia só até 07/2020): temperatura média mensal = média de (Tmax + Tmin)/2 diários, chuva mensal =
soma (baixar_xavier.py). Classificação com classificacao_koppen_grade da agrometeorologiapy (a mesma dos
capítulos 3 e 5, validada contra o Köppen do relatório v1) e filtro de moda 3 x 3 (moda3x3 do capítulo 3).

Saídas (em C4/resultados/koppen_xavier_1991_2020/):
    koppen_xavier_1991_2020.tif   uint8, EPSG:4326, grade do Xavier (0,1°, 391 x 393), nodata 0;
                                  banda 1 'koppen' (com moda 3 x 3), banda 2 'koppen_sem_filtro'
    legenda.csv                   id, classe, cor, área no Brasil (%) e pixels
    visualizar_gee.js             paleta e legenda para o Code Editor
    koppen_xavier_1991_2020.png   prévia
    conferencia.csv               concordância com o Köppen do CHELSA 1991-2020 (v1) e com o do capítulo 3

Uso: python koppen_1991_2020.py
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
from rasterio.transform import Affine
from rasterio.warp import reproject

from agrometeorologiapy.classificacao_climatica import KOPPEN_CLASSES, classificacao_koppen_grade

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / 'climas_tempo' / 'codigo'))
from classificar import moda3x3  # noqa: E402
from mapas import PAL_KOPPEN  # noqa: E402

MENSAL = RAIZ / 'C4' / 'dados' / 'xavier_mensal'
SAIDA = RAIZ / 'C4' / 'resultados' / 'koppen_xavier_1991_2020'
CHELSA = RAIZ / 'climas' / 'dados_chelsa' / 'koppen' / 'Koppen_CHELSA_BR_1991_2020.tif'
CAP3 = RAIZ / 'climas_tempo' / 'dados' / 'classes_1991_2020.npz'
ANOS = range(1991, 2021)
# grade do BR-DWGD no GEE (a mesma do download)
TRANSF = Affine(0.1, 0, -73.89999847412109, 0, -0.09999999586416751, 5.399999902564652)
H, W = 393, 391


def normal():
    T, P = [], []
    for a in ANOS:
        d = np.load(MENSAL / f'{a}.npz')
        T.append((d['Tmax'] + d['Tmin']) / 2)
        P.append(d['P'])
    T, P = np.stack(T), np.stack(P)
    assert np.isfinite(P).sum(0).min(axis=0)[np.isfinite(P[0, 0])].min() == len(ANOS)
    return T.mean(0), P.mean(0)


def concordancia(a, b):
    ok = (a > 0) & (b > 0)
    return 100 * (a[ok] == b[ok]).mean(), int(ok.sum())


def main():
    SAIDA.mkdir(parents=True, exist_ok=True)
    T, P = normal()
    lat = TRANSF.f + TRANSF.e * (np.arange(H) + 0.5)
    lat = np.repeat(lat[:, None], W, axis=1)
    brasil = np.isfinite(T).all(0) & np.isfinite(P).all(0)
    bruto = classificacao_koppen_grade(np.where(brasil, T, np.nan), np.where(brasil, P, np.nan), lat)['id']
    bruto = np.where(brasil, bruto, 0).astype(np.uint8)
    filtrado = moda3x3(bruto, brasil).astype(np.uint8)

    perfil = {'driver': 'GTiff', 'height': H, 'width': W, 'count': 2, 'dtype': 'uint8', 'crs': 'EPSG:4326',
              'transform': TRANSF, 'nodata': 0, 'compress': 'deflate'}
    with rasterio.open(SAIDA / 'koppen_xavier_1991_2020.tif', 'w', **perfil) as r:
        r.write(filtrado, 1)
        r.write(bruto, 2)
        r.set_band_description(1, 'koppen')
        r.set_band_description(2, 'koppen_sem_filtro')
        r.update_tags(fonte='Xavier et al. (2022) BR-DWGD v3.2.4, normal 1991-2020',
                      metodo='agrometeorologiapy classificacao_koppen_grade; banda 1 com moda 3x3',
                      classes='; '.join(f'{k}={v}' for k, v in KOPPEN_CLASSES.items()))

    # legenda (área ponderada pelo cosseno da latitude)
    peso = np.cos(np.deg2rad(lat)) * brasil
    ids = [int(k) for k in np.unique(filtrado[filtrado > 0])]
    leg = pd.DataFrame([{'id': k, 'classe': KOPPEN_CLASSES[k], 'cor': PAL_KOPPEN[k - 1],
                         'area_pct': 100 * peso[filtrado == k].sum() / peso.sum(),
                         'pixels': int((filtrado == k).sum())} for k in ids])
    leg.to_csv(SAIDA / 'legenda.csv', index=False, float_format='%.2f')

    js = ["// Köppen-Geiger do Xavier v3.2.4, normal 1991-2020 (agrometeorologiapy, moda 3x3)",
          "// troque o caminho pelo asset que você subiu",
          "var koppen = ee.Image('projects/SEU_PROJETO/assets/koppen_xavier_1991_2020').select('koppen');",
          f"var paleta = {[c for c in PAL_KOPPEN]};",
          "Map.addLayer(koppen, {min: 1, max: 31, palette: paleta}, 'Köppen Xavier 1991-2020');",
          "// classes presentes: " + ', '.join(f"{r.id}={r.classe}" for r in leg.itertuples())]
    (SAIDA / 'visualizar_gee.js').write_text('\n'.join(js) + '\n', encoding='utf-8')

    # conferências: CHELSA 1991-2020 (v1) reamostrado para a grade do Xavier pela moda; capítulo 3 (v3.2.2)
    conf = []
    with rasterio.open(CHELSA) as r:
        ch = np.zeros((H, W), np.uint8)
        reproject(r.read(1), ch, src_transform=r.transform, src_crs=r.crs, dst_transform=TRANSF, dst_crs='EPSG:4326',
                  resampling=Resampling.mode, src_nodata=r.nodata or 0, dst_nodata=0)
    c, n = concordancia(filtrado, ch)
    conf.append({'comparacao': 'Xavier v3.2.4 x CHELSA 1991-2020 (v1)', 'concordancia_pct': c, 'pixels': n})
    if CAP3.exists():
        k3 = np.load(CAP3)['koppen']
        c, n = concordancia(filtrado, k3)
        conf.append({'comparacao': 'Xavier v3.2.4 x Xavier v3.2.2 do capítulo 3', 'concordancia_pct': c, 'pixels': n})
    c, n = concordancia(filtrado, bruto)
    conf.append({'comparacao': 'com moda 3x3 x sem filtro', 'concordancia_pct': c, 'pixels': n})
    pd.DataFrame(conf).to_csv(SAIDA / 'conferencia.csv', index=False, float_format='%.2f')

    # prévia
    fig, ax = plt.subplots(figsize=(8, 8))
    ext = (TRANSF.c, TRANSF.c + W * TRANSF.a, TRANSF.f + H * TRANSF.e, TRANSF.f)
    ax.imshow(np.ma.masked_equal(filtrado, 0), cmap=ListedColormap(PAL_KOPPEN), vmin=1, vmax=31,
              extent=ext, interpolation='nearest')
    ax.legend(handles=[mpatches.Patch(color=r.cor, label=f'{r.classe} ({r.area_pct:.1f}%)') for r in leg.itertuples()],
              loc='lower left', fontsize=9, frameon=False)
    ax.set_title('Köppen-Geiger, Xavier v3.2.4, normal 1991-2020', fontsize=12)
    ax.set_xlabel('longitude'), ax.set_ylabel('latitude')
    fig.tight_layout()
    fig.savefig(SAIDA / 'koppen_xavier_1991_2020.png', dpi=150)
    plt.close(fig)
    print(leg.round(2).to_string(index=False))
    print(pd.DataFrame(conf).round(2).to_string(index=False))


if __name__ == '__main__':
    main()
