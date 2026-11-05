"""Monta no GEE a coleção anual do conjunto curto a partir do GeoTIFF de gerar_geotiff_gee.py, depois que ele foi
subido manualmente (Code Editor: Assets > NEW > Image Upload > GeoTIFF). O upload chama as bandas de b1 a b380, na
ordem de resultados/gee/bandas.csv; aqui cada ano vira uma imagem com os nomes das variáveis.

Uso: python montar_colecao_gee.py exportar <asset do GeoTIFF>
     python montar_colecao_gee.py conferir             # asset x .npz locais, todos os anos e bandas
     python montar_colecao_gee.py descricao
"""
import sys
from pathlib import Path

import ee
import numpy as np
import pandas as pd

from publicar_curto_gee import ANOS, BANDAS, COLECAO, DX, DY, GRADE, HE, VARIAVEIS, WE, X0E, Y0E, alvo, preencher

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / 'corelacao' / 'codigo'))
from gee_utils import conectar  # noqa: E402

BANDAS_CSV = RAIZ / 'C4' / 'resultados' / 'gee' / 'bandas.csv'

# texto completo (resumo, processamento, validação, limitações, exemplos JS e Python, citação, licença)
DESCRICAO = (RAIZ / 'C4' / 'gee' / 'descricao_colecao.md').read_text(encoding='utf-8')


def nomes():
    return pd.read_csv(BANDAS_CSV).nome.tolist()


def imagem(fonte, ano):
    lista = nomes()
    idx = [lista.index(f'{b}_{ano}') + 1 for b in BANDAS] + [lista.index('dist_preenchimento_km') + 1,
                                                              lista.index('z_pixel_m') + 1]
    img = ee.Image(fonte).select([f'b{i}' for i in idx], list(BANDAS) + ['dist_preenchimento_km', 'z_pixel_m'])
    return img.toFloat().set({'year': ano, 'inicio_janela': ano - 10, 'fim_janela': ano - 1,
                              'system:time_start': ee.Date.fromYMD(ano, 1, 1).millis(),
                              'fonte': 'Xavier et al. (2022) BR-DWGD v3.2.4'})


def exportar(fonte):
    b = ee.Image(fonte).bandNames().size().getInfo()
    assert b == len(nomes()), f'o asset tem {b} bandas; esperado {len(nomes())}'
    try:
        ee.data.getAsset(COLECAO)
    except ee.EEException:
        ee.data.createAsset({'type': 'IMAGE_COLLECTION'}, COLECAO)
    regiao = ee.Geometry.Rectangle([X0E, Y0E + HE * DY, X0E + WE * DX, Y0E], 'EPSG:4326', False)
    for ano in ANOS:
        t = ee.batch.Export.image.toAsset(image=imagem(fonte, ano), description=f'curto_decenal_{ano}',
                                          assetId=f'{COLECAO}/{ano}', crs='EPSG:4326',
                                          crsTransform=[DX, 0, X0E, 0, DY, Y0E], region=regiao, maxPixels=1e9,
                                          pyramidingPolicy={'.default': 'mean'})
        t.start()
        print(ano, t.id, flush=True)


def conferir():
    col = ee.ImageCollection(COLECAO)
    print('imagens na coleção:', col.size().getInfo())
    a, pior = alvo(), {}
    for ano in ANOS:
        img = col.filter(ee.Filter.eq('year', ano)).first().select(list(BANDAS))
        arr = ee.data.computePixels({'expression': img, 'fileFormat': 'NUMPY_NDARRAY', 'grid': GRADE})
        d = np.load(VARIAVEIS / f'{ano}.npz')
        for b in BANDAS:
            v, _ = preencher(d[b])
            g = np.ma.filled(np.ma.masked_array(arr[b]).astype(float), np.nan)
            assert np.isfinite(g[a]).all(), (ano, b, 'pixel do Brasil sem valor')
            pior[b] = max(pior.get(b, 0), float(np.abs(g[a] - v[a]).max()))
        print(ano, 'ok', flush=True)
    print('maior diferença absoluta asset x local:', {b: round(x, 5) for b, x in pior.items()})


def descricao():
    ee.data.setAssetProperties(COLECAO, {'description': DESCRICAO})
    print('descrição:', len(ee.data.getAsset(COLECAO)['properties']['description']), 'caracteres')


if __name__ == '__main__':
    conectar(None)
    etapa = sys.argv[1] if len(sys.argv) > 1 else ''
    if etapa == 'exportar':
        exportar(sys.argv[2])
    elif etapa == 'conferir':
        conferir()
    elif etapa == 'descricao':
        descricao()
    else:
        raise SystemExit(__doc__)
