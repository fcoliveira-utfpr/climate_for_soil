"""Etapa 7a: SOC oficial do MapBiomas Solo C3 (0-30 cm, t/ha, bandas carbon_1985 ... carbon_2024) nos locais
do painel, para conferir as trajetórias previstas (§5.1 do plano).

Saída (restrita): climas/dados_espaco_tempo/soc_oficial_c3.parquet (ponto_id, year, soc_oficial_t_ha).

Uso: python soc_oficial.py
"""
from concurrent.futures import ThreadPoolExecutor

import ee
import pandas as pd

import config as cfg
from gee_utils import conectar

SOC_OFICIAL = 'projects/mapbiomas-workspace/SOLOS/PRODUTOS_C03/mapbiomas_soil_collection3_soc_t_ha_000_030cm'


def extrair(bloco=2000, workers=3):
    loc = pd.read_parquet(cfg.PAINEL, columns=['ponto_id', 'longitude', 'latitude']).drop_duplicates('ponto_id')
    img = ee.Image(SOC_OFICIAL)

    def parte(ini):
        sub = loc.iloc[ini:ini + bloco]
        fc = ee.FeatureCollection([ee.Feature(ee.Geometry.Point([r.longitude, r.latitude]), {'ponto_id': r.ponto_id})
                                   for r in sub.itertuples()])
        res = img.reduceRegions(fc, ee.Reducer.first(), scale=30).getInfo()['features']
        return pd.DataFrame([f['properties'] for f in res])

    with ThreadPoolExecutor(max_workers=workers) as pool:
        largo = pd.concat(pool.map(parte, range(0, len(loc), bloco)), ignore_index=True)
    longo = largo.melt(id_vars='ponto_id', var_name='banda', value_name='soc_oficial_t_ha')
    longo['year'] = longo.banda.str.replace('carbon_', '').astype(int)
    return longo.drop(columns='banda')


if __name__ == '__main__':
    conectar(None)
    soc = extrair()
    soc.to_parquet(cfg.DADOS / 'soc_oficial_c3.parquet', index=False)
    print(f'{soc.ponto_id.nunique()} locais x {soc.year.nunique()} anos; sem valor: {soc.soc_oficial_t_ha.isna().mean():.2%}')
    print(soc.groupby('year').soc_oficial_t_ha.mean().round(2).to_string())
