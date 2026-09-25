"""Fase 2 (textura): mapas de areia, silte e argila de 0-30 cm para cada cenário de clima.

Grade de 0,05° (~5 km), alinhada à do CHELSA. Em cada pixel, as covariáveis são as do centro do pixel
(amostragem pelo vizinho mais próximo, como um "ponto virtual"); os modelos são os da fase 1a (GBM por
camada sobre as razões log), treinados com todos os horizontes. A textura de 0-30 cm é a média das três
camadas (0-10, 10-20, 20-30 cm).

Saídas em climas/dados_reproducao/mapas/:
  covariaveis_textura_5km.tif        pilha de covariáveis do MapBiomas + Köppen IPEF (baixada do GEE)
  clima_5km.parquet                  classes e clima contínuo de cada pixel (dos rasters CHELSA locais)
  textura_0_30cm_<cenario>.tif       3 bandas: areia, silte, argila (%)
"""
import sys

import numpy as np
import pandas as pd
import rasterio
from rasterio.transform import Affine

import config as cfg
import dados
import modelagem as m

RES = 0.05
TRANSFORM = Affine(RES, 0, -74.0, 0, -RES, 5.5)
FORMA = (790, 910)                                   # linhas, colunas (-74..-28,5 / 5,5..-34)
CLIMAS = cfg.RAIZ / 'climas' / 'dados_chelsa'
ARQ_COV = cfg.MAPAS / 'covariaveis_textura_5km.tif'
ARQ_CLIMA = cfg.MAPAS / 'clima_5km.parquet'


def centros():
    lin, col = np.meshgrid(np.arange(FORMA[0]), np.arange(FORMA[1]), indexing='ij')
    lon = TRANSFORM.c + (col.ravel() + 0.5) * RES
    lat = TRANSFORM.f - (lin.ravel() + 0.5) * RES
    return lon, lat


def baixar_covariaveis():
    import ee
    import geemap
    from gee_utils import conectar
    import covariaveis_gee as cg
    conectar(None)
    img = ee.Image.cat([cg.estaticas_textura(), cg.koppen_ipef()]).toFloat()
    nomes = img.bandNames().getInfo()
    cfg.MAPAS.mkdir(parents=True, exist_ok=True)
    geemap.download_ee_image(img, filename=str(ARQ_COV), crs='EPSG:4326',
                             crs_transform=list(TRANSFORM)[:6], shape=FORMA, dtype='float32',
                             max_tile_size=8)
    # geemap.download_ee_image nao grava as descricoes de banda no GeoTIFF; grava aqui, na
    # mesma ordem de img.bandNames(), ja que grade_completa() le por nome (r.descriptions).
    with rasterio.open(ARQ_COV, 'r+') as dst:
        dst.descriptions = tuple(nomes)


def _amostrar(arq, lon, lat, bandas=None):
    with rasterio.open(arq) as r:
        idx = bandas or list(range(1, r.count + 1))
        v = np.array([x for x in r.sample(zip(lon, lat), indexes=idx)], dtype=float)
        if r.nodata is not None and not np.isnan(r.nodata):
            v[v == r.nodata] = np.nan
    return v


def clima_no_grid():
    """Classes de todos os sistemas e clima contínuo no centro de cada pixel, com as mesmas funções da
    análise de pontos (corelacao)."""
    from experimento_dados import calcular_variaveis
    from preparar_dados import classes_climaticas
    import zonas_clima as zc
    lon, lat = centros()
    with rasterio.open(CLIMAS / 'awc' / 'AWC_BR_grade_CHELSA.tif') as r:
        br = np.array([x[0] for x in r.sample(zip(lon, lat), indexes=[2])]) == 1
    lon, lat = lon[br], lat[br]
    normal = CLIMAS / 'normal_1991_2020' / 'chelsa_brasil_{}_normal_1991_2020.tif'
    tas, pr, pet = (_amostrar(str(normal).format(v), lon, lat) for v in ('tas', 'pr', 'pet'))
    th100 = _amostrar(CLIMAS / 'thornthwaite' / 'Thornthwaite_CHELSA_BR_1991_2020_CAD100.tif', lon, lat)
    thsolo = _amostrar(CLIMAS / 'thornthwaite' / 'Thornthwaite_CHELSA_BR_1991_2020_CADsolo.tif', lon, lat)
    cont = pd.DataFrame(calcular_variaveis(tas, pr, pet, lat, th100[:, 5], th100[:, 6], th100[:, 9]))
    cod = pd.DataFrame({
        'koppen_chelsa': _amostrar(CLIMAS / 'koppen' / 'Koppen_CHELSA_BR_1991_2020.tif', lon, lat)[:, 0],
        'holdridge_etpm': _amostrar(CLIMAS / 'holdridge' / 'Holdridge_CHELSA_BR_1991_2020_ETPM.tif', lon, lat)[:, 0],
        'holdridge_eth': _amostrar(CLIMAS / 'holdridge' / 'Holdridge_CHELSA_BR_1991_2020_ETH.tif', lon, lat)[:, 0],
        **{f'th100_{b}': th100[:, i] for i, b in enumerate(('umidade', 'subtipo', 'termica', 'concentracao'))},
        **{f'thsolo_{b}': thsolo[:, i] for i, b in enumerate(('umidade', 'subtipo', 'termica', 'concentracao'))},
    })
    for c in ('koppen_chelsa', 'holdridge_etpm', 'holdridge_eth'):
        cod[c] = cod[c].where(cod[c] > 0)                        # 0 = sem dado nos TIFs de classes
    df = pd.concat([pd.DataFrame({'longitude': lon, 'latitude': lat}), classes_climaticas(cod), cont], axis=1)
    ok = df[cfg.CLIMA_CONTINUO].notna().all(axis=1)
    cent, media, dp = zc.carregar(10)
    df['zona_k10'] = pd.Series(pd.NA, index=df.index, dtype='string')
    df.loc[ok, 'zona_k10'] = zc.atribuir(df[ok], cent, media, dp).astype(str)
    return df


def koppen_ipef_classes(cov, nomes):
    """Dummies do Köppen IPEF da pilha -> classes L1-L3 (L3 do grupo A = L2, como em preparar_dados)."""
    out = {}
    for nivel in ('l1', 'l2', 'l3'):
        cols = [i for i, n in enumerate(nomes) if n.startswith(f'koppen_{nivel}_')]
        bloco = cov[:, cols]
        valido = np.isclose(np.nansum(bloco, axis=1), 1) & np.isfinite(bloco).all(axis=1)
        rot = np.array([nomes[c].removeprefix(f'koppen_{nivel}_') for c in cols])[np.nanargmax(np.nan_to_num(bloco, nan=-1), axis=1)]
        out[f'koppen_ipef_{nivel}'] = pd.Series(np.where(valido, rot, None), dtype='string')
    df = pd.DataFrame(out)
    df['koppen_ipef_l3'] = df.koppen_ipef_l3.fillna(df.koppen_ipef_l2.where(df.koppen_ipef_l1 == 'A'))
    return df


def grade_completa():
    """Covariáveis + climas por pixel do Brasil (DataFrame), e o índice de cada pixel na grade."""
    with rasterio.open(ARQ_COV) as r:
        nomes = list(r.descriptions)
        cov = r.read().reshape(r.count, -1).T
    cov[~np.isfinite(cov)] = np.nan          # sem dado veio como -inf no download
    lon, lat = centros()
    idx = pd.DataFrame({'longitude': np.round(lon, 6), 'latitude': np.round(lat, 6), 'pixel': np.arange(len(lon))})
    clima = pd.read_parquet(ARQ_CLIMA)
    clima[['longitude', 'latitude']] = clima[['longitude', 'latitude']].round(6)
    clima = clima.merge(idx, on=['longitude', 'latitude'])
    g = pd.DataFrame(cov[clima.pixel.to_numpy()], columns=nomes)
    ipef = koppen_ipef_classes(cov[clima.pixel.to_numpy()], nomes)
    cov_mb = [n for n in nomes if not n.startswith('koppen_')]
    g = pd.concat([g.drop(columns=[n for n in nomes if n.startswith('koppen_')]), ipef,
                   clima.reset_index(drop=True)], axis=1)
    g['cov_ok'] = g[cov_mb].notna().all(axis=1)      # pixel com todas as covariáveis do MapBiomas
    return g


def prever(cenario, tex, soc, grade):
    cov_base = m.base(tex)
    cats = m.categorias(cenario, tex, soc)
    camadas = []
    for camada, centro in cfg.CAMADAS.items():
        d = tex[tex.profundidade.between(centro - cfg.MEIA_JANELA, centro + cfg.MEIA_JANELA)]
        x_tr = pd.concat([d[cov_base], m.clima(d, cenario, cats)], axis=1)
        x_g = pd.concat([grade.assign(profundidade=float(centro))[cov_base], m.clima(grade, cenario, cats)], axis=1)
        x_g = x_g[x_tr.columns]
        razoes = [m.gbm(cfg.SEMENTE).fit(x_tr.to_numpy(float), d[a].to_numpy()).predict(x_g.to_numpy(float))
                  for a in cfg.ALVOS_TEXTURA]
        camadas.append(np.column_stack(m.razoes_para_pct(*razoes)))
    return np.mean(camadas, axis=0)


def salvar(pct, grade, cenario):
    arr = np.full((3, FORMA[0] * FORMA[1]), np.nan, dtype='float32')
    ok = grade[cfg.CENARIOS[cenario][1]].notna().all(axis=1).to_numpy() if cfg.CENARIOS[cenario][1] else \
        np.ones(len(grade), bool)
    ok = ok & grade.cov_ok.to_numpy()
    arr[:, grade.pixel.to_numpy()[ok]] = pct[ok].T
    perfil = dict(driver='GTiff', height=FORMA[0], width=FORMA[1], count=3, dtype='float32', crs='EPSG:4326',
                  transform=TRANSFORM, nodata=np.nan, compress='deflate')
    with rasterio.open(cfg.MAPAS / f'textura_0_30cm_{cenario}{cfg.SUFIXO}.tif', 'w', **perfil) as dst:
        dst.write(arr.reshape(3, *FORMA))
        dst.descriptions = ('areia', 'silte', 'argila')


def main(etapas=('covariaveis', 'clima', 'mapas')):
    cfg.MAPAS.mkdir(parents=True, exist_ok=True)
    if 'covariaveis' in etapas and not ARQ_COV.exists():
        baixar_covariaveis()
    if 'clima' in etapas and not ARQ_CLIMA.exists():
        clima_no_grid().to_parquet(ARQ_CLIMA, index=False)
    if 'mapas' in etapas:
        tex, soc = dados.carregar()
        grade = grade_completa()
        print(f'grade: {len(grade)} pixels do Brasil', flush=True)
        for cen in cfg.CENARIOS:
            salvar(prever(cen, tex, soc, grade), grade, cen)
            print(f'  mapa de textura: {cen}', flush=True)


if __name__ == '__main__':
    main(tuple(sys.argv[1:]) or ('covariaveis', 'clima', 'mapas'))
