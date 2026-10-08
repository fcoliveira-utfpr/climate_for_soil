"""Etapa 7f: camadas do pós-processamento do mapa oficial de SOC (carbon/2_model_prediction) nos locais do
painel: uso da terra da Coleção 10 (1985-2024), grupo textural da C3 (0-30 cm) e máscara de areia histórica.

No mapa oficial: SOC = 0 onde o uso é 23 (dunas, praias), 24 (urbano) ou 30 (mineração) ou o grupo textural
é 1; SOC = 10 t/ha onde MB_2024_SANDMASK = 1; 1985-1987 = mediana de 1985-1989 onde o uso foi estável nesses
cinco anos; tudo arredondado para t/ha inteiras.

A máscara de areia (MB_2024_SANDMASK) não abre nesta conta; os pontos dentro dela são os que têm exatamente
10 t/ha no mapa oficial.

Saída (restrita): climas/dados_espaco_tempo/mascaras_mapa.parquet (ponto_id, year, lulc, textura_grupo).

Uso: python mascaras_mapa.py
"""
from concurrent.futures import ThreadPoolExecutor

import ee
import pandas as pd

import config as cfg
from gee_utils import conectar

LULC = 'projects/mapbiomas-public/assets/brazil/lulc/collection10/mapbiomas_brazil_collection10_integration_v2'
TEXTURA = 'projects/mapbiomas-workspace/SOLOS/PRODUTOS_C03/mapbiomas_soil_collection3_textural_group'
SAND = 'projects/mapbiomas-workspace/SOLOS/COVARIAVEIS/MB_2024_SANDMASK'


def extrair(bloco=2000, workers=3):
    loc = pd.read_parquet(cfg.PAINEL, columns=['ponto_id', 'longitude', 'latitude']).drop_duplicates('ponto_id')
    img = ee.Image.cat([ee.Image(LULC),
                        ee.Image(TEXTURA).select(['textural_group_000_030cm'], ['textura_grupo'])])

    def parte(ini):
        sub = loc.iloc[ini:ini + bloco]
        fc = ee.FeatureCollection([ee.Feature(ee.Geometry.Point([r.longitude, r.latitude]), {'ponto_id': r.ponto_id})
                                   for r in sub.itertuples()])
        res = img.reduceRegions(fc, ee.Reducer.first(), scale=30).getInfo()['features']
        return pd.DataFrame([f['properties'] for f in res])

    with ThreadPoolExecutor(max_workers=workers) as pool:
        largo = pd.concat(pool.map(parte, range(0, len(loc), bloco)), ignore_index=True)
    fixo = largo[['ponto_id', 'textura_grupo']]
    lulc = largo.melt(id_vars='ponto_id', value_vars=[c for c in largo if c.startswith('classification_')],
                      var_name='banda', value_name='lulc')
    lulc['year'] = lulc.banda.str.replace('classification_', '').astype(int)
    return lulc.drop(columns='banda').merge(fixo, on='ponto_id')


if __name__ == '__main__':
    conectar(None)
    d = extrair()
    d.to_parquet(cfg.DADOS / 'mascaras_mapa.parquet', index=False)
    print(f'{d.ponto_id.nunique()} locais x {d.year.nunique()} anos')
    print('uso 23/24/30:', d.lulc.isin([23, 24, 30]).mean().round(4), '| textura grupo 1:',
          (d.drop_duplicates('ponto_id').textura_grupo == 1).mean().round(4))
