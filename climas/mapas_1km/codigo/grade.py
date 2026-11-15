"""Grade de ~1 km dos mapas de SOC do artigo, alinhada à grade de 30 m do MapBiomas.

Pixel = 33 x 33 pixels de 30 m do MapBiomas (0,000269494585° x 33 = 0,0088933° ≈ 990 m no equador), com a
mesma origem da Coleção 10 de uso da terra. Com 33 (ímpar), o centro de cada pixel de 1 km coincide com o
centro de um pixel de 30 m (o 17º do bloco), de onde vêm as covariáveis (amostra sistemática do mapa de 30 m).

Tiles para download: 560 x 560 pixels (~4,98° x 4,98°).
"""
import math
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[3]
DADOS = RAIZ / 'climas' / 'dados_mapas_1km'
PASTA = Path(__file__).resolve().parents[1]

RES30 = 0.00026949458523585647                 # pixel de 30 m do MapBiomas (graus)
X0, Y0 = -74.02073025380652, 5.405791885246045  # origem da Coleção 10 (canto superior esquerdo)
N = 33
RES = RES30 * N
NCOL = math.ceil(154468 / N)                    # 4.681 colunas
NLIN = math.ceil(146235 / N)                    # 4.432 linhas
TILE = 560
CRS = 'EPSG:4326'


def transformacao(col0=0, lin0=0, res=RES):
    """crs_transform (lista de 6) do canto da coluna/linha col0, lin0 da grade de 1 km."""
    return [res, 0, X0 + col0 * RES, 0, -res, Y0 - lin0 * RES]


def tiles():
    """(i, j, col0, lin0, largura, altura) de todos os tiles da grade."""
    out = []
    for j, lin0 in enumerate(range(0, NLIN, TILE)):
        for i, col0 in enumerate(range(0, NCOL, TILE)):
            out.append((i, j, col0, lin0, min(TILE, NCOL - col0), min(TILE, NLIN - lin0)))
    return out


def tile_de(lon, lat):
    """Tile que contém a coordenada."""
    col, lin = int((lon - X0) / RES), int((Y0 - lat) / RES)
    return next(t for t in tiles() if t[2] <= col < t[2] + t[4] and t[3] <= lin < t[3] + t[5])


def centro(col, lin):
    """Coordenada do centro do pixel (col, lin) da grade de 1 km."""
    return X0 + (col + 0.5) * RES, Y0 - (lin + 0.5) * RES
