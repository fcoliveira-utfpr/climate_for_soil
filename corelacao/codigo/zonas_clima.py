"""Zonas climáticas homogêneas (k-means) sobre o clima CHELSA do Brasil inteiro.

O agrupamento é ajustado nos pixels do país (amostra aleatória ponderada pela área), não nos locais de
solo: as zonas descrevem o clima do Brasil, viram um mapa aplicável no GEE e não são moldadas pela
concentração da amostra (Rondônia, RS). Os locais são só atribuídos à zona de centróide mais próximo.

Variáveis (padronizadas; chuva, DEF e EXC em log): temperatura média e do mês mais frio, chuva anual e do
mês mais seco, sazonalidade da chuva, ETP anual, DEF, EXC e Im do BHC (Thornthwaite CAD 100 mm).

Saída: resultados/tabelas/zonas_k{K}_centroides.csv (centróides, médias e desvios da padronização) e
climas/dados_chelsa/zonas/zonas_climaticas_k{K}.tif (mapa, uint8, 0 = sem dado).
"""
from pathlib import Path

import numpy as np
import pandas as pd
import rasterio
from rasterio.windows import Window
from sklearn.cluster import KMeans

from experimento_dados import calcular_variaveis

ROOT = Path(__file__).resolve().parents[1]
CLIMAS = ROOT.parent / 'climas' / 'dados_chelsa'
TABELAS = ROOT / 'resultados' / 'tabelas'
NORMAL = CLIMAS / 'normal_1991_2020' / 'chelsa_brasil_{}_normal_1991_2020.tif'
THORNTHWAITE = CLIMAS / 'thornthwaite' / 'Thornthwaite_CHELSA_BR_1991_2020_CAD100.tif'
MASCARA = CLIMAS / 'awc' / 'AWC_BR_grade_CHELSA.tif'   # banda 2 = Brasil

VARIAVEIS_ZONA = ['clim_t_media', 'clim_t_mes_frio', 'clim_p_anual', 'clim_p_mes_seco',
                  'clim_p_sazonalidade', 'clim_etp_anual', 'clim_def_anual', 'clim_exc_anual', 'clim_im']
EM_LOG = {'clim_p_anual', 'clim_p_mes_seco', 'clim_def_anual', 'clim_exc_anual'}


def transformar(df):
    x = df[VARIAVEIS_ZONA].astype(float).copy()
    for c in EM_LOG:
        x[c] = np.log1p(x[c].clip(lower=0))
    return x


def ler_bloco(lin0, n, largura):
    """Variáveis climáticas dos pixels de um bloco de linhas; devolve (DataFrame, máscara válida)."""
    jan = Window(0, lin0, largura, n)
    dados = {}
    for v in ('tas', 'pr', 'pet'):
        with rasterio.open(str(NORMAL).format(v)) as r:
            dados[v] = r.read(window=jan, masked=True).filled(np.nan).reshape(12, -1).T
    with rasterio.open(THORNTHWAITE) as r:
        th = {nome: r.read(i, window=jan).ravel() for i, nome in ((6, 'def'), (7, 'exc'), (10, 'im'))}
    with rasterio.open(MASCARA) as r:
        br = r.read(2, window=jan).ravel() == 1
        t = r.transform
    lat = np.repeat(t.f + t.e * (lin0 + np.arange(n) + 0.5), largura)
    ok = br & np.isfinite(dados['tas']).all(1) & np.isfinite(dados['pr']).all(1) & \
        np.isfinite(dados['pet']).all(1) & np.isfinite(th['def']) & np.isfinite(th['im'])
    var = calcular_variaveis(dados['tas'][ok], dados['pr'][ok], dados['pet'][ok], lat[ok],
                             th['def'][ok], th['exc'][ok], th['im'][ok])
    return pd.DataFrame(var), ok, lat


def amostra_do_grid(n_amostra=300_000, semente=2026, linhas_por_bloco=400):
    """Amostra aleatória de pixels do Brasil, com probabilidade proporcional à área (cos da latitude)."""
    rng = np.random.default_rng(semente)
    with rasterio.open(MASCARA) as r:
        altura, largura = r.height, r.width
        total = int((r.read(2) == 1).sum())
    frac = min(1.0, 1.3 * n_amostra / total)
    partes = []
    for lin0 in range(0, altura, linhas_por_bloco):
        n = min(linhas_por_bloco, altura - lin0)
        var, ok, lat = ler_bloco(lin0, n, largura)
        if len(var) == 0:
            continue
        p = frac * np.cos(np.radians(lat[ok]))
        partes.append(var[rng.random(len(var)) < p])
    amostra = pd.concat(partes, ignore_index=True)
    return amostra.sample(min(n_amostra, len(amostra)), random_state=semente)


def ajustar(k, amostra, semente=2026):
    x = transformar(amostra)
    media, dp = x.mean(), x.std()
    km = KMeans(n_clusters=k, n_init=10, random_state=semente).fit(((x - media) / dp).to_numpy())
    # zonas numeradas da mais quente para a mais fria (leitura mais fácil do mapa)
    cent = pd.DataFrame(km.cluster_centers_ * dp.to_numpy() + media.to_numpy(), columns=VARIAVEIS_ZONA)
    ordem = np.argsort(-cent.clim_t_media.to_numpy())
    cent = cent.iloc[ordem].reset_index(drop=True)
    cent.index = np.arange(1, k + 1)
    cent.index.name = 'zona'
    return cent, media, dp


def atribuir(df, cent, media, dp):
    """Zona (1..k) de centróide mais próximo, no espaço padronizado."""
    x = ((transformar(df) - media) / dp).to_numpy()
    c = ((cent[VARIAVEIS_ZONA] - media) / dp).to_numpy()
    d = ((x[:, None, :] - c[None, :, :]) ** 2).sum(axis=2)
    return cent.index.to_numpy()[d.argmin(axis=1)]


def salvar(k, cent, media, dp):
    TABELAS.mkdir(parents=True, exist_ok=True)
    out = cent.copy()
    for c in VARIAVEIS_ZONA:     # desfaz o log para a tabela ficar em unidades físicas
        if c in EM_LOG:
            out[c] = np.expm1(out[c])
    out.to_csv(TABELAS / f'zonas_k{k}_centroides.csv')
    pd.DataFrame({'media': media, 'dp': dp}).to_csv(TABELAS / f'zonas_k{k}_padronizacao.csv')


def carregar(k):
    cent = pd.read_csv(TABELAS / f'zonas_k{k}_centroides.csv', index_col='zona')
    for c in VARIAVEIS_ZONA:
        if c in EM_LOG:
            cent[c] = np.log1p(cent[c])
    pad = pd.read_csv(TABELAS / f'zonas_k{k}_padronizacao.csv', index_col=0)
    return cent, pad.media, pad.dp


def mapear(k, cent, media, dp, linhas_por_bloco=200):
    saida = CLIMAS / 'zonas' / f'zonas_climaticas_k{k}.tif'
    saida.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(MASCARA) as r:
        perfil = r.profile.copy()
        altura, largura = r.height, r.width
    perfil.update(count=1, dtype='uint8', nodata=0, compress='deflate', tiled=True,
                  blockxsize=512, blockysize=512)
    with rasterio.open(saida, 'w', **perfil) as dst:
        for lin0 in range(0, altura, linhas_por_bloco):
            n = min(linhas_por_bloco, altura - lin0)
            var, ok, _ = ler_bloco(lin0, n, largura)
            z = np.zeros(n * largura, np.uint8)
            if len(var):
                z[ok] = atribuir(var, cent, media, dp)
            dst.write(z.reshape(n, largura), 1, window=Window(0, lin0, largura, n))
    return saida


def main(ks=(10,)):
    amostra = amostra_do_grid()
    print(f'amostra do grid: {len(amostra)} pixels')
    for k in ks:
        cent, media, dp = ajustar(k, amostra)
        salvar(k, cent, media, dp)
        print(f'k={k}: mapa em {mapear(k, cent, media, dp)}')


if __name__ == '__main__':
    main()
