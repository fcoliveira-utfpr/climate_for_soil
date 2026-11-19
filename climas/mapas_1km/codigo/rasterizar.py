"""Etapa 4b dos mapas de 1 km: predições do ranger (parquet por ano) -> GeoTIFF na grade de 1 km (grade.py).

Regras do pós-processamento do mapa oficial (carbon/2_model_prediction) aplicáveis aqui, pelo uso da terra da
Coleção 10 no pixel central: SOC = 0 em 23 (praias e dunas), 24 (área urbana) e 30 (mineração); sem dado em água
(31 aquicultura, 33 rios e lagos). A máscara de areia histórica e o grupo textural 1 do mapa oficial não entram
(não baixados).

Saída: climas/dados_mapas_1km/mapas/<cenario>/soc_<ano>.tif (int16, 0,1 t/ha, nodata -1, EPSG:4326, tiles 256,
deflate), fora do git.

Uso: python rasterizar.py <cenario> [ano0 ano1]
"""
import sys

import numpy as np
import pandas as pd
import rasterio
from rasterio.transform import Affine

import grade as g

ZERO = [23, 24, 30]
AGUA = [31, 33]
NODATA = -1


def rasterizar(cenario, ano):
    arq = g.DADOS / 'predicoes' / cenario / f'{ano}.parquet'
    saida = g.DADOS / 'mapas' / cenario / f'soc_{ano}.tif'
    if saida.exists() or not arq.exists():
        return None
    d = pd.read_parquet(arq)
    d = d[~d.lulc.isin(AGUA)]
    soc = np.where(d.lulc.isin(ZERO), 0, d.soc).astype(np.int16)
    img = np.full((g.NLIN, g.NCOL), NODATA, np.int16)
    img[d.lin.to_numpy(), d.col.to_numpy()] = soc
    saida.parent.mkdir(parents=True, exist_ok=True)
    perfil = dict(driver='GTiff', height=g.NLIN, width=g.NCOL, count=1, dtype='int16', crs=g.CRS, nodata=NODATA,
                  transform=Affine(*[g.RES, 0, g.X0, 0, -g.RES, g.Y0]), tiled=True, blockxsize=256,
                  blockysize=256, compress='deflate', predictor=2)
    with rasterio.open(saida, 'w', **perfil) as dst:
        dst.write(img, 1)
        dst.update_tags(unidade='0,1 t/ha (SOC 0-30 cm)', cenario=cenario, ano=str(ano))
    return saida, len(d)


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit()
    cen = sys.argv[1]
    a0, a1 = (int(sys.argv[2]), int(sys.argv[3])) if len(sys.argv) > 3 else (1985, 2024)
    for ano in range(a0, a1 + 1):
        r = rasterizar(cen, ano)
        if r:
            print(f'{r[0].name}: {r[1]:,} pixels')
