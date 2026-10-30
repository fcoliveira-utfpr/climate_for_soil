"""Escala fina, etapa 1: altitude nos locais e na grade do Xavier, e gradiente vertical de cada variável de
temperatura estimado no próprio Xavier.

- Altitude fina: MERIT DEM (90 m) em cada local da matriz e do painel (amostragem no GEE).
- Altitude grossa: média do MERIT em cada pixel de 0,1° da grade do Xavier estendida (a de publicar_curto_gee.py),
  preenchida para fora da máscara pelo vizinho mais próximo, como as variáveis.
- Gradiente (°C/km): regressão de cada variável de temperatura decenal (pixels de 0,1° do Brasil, média das
  janelas de 1985 a 2024) na altitude do pixel, controlando a tendência regional com um polinômio de 3º grau em
  latitude e longitude. A amplitude diária (Tmax - Tmin) não é corrigida: a mesma correção nas duas se anula.

Saídas: C4/dados/altitude_locais.parquet (ponto_id, longitude, latitude, z_merit),
        C4/dados/altitude_grade.npz (z na grade estendida) e resultados/tabelas/gradiente_altitude.csv

Uso: python relevo.py
"""
import sys
from pathlib import Path

import ee
import numpy as np
import pandas as pd

from publicar_curto_gee import GRADE, HE, PAD, VARIAVEIS, W, WE, X0E, Y0E, DX, DY, H, preencher

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / 'corelacao' / 'codigo'))
from gee_utils import conectar  # noqa: E402

DADOS = RAIZ / 'C4' / 'dados'
TAB = RAIZ / 'C4' / 'resultados' / 'tabelas'
TEMPERATURAS = ['cd_t_media', 'cd_tmax_media', 'cd_tmin_media', 'cd_t_mes_quente', 'cd_t_mes_frio', 'cd_biotemp']


def dem():
    return ee.Image('MERIT/DEM/v1_0_3').select('dem')


def locais():
    m = pd.read_parquet(DADOS / 'matriz_c4.parquet', columns=['longitude', 'latitude'])
    p = pd.read_parquet(DADOS / 'painel_c4.parquet', columns=['ponto_id', 'longitude', 'latitude']).drop_duplicates('ponto_id')
    u = pd.concat([m, p[['longitude', 'latitude']]]).round(6).drop_duplicates().reset_index(drop=True)
    return u


def altitude_locais():
    u = locais()
    partes = []
    for i in range(0, len(u), 3000):
        b = u.iloc[i:i + 3000]
        fc = ee.FeatureCollection([ee.Feature(ee.Geometry.Point([x, y]), {'i': int(k)})
                                   for k, x, y in zip(b.index, b.longitude, b.latitude)])
        r = dem().reduceRegions(fc, ee.Reducer.first(), 90).getInfo()['features']
        partes += [(f['properties']['i'], f['properties'].get('first')) for f in r]
    z = pd.DataFrame(partes, columns=['i', 'z_merit']).set_index('i')
    u = u.join(z)
    # locais no mar ou fora do MERIT (raros): altitude 0
    print('locais:', len(u), '| sem altitude no MERIT:', int(u.z_merit.isna().sum()))
    u['z_merit'] = u.z_merit.fillna(0.0)
    u.to_parquet(DADOS / 'altitude_locais.parquet', index=False)


def altitude_grade():
    # 90 m -> 0,01° pela pirâmide do GEE (média) -> média em 0,1° (um pedido direto passa do limite de pixels)
    km = dem().reproject(crs='EPSG:4326', crsTransform=[DX / 10, 0, X0E, 0, DY / 10, Y0E])
    zc = km.reduceResolution(ee.Reducer.mean(), maxPixels=1024).reproject(
        crs='EPSG:4326', crsTransform=[DX, 0, X0E, 0, DY, Y0E]).rename('z')
    arr = ee.data.computePixels({'expression': zc, 'fileFormat': 'NUMPY_NDARRAY', 'grid': GRADE})
    z = np.ma.filled(np.ma.masked_array(arr['z']).astype(float), np.nan)
    # mesma máscara do Xavier, depois preenchida como as variáveis (a altitude do pixel deve casar com a dele)
    x = np.load(VARIAVEIS / '2000.npz')['cd_t_media']
    zg = z[PAD:PAD + H, PAD:PAD + W].copy()
    zg[~np.isfinite(x)] = np.nan
    zf, _ = preencher(zg)
    np.savez_compressed(DADOS / 'altitude_grade.npz', z=zf.astype(np.float32))
    print('altitude da grade: mín', np.nanmin(zf).round(), 'máx', np.nanmax(zf).round())


def gradientes():
    z = np.load(DADOS / 'altitude_grade.npz')['z'][PAD:PAD + H, PAD:PAD + W]
    lat = (Y0E + DY * (np.arange(HE) + 0.5))[PAD:PAD + H]
    lon = (X0E + DX * (np.arange(WE) + 0.5))[PAD:PAD + W]
    LON, LAT = np.meshgrid(lon, lat)
    media = {v: np.mean([np.load(VARIAVEIS / f'{a}.npz')[v] for a in range(1985, 2025)], axis=0) for v in TEMPERATURAS}
    ok = np.isfinite(z) & np.all([np.isfinite(media[v]) for v in TEMPERATURAS], axis=0)
    x, y = (LON[ok] + 55) / 10, (LAT[ok] + 15) / 10
    poli = [x ** i * y ** j for i in range(4) for j in range(4 - i)]
    X = np.column_stack(poli + [z[ok] / 1000])
    linhas = []
    for v in TEMPERATURAS:
        coef, res, *_ = np.linalg.lstsq(X, media[v][ok], rcond=None)
        pred = X @ coef
        r2 = 1 - ((media[v][ok] - pred) ** 2).sum() / ((media[v][ok] - media[v][ok].mean()) ** 2).sum()
        linhas.append({'variavel': v, 'gradiente_c_por_km': coef[-1], 'r2_modelo': r2, 'pixels': int(ok.sum())})
    t = pd.DataFrame(linhas)
    TAB.mkdir(parents=True, exist_ok=True)
    t.to_csv(TAB / 'gradiente_altitude.csv', index=False, float_format='%.4f')
    print(t.round(3).to_string(index=False))


if __name__ == '__main__':
    conectar(None)
    if not (DADOS / 'altitude_locais.parquet').exists():
        altitude_locais()
    altitude_grade()
    gradientes()
