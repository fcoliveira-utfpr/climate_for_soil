"""Etapa 1: dados mensais de cada ano do Xavier (BR-DWGD) no GEE, baixados como arrays na grade nativa
(0,1°, 391 x 393 pixels).

Por ano: T média mensal (média de (Tmax + Tmin)/2 diários, °C), chuva mensal (soma, mm) e ETo mensal (soma,
mm, Penman-Monteith FAO-56 do próprio BR-DWGD). Meses sem dado no GEE (T e ETo depois de 07/2020) ficam NaN.

Saída (fora do git): climas_tempo/dados/xavier_mensal/<ano>.npz com T, P, ETo (12, 393, 391) e
climas_tempo/dados/xavier_mensal/grade.json (transformação afim e dimensões).

Uso: python baixar_xavier.py [ano_ini ano_fim]
"""
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import ee
import numpy as np

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / 'corelacao' / 'codigo'))
from gee_utils import conectar  # noqa: E402

DADOS = RAIZ / 'climas_tempo' / 'dados' / 'xavier_mensal'
BASE = 'projects/sat-io/open-datasets/BR-DWGD/'
ESCALA = {'TMAX': (0.001068148, 15.0), 'TMIN': (0.001068148, 15.0), 'PR': (0.006866665, 225.0),
          'ET': (0.051181102, 0.0)}
FIM_T = '2020-08-01'          # temperatura e ETo vão até 31/07/2020 no GEE; a chuva, até 2022
GRADE = {'dimensions': {'width': 391, 'height': 393},
         'affineTransform': {'scaleX': 0.1, 'shearX': 0, 'translateX': -73.89999847412109,
                             'shearY': 0, 'scaleY': -0.09999999586416751, 'translateY': 5.399999902564652},
         'crsCode': 'EPSG:4326'}


def _col(v):
    a, b = ESCALA[v]
    return ee.ImageCollection(BASE + v).map(
        lambda im: im.multiply(a).add(b).copyProperties(im, ['system:time_start']))


def _vazio(nome):
    return ee.Image.constant(0).toFloat().updateMask(0).rename(nome)


def mensal(ano):
    """36 bandas: T_01..T_12, P_01..P_12, ETo_01..ETo_12."""
    tmax, tmin, pr, et = _col('TMAX'), _col('TMIN'), _col('PR'), _col('ET')
    bandas = {'T': [], 'P': [], 'ETo': []}
    for m in range(1, 13):
        ini = f'{ano}-{m:02d}-01'
        fim = f'{ano + 1}-01-01' if m == 12 else f'{ano}-{m + 1:02d}-01'
        com_t = fim <= FIM_T
        bandas['T'].append(tmax.filterDate(ini, fim).mean().add(tmin.filterDate(ini, fim).mean()).divide(2)
                           .rename(f'T_{m:02d}') if com_t else _vazio(f'T_{m:02d}'))
        bandas['P'].append(pr.filterDate(ini, fim).sum().rename(f'P_{m:02d}'))
        bandas['ETo'].append(et.filterDate(ini, fim).sum().rename(f'ETo_{m:02d}') if com_t else _vazio(f'ETo_{m:02d}'))
    # a soma de uma coleção não tem máscara própria; usa a máscara da chuva diária
    mascara = ee.Image(pr.first()).mask()
    img = ee.Image.cat(bandas['T'] + bandas['P'] + bandas['ETo']).toFloat()
    return img.updateMask(mascara)


def baixar(ano):
    arq = DADOS / f'{ano}.npz'
    if arq.exists():
        return ano, 'já existe'
    for tentativa in range(4):
        try:
            arr = ee.data.computePixels({'expression': mensal(ano), 'fileFormat': 'NUMPY_NDARRAY', 'grid': GRADE})
            break
        except ee.EEException:
            if tentativa == 3:
                raise
    pilha = {}
    for v in ('T', 'P', 'ETo'):
        x = np.stack([arr[f'{v}_{m:02d}'] for m in range(1, 13)]).astype(np.float32)
        pilha[v] = np.where(np.ma.getmaskarray(np.ma.masked_invalid(x)), np.nan, x)
    np.savez_compressed(arq, **pilha)
    return ano, 'ok'


def main(ini=1961, fim=2022):
    conectar(None)
    DADOS.mkdir(parents=True, exist_ok=True)
    (DADOS / 'grade.json').write_text(json.dumps(GRADE, indent=1))
    with ThreadPoolExecutor(max_workers=4) as pool:
        for ano, st in pool.map(baixar, range(ini, fim + 1)):
            print(ano, st, flush=True)


if __name__ == '__main__':
    main(*[int(a) for a in sys.argv[1:3]])
