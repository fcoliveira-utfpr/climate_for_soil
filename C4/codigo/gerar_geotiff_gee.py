"""GeoTIFF com o conjunto curto de 1985 a 2026 para subir manualmente no GEE (Assets > NEW > Image Upload > GeoTIFF).

O envio por ee.Array não funciona para os assets anuais (o pedido de exportação passa do limite do GEE), então
vai um único arquivo com todas as bandas, e montar_colecao_gee.py separa no GEE uma imagem por ano.

Grade: a do BR-DWGD estendida (publicar_curto_gee.py: 0,1°, 413 x 469 pixels, de 74,9° W a 28,0° W e de 6,4° N a
34,9° S), com os pixels sem dado preenchidos pelo vizinho válido mais próximo e valores só no Brasil + 2 pixels
(fora disso, NaN = nodata).

Bandas (float32):
    <variável>_<ano>        as 9 variáveis do conjunto curto, para cada ano de 1985 a 2026 (378 bandas)
    dist_preenchimento_km  distância até o pixel do Xavier de onde veio o valor (0 = dado original)
    z_pixel_m              altitude média do pixel (MERIT DEM, m), para a correção pelo relevo das temperaturas

Saída: C4/resultados/gee/xavier_conjunto_curto_1985_2026.tif (e um .csv com a lista de bandas)

Uso: python gerar_geotiff_gee.py
"""
from pathlib import Path

import numpy as np
import pandas as pd
import rasterio
from rasterio.transform import Affine

from publicar_curto_gee import ANOS, BANDAS, DX, DY, HE, VARIAVEIS, WE, X0E, Y0E, alvo, preencher

RAIZ = Path(__file__).resolve().parents[2]
SAIDA = RAIZ / 'C4' / 'resultados' / 'gee'
Z = RAIZ / 'C4' / 'dados' / 'altitude_grade.npz'


def main():
    SAIDA.mkdir(parents=True, exist_ok=True)
    a = alvo()
    nomes, camadas = [], []
    km = None
    for ano in ANOS:
        d = np.load(VARIAVEIS / f'{ano}.npz')
        for b in BANDAS:
            v, km = preencher(d[b])
            camadas.append(np.where(a, v, np.nan).astype(np.float32))
            nomes.append(f'{b}_{ano}')
    camadas.append(np.where(a, km, np.nan).astype(np.float32)); nomes.append('dist_preenchimento_km')
    camadas.append(np.where(a, np.load(Z)['z'], np.nan).astype(np.float32)); nomes.append('z_pixel_m')
    assert all(np.isfinite(c[a]).all() for c in camadas), 'pixel do Brasil sem valor'

    perfil = {'driver': 'GTiff', 'height': HE, 'width': WE, 'count': len(camadas), 'dtype': 'float32',
              'crs': 'EPSG:4326', 'transform': Affine(DX, 0, X0E, 0, DY, Y0E), 'nodata': np.nan,
              'compress': 'deflate', 'predictor': 3, 'tiled': True, 'blockxsize': 256, 'blockysize': 256}
    arq = SAIDA / 'xavier_conjunto_curto_1985_2026.tif'
    with rasterio.open(arq, 'w', **perfil) as r:
        for i, (n, c) in enumerate(zip(nomes, camadas), 1):
            r.write(c, i)
            r.set_band_description(i, n)
    pd.DataFrame({'banda': range(1, len(nomes) + 1), 'nome': nomes}).to_csv(SAIDA / 'bandas.csv', index=False)
    print(arq, f'{arq.stat().st_size / 1e6:.1f} MB,', len(nomes), 'bandas')


if __name__ == '__main__':
    main()
