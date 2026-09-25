"""Dados da reprodução: horizontes de textura (0-30 cm) e locais de SOC, com as covariáveis das matrizes
do MapBiomas e os climas.

- Textura: uma linha por horizonte com centro em 0-30 cm (como no MapBiomas: os modelos são por camada),
  com as razões log, a profundidade e os mapas de textura da coleção 2 como covariáveis.
- SOC: uma linha por local (mediana das réplicas anuais), estoque de 0-30 cm.
- Climas: reaproveitados da análise solo-clima (corelacao/.local/dados/exp_*.parquet, por ponto_id):
  classes de todos os sistemas e o clima contínuo; a zona k10 é atribuída pelo clima contínuo.

Saída (restrita, fora do git): climas/dados_reproducao/pontos/{textura_horizontes,soc_pontos}.parquet
"""
import re

import numpy as np
import pandas as pd

import config as cfg
import experimento_dados as ed          # corelacao/codigo
import legendas as leg                  # corelacao/codigo
import zonas_clima as zc                # corelacao/codigo
from gee_utils import conectar          # corelacao/codigo
from preparar_dados import baixar_featurecollection, coordenadas_validas, ponto_id

# Não são covariáveis (ou vazariam o alvo). Diferente da corelacao: aqui a profundidade e os mapas de
# textura da coleção 2 ficam, porque o MapBiomas os usa.
NAO_COVARIAVEIS = re.compile(
    r'^(koppen_|HLZ_|log_|system:index|\.geo$|id$|dataset_id$|chunk_id$|ponto_id$|year$|YEAR_index$|'
    r'PSEUDO_index$|IFN_index$|latitude$|longitude$|soc_stock_g_m2$|areia$|silte$|argila$|textura_l1_030cm$)')
CLIMA_COLS = leg.COLUNAS_CLIMA + cfg.CLIMA_CONTINUO


def covariaveis(df):
    return [c for c in df.columns if not NAO_COVARIAVEIS.match(c)]


def climas_por_ponto():
    """Classes e clima contínuo por ponto_id (dos parquets da corelacao), com a zona k10."""
    soc, tex = ed.carregar_experimento()
    cl = pd.concat([soc, tex])[['ponto_id'] + CLIMA_COLS].drop_duplicates('ponto_id')
    ok = cl[cfg.CLIMA_CONTINUO].notna().all(axis=1)
    cent, media, dp = zc.carregar(10)
    cl['zona_k10'] = pd.Series(pd.NA, index=cl.index, dtype='string')
    cl.loc[ok, 'zona_k10'] = zc.atribuir(cl[ok], cent, media, dp).astype(str)
    return cl


def textura_horizontes():
    df = baixar_featurecollection(cfg.MATRIZ_TEXTURA)
    df['ponto_id'] = ponto_id(df)
    artificial = (df.id.astype(str).str.contains('pseudo', case=False, regex=False)
                  | df.id.astype(str).str.startswith('clay-copy-'))
    prof = pd.to_numeric(df.profundidade, errors='coerce')
    fr = df[['areia', 'silte', 'argila']].apply(pd.to_numeric, errors='coerce')
    ok = ~artificial & coordenadas_validas(df) & prof.gt(0) & prof.le(30)
    ok &= np.isfinite(fr.to_numpy()).all(axis=1) & (fr >= 0).all(axis=1)
    ok &= np.isclose(fr.sum(axis=1), 1000, atol=15)
    df = df[ok].copy()
    cov = covariaveis(df)
    out = df[cov].apply(pd.to_numeric, errors='coerce')
    out['ponto_id'] = df.ponto_id.values
    out['longitude'], out['latitude'] = df.longitude.astype(float).values, df.latitude.astype(float).values
    for f in ('areia', 'silte', 'argila'):
        out[f] = fr.loc[df.index, f].values                          # g/kg
    out['log_areia1p_argila1p'] = np.log((out.areia + 1) / (out.argila + 1))
    out['log_silte1p_argila1p'] = np.log((out.silte + 1) / (out.argila + 1))
    return out.reset_index(drop=True)


def soc_pontos():
    df = baixar_featurecollection(cfg.MATRIZ_SOC)
    df['ponto_id'] = ponto_id(df)
    soc = pd.to_numeric(df.soc_stock_g_m2, errors='coerce')
    ok = ~df.PSEUDO_index.astype(float).eq(1) & coordenadas_validas(df) & (soc > 0)
    df = df[ok].copy()
    cov = covariaveis(df)
    num = df[cov].apply(pd.to_numeric, errors='coerce')
    num['soc_g_m2'] = soc[ok].values
    num['longitude'], num['latitude'] = df.longitude.astype(float).values, df.latitude.astype(float).values
    num['ponto_id'] = df.ponto_id.values
    return num.groupby('ponto_id').median().reset_index()


def main():
    cfg.PONTOS.mkdir(parents=True, exist_ok=True)
    print(f'GEE: {conectar(None)}')
    clima = climas_por_ponto()
    for nome, func in (('textura_horizontes', textura_horizontes), ('soc_pontos', soc_pontos)):
        d = func().merge(clima, on='ponto_id', how='inner')
        d = d[d[CLIMA_COLS + ['zona_k10']].notna().all(axis=1)].reset_index(drop=True)
        d.to_parquet(cfg.PONTOS / f'{nome}.parquet', index=False)
        print(f'{nome}: {len(d)} linhas, {d.ponto_id.nunique()} locais')


def carregar():
    return (pd.read_parquet(cfg.PONTOS / 'textura_horizontes.parquet'),
            pd.read_parquet(cfg.PONTOS / 'soc_pontos.parquet'))


if __name__ == '__main__':
    main()
