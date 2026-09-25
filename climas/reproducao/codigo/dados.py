"""Dados da reprodução: horizontes de textura (0-30 cm) e locais de SOC, com as covariáveis das matrizes
do MapBiomas e os climas.

- Textura: uma linha por horizonte com centro em 0-30 cm (como no MapBiomas: os modelos são por camada),
  com as razões log, a profundidade e os mapas de textura da coleção 2 como covariáveis.
- SOC: pontos da coleção 3 (cfg.ASSET_SOC), estoque acumulado da superfície até a `profundidade` (g/m²,
  com a correção de viés `carbono_gm2_qmap`). Uma linha por local e profundidade; a profundidade é
  covariável (como no MapBiomas) e o estoque avaliado e mapeado é o de 0-30 cm. As covariáveis do
  MapBiomas são extraídas no GEE (30 m) no ano de coleta de cada amostra.
- Climas: textura, reaproveitados da análise solo-clima (corelacao/.local/dados/exp_*.parquet, por
  ponto_id); SOC, extraídos nos pontos com as mesmas funções. A zona k10 é atribuída pelo clima contínuo.

Saída (restrita, fora do git): climas/dados_reproducao/pontos/{textura_horizontes,soc_pontos}.parquet
"""
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import ee
import numpy as np
import pandas as pd

import config as cfg
import experimento_dados as ed          # corelacao/codigo
import legendas as leg                  # corelacao/codigo
import zonas_clima as zc                # corelacao/codigo
from gee_utils import conectar          # corelacao/codigo
import covariaveis_gee as cg
from preparar_dados import (baixar_featurecollection, com_climas, completar_ipef_l3, coordenadas_validas,
                            decodificar_koppen_ipef, ponto_id)

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


def _amostrar(img, locais, bloco, workers, rotulo):
    """Valor de cada banda no pixel (30 m) de cada local; blocos em paralelo, com novas tentativas."""
    def parte(ini):
        sub = locais.iloc[ini:ini + bloco]
        fc = ee.FeatureCollection([ee.Feature(ee.Geometry.Point([r.longitude, r.latitude]), {'idx': int(r.Index)})
                                   for r in sub.itertuples()])
        for tentativa in range(4):
            try:
                res = img.reduceRegions(fc, ee.Reducer.first(), scale=30, tileScale=4).getInfo()['features']
                return pd.DataFrame([f['properties'] for f in res]).set_index('idx')
            except ee.EEException:
                if tentativa == 3:
                    raise
                time.sleep(30 * (tentativa + 1))

    partes = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for fut in as_completed([pool.submit(parte, i) for i in range(0, len(locais), bloco)]):
            partes.append(fut.result())
    print(f'  {rotulo}: {len(locais)} locais', flush=True)
    return pd.concat(partes)


def covariaveis_soc(locais, bloco=500, workers=4):
    """Covariáveis do SOC (cfg.COVARIAVEIS_SOC) e Köppen IPEF em cada local, no ano de `ano_cov`.
    Cache por ano em dados_reproducao/pontos/soc_covariaveis/ (a extração leva horas)."""
    pasta = cfg.PONTOS / 'soc_covariaveis'
    pasta.mkdir(parents=True, exist_ok=True)
    kp = cg.koppen_ipef()
    partes = []
    for ano, sub in locais.groupby('ano_cov'):
        arq = pasta / f'{ano}.parquet'
        if not arq.exists():
            img = ee.Image.cat([cg.estaticas_textura(), cg.extras_soc(int(ano))]).select(cfg.COVARIAVEIS_SOC)
            sub = sub.reset_index(drop=True)
            v = _amostrar(img.addBands(kp), sub, bloco, workers, f'covariáveis {ano}')
            v = pd.concat([v.reindex(range(len(sub))), sub[['ponto_id', 'ano_cov']]], axis=1)
            v.to_parquet(arq, index=False)
        partes.append(pd.read_parquet(arq))
    return pd.concat(partes, ignore_index=True)


def climas_soc(locais):
    """Classes de todos os sistemas, clima contínuo e zona k10 nos locais (mesmas funções da corelacao)."""
    loc = locais[['ponto_id', 'longitude', 'latitude']].drop_duplicates('ponto_id').reset_index(drop=True)
    cls = com_climas(loc)
    cont = ed.variaveis_climaticas(ed.extrair_clima_mensal(loc), loc.latitude)
    cl = pd.concat([cls[['ponto_id'] + [c for c in leg.COLUNAS_CLIMA if c in cls.columns]], cont], axis=1)
    ok = cl[cfg.CLIMA_CONTINUO].notna().all(axis=1)
    cent, media, dp = zc.carregar(10)
    cl['zona_k10'] = pd.Series(pd.NA, index=cl.index, dtype='string')
    cl.loc[ok, 'zona_k10'] = zc.atribuir(cl[ok], cent, media, dp).astype(str)
    return cl


def soc_pontos():
    """SOC da coleção 3: uma linha por local e profundidade. Sem pseudoamostras (afloramentos, areias)
    e sem as réplicas temporais trep10/trep20 do asset (cópias de ~2.300 perfis com o ano recuado em 10
    e 20 anos e o mesmo carbono: aumentam o peso desses perfis no modelo temporal do MapBiomas, mas não
    trazem informação nova para a validação por local)."""
    df = baixar_featurecollection(cfg.ASSET_SOC)
    soc = pd.to_numeric(df.carbono_gm2_qmap, errors='coerce')
    prof = pd.to_numeric(df.profundidade, errors='coerce')
    pseudo = df.PSEUDOROCK_index.astype(float).eq(1) | df.PSEUDOSAND_index.astype(float).eq(1)
    trep = df.id.astype(str).str.startswith('trep')
    ok = ~pseudo & ~trep & coordenadas_validas(df) & (soc > 0) & prof.between(0, cfg.PROF_SOC, inclusive='right')
    df = df[ok].copy()
    df['ponto_id'] = ponto_id(df)
    df['ano_cov'] = df.ano.astype(int).clip(upper=cfg.ANO_MAX_COVARIAVEIS)
    df['soc_g_m2'], df['profundidade'] = soc[ok].values, prof[ok].values
    print(f'  SOC: {len(df)} linhas, {df.ponto_id.nunique()} locais '
          f'(excluídas: {int(pseudo.sum())} pseudo, {int(trep.sum())} trep)', flush=True)
    locais = df[['ponto_id', 'ano_cov', 'longitude', 'latitude']].drop_duplicates(['ponto_id', 'ano_cov'])
    cov = covariaveis_soc(locais)
    kp = cov[[c for c in cov.columns if c.startswith('koppen_l')]]
    cov = pd.concat([cov.drop(columns=kp.columns), decodificar_koppen_ipef(kp)], axis=1)
    d = df[['ponto_id', 'ano_cov', 'profundidade', 'soc_g_m2', 'longitude', 'latitude']].merge(
        cov, on=['ponto_id', 'ano_cov'], how='left')
    # perfis no mesmo local e profundidade (outro id ou outro ano): mediana, como antes com as réplicas
    num = d.drop(columns=['ponto_id', 'ano_cov']).select_dtypes('number')
    num[['ponto_id', 'profundidade_']] = d[['ponto_id', 'profundidade']]
    num = num.groupby(['ponto_id', 'profundidade_']).median().reset_index().drop(columns='profundidade_')
    ipef = d.groupby('ponto_id')[['koppen_ipef_l1', 'koppen_ipef_l2', 'koppen_ipef_l3']].first().reset_index()
    out = completar_ipef_l3(num.merge(ipef, on='ponto_id'))
    return out.merge(climas_soc(out), on='ponto_id', how='left')


def main():
    cfg.PONTOS.mkdir(parents=True, exist_ok=True)
    print(f'GEE: {conectar(None)}')
    clima = climas_por_ponto()
    for nome, func in (('textura_horizontes', textura_horizontes), ('soc_pontos', soc_pontos)):
        d = func()
        if nome == 'textura_horizontes':
            d = d.merge(clima, on='ponto_id', how='inner')
        d = d[d[CLIMA_COLS + ['zona_k10']].notna().all(axis=1)].reset_index(drop=True)
        d.to_parquet(cfg.PONTOS / f'{nome}.parquet', index=False)
        print(f'{nome}: {len(d)} linhas, {d.ponto_id.nunique()} locais')


def carregar():
    return (pd.read_parquet(cfg.PONTOS / 'textura_horizontes.parquet'),
            pd.read_parquet(cfg.PONTOS / 'soc_pontos.parquet'))


if __name__ == '__main__':
    main()
