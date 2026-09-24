"""Baixa as duas matrizes de pontos do MapBiomas Solo C3 (acesso restrito, liberado para a conta
fcoliveira), limpa, agrega por local e amostra os climas comparados em cada ponto.

Saída (fora do git, dados restritos): .local/dados/soc.parquet e .local/dados/textura.parquet,
uma linha por local, com a variável-resposta e uma coluna de classe por sistema/nível
(legendas.COLUNAS_CLIMA).
"""
import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

import ee
import numpy as np
import pandas as pd

import legendas as leg
from gee_utils import conectar

ROOT = Path(__file__).resolve().parents[1]
DADOS = ROOT / '.local' / 'dados'
FRACOES = ['areia', 'silte', 'argila']
NIVEIS_IPEF = ['koppen_l1', 'koppen_l2', 'koppen_l3']

MATRIZ_SOC = 'projects/mapbiomas-workspace/SOLOS/AMOSTRAS/MATRIZES/collection3/matriz-collection3_carbon_datac2v2'
MATRIZ_TEXTURA = 'projects/mapbiomas-workspace/SOLOS/AMOSTRAS/MATRIZES/collection3/c03_psd_v2025_11_18'


# ---------------------------------------------------------------------------------------------
# Download e limpeza das matrizes
# ---------------------------------------------------------------------------------------------
def ponto_id(df):
    return df.longitude.round(6).astype(str) + '_' + df.latitude.round(6).astype(str)


def coordenadas_validas(df):
    """Graus geográficos: jamais corrigir escala decimal por suposição."""
    return df.longitude.between(-180, 180) & df.latitude.between(-90, 90)


def baixar_featurecollection(asset_id, tamanho_pagina=2000):
    """Baixa uma FeatureCollection inteira paginando por nextPageToken (evita o limite de
    payload de getInfo numa matriz deste tamanho)."""
    linhas, token, t0 = [], None, time.time()
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
        token = resp.get('nextPageToken')
        print(f'  {len(linhas):>6} linhas ({time.time() - t0:5.1f}s)', flush=True)
        if not token or not feicoes:
            break
    return pd.DataFrame(linhas)


def decodificar_koppen_ipef(df):
    """Converte as dummies koppen_l1_*/l2_*/l3_* (Köppen IPEF, nativas nas duas matrizes) em
    colunas categóricas koppen_ipef_l1/l2/l3."""
    out = {}
    for nivel in NIVEIS_IPEF:
        prefixo = nivel + '_'
        cols = [c for c in df.columns if c.startswith(prefixo)]
        bloco = df[cols].astype(float)
        valid = bloco.notna().all(axis=1) & bloco.isin([0, 1]).all(axis=1) & bloco.sum(axis=1).eq(1)
        rot = pd.Series(pd.NA, index=df.index, dtype='string')
        rot.loc[valid] = bloco.loc[valid].idxmax(axis=1).str.removeprefix(prefixo)
        out['koppen_ipef_' + nivel[-2:]] = rot
    return pd.DataFrame(out)


def preparar_carbono():
    print('[SOC] Baixando matriz-collection3_carbon_datac2v2...')
    df = baixar_featurecollection(MATRIZ_SOC)
    n_bruto = len(df)
    df['ponto_id'] = ponto_id(df)

    pseudo = df.PSEUDO_index.astype(float).eq(1)
    valid = np.isfinite(df[['longitude', 'latitude', 'soc_stock_g_m2']].astype(float)).all(axis=1)
    valid &= df.soc_stock_g_m2.astype(float) > 0          # log(SOC) exige SOC > 0
    valid &= coordenadas_validas(df)
    take = df[~pseudo & valid].copy()

    take = pd.concat([take[['ponto_id', 'longitude', 'latitude']],
                      take.soc_stock_g_m2.astype(float).rename('soc_g_m2'),
                      decodificar_koppen_ipef(take)], axis=1)
    # pseudo-replicação: a mesma coordenada aparece uma vez por ano (até ~40x); mediana por ponto.
    agg = {'longitude': 'first', 'latitude': 'first', 'soc_g_m2': 'median',
           **{c: 'first' for c in ('koppen_ipef_l1', 'koppen_ipef_l2', 'koppen_ipef_l3')}}
    pontos = take.groupby('ponto_id', as_index=False).agg(agg)

    info = {'linhas_brutas': n_bruto, 'pseudoamostras_excluidas': int(pseudo.sum()),
            'invalidas_excluidas': int((~pseudo & ~valid).sum()), 'locais': len(pontos)}
    print(f'  {info}')
    return pontos, info


def preparar_textura():
    print('[Textura] Baixando c03_psd_v2025_11_18...')
    df = baixar_featurecollection(MATRIZ_TEXTURA)
    n_bruto = len(df)
    df['ponto_id'] = ponto_id(df)

    artificial = (df.id.astype(str).str.contains('pseudo', case=False, regex=False)
                  | df.id.astype(str).str.startswith('clay-copy-'))
    profundidade = pd.to_numeric(df.profundidade, errors='coerce')
    fracoes = df[FRACOES].astype(float)
    valid = coordenadas_validas(df) & profundidade.le(30) & profundidade.gt(0)
    valid &= np.isfinite(fracoes.to_numpy()).all(axis=1) & (fracoes >= 0).all(axis=1)
    valid &= np.isclose(fracoes.sum(axis=1), 1000, atol=15)  # g/kg fecham ~1000
    take = df[~artificial & valid].copy()

    take = pd.concat([take[['ponto_id', 'longitude', 'latitude']].reset_index(drop=True),
                      (fracoes.loc[take.index] / 10.0).reset_index(drop=True),   # g/kg -> %
                      decodificar_koppen_ipef(take).reset_index(drop=True)], axis=1)
    agg = {'longitude': 'first', 'latitude': 'first', **{f: 'median' for f in FRACOES},
           **{c: 'first' for c in ('koppen_ipef_l1', 'koppen_ipef_l2', 'koppen_ipef_l3')}}
    pontos = take.groupby('ponto_id', as_index=False).agg(agg)

    # Com mais de um horizonte em 0-30 cm, a mediana coluna a coluna pode não fechar 100%.
    n_antes = len(pontos)
    pontos = pontos[(pontos[FRACOES].sum(axis=1) - 100).abs() <= 1].reset_index(drop=True)

    info = {'linhas_brutas': n_bruto, 'amostras_artificiais': int(artificial.sum()),
            'fora_camada_ou_invalidas': int((~artificial & ~valid).sum()),
            'agregados_sem_fechar_100': n_antes - len(pontos), 'locais': len(pontos)}
    print(f'  {info}')
    return pontos, info


# ---------------------------------------------------------------------------------------------
# Climas CHELSA nos pontos
# ---------------------------------------------------------------------------------------------
BANDAS_TH = ['umidade', 'subtipo', 'termica', 'concentracao']  # b1-b4 dos assets de Thornthwaite


def imagem_climas():
    """Os assets novos numa imagem só (mesma grade CHELSA, ~928 m), mais a temperatura do
    mês mais frio (critério da fronteira A/C do Köppen, usada no diagnóstico)."""
    th100 = ee.Image(leg.ASSET_TH100).select([0, 1, 2, 3], [f'th100_{b}' for b in BANDAS_TH])
    thsolo = ee.Image(leg.ASSET_THSOLO).select([0, 1, 2, 3], [f'thsolo_{b}' for b in BANDAS_TH])
    return (ee.Image(leg.ASSET_KOPPEN).select([0], ['koppen_chelsa'])
            .addBands(ee.Image(leg.ASSET_HOLDRIDGE_ETPM).select([0], ['holdridge_etpm']))
            .addBands(ee.Image(leg.ASSET_HOLDRIDGE_ETH).select([0], ['holdridge_eth']))
            .addBands(th100).addBands(thsolo)
            .addBands(ee.Image(leg.ASSET_TAS).reduce(ee.Reducer.min()).rename('tas_mes_mais_frio')))


def extrair_climas(df, bloco=3000, workers=3):
    """Valor de cada banda no pixel de cada ponto, na grade nativa dos assets (sem reamostrar)."""
    img = imagem_climas()
    proj = ee.Image(leg.ASSET_HOLDRIDGE_ETPM).projection().getInfo()
    bandas = img.bandNames().getInfo()

    def parte(ini):
        sub = df.iloc[ini:ini + bloco]
        pts = [ee.Feature(ee.Geometry.Point([r.longitude, r.latitude]), {'idx': int(r.Index)})
               for r in sub.itertuples()]
        amostra = img.reduceRegions(ee.FeatureCollection(pts), ee.Reducer.first(),
                                    crs=proj['crs'], crsTransform=proj['transform'], tileScale=4)
        return pd.DataFrame([f['properties'] for f in amostra.getInfo()['features']]).set_index('idx')

    partes = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for fut in as_completed([pool.submit(parte, i) for i in range(0, len(df), bloco)]):
            partes.append(fut.result())
            print(f'  climas: {sum(len(p) for p in partes):>6}/{len(df)}', flush=True)
    return pd.concat(partes).reindex(range(len(df)))[bandas]


def classes_climaticas(cod):
    """Códigos numéricos dos assets -> uma coluna de classe (texto) por sistema/nível."""
    def mapa(serie, dic):
        return serie.round().astype('Int64').map(dic).astype('string')

    out = pd.DataFrame(index=cod.index)
    kp = mapa(cod.koppen_chelsa, leg.KOPPEN)
    out['koppen_chelsa_l1'] = kp.str[0]
    out['koppen_chelsa_l2'] = kp.str[:2]
    out['koppen_chelsa_l3'] = kp
    out['holdridge_l1'] = mapa(cod.holdridge_etpm, leg.HOLDRIDGE_L1)
    out['holdridge_etpm_l2'] = mapa(cod.holdridge_etpm, leg.HOLDRIDGE_L2)
    out['holdridge_eth_l2'] = mapa(cod.holdridge_eth, leg.HOLDRIDGE_L2)
    for v in ('th100', 'thsolo'):
        u = mapa(cod[f'{v}_umidade'], leg.TH_UMIDADE)
        s = mapa(cod[f'{v}_subtipo'], leg.TH_SUBTIPO)
        t = mapa(cod[f'{v}_termica'], leg.TH_TERMICA)
        c = mapa(cod[f'{v}_concentracao'], leg.TH_CONCENTRACAO)
        out[f'{v}_l1'] = u
        out[f'{v}_l2'] = u + s
        out[f'{v}_l3'] = u + s + t + c
    return out


def com_climas(pontos):
    pontos = pontos.reset_index(drop=True)
    cod = extrair_climas(pontos)
    return pd.concat([pontos, classes_climaticas(cod), cod[['tas_mes_mais_frio']]], axis=1)


def main():
    DADOS.mkdir(parents=True, exist_ok=True)
    print(f'GEE: {conectar(None)}\n')
    soc, info_soc = preparar_carbono()
    soc = com_climas(soc)
    soc.to_parquet(DADOS / 'soc.parquet', index=False)
    print()
    tex, info_tex = preparar_textura()
    tex = com_climas(tex)
    tex.to_parquet(DADOS / 'textura.parquet', index=False)

    info = {'gerado_em': datetime.now(timezone.utc).isoformat(),
            'assets': {'soc': MATRIZ_SOC, 'textura': MATRIZ_TEXTURA, 'koppen_chelsa': leg.ASSET_KOPPEN,
                       'holdridge_etpm': leg.ASSET_HOLDRIDGE_ETPM, 'holdridge_eth': leg.ASSET_HOLDRIDGE_ETH, 'thornthwaite_cad100': leg.ASSET_TH100,
                       'thornthwaite_cadsolo': leg.ASSET_THSOLO},
            'soc': info_soc, 'textura': info_tex}
    (DADOS / 'preparacao.json').write_text(json.dumps(info, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'\nSOC: {len(soc)} locais | Textura: {len(tex)} locais')


def completar_ipef_l3(df):
    """No Köppen IPEF o nível 3 só existe para B e C (Bsh, Cfa...); no grupo A o tipo (Af, Am,
    As, Aw) já é a classe completa. Completa o L3 com o L2 para ficar equivalente ao L3 do
    Köppen CHELSA e não perder os locais do grupo A na amostra comum."""
    df = df.copy()
    df['koppen_ipef_l3'] = df.koppen_ipef_l3.fillna(df.koppen_ipef_l2.where(df.koppen_ipef_l1 == 'A'))
    return df


def carregar_bases():
    return tuple(completar_ipef_l3(pd.read_parquet(DADOS / f'{b}.parquet')) for b in ('soc', 'textura'))


if __name__ == '__main__':
    main()
