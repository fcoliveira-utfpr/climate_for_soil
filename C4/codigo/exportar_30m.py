"""Covariáveis climáticas no formato do MapBiomas Solo (Coleção 4), a 30 m, em
projects/mapbiomas-solos-workspace/assets/covariates/climate:

    holdridge  XAVIER_1991_2020_HOLDRIDGE_30M_2026: como o IPEF_2013_KOPPEN_30M_2026, uma ImageCollection com as
               imagens Holdridge_L1 (região latitudinal) e Holdridge_L2 (zona de vida), cada zona uma banda binária
               (0/1, byte), reamostradas pelo vizinho mais próximo
    decenal    XAVIER_1985_2026_CLIMA_DECENAL_30M_2026: como o ISRIC_2021_SOILGRIDS_250M_2026, bandas Int16 com os
               valores arredondados (temperaturas x 100, CDD e ARM x 10), uma imagem por ano (1985-2026), com
               interpolação bilinear
    conferir   compara as coleções a 30 m com os assets de 0,1° em pontos aleatórios

Grade: a do IPEF_2013_KOPPEN_30M_2026 (EPSG:4326, 0,000269°); máscara: biome_2025_buf5k_30m (biomas com buffer de
5 km). As fontes (0,1°, grade estendida, toda preenchida) são as cópias em covariates/climate.

Uso: python exportar_30m.py holdridge | decenal | conferir
"""
import sys
from pathlib import Path

import ee

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / 'corelacao' / 'codigo'))
from gee_utils import conectar  # noqa: E402

W = 'projects/mapbiomas-solos-workspace/assets/covariates/climate'
FONTE_HOLD = f'{W}/XAVIER_1991-2020_HOLDRIDGE_11KM_2026'
FONTE_DEC = f'{W}/XAVIER_1985-2026_CLIMA_DECENAL_11KM_2026'
COL_HOLD = f'{W}/XAVIER_1991_2020_HOLDRIDGE_30M_2026'
COL_DEC = f'{W}/XAVIER_1985_2026_CLIMA_DECENAL_30M_2026'
MASCARA = 'projects/mapbiomas-workspace/AUXILIAR/biome_2025_buf5k_30m'
KOPPEN = 'projects/mapbiomas-brazil/assets/SOIL/COVARIATES/IPEF_2013_KOPPEN_30M_2026/Koppen_L1'
CRS = 'EPSG:4326'
TRANSF = [0.00026949458523585647, 0, -74.02890053734778, 0, -0.0002694945852358565, 5.3323104266780685]
LARG, ALT = 167831, 145421

# Holdridge: nível 1 (região latitudinal) agrupa as zonas de vida do nível 2
L1 = {'tq': [22, 23], 'st': [27, 28, 29, 30], 'tr': [35, 36, 37, 38]}
L2 = [22, 23, 27, 28, 29, 30, 35, 36, 37, 38]
# variáveis decenais: fator de escala para Int16
ESCALA = {'cd_t_media': 100, 'cd_tmax_media': 100, 'cd_tmin_media': 100, 'cd_t_mes_quente': 100,
          'cd_t_mes_frio': 100, 'cd_amplitude': 100, 'cd_biotemp': 100, 'cd_cdd': 10, 'cd_arm_csolo': 10}


def regiao():
    x0, y0 = TRANSF[2], TRANSF[5]
    return ee.Geometry.Rectangle([x0, y0 + ALT * TRANSF[4], x0 + LARG * TRANSF[0], y0], CRS, False)


def mascara():
    return ee.Image(MASCARA).gt(0)


def existe(asset):
    try:
        ee.data.getAsset(asset)
        return True
    except ee.EEException:
        return False


def colecao(asset):
    if not existe(asset):
        ee.data.createAsset({'type': 'IMAGE_COLLECTION'}, asset)


def exportar(img, asset, nome, piramide):
    if existe(asset):
        print('já existe:', asset.split('/')[-1])
        return
    t = ee.batch.Export.image.toAsset(image=img, description=nome, assetId=asset, crs=CRS, crsTransform=TRANSF,
                                      region=regiao(), maxPixels=1e13, pyramidingPolicy={'.default': piramide})
    t.start()
    print(nome, t.id, flush=True)


def holdridge():
    colecao(COL_HOLD)
    z = ee.Image(FONTE_HOLD).select('holdridge')          # vizinho mais próximo (padrão do GEE): classe
    m = mascara()
    n1 = ee.Image.cat([z.remap(v, [1] * len(v), 0).rename(f'holdridge_l1_{k}') for k, v in L1.items()])
    n2 = ee.Image.cat([z.eq(c).rename(f'holdridge_l2_{c}') for c in L2])
    for nome, img in (('Holdridge_L1', n1), ('Holdridge_L2', n2)):
        img = img.toByte().updateMask(m).set({'fonte': 'Xavier BR-DWGD v3.2.4, normal 1991-2020',
                                              'origem': FONTE_HOLD})
        exportar(img, f'{COL_HOLD}/{nome}', f'holdridge_30m_{nome}', 'mode')


def decenal():
    colecao(COL_DEC)
    col = ee.ImageCollection(FONTE_DEC)
    m = mascara()
    for ano in range(1985, 2027):
        fonte = ee.Image(col.filter(ee.Filter.eq('year', ano)).first())
        img = ee.Image.cat([fonte.select(b).resample('bilinear').multiply(e).round().rename(b)
                            for b, e in ESCALA.items()]).toInt16().updateMask(m)
        img = img.set({'year': ano, 'inicio_janela': ano - 10, 'fim_janela': ano - 1,
                       'system:time_start': ee.Date.fromYMD(ano, 1, 1).millis(),
                       'escala': ', '.join(f'{b}: x{e}' for b, e in ESCALA.items()),
                       'fonte': 'Xavier BR-DWGD v3.2.4', 'origem': FONTE_DEC})
        exportar(img, f'{COL_DEC}/{ano}', f'clima_decenal_30m_{ano}', 'mean')


def conferir():
    """Pontos aleatórios no Brasil: a 30 m = fonte (Holdridge pelo vizinho; decenal bilinear x escala)."""
    pts = ee.FeatureCollection.randomPoints(
        ee.FeatureCollection('FAO/GAUL/2015/level0').filter(ee.Filter.eq('ADM0_NAME', 'Brazil')).geometry()
        .simplify(5000), 300, 7)
    if existe(f'{COL_HOLD}/Holdridge_L2'):
        h30 = ee.Image(f'{COL_HOLD}/Holdridge_L2')
        zona = ee.Image(FONTE_HOLD).select('holdridge')
        dif = ee.Image.cat([h30.select(f'holdridge_l2_{c}').neq(zona.eq(c)) for c in L2]).reduce('sum')
        r = dif.reduceRegions(pts, ee.Reducer.first(), 30).aggregate_array('first').getInfo()
        r = [x for x in r if x is not None]
        print(f'Holdridge_L2: {len(r)} pontos, {sum(1 for x in r if x)} com zona diferente da fonte')
        soma = h30.reduce('sum').reduceRegions(pts, ee.Reducer.first(), 30).aggregate_array('first').getInfo()
        print('  bandas ligadas por pixel:', sorted(set(x for x in soma if x is not None)))
    col = ee.ImageCollection(COL_DEC)
    print('decenal: imagens', col.size().getInfo())
    if col.size().getInfo():
        ano = col.aggregate_array('year').sort().get(0).getInfo()
        a = ee.Image(col.filter(ee.Filter.eq('year', ano)).first())
        f = ee.Image(ee.ImageCollection(FONTE_DEC).filter(ee.Filter.eq('year', ano)).first())
        for b, e in ESCALA.items():
            d = a.select(b).divide(e).subtract(f.select(b).resample('bilinear')).abs()
            v = d.reduceRegions(pts, ee.Reducer.first(), 30).aggregate_array('first').getInfo()
            v = [x for x in v if x is not None]
            print(f'  {ano} {b}: {len(v)} pontos, diferença máxima {max(v):.4f} (arredondamento: {0.5 / e})')


if __name__ == '__main__':
    conectar(None)
    {'holdridge': holdridge, 'decenal': decenal, 'conferir': conferir}[sys.argv[1]]()
