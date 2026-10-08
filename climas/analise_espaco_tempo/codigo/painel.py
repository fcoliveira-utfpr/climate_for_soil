"""Etapa 3: painel de predição local × ano, 1985-2024 (painel_soc_c3_fabricio_1985_2024, §3.4 do plano).

Locais de amostras reais (sem pseudoamostras; as réplicas trep estão nos mesmos locais). As estáticas
(covariaveis_c3.ESTATICAS) são extraídas uma vez por local e as dinâmicas (covariaveis_c3.DINAMICAS) em
cada ano; como no mapa da produção, profundidade = 30 e os índices (IFN, YEAR, PSEUDO*) = 0.

Uso:
    python painel.py exportar     # 1 tarefa de estáticas + 40 de dinâmicas (assets em SOC_C3_FABRICIO/painel)
    python painel.py baixar       # junta tudo em climas/dados_espaco_tempo/painel_soc_c3_fabricio_1985_2024.parquet
"""
import sys

import ee
import pandas as pd
from scipy.spatial import cKDTree

import config as cfg
import covariaveis_c3 as c3
from gee_utils import conectar
from preparar_dados import baixar_featurecollection

PASTA = f'{cfg.PASTA_GEE}/painel'
ANOS = range(1985, 2025)


def _locais_gee():
    pts = ee.FeatureCollection(cfg.ASSET_PONTOS).filter(ee.Filter.And(
        ee.Filter.eq('PSEUDOROCK_index', 0), ee.Filter.eq('PSEUDOSAND_index', 0)))
    # um ponto por local (as profundidades e réplicas repetem a geometria)
    return pts.map(lambda f: f.set('chave', f.geometry().coordinates())).distinct('chave').select([])


def exportar():
    try:
        ee.data.getAsset(PASTA)
    except ee.EEException:
        ee.data.createAsset({'type': 'FOLDER'}, PASTA)
    loc = _locais_gee()
    tarefas = [('estaticas', c3.estaticas().select(c3.ESTATICAS).round())]
    tarefas += [(f'dinamicas_{a}', c3.dinamicas(a).select(c3.DINAMICAS).round()) for a in ANOS]
    for nome, img in tarefas:
        t = ee.batch.Export.table.toAsset(
            collection=img.sampleRegions(collection=loc, scale=30, geometries=True),
            description=f'painel_{nome}', assetId=f'{PASTA}/{nome}')
        t.start()
        print(f'  {nome}: {t.id}', flush=True)


TOLERANCIA = 2e-4          # graus (~20 m)


def _casar(df, originais, arvore):
    """sampleRegions devolve a geometria no centro do pixel da imagem amostrada (~5 m do ponto, e em grades
    diferentes nas estáticas e nas dinâmicas); cada linha recebe o ponto_id do local original mais próximo."""
    dist, i = arvore.query(df[['longitude', 'latitude']].to_numpy())
    if dist.max() > TOLERANCIA or pd.Series(i).duplicated().any():
        raise ValueError(f'casamento ambíguo: distância máx. {dist.max():.2e}°')
    df['ponto_id'] = originais.ponto_id.to_numpy()[i]
    return df.drop(columns=['longitude', 'latitude', 'system:index'], errors='ignore')


def baixar():
    originais = pd.read_parquet(cfg.DADOS / 'climas_locais.parquet', columns=['ponto_id'])
    originais[['longitude', 'latitude']] = originais.ponto_id.str.split('_', expand=True).astype(float)
    arvore = cKDTree(originais[['longitude', 'latitude']].to_numpy())
    est = _casar(baixar_featurecollection(f'{PASTA}/estaticas'), originais, arvore)
    partes = []
    for a in ANOS:
        d = _casar(baixar_featurecollection(f'{PASTA}/dinamicas_{a}'), originais, arvore)
        d['year'] = a
        partes.append(d)
    painel = pd.concat(partes, ignore_index=True).merge(est, on='ponto_id', how='inner')
    painel = painel.merge(originais, on='ponto_id')
    painel['profundidade'] = 30
    for c in ('IFN_index', 'YEAR_index', 'PSEUDOROCK_index', 'PSEUDOSAND_index'):
        painel[c] = 0
    cfg.DADOS.mkdir(parents=True, exist_ok=True)
    painel.to_parquet(cfg.PAINEL, index=False)
    print(f'{painel.ponto_id.nunique()} locais x {painel.year.nunique()} anos = {len(painel)} linhas -> {cfg.PAINEL}')


if __name__ == '__main__':
    conectar(None)
    etapa = sys.argv[1] if len(sys.argv) > 1 else ''
    {'exportar': exportar, 'baixar': baixar}.get(etapa, lambda: print(__doc__))()
