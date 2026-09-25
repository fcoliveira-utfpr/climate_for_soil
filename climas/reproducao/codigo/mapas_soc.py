"""Fase 2 (SOC): mapas do estoque de SOC de 0-30 cm (t/ha, ano 2023) para cada cenário de clima.

Mesmo esquema da fase 1b, agora com todos os dados: (1) modelos de textura da cadeia (covariáveis comuns
às duas matrizes + profundidade + clima), que preveem a textura de 0-30 cm nos locais de SOC e na grade;
(2) RF de log(SOC) com as covariáveis da matriz de SOC + clima + essa textura, aplicado à grade de 5 km.
As covariáveis dinâmicas (idades de uso, índices, água, fogo, bordas) são as de 2023.

O RF prevê log(SOC); voltar com exp() estima ~a mediana e subestima a média em ~10 t/ha. Por isso o mapa é
multiplicado pelo fator de Duan (smearing), média de exp(resíduo) nas predições fora da amostra da fase 1b
(soc_oof.parquet) do mesmo cenário. Os resíduos dentro da amostra não servem: o RF quase os zera (fator ≈ 1).

Saídas em climas/dados_reproducao/mapas/: covariaveis_soc_extras_5km.tif e soc_0_30cm_<cenario>.tif (t/ha).
"""
import sys

import numpy as np
import pandas as pd
import rasterio

import config as cfg
import dados
import mapas_textura as mt
import modelagem as m

ANO = 2023
ARQ_EXTRAS = cfg.MAPAS / 'covariaveis_soc_extras_5km.tif'


def baixar_extras():
    import geemap
    from gee_utils import conectar
    import covariaveis_gee as cg
    conectar(None)
    img = cg.extras_soc(ANO).toFloat()
    nomes = img.bandNames().getInfo()
    geemap.download_ee_image(img, filename=str(ARQ_EXTRAS), crs='EPSG:4326',
                             crs_transform=list(mt.TRANSFORM)[:6], shape=mt.FORMA, dtype='float32',
                             max_tile_size=8)
    # geemap.download_ee_image nao grava as descricoes de banda no GeoTIFF; grava aqui (ver mapas_textura.py).
    with rasterio.open(ARQ_EXTRAS, 'r+') as dst:
        dst.descriptions = tuple(nomes)


def grade_soc():
    g = mt.grade_completa()
    with rasterio.open(ARQ_EXTRAS) as r:
        nomes = list(r.descriptions)
        ex = r.read().reshape(r.count, -1).T[g.pixel.to_numpy()]
    ex[~np.isfinite(ex)] = np.nan
    g = pd.concat([g, pd.DataFrame(ex, columns=nomes)], axis=1)
    g['cov_ok'] &= g[nomes].notna().all(axis=1)
    return g


def fatores_smearing():
    oof = pd.read_parquet(cfg.PONTOS / f'soc_oof{cfg.SUFIXO}.parquet')
    return oof.groupby('cenario').apply(lambda g: np.mean(np.exp(g.log_soc_obs - g.log_soc_prev)))


def prever(cenario, tex, soc, grade):
    cats = m.categorias(cenario, tex, soc)
    comuns = sorted(set(m.base(tex)) & set(m.base(soc)) - {'profundidade'})
    cov_tex = comuns + ['profundidade']
    cov_soc = [c for c in m.base(soc) if c not in cfg.TEXTURA_C2]
    clima_soc, clima_g = m.clima(soc, cenario, cats), m.clima(grade, cenario, cats)
    t_soc, t_g = [], []
    for camada, centro in cfg.CAMADAS.items():
        d = tex[tex.profundidade.between(centro - cfg.MEIA_JANELA, centro + cfg.MEIA_JANELA)]
        x_tr = pd.concat([d[cov_tex], m.clima(d, cenario, cats)], axis=1).to_numpy(float)
        mods = [m.gbm(cfg.SEMENTE).fit(x_tr, d[a].to_numpy()) for a in cfg.ALVOS_TEXTURA]
        for alvo_df, clima_, destino in ((soc, clima_soc, t_soc), (grade, clima_g, t_g)):
            x = pd.concat([alvo_df[comuns].assign(profundidade=float(centro)), clima_], axis=1).to_numpy(float)
            destino.append(np.column_stack(m.razoes_para_pct(*[mo.predict(x) for mo in mods])))
    nomes_t = ['areia_prev', 'silte_prev', 'argila_prev']
    tex_soc = pd.DataFrame(np.mean(t_soc, axis=0), columns=nomes_t, index=soc.index)
    tex_g = pd.DataFrame(np.mean(t_g, axis=0), columns=nomes_t, index=grade.index)
    x_tr = pd.concat([soc[cov_soc], clima_soc, tex_soc], axis=1)
    med = x_tr.median()
    rf = m.rf(cfg.SEMENTE).fit(x_tr.fillna(med).to_numpy(float), np.log(soc.soc_g_m2.to_numpy(float)))
    x_g = pd.concat([grade.assign(profundidade=float(cfg.PROF_SOC))[cov_soc], clima_g, tex_g], axis=1)[x_tr.columns]
    return np.exp(rf.predict(x_g.fillna(med).to_numpy(float))) * 0.01            # g/m² -> t/ha


def salvar(soc_tha, grade, cenario):
    arr = np.full(mt.FORMA[0] * mt.FORMA[1], np.nan, dtype='float32')
    cols = cfg.CENARIOS[cenario][1]
    ok = grade[cols].notna().all(axis=1).to_numpy() if cols else np.ones(len(grade), bool)
    ok = ok & grade.cov_ok.to_numpy()
    arr[grade.pixel.to_numpy()[ok]] = soc_tha[ok]
    perfil = dict(driver='GTiff', height=mt.FORMA[0], width=mt.FORMA[1], count=1, dtype='float32',
                  crs='EPSG:4326', transform=mt.TRANSFORM, nodata=np.nan, compress='deflate')
    with rasterio.open(cfg.MAPAS / f'soc_0_30cm_{cenario}{cfg.SUFIXO}.tif', 'w', **perfil) as dst:
        dst.write(arr.reshape(1, *mt.FORMA))
        dst.descriptions = ('soc_t_ha',)


def main(etapas=('extras', 'mapas')):
    if 'extras' in etapas and not ARQ_EXTRAS.exists():
        baixar_extras()
    if 'mapas' in etapas:
        tex, soc = dados.carregar()
        grade = grade_soc()
        fatores = fatores_smearing()
        for cen in cfg.CENARIOS:
            salvar(prever(cen, tex, soc, grade) * fatores[cen], grade, cen)
            print(f'  mapa de SOC: {cen} (smearing {fatores[cen]:.3f})', flush=True)


if __name__ == '__main__':
    main(tuple(sys.argv[1:]) or ('extras', 'mapas'))
