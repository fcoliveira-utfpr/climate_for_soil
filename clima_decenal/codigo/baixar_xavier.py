"""Etapa 1: variáveis mensais de cada ano do Xavier (BR-DWGD) para a ETo de Penman-Monteith e a altitude.

Por ano (1961-2022), na grade nativa (0,1°, 391 x 393): médias mensais de Tmax e Tmin (°C), umidade relativa
(%), radiação solar global Rs (MJ/m² dia) e vento a 2 m (m/s). A chuva mensal já está em
climas_tempo/dados/xavier_mensal (baixar_xavier.py do capítulo 3). Meses sem dado no GEE (depois de 07/2020)
ficam NaN. Também a altitude média de cada pixel (ETOPO1, 1 minuto de arco, média dos pixels; o MERIT de
90 m estoura o limite de pixels do GEE nessa redução).

Escalas do BR-DWGD no GEE (valor x escala + deslocamento): Tmax e Tmin 0,001068148 e 15; UR 0,393700787;
Rs 0,157086614; vento 0,059055118.

Saída (fora do git): clima_decenal/dados/xavier_mensal/<ano>.npz (Tmax, Tmin, UR, Rs, u2: (12, 393, 391))
e clima_decenal/dados/altitude.npy

Uso: python baixar_xavier.py [ano_ini ano_fim]
"""
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import ee
import numpy as np

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / 'corelacao' / 'codigo'))
from gee_utils import conectar  # noqa: E402

DADOS = RAIZ / 'clima_decenal' / 'dados'
MENSAL = DADOS / 'xavier_mensal'
BASE = 'projects/sat-io/open-datasets/BR-DWGD/'
VARS = {'Tmax': ('TMAX', 0.001068148, 15.0), 'Tmin': ('TMIN', 0.001068148, 15.0), 'UR': ('RH', 0.393700787, 0.0),
        'Rs': ('RS', 0.157086614, 0.0), 'u2': ('U2', 0.059055118, 0.0)}
FIM = '2020-08-01'
GRADE = {'dimensions': {'width': 391, 'height': 393},
         'affineTransform': {'scaleX': 0.1, 'shearX': 0, 'translateX': -73.89999847412109,
                             'shearY': 0, 'scaleY': -0.09999999586416751, 'translateY': 5.399999902564652},
         'crsCode': 'EPSG:4326'}


def _col(colecao, a, b):
    return ee.ImageCollection(BASE + colecao).map(
        lambda im: im.multiply(a).add(b).copyProperties(im, ['system:time_start']))


def mensal(ano):
    cols = {v: _col(*VARS[v]) for v in VARS}
    bandas = []
    for v, col in cols.items():
        for m in range(1, 13):
            ini = f'{ano}-{m:02d}-01'
            fim = f'{ano + 1}-01-01' if m == 12 else f'{ano}-{m + 1:02d}-01'
            if fim <= FIM:
                bandas.append(col.filterDate(ini, fim).mean().rename(f'{v}_{m:02d}'))
            else:
                bandas.append(ee.Image.constant(0).toFloat().updateMask(0).rename(f'{v}_{m:02d}'))
    mascara = ee.Image(ee.ImageCollection(BASE + 'PR').first()).mask()
    return ee.Image.cat(bandas).toFloat().updateMask(mascara)


def _ndarray(arr, nomes):
    x = np.stack([arr[n] for n in nomes]).astype(np.float32)
    return np.where(np.ma.getmaskarray(np.ma.masked_invalid(x)), np.nan, x)


def baixar(ano):
    arq = MENSAL / f'{ano}.npz'
    if arq.exists():
        return ano, 'já existe'
    for tentativa in range(4):
        try:
            arr = ee.data.computePixels({'expression': mensal(ano), 'fileFormat': 'NUMPY_NDARRAY', 'grid': GRADE})
            break
        except ee.EEException:
            if tentativa == 3:
                raise
    np.savez_compressed(arq, **{v: _ndarray(arr, [f'{v}_{m:02d}' for m in range(1, 13)]) for v in VARS})
    return ano, 'ok'


def altitude():
    arq = DADOS / 'altitude.npy'
    if arq.exists():
        return
    dem = (ee.Image('NOAA/NGDC/ETOPO1').select('bedrock').max(0)
           .reduceResolution(ee.Reducer.mean(), maxPixels=1024)
           .reproject(crs='EPSG:4326', crsTransform=[0.1, 0, -73.89999847412109, 0, -0.09999999586416751,
                                                     5.399999902564652]))
    arr = ee.data.computePixels({'expression': dem.rename('z').toFloat(), 'fileFormat': 'NUMPY_NDARRAY',
                                 'grid': GRADE})
    np.save(arq, _ndarray(arr, ['z'])[0])


def main(ini=1961, fim=2022):
    conectar(None)
    MENSAL.mkdir(parents=True, exist_ok=True)
    altitude()
    print('altitude ok', flush=True)
    with ThreadPoolExecutor(max_workers=4) as pool:
        for ano, st in pool.map(baixar, range(ini, fim + 1)):
            print(ano, st, flush=True)


if __name__ == '__main__':
    main(*[int(a) for a in sys.argv[1:3]])
