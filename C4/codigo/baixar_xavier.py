"""Etapa 1: Xavier (BR-DWGD) v3.2.4, 1961-2025, do asset do autor no GEE, em arrays mensais por ano e CDD
anual.

Fonte: projects/ee-alexandrexavier/assets/BR-DWGD (diário, 0,1°, 391 x 393; versão v3.2.4, abril de 2026,
todas as variáveis até 31/12/2025). As escalas vêm das propriedades de cada imagem (BAND_<v>_MULT e
BAND_<v>_ADD); nesta versão UR, Rs, vento e ETo têm deslocamento diferente de zero, ao contrário do asset
antigo (projects/sat-io/open-datasets/BR-DWGD/, v3.2.2, que ia só até 07/2020 e 2022). A coleção mensal do
autor (BR-DWGD_Monthly) não é usada: num teste (Brasília, 01/2010) a chuva dela não bate com a soma dos dias
(171 x 114 mm), então os meses são agregados aqui a partir do diário.

Por ano: médias mensais de Tmax, Tmin (°C), UR (%), Rs (MJ/m² dia) e vento a 2 m (m/s); somas mensais de chuva
e da ETo do próprio Xavier (mm; só para a conferência da ETo pelo Rn); e o CDD anual (índice ETCCDI: maior
sequência de dias com chuva < 1 mm, contando a estiagem que vem do ano anterior), com o mesmo algoritmo de
climas/analise_espaco_tempo/codigo/cdd_brdwgd.py, calculado no GEE e baixado como array (sem asset).

Saída (fora do git): C4/dados/xavier_mensal/<ano>.npz (Tmax, Tmin, UR, Rs, u2, P, ETo_xavier: (12, 393, 391);
CDD: (393, 391))

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

MENSAL = RAIZ / 'C4' / 'dados' / 'xavier_mensal'
ASSET = 'projects/ee-alexandrexavier/assets/BR-DWGD'
BANDAS = {'Tmax': 'Tmax', 'Tmin': 'Tmin', 'UR': 'RH', 'Rs': 'Rs', 'u2': 'u2', 'P': 'pr', 'ETo_xavier': 'ET'}
SOMA = {'P', 'ETo_xavier'}
LIMIAR_MM = 1.0
PRIMEIRO_ANO, ULTIMO_ANO = 1961, 2025
GRADE = {'dimensions': {'width': 391, 'height': 393},
         'affineTransform': {'scaleX': 0.1, 'shearX': 0, 'translateX': -73.89999847412109,
                             'shearY': 0, 'scaleY': -0.09999999586416751, 'translateY': 5.399999902564652},
         'crsCode': 'EPSG:4326'}


def diario():
    """Coleção diária em unidades físicas, com os nomes de BANDAS."""
    orig = list(BANDAS.values())

    def escala(im):
        mult = ee.Image.constant([ee.Number(im.get(f'BAND_{b}_MULT')) for b in orig]).rename(orig)
        add = ee.Image.constant([ee.Number(im.get(f'BAND_{b}_ADD')) for b in orig]).rename(orig)
        return (im.select(orig).multiply(mult).add(add).rename(list(BANDAS))
                .copyProperties(im, ['system:time_start']))
    return ee.ImageCollection(ASSET).map(escala)


def _dias(col, ano):
    return col.filterDate(f'{ano}-01-01', f'{ano + 1}-01-01').sort('system:time_start')


def _sequencias(seco):
    acum = seco.arrayAccum(0, ee.Reducer.sum())
    chuvoso = seco.multiply(-1).add(1)
    no_ultimo_chuvoso = acum.multiply(chuvoso).arrayAccum(0, ee.Reducer.max())
    return acum.subtract(no_ultimo_chuvoso), chuvoso.arrayAccum(0, ee.Reducer.max())


def cdd_ano(col, ano):
    def secos(a):
        return _dias(col, a).map(lambda im: im.select('P').lt(LIMIAR_MM).toInt16()).toArray().arrayProject([0])
    seq, ja_choveu = _sequencias(secos(ano))
    if ano > PRIMEIRO_ANO:
        seq_ant, _ = _sequencias(secos(ano - 1))
        herdada = seq_ant.arraySlice(0, -1).arrayGet([0])
        seq = seq.add(ja_choveu.multiply(-1).add(1).multiply(herdada))
    return seq.arrayReduce(ee.Reducer.max(), [0]).arrayGet([0]).rename('CDD').toFloat()


def mensal(col, ano, v):
    """12 bandas (v_01..v_12) de uma variável; média do mês, ou soma para chuva e ETo."""
    bandas = []
    for m in range(1, 13):
        ini = f'{ano}-{m:02d}-01'
        fim = f'{ano + 1}-01-01' if m == 12 else f'{ano}-{m + 1:02d}-01'
        mes = col.filterDate(ini, fim).select(v)
        bandas.append((mes.sum() if v in SOMA else mes.mean()).rename(f'{v}_{m:02d}'))
    return ee.Image.cat(bandas).toFloat()


def _ndarray(arr, nomes):
    x = np.stack([arr[n] for n in nomes]).astype(np.float32)
    return np.where(np.ma.getmaskarray(np.ma.masked_invalid(x)), np.nan, x)


def _pixels(img):
    for tentativa in range(4):
        try:
            return ee.data.computePixels({'expression': img, 'fileFormat': 'NUMPY_NDARRAY', 'grid': GRADE})
        except ee.EEException:
            if tentativa == 3:
                raise


def baixar(ano):
    arq = MENSAL / f'{ano}.npz'
    if arq.exists():
        return ano, 'já existe'
    col = diario()
    mascara = ee.Image(_dias(col, ano).first()).select('P').mask()
    out = {}
    for v in BANDAS:     # uma variável por pedido: o computePixels aceita até 48 MB
        arr = _pixels(mensal(col, ano, v).updateMask(mascara))
        out[v] = _ndarray(arr, [f'{v}_{m:02d}' for m in range(1, 13)])
    out['CDD'] = _ndarray(_pixels(cdd_ano(col, ano).updateMask(mascara)), ['CDD'])[0]
    np.savez_compressed(arq, **out)
    return ano, 'ok'


def main(ini=PRIMEIRO_ANO, fim=ULTIMO_ANO):
    conectar(None)
    MENSAL.mkdir(parents=True, exist_ok=True)
    with ThreadPoolExecutor(max_workers=4) as pool:
        for ano, st in pool.map(baixar, range(ini, fim + 1)):
            print(ano, st, flush=True)


if __name__ == '__main__':
    main(*[int(a) for a in sys.argv[1:3]])
