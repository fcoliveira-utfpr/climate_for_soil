"""Dados do experimento "o que colocar no lugar do Köppen nos modelos do MapBiomas Solo".

Para cada local (mesma limpeza e agregação de preparar_dados.py): todas as covariáveis das matrizes de
treino do MapBiomas (menos identificadores, alvos, produtos de textura e as dummies de clima antigas), o
clima contínuo do CHELSA extraído no ponto e as classes climáticas já amostradas por preparar_dados.py.

Saída (fora do git, dados restritos): .local/dados/exp_soc.parquet e .local/dados/exp_textura.parquet.
Pré-requisito: rodar preparar_dados.py antes (as classes climáticas vêm de soc/textura.parquet).
"""
import re
from concurrent.futures import ThreadPoolExecutor, as_completed

import ee
import numpy as np
import pandas as pd

import legendas as leg
from gee_utils import conectar
from preparar_dados import (DADOS, FRACOES, MATRIZ_SOC, MATRIZ_TEXTURA, baixar_featurecollection,
                            carregar_bases, coordenadas_validas, ponto_id)

ASSET_PR = 'projects/fcoliveira/assets/chelsa_brasil_pr_normal_1991_2020'
ASSET_PET = 'projects/fcoliveira/assets/chelsa_brasil_pet_normal_1991_2020'

# Colunas das matrizes que não são covariáveis (ou vazariam o alvo) -> fora do modelo.
NAO_COVARIAVEIS = re.compile(
    r'^(koppen_|HLZ_|log_|system:index|\.geo$|id$|dataset_id$|chunk_id$|ponto_id$|year$|YEAR_index$|'
    r'PSEUDO_index$|IFN_index$|profundidade$|latitude$|longitude$|soc_stock_g_m2$|areia$|silte$|argila$|'
    r'clay_000_030cm$|sand_000_030cm$|silt_000_030cm$|textura_l1_030cm$)')


def covariaveis(df):
    return [c for c in df.columns if not NAO_COVARIAVEIS.match(c)]


def agregar(df, alvo_cols):
    """Uma linha por local: mediana de alvos e covariáveis (réplicas por ano/horizonte)."""
    cov = covariaveis(df)
    num = df[cov + alvo_cols].apply(pd.to_numeric, errors='coerce')
    num['ponto_id'] = df.ponto_id.values
    return num.groupby('ponto_id').median().reset_index()


def matriz_soc():
    df = baixar_featurecollection(MATRIZ_SOC)
    df['ponto_id'] = ponto_id(df)
    ok = ~df.PSEUDO_index.astype(float).eq(1) & coordenadas_validas(df)
    ok &= pd.to_numeric(df.soc_stock_g_m2, errors='coerce') > 0
    return agregar(df[ok], ['soc_stock_g_m2'])


def matriz_textura():
    df = baixar_featurecollection(MATRIZ_TEXTURA)
    df['ponto_id'] = ponto_id(df)
    artificial = (df.id.astype(str).str.contains('pseudo', case=False, regex=False)
                  | df.id.astype(str).str.startswith('clay-copy-'))
    prof = pd.to_numeric(df.profundidade, errors='coerce')
    fr = df[FRACOES].astype(float)
    ok = ~artificial & coordenadas_validas(df) & prof.le(30) & prof.gt(0)
    ok &= np.isfinite(fr.to_numpy()).all(axis=1) & (fr >= 0).all(axis=1)
    ok &= np.isclose(fr.sum(axis=1), 1000, atol=15)
    return agregar(df[ok], FRACOES)


# ---------------------------------------------------------------------------------------------
# Clima contínuo no ponto
# ---------------------------------------------------------------------------------------------
def extrair_clima_mensal(pontos, bloco=3000, workers=3):
    """tas, pr e pet mensais (36 bandas) e DEF/EXC/Im do BHC (Thornthwaite CAD 100 mm)."""
    img = (ee.Image(leg.ASSET_TAS).rename([f'tas_{m:02d}' for m in range(1, 13)])
           .addBands(ee.Image(ASSET_PR).rename([f'pr_{m:02d}' for m in range(1, 13)]))
           .addBands(ee.Image(ASSET_PET).rename([f'pet_{m:02d}' for m in range(1, 13)]))
           .addBands(ee.Image(leg.ASSET_TH100).select([5, 6, 9], ['def_anual', 'exc_anual', 'im'])))
    proj = ee.Image(leg.ASSET_TAS).projection().getInfo()
    bandas = img.bandNames().getInfo()

    def parte(ini):
        sub = pontos.iloc[ini:ini + bloco]
        fc = ee.FeatureCollection([ee.Feature(ee.Geometry.Point([r.longitude, r.latitude]), {'idx': int(r.Index)})
                                   for r in sub.itertuples()])
        res = img.reduceRegions(fc, ee.Reducer.first(), crs=proj['crs'], crsTransform=proj['transform'],
                                tileScale=4).getInfo()['features']
        return pd.DataFrame([f['properties'] for f in res]).set_index('idx')

    partes = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for fut in as_completed([pool.submit(parte, i) for i in range(0, len(pontos), bloco)]):
            partes.append(fut.result())
            print(f'  clima mensal: {sum(len(p) for p in partes):>6}/{len(pontos)}', flush=True)
    return pd.concat(partes).reindex(range(len(pontos)))[bandas]


def variaveis_climaticas(m, lat):
    """Variáveis contínuas derivadas da normal mensal (mesmas usadas no zoneamento do grid)."""
    tas = m[[f'tas_{i:02d}' for i in range(1, 13)]].to_numpy(float)
    pr = m[[f'pr_{i:02d}' for i in range(1, 13)]].to_numpy(float)
    pet = m[[f'pet_{i:02d}' for i in range(1, 13)]].to_numpy(float)
    return pd.DataFrame(calcular_variaveis(tas, pr, pet, np.asarray(lat, float),
                                           m.def_anual.to_numpy(float), m.exc_anual.to_numpy(float),
                                           m.im.to_numpy(float)))


def calcular_variaveis(tas, pr, pet, lat, def_anual, exc_anual, im):
    """tas/pr/pet: (n, 12). Mesma função para pontos e pixels."""
    # biotemperatura de Holdridge (correção de latitude só nos meses > 24 °C, como em holdridge_gee.py)
    corr = np.where(tas > 24, 0.03 * np.abs(lat)[:, None] * (tas - 24) ** 2, 0)
    biotemp = np.clip(tas - corr, 0, 30).mean(axis=1)
    p_anual = pr.sum(axis=1)
    return {
        'clim_t_media': tas.mean(axis=1),
        'clim_t_mes_frio': tas.min(axis=1),
        'clim_t_mes_quente': tas.max(axis=1),
        'clim_biotemp': biotemp,
        'clim_p_anual': p_anual,
        'clim_p_mes_seco': pr.min(axis=1),
        'clim_p_sazonalidade': pr.std(axis=1) / np.maximum(pr.mean(axis=1), 1e-6),
        'clim_etp_anual': pet.sum(axis=1),
        'clim_etp_p': pet.sum(axis=1) / np.maximum(p_anual, 1),
        'clim_def_anual': def_anual,
        'clim_exc_anual': exc_anual,
        'clim_im': im,
    }


def montar(matriz, classes):
    """Junta covariáveis da matriz, classes climáticas e clima contínuo, pelo ponto_id."""
    df = classes.merge(matriz, on='ponto_id', how='inner').reset_index(drop=True)
    clima = variaveis_climaticas(extrair_clima_mensal(df), df.latitude)
    return pd.concat([df, clima], axis=1)


def main():
    print(f'GEE: {conectar(None)}')
    soc_cls, tex_cls = carregar_bases()
    cls_cols = ['ponto_id', 'longitude', 'latitude'] + leg.COLUNAS_CLIMA
    print('[SOC] matriz completa...')
    soc = montar(matriz_soc(), soc_cls[cls_cols + ['soc_g_m2']])
    soc.to_parquet(DADOS / 'exp_soc.parquet', index=False)
    print('[Textura] matriz completa...')
    tex = montar(matriz_textura(), tex_cls[cls_cols + FRACOES].rename(columns={f: f + '_alvo' for f in FRACOES}))
    tex.to_parquet(DADOS / 'exp_textura.parquet', index=False)
    print(f'SOC: {soc.shape} | Textura: {tex.shape}')


def carregar_experimento():
    return pd.read_parquet(DADOS / 'exp_soc.parquet'), pd.read_parquet(DADOS / 'exp_textura.parquet')


if __name__ == '__main__':
    main()
