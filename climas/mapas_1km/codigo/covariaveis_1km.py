"""Etapa 2: covariáveis do modelo de SOC na grade de 1 km (grade.py), baixadas do GEE pela API.

As covariáveis são as da produção da C3 (climas/analise_espaco_tempo/codigo/covariaveis_c3.py): estáticas
(ESTATICAS, inclui as dummies do Köppen IPEF) e dinâmicas de cada ano (DINAMICAS), arredondadas como na matriz.
O valor de cada pixel de 1 km deve ser o do pixel de 30 m central (a matriz de treino tem valores pontuais
de 30 m). A etapa `teste` confere isso: baixa um tile e compara com a amostragem a 30 m nos centros.

Saída (fora do git): climas/dados_mapas_1km/<bloco>/<tile>.tif

Uso:
    python covariaveis_1km.py blocos            # lista os blocos de ~1° que tocam o Brasil (DADOS/blocos.csv)
    python covariaveis_1km.py estaticas         # estáticas, uma vez: DADOS/estaticas/<col0>_<lin0>.parquet
    python covariaveis_1km.py dinamicas 1985 2024   # dinâmicas + classe LULC do ano: DADOS/dinamicas/<ano>/
    python covariaveis_1km.py teste [lon lat]   # um tile (padrão: fronteira Amazônia-Cerrado, MT), estáticas
                                                # + dinâmicas de 2020, e a conferência com pontos a 30 m
"""
import sys
import time
from pathlib import Path

import ee
import geemap
import numpy as np
import pandas as pd
import rasterio

import grade as g

RAIZ = g.RAIZ
sys.path.insert(0, str(RAIZ / 'climas' / 'analise_espaco_tempo' / 'codigo'))
sys.path.insert(0, str(RAIZ / 'corelacao' / 'codigo'))
import covariaveis_c3 as c3  # noqa: E402
from gee_utils import conectar  # noqa: E402


def imagem_estaticas():
    return c3.estaticas().select(c3.ESTATICAS).round().toFloat()


def imagem_dinamicas(ano):
    return c3.dinamicas(ano).select(c3.DINAMICAS).round().toFloat()


def baixar(img, tile, arquivo, forcar_30m=False):
    """Baixa o tile na grade de 1 km. forcar_30m: avalia a imagem na grade de 30 m antes (reproject), para que
    a reamostragem para 1 km pegue o pixel de 30 m central em vez das pirâmides do GEE."""
    i, j, col0, lin0, w, h = tile
    if forcar_30m:
        img = img.reproject(crs=g.CRS, crsTransform=g.transformacao(res=g.RES30))
    arquivo.parent.mkdir(parents=True, exist_ok=True)
    nomes = img.bandNames().getInfo()
    geemap.download_ee_image(img, filename=str(arquivo), crs=g.CRS, crs_transform=g.transformacao(col0, lin0),
                             shape=(h, w), dtype='float32', max_tile_size=8)
    with rasterio.open(arquivo, 'r+') as r:
        r.descriptions = tuple(nomes)
    return nomes


def amostra_30m(img, tile, n=400, semente=2026):
    """Valores a 30 m (sem pirâmides) nos centros de n pixels aleatórios do tile."""
    i, j, col0, lin0, w, h = tile
    rng = np.random.default_rng(semente)
    cols, lins = rng.integers(0, w, n), rng.integers(0, h, n)
    pts = [ee.Feature(ee.Geometry.Point(g.centro(col0 + c, lin0 + l)), {'c': int(c), 'l': int(l)})
           for c, l in zip(cols, lins)]
    proj30 = ee.Projection(g.CRS, g.transformacao(res=g.RES30))
    res = img.sampleRegions(ee.FeatureCollection(pts), projection=proj30, geometries=False).getInfo()['features']
    return pd.DataFrame([f['properties'] for f in res])


def centros(img, col0, lin0, w, h, nodata=-9999):
    """Valores a 30 m (sem pirâmides) nos pixels centrais de um bloco da grade de 1 km, por amostragem: máscara
    que só deixa o pixel de 30 m central de cada bloco 33 x 33 e `sample` na projeção de 30 m. Devolve
    DataFrame com col, lin (da grade de 1 km) e as bandas (sem dado = nodata)."""
    proj30 = ee.Projection(g.CRS, g.transformacao(res=g.RES30))
    xy = ee.Image.pixelCoordinates(proj30)           # índice do pixel de 30 m (centro em k + 0,5)
    c30, l30 = xy.select('x').floor(), xy.select('y').floor()
    meio = (g.N - 1) // 2
    centro = c30.mod(g.N).eq(meio).And(l30.mod(g.N).eq(meio))
    idx = ee.Image.cat([c30.subtract(meio).divide(g.N).toInt().rename('col'),
                        l30.subtract(meio).divide(g.N).toInt().rename('lin')])
    x0, y0 = g.X0 + col0 * g.RES, g.Y0 - lin0 * g.RES
    regiao = ee.Geometry.Rectangle([x0, y0 - h * g.RES, x0 + w * g.RES, y0], g.CRS, False)
    amostra = (img.unmask(nodata).addBands(idx).updateMask(centro)
               .sample(region=regiao, projection=proj30, geometries=False, dropNulls=True, tileScale=4))
    return ee.data.computeFeatures({'expression': amostra, 'fileFormat': 'PANDAS_DATAFRAME'})


def centros_pontos(img, col0, lin0, w, h, mascara=None, nodata=-9999):
    """Como centros(), mas com um ponto explícito no centro de cada pixel de 1 km (= centro de um pixel de 30 m),
    gerado no servidor, e sampleRegions na projeção de 30 m. A versão por máscara de pixelCoordinates repetia
    alguns pixels e perdia outros (o índice oscila entre os tiles internos do GEE). `mascara`: imagem 0/1; só
    entram os centros com mascara = 1 (o Brasil)."""
    proj30 = ee.Projection(g.CRS, g.transformacao(res=g.RES30))
    cols, lins = ee.List.sequence(col0, col0 + w - 1), ee.List.sequence(lin0, lin0 + h - 1)

    def linha(l):
        l = ee.Number(l)
        y = ee.Number(g.Y0).subtract(l.add(0.5).multiply(g.RES))
        return cols.map(lambda c: ee.Feature(
            ee.Geometry.Point([ee.Number(g.X0).add(ee.Number(c).add(0.5).multiply(g.RES)), y]),
            {'col': c, 'lin': l}))

    pts = ee.FeatureCollection(lins.map(linha).flatten())
    img = img.unmask(nodata)
    if mascara is not None:
        img = img.updateMask(mascara)
    amostra = img.sampleRegions(pts, projection=proj30, geometries=False, tileScale=4)
    return ee.data.computeFeatures({'expression': amostra, 'fileFormat': 'PANDAS_DATAFRAME'})


def teste_centros(col0=2240, lin0=1680, w=112, h=112, ano=2020):
    """Tempo e conferência da amostragem dos centros num bloco de ~1° (padrão: dentro do tile do teste)."""
    conectar(None)
    img = ee.Image.cat([imagem_estaticas(), imagem_dinamicas(ano)])
    t0 = time.time()
    df = centros(img, col0, lin0, w, h)
    dt = time.time() - t0
    print(f'{len(df)} centros ({w * h} esperados), {df.shape[1]} colunas, {dt:.0f} s', flush=True)
    a = pd.read_parquet(g.DADOS / 'teste' / 'amostra30m_4_3_2020.parquet')
    a = a.assign(col=a.c + 2240, lin=a.l + 1680)
    j = a.merge(df, on=['col', 'lin'], suffixes=('_pt', ''))
    bandas = [b for b in df.columns if b not in ('col', 'lin') and b + '_pt' in j]
    iguais = {b: 100 * np.mean(np.isclose(j[b + '_pt'].astype(float), j[b].replace(-9999, np.nan).astype(float),
                                          equal_nan=True)) for b in bandas}
    s = pd.Series(iguais)
    print(f'conferência com pontos a 30 m: {len(j)} pontos em comum; bandas 100% iguais: {(s >= 99.9).sum()} de {len(s)};'
          f' piores: {s.sort_values().head(5).round(1).to_dict()}')
    df.to_parquet(g.DADOS / 'teste' / f'centros_{col0}_{lin0}_{ano}.parquet', index=False)


# --- Download completo ------------------------------------------------------------------------------------
BLOCO = 112                                   # pixels de 1 km por lado (~1°)
LULC = 'projects/mapbiomas-public/assets/brazil/lulc/collection10/mapbiomas_brazil_collection10_integration_v2'


def blocos():
    """Blocos de BLOCO x BLOCO pixels que tocam o Brasil (LULC da Coleção 10). Cache em DADOS/blocos.csv."""
    arq = g.DADOS / 'blocos.csv'
    if arq.exists():
        return pd.read_csv(arq)
    linhas = []
    for lin0 in range(0, g.NLIN, BLOCO):
        for col0 in range(0, g.NCOL, BLOCO):
            w, h = min(BLOCO, g.NCOL - col0), min(BLOCO, g.NLIN - lin0)
            x0, y0 = g.X0 + col0 * g.RES, g.Y0 - lin0 * g.RES
            linhas.append({'col0': col0, 'lin0': lin0, 'w': w, 'h': h,
                           'oeste': x0, 'norte': y0, 'leste': x0 + w * g.RES, 'sul': y0 - h * g.RES})
    df = pd.DataFrame(linhas)
    # Máscara do Brasil de 0,1° (grade do Xavier, capítulo 5), com margem de 0,15° para não perder o litoral
    m = np.load(RAIZ / 'climas' / 'dados_koppen_movel30' / 'grade.npz')
    lon, lat = m['lon'][m['brasil']], m['lat'][m['brasil']]
    toca = [((lon >= r.oeste - 0.15) & (lon <= r.leste + 0.15) & (lat >= r.sul - 0.15) & (lat <= r.norte + 0.15)).any()
            for r in df.itertuples()]
    df = df[toca].reset_index(drop=True)
    g.DADOS.mkdir(parents=True, exist_ok=True)
    df.to_csv(arq, index=False)
    return df


def _mascara_brasil():
    return ee.Image(LULC).select('classification_2020').mask().rename('m')


def baixar_blocos(nome, img, workers=12, tentativas=5):
    """Amostra os centros de todos os blocos e grava DADOS/<nome>/<col0>_<lin0>.parquet (float32; sem dado =
    NaN). Retomável: pula blocos já gravados; blocos sem pixel do Brasil gravam um arquivo vazio."""
    pasta = g.DADOS / nome
    pasta.mkdir(parents=True, exist_ok=True)
    mascara = _mascara_brasil()
    todos = blocos()
    faltam = [r for r in todos.itertuples() if not (pasta / f'{r.col0}_{r.lin0}.parquet').exists()]
    print(f'{nome}: {len(todos)} blocos, faltam {len(faltam)}', flush=True)

    def um(r):
        for t in range(tentativas):
            try:
                df = centros_pontos(img, r.col0, r.lin0, r.w, r.h, mascara=mascara)
                df = df.drop(columns=['geo'], errors='ignore')
                if len(df):
                    df = df.astype({c: 'float32' for c in df.columns if c not in ('col', 'lin')})
                    df = df.replace(-9999, np.nan).astype({'col': 'int32', 'lin': 'int32'})
                df.to_parquet(pasta / f'{r.col0}_{r.lin0}.parquet', index=False)
                return len(df)
            except Exception as e:  # cota, memória, rede
                if t == tentativas - 1:
                    print(f'  FALHOU {r.col0}_{r.lin0}: {str(e)[:150]}', flush=True)
                    return -1
                time.sleep(20 * (t + 1))

    from concurrent.futures import ThreadPoolExecutor, as_completed
    t0, feitos, pixels = time.time(), 0, 0
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for fut in as_completed([pool.submit(um, r) for r in faltam]):
            n = fut.result()
            feitos += 1
            pixels += max(n, 0)
            if feitos % 25 == 0 or feitos == len(faltam):
                print(f'  {feitos}/{len(faltam)} blocos, {pixels:,} pixels, {(time.time() - t0) / 60:.0f} min',
                      flush=True)


def comparar(arquivo, amostra):
    with rasterio.open(arquivo) as r:
        nomes, arr = list(r.descriptions), r.read()
    linhas = []
    for b, nome in enumerate(nomes):
        a = amostra[nome].to_numpy(float)
        x = arr[b, amostra.l.to_numpy(), amostra.c.to_numpy()].astype(float)
        ok = np.isfinite(a) & np.isfinite(x)
        linhas.append({'banda': nome, 'n': int(ok.sum()), 'igual_pct': 100 * np.mean(np.isclose(a[ok], x[ok])),
                       'mae': np.mean(np.abs(a[ok] - x[ok])) if ok.any() else np.nan})
    return pd.DataFrame(linhas)


def teste(lon=-52.5, lat=-12.5, ano=2020):
    conectar(None)
    tile = g.tile_de(lon, lat)
    i, j, col0, lin0, w, h = tile
    lo, la = g.centro(col0, lin0)
    print(f'tile {i},{j}: {w} x {h} pixels, canto superior esquerdo {lo:.3f}, {la:.3f}', flush=True)
    pasta = g.DADOS / 'teste'
    img = ee.Image.cat([imagem_estaticas(), imagem_dinamicas(ano)])
    resumo = {}
    for nome, forcar in (('direto', False), ('forcado_30m', True)):
        arq = pasta / f'tile_{i}_{j}_{ano}_{nome}.tif'
        t0 = time.time()
        try:
            if not arq.exists():
                baixar(img, tile, arq, forcar_30m=forcar)
            resumo[nome] = f'{time.time() - t0:.0f} s, {arq.stat().st_size / 1e6:.0f} MB'
        except Exception as e:
            resumo[nome] = f'falhou: {str(e)[:200]}'
        print(nome, resumo[nome], flush=True)
    amostra = amostra_30m(img, tile)
    amostra.to_parquet(pasta / f'amostra30m_{i}_{j}_{ano}.parquet', index=False)
    for nome in ('direto', 'forcado_30m'):
        arq = pasta / f'tile_{i}_{j}_{ano}_{nome}.tif'
        if not arq.exists():
            continue
        cmp_ = comparar(arq, amostra)
        cmp_.to_csv(pasta / f'comparacao_{nome}.csv', index=False)
        print(f'\n== {nome}: % de pixels iguais ao valor de 30 m no centro (mediana {cmp_.igual_pct.median():.1f}%)')
        print(cmp_.sort_values('igual_pct').head(12).round(2).to_string(index=False))


if __name__ == '__main__':
    etapa = sys.argv[1] if len(sys.argv) > 1 else ''
    if etapa == 'teste':
        teste(*[float(x) for x in sys.argv[2:4]])
    elif etapa == 'teste_centros':
        teste_centros(*[int(x) for x in sys.argv[2:6]])
    elif etapa == 'blocos':
        conectar(None)
        print(len(blocos()), 'blocos tocam o Brasil')
    elif etapa == 'estaticas':
        conectar(None)
        baixar_blocos('estaticas', imagem_estaticas())
    elif etapa == 'dinamicas':
        conectar(None)
        a0, a1 = (int(x) for x in sys.argv[2:4])
        for ano in range(a0, a1 + 1):
            lulc = ee.Image(LULC).select(f'classification_{ano}').rename('lulc').toFloat()
            baixar_blocos(f'dinamicas/{ano}', imagem_dinamicas(ano).addBands(lulc))
    else:
        print(__doc__)
