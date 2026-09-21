"""Preparacao auditavel das duas matrizes de treino do Earth Engine (acesso restrito,
liberado para esta conta - ver docs/assets.md). Holdridge nao vem das matrizes: vem de
uma extracao a parte com legenda confirmada (clima_legendas.py)."""
import hashlib
import json
import time
from datetime import datetime, timezone
from pathlib import Path

import ee
import numpy as np
import pandas as pd

from gee_utils import conectar
from clima_legendas import HOLDRIDGE, HLZ_L2_LEGENDA, HLZ_L1_LEGENDA, HLZ_L2_PARA_L1

ROOT = Path(__file__).resolve().parents[1]
DADOS = ROOT / '.local' / 'dados'
RES = ROOT / '.local' / 'resultados'
PUBLIC = ROOT / 'resultados'
FRACOES = ['areia', 'silte', 'argila']
CLIMAS = ['koppen_l1', 'koppen_l2', 'koppen_l3', 'HLZ_L1', 'HLZ_L2']
NIVEIS_KOPPEN = ['koppen_l1', 'koppen_l2', 'koppen_l3']

MATRIZ_SOC = 'projects/mapbiomas-workspace/SOLOS/AMOSTRAS/MATRIZES/collection3/matriz-collection3_carbon_datac2v2'
MATRIZ_TEXTURA = 'projects/mapbiomas-workspace/SOLOS/AMOSTRAS/MATRIZES/collection3/c03_psd_v2025_11_18'


def ponto_id(df):
    return df.longitude.round(6).astype(str) + '_' + df.latitude.round(6).astype(str)


def coordenadas_validas(df):
    """Graus geograficos: jamais corrigir escala decimal por suposicao."""
    return df.longitude.between(-180, 180) & df.latitude.between(-90, 90)


def baixar_featurecollection(asset_id, tamanho_pagina=2000):
    """Baixa uma FeatureCollection inteira paginando por nextPageToken (evita o
    limite de payload de getInfo/ee_to_df numa matriz deste tamanho)."""
    linhas, token, pagina, t0 = [], None, 0, time.time()
    while True:
        params = {'assetId': asset_id, 'pageSize': tamanho_pagina}
        if token:
            params['pageToken'] = token
        resp = ee.data.listFeatures(params)
        feicoes = resp.get('features', [])
        for f in feicoes:
            props = dict(f.get('properties', {}))
            geom = f.get('geometry')
            if geom and geom.get('type') == 'Point':
                props['longitude'], props['latitude'] = geom['coordinates'][:2]
            linhas.append(props)
        pagina += 1
        token = resp.get('nextPageToken')
        print(f'  pagina {pagina:>3}: {len(linhas):>6} linhas ({time.time()-t0:5.1f}s)', flush=True)
        if not token or not feicoes:
            break
    return pd.DataFrame(linhas)


def decodificar_koppen(df):
    """Converte as dummies koppen_l1_*/l2_*/l3_* (nativas nas duas matrizes) em colunas categoricas."""
    out = {}
    for nivel in NIVEIS_KOPPEN:
        prefixo = nivel + '_'
        cols = [c for c in df.columns if c.startswith(prefixo)]
        bloco = df[cols].astype(float)
        valid = bloco.notna().all(axis=1) & bloco.isin([0, 1]).all(axis=1) & bloco.sum(axis=1).eq(1)
        rot = pd.Series(pd.NA, index=df.index, dtype='string')
        rot.loc[valid] = bloco.loc[valid].idxmax(axis=1).str.removeprefix(prefixo)
        out[nivel] = rot
    return pd.DataFrame(out)


def extrair_holdridge(df, bloco=3000, workers=3):
    """Amostra holdridge_lifezones_chelsa-v2026 (zone38_id) em cada ponto e decodifica
    HLZ_L1/L2 com a legenda confirmada na propria descricao do asset."""
    from concurrent.futures import ThreadPoolExecutor, as_completed
    img = ee.Image(HOLDRIDGE).select('zone38_id').rename('zone38_id')

    def parte(ini):
        sub = df.iloc[ini:ini + bloco]
        pts = [ee.Feature(ee.Geometry.Point([r.longitude, r.latitude]), {'idx': int(r.Index)})
               for r in sub.itertuples()]
        amostra = img.reduceRegions(ee.FeatureCollection(pts), ee.Reducer.first(),
                                    scale=1000, crs='EPSG:4326', tileScale=4)
        resp = amostra.getInfo()['features']
        # reduceRegions com imagem de 1 banda nomeia a saida 'first', nao o nome da banda.
        out = pd.DataFrame([f['properties'] for f in resp]).set_index('idx')
        return out.rename(columns={'first': 'zone38_id'})

    partes = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(parte, ini) for ini in range(0, len(df), bloco)]
        for fut in as_completed(futures):
            partes.append(fut.result())
            print(f'  holdridge: {sum(len(p) for p in partes):>6}/{len(df)}', flush=True)
    codigos = pd.concat(partes).sort_index()['zone38_id'].reindex(range(len(df)))
    hlz_l2 = codigos.map(HLZ_L2_LEGENDA)
    hlz_l1 = codigos.map(HLZ_L2_PARA_L1).map(HLZ_L1_LEGENDA)
    return hlz_l1.astype('string').to_numpy(), hlz_l2.astype('string').to_numpy()


def preparar_carbono():
    print('[SOC] Baixando matriz-collection3_carbon_datac2v2...')
    df = baixar_featurecollection(MATRIZ_SOC)
    n_bruto = len(df)
    df['ponto_id'] = ponto_id(df)

    pseudo = df.PSEUDO_index.astype(float).eq(1)
    valid = np.isfinite(df[['longitude', 'latitude', 'soc_stock_g_m2']].astype(float)).all(axis=1)
    valid &= (df.soc_stock_g_m2.astype(float) >= 0)
    valid &= coordenadas_validas(df)
    take = df[~pseudo & valid].copy()

    koppen = decodificar_koppen(take)
    take = pd.concat([take[['ponto_id', 'longitude', 'latitude', 'soc_stock_g_m2', 'elevation', 'year']], koppen], axis=1)
    take['soc_g_m2'] = take.soc_stock_g_m2.astype(float)
    take['elevation'] = take.elevation.astype(float)

    # pseudo-replicacao: mesma coordenada aparece uma vez por ano (ate ~40x); mediana por ponto.
    agg = {'longitude': 'first', 'latitude': 'first', 'soc_g_m2': 'median', 'elevation': 'median'}
    agg.update({n: 'first' for n in NIVEIS_KOPPEN})
    pontos = take.groupby('ponto_id', as_index=False).agg(agg)

    info = {'linhas_brutas': n_bruto, 'pseudoamostras_excluidas': int(pseudo.sum()),
            'invalidas_excluidas': int((~pseudo & ~valid).sum()), 'pontos_validos': len(pontos)}
    print(f'  linhas brutas ............. {n_bruto}')
    print(f'  pseudoamostras excluidas .. {info["pseudoamostras_excluidas"]}')
    print(f'  linhas invalidas excluidas  {info["invalidas_excluidas"]}')
    print(f'  pontos unicos (agregados) . {len(pontos)}')

    print('[SOC] Extraindo Holdridge confirmado...')
    pontos = pontos.reset_index(drop=True)
    pontos['HLZ_L1'], pontos['HLZ_L2'] = extrair_holdridge(pontos)

    return pontos, info


def preparar_textura():
    print('[Textura] Baixando c03_psd_v2025_11_18...')
    df = baixar_featurecollection(MATRIZ_TEXTURA)
    n_bruto = len(df)
    df['ponto_id'] = ponto_id(df)

    artificial = df.id.astype(str).str.contains('pseudo', case=False, regex=False) | df.id.astype(str).str.startswith('clay-copy-')
    profundidade = pd.to_numeric(df.profundidade, errors='coerce')
    fracoes = df[FRACOES].astype(float)
    valid = coordenadas_validas(df) & profundidade.le(30) & profundidade.gt(0)
    valid &= np.isfinite(fracoes.to_numpy()).all(axis=1) & (fracoes >= 0).all(axis=1)
    valid &= np.isclose(fracoes.sum(axis=1), 1000, atol=15)  # g/kg fecham ~1000; tolerancia de arredondamento
    take = df[~artificial & valid].copy()

    koppen = decodificar_koppen(take)
    take = pd.concat([take[['ponto_id', 'longitude', 'latitude', 'elevation']].reset_index(drop=True),
                      (fracoes.loc[take.index] / 10.0).reset_index(drop=True), koppen.reset_index(drop=True)], axis=1)
    take['elevation'] = pd.to_numeric(take.elevation, errors='coerce')

    agg = {'longitude': 'first', 'latitude': 'first', 'elevation': 'median',
          **{f: 'median' for f in FRACOES}}
    agg.update({n: 'first' for n in NIVEIS_KOPPEN})
    pontos = take.groupby('ponto_id', as_index=False).agg(agg)

    # Pontos com mais de um horizonte em 0-30cm: a mediana por fracao, tomada coluna a
    # coluna, pode nao fechar 100% mesmo que cada linha original fechasse. Exigir o
    # fechamento tambem depois de agregar.
    n_antes_fechamento = len(pontos)
    fechamento = (pontos[FRACOES].sum(axis=1) - 100).abs()
    pontos = pontos[fechamento <= 1].reset_index(drop=True)

    info = {'linhas_brutas': n_bruto, 'amostras_artificiais': int(artificial.sum()),
            'fora_camada_ou_invalidas': int((~artificial & ~valid).sum()),
            'pontos_agregados_sem_fechar': n_antes_fechamento - len(pontos), 'pontos_validos': len(pontos)}
    print(f'  linhas brutas ............. {n_bruto}')
    print(f'  amostras artificiais ...... {info["amostras_artificiais"]}')
    print(f'  fora de 0-30cm/invalidas .. {info["fora_camada_ou_invalidas"]}')
    print(f'  agregados sem fechar 100% . {info["pontos_agregados_sem_fechar"]}')
    print(f'  pontos unicos (agregados) . {len(pontos)}')

    print('[Textura] Extraindo Holdridge confirmado...')
    pontos = pontos.reset_index(drop=True)
    pontos['HLZ_L1'], pontos['HLZ_L2'] = extrair_holdridge(pontos)

    return pontos, info


def main():
    DADOS.mkdir(parents=True, exist_ok=True)
    RES.mkdir(parents=True, exist_ok=True)
    projeto = conectar(None)
    print(f'Autenticado ({projeto})\n')
    soc, info_soc = preparar_carbono()
    soc.to_parquet(DADOS / 'soc.parquet', index=False)
    print()
    tex, info_tex = preparar_textura()
    tex.to_parquet(DADOS / 'textura.parquet', index=False)

    joint = tex.merge(soc[['ponto_id', 'soc_g_m2']], on='ponto_id', how='inner')
    joint = joint[joint.soc_g_m2 > 0].reset_index(drop=True)
    joint.to_parquet(DADOS / 'joint.parquet', index=False)

    info = {'gerado_em': datetime.now(timezone.utc).isoformat(),
           'assets': {'soc': MATRIZ_SOC, 'textura': MATRIZ_TEXTURA, 'holdridge': HOLDRIDGE},
           'textura': info_tex, 'carbono': info_soc, 'pontos_para_extracao': len(joint),
           'n_textura': len(tex), 'n_carbono': len(soc), 'n_pareados': len(joint)}
    (RES / 'preparacao.json').write_text(json.dumps(info, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f"\nSOC: {len(soc)} pontos | Textura: {len(tex)} pontos | Pareados: {len(joint)}")


def carregar_bases():
    """Uma linha por local; tex/soc/joint com as mesmas colunas de nivel climatico."""
    tex = pd.read_parquet(DADOS / 'textura.parquet')
    soc = pd.read_parquet(DADOS / 'soc.parquet')
    joint = pd.read_parquet(DADOS / 'joint.parquet')
    if not all(coordenadas_validas(x).all() for x in (tex, soc)):
        raise ValueError('Coordenadas fora dos limites geograficos; execute preparar_dados.py.')
    return tex, soc, joint


if __name__ == '__main__':
    main()
