# -*- coding: utf-8 -*-
"""Downscaling da temperatura média mensal do CHELSA (~1 km) para 30 m, por correção de
elevação (lapse rate), sem depender de estação nenhuma.

T_30m = T_CHELSA (reamostrada p/ 30 m) + lapse_rate x (elevação "efetiva" do CHELSA no pixel - elevação real 30 m)

"Elevação efetiva do CHELSA" é o DEM de 30 m agregado (média) na grade nativa do CHELSA -- a altitude que
a temperatura de ~1 km já reflete implicitamente (o próprio CHELSA já faz correção orográfica por dentro,
com o DEM dele). A correção daqui é só a diferença ENTRE essa elevação "vista" pelo CHELSA e a elevação
real de cada pixel de 30 m; tanto a temperatura quanto essa elevação efetiva são reamostradas do mesmo
jeito (bilinear) para a grade fina do DEM, para a anomalia ficar coerente pixel a pixel.

Referência da abordagem: Xavier et al. (2022, joc.7731) -- melhoraram a grade diária brasileira de
0,25° para 0,1° em Tmax/Tmin exatamente incorporando elevação + lapse rate (sem precisar disso para
chuva, que não tem relação linear confiável com altitude).
"""
import ee

DEM_30M = "NASA/NASADEM_HGT/001"
LAPSE_RATE = -0.0065  # °C/m (padrão ambiental, -6,5 °C/km)


def elevacao_30m() -> ee.Image:
    return ee.Image(DEM_30M).select("elevation")


def elevacao_efetiva_chelsa(asset_tas: str, dem30: ee.Image = None) -> ee.Image:
    """DEM de 30 m agregado (média) na grade exata do asset de tas do CHELSA (~1 km):
    a elevação que a temperatura do CHELSA já reflete implicitamente naquele pixel."""
    dem30 = dem30 if dem30 is not None else elevacao_30m()
    proj_chelsa = ee.Image(asset_tas).projection()
    # maxPixels precisa cobrir todos os sub-pixels de 30 m dentro de 1 celula do CHELSA (~1 km =~
    # 1111 sub-pixels de 30 m); com um valor menor o reduceResolution trunca de forma tendenciosa
    # (nao e uma amostra aleatoria dos sub-pixels) em vez de usar a celula inteira.
    return (dem30
            .reduceResolution(reducer=ee.Reducer.mean(), maxPixels=4096)
            .reproject(crs=proj_chelsa)
            .rename("elev_chelsa"))


def corrigir_temperatura(asset_tas: str, mes: int, dem30: ee.Image = None,
                         lapse_rate: float = LAPSE_RATE) -> ee.Image:
    """Temperatura de um mes (banda b<mes> do asset, 1-indexado jan..dez) corrigida por elevacao,
    na grade de 30 m do DEM."""
    dem30 = dem30 if dem30 is not None else elevacao_30m()
    nome_saida = f"tas_{mes:02d}"
    tas = ee.Image(asset_tas).select(f"b{mes}")
    elev_chelsa = elevacao_efetiva_chelsa(asset_tas, dem30)

    grade_fina = dem30.projection()
    tas_fina = tas.resample("bilinear").reproject(grade_fina)
    elev_chelsa_fina = elev_chelsa.resample("bilinear").reproject(grade_fina)

    correcao = elev_chelsa_fina.subtract(dem30).multiply(lapse_rate)
    return tas_fina.add(correcao).rename(nome_saida)


def temperatura_sem_correcao(asset_tas: str, mes: int) -> ee.Image:
    """Mesma banda do CHELSA, so reamostrada bilinear (sem lapse rate) -- baseline para comparar."""
    return ee.Image(asset_tas).select(f"b{mes}").resample("bilinear").rename(f"tas_{mes:02d}")
