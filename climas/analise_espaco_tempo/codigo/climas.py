"""Etapa 4: climas dos cenários nos locais da matriz e do painel.

- Estáticos, por local (normais 1991-2020): classes de todos os sistemas (Köppen, Holdridge, Thornthwaite;
  as mesmas funções da corelacao), as 12 variáveis do clima contínuo (CHELSA + BHC) e a zona k10.
- Decenais, por local e ano de 1985 a 2024: temperatura e chuva do GT de clima do MapBiomas Solo
  (GT_DECADE_*_CONTI_2026) e o CDD calculado do Xavier (cdd_brdwgd.py). A imagem do ano Y é a média de
  Y-10 a Y-1; serve à matriz (ano de cada linha) e ao painel (todos os anos).

Saídas (restritas, fora do git): climas/dados_espaco_tempo/climas_locais.parquet e climas_decenais.parquet,
com a chave ponto_id (longitude_latitude com 6 casas, como na corelacao).

Uso: python climas.py
"""
from concurrent.futures import ThreadPoolExecutor

import ee
import pandas as pd

import config as cfg
import experimento_dados as ed          # corelacao/codigo
import legendas as leg                  # corelacao/codigo
import zonas_clima as zc                # corelacao/codigo
from gee_utils import conectar          # corelacao/codigo
from preparar_dados import baixar_featurecollection, com_climas, coordenadas_validas, ponto_id

COV = 'projects/mapbiomas-workspace/SOLOS/COVARIAVEIS/'
DECENAIS = {   # nome da coluna: (coleção, banda)
    'dec_tmean': (COV + 'GT_DECADE_TMEAN_CONTI_2026', 'tmean_10yr_mean'),
    'dec_prec': (COV + 'GT_DECADE_PRECIPITATION_CONTI_2026', 'prec_10yr_mean'),
    'dec_cdd': ('projects/fcoliveira/assets/Climas2/CDD_DECENAL_BRDWGD', 'cdd_10yr_mean'),
}
ANOS = range(1985, 2025)
ESCALA_DECENAL = 11132          # 0,1°, a grade do Xavier


def locais():
    pts = baixar_featurecollection(cfg.ASSET_PONTOS)
    pts = pts[coordenadas_validas(pts)].copy()
    pts['ponto_id'] = ponto_id(pts)
    return pts[['ponto_id', 'longitude', 'latitude']].drop_duplicates('ponto_id').reset_index(drop=True)


def estaticos(loc):
    """Igual a climas_soc() da reprodução: classes, clima contínuo e zona k10."""
    cls = com_climas(loc)
    cont = ed.variaveis_climaticas(ed.extrair_clima_mensal(loc), loc.latitude)
    cl = pd.concat([cls[['ponto_id'] + [c for c in leg.COLUNAS_CLIMA if c in cls.columns]], cont], axis=1)
    ok = cl[cfg.CLIMA_CONTINUO].notna().all(axis=1)
    cent, media, dp = zc.carregar(10)
    cl['zona_k10'] = pd.Series(pd.NA, index=cl.index, dtype='string')
    cl.loc[ok, 'zona_k10'] = zc.atribuir(cl[ok], cent, media, dp).astype(str)
    return cl


def _imagem_decenal():
    """Uma banda por variável e ano: dec_tmean_1985, ..., dec_cdd_2024."""
    bandas = []
    for nome, (col, banda) in DECENAIS.items():
        ic = ee.ImageCollection(col)
        bandas += [ee.Image(ic.filter(ee.Filter.eq('year', a)).first()).select([banda], [f'{nome}_{a}'])
                   for a in ANOS]
    return ee.Image.cat(bandas)


def decenais(loc, bloco=2000, workers=3):
    img = _imagem_decenal()

    def parte(ini):
        sub = loc.iloc[ini:ini + bloco]
        fc = ee.FeatureCollection([ee.Feature(ee.Geometry.Point([r.longitude, r.latitude]), {'ponto_id': r.ponto_id})
                                   for r in sub.itertuples()])
        res = img.reduceRegions(fc, ee.Reducer.first(), scale=ESCALA_DECENAL).getInfo()['features']
        return pd.DataFrame([f['properties'] for f in res])

    with ThreadPoolExecutor(max_workers=workers) as pool:
        largo = pd.concat(pool.map(parte, range(0, len(loc), bloco)), ignore_index=True)
    longo = largo.melt(id_vars='ponto_id', var_name='banda', value_name='valor')
    longo[['variavel', 'ano']] = longo.banda.str.rsplit('_', n=1, expand=True)
    longo['ano'] = longo.ano.astype(int)
    return longo.pivot_table(index=['ponto_id', 'ano'], columns='variavel', values='valor').reset_index()


def main():
    conectar(None)
    cfg.DADOS.mkdir(parents=True, exist_ok=True)
    loc = locais()
    print(f'{len(loc)} locais', flush=True)
    dec = decenais(loc)
    dec.to_parquet(cfg.DADOS / 'climas_decenais.parquet', index=False)
    print(f'decenais: {len(dec)} linhas; faltantes por variável:\n{dec[list(DECENAIS)].isna().mean().round(4)}',
          flush=True)
    est = estaticos(loc)
    est.to_parquet(cfg.DADOS / 'climas_locais.parquet', index=False)
    print(f'estáticos: {len(est)} locais; faltantes:\n{est.isna().mean().round(4).to_string()}')


if __name__ == '__main__':
    main()
