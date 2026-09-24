# -*- coding: utf-8 -*-
"""Classificação de zonas de vida de Holdridge (38 zonas) no Earth Engine (API Python).

Entrada: três assets separados (um por variável: tas, pet, pr), cada um com 12 bandas mensais,
gerados por gerar_normal_multibanda.py. As bandas já estão em unidades físicas (tas em °C; pet e
pr em mm/mês): não há offset/fator a aplicar (nem -273,15 nem divisões por 10/100).
"""
import ee

# (classe de temperatura, classe RETP mínima, classe RETP máxima, id da zona).
# Numeração e nomes de Jungkunst et al. (2021, J. Plant Nutr. Soil Sci. 184:5-11, Tab. 1), base
# Leemans (1990), 38 zonas. Faixas de ETP/P pela Fig. 1 do artigo: cada faixa térmica começa numa
# linha de ETP/P diferente (tropical em 32, subtropical e temperado quente em 16, temperado frio em
# 8, boreal em 4, subpolar em 2), e cada tipo de vegetação ocupa sempre a mesma província de
# umidade (moist = 0,5-1; wet = 0,25-0,5; rain = 0,125-0,25; dry = 1-2; very dry = 2-4). Valores
# além das pontas de cada faixa entram na zona extrema (ex.: tropical com ETP/P < 0,5 -> 38).
# Correção (2026-09-24): o script JS usava em todas as faixas o padrão do subtropical, o que deslocava
# o tropical em uma zona (ETP/P 0,5-1 virava 36, "dry forest", em vez de 37, "moist forest") e
# também o temperado frio, o boreal e o subpolar.
# Classes RETP (classe_retp): 1 >=32, 2 16-32, 3 8-16, 4 4-8, 5 2-4, 6 1-2, 7 0,5-1, 8 0,25-0,5,
# 9 0,125-0,25, 10 <0,125.
TABELA_ZONAS = [
    (2, 1, 6, 3), (2, 7, 7, 4), (2, 8, 8, 5), (2, 9, 10, 6),                                 # subpolar
    (3, 1, 5, 7), (3, 6, 6, 8), (3, 7, 7, 9), (3, 8, 8, 10), (3, 9, 10, 11),                 # boreal
    (4, 1, 4, 12), (4, 5, 5, 13), (4, 6, 6, 14), (4, 7, 7, 15), (4, 8, 8, 16), (4, 9, 10, 17),  # temperado frio
    (5, 1, 3, 18), (5, 4, 4, 19), (5, 5, 5, 20), (5, 6, 6, 21), (5, 7, 7, 22), (5, 8, 8, 23), (5, 9, 10, 24),  # temperado quente
    (6, 1, 3, 25), (6, 4, 4, 26), (6, 5, 5, 27), (6, 6, 6, 28), (6, 7, 7, 29), (6, 8, 8, 30), (6, 9, 10, 31),  # subtropical
    (7, 1, 2, 32), (7, 3, 3, 33), (7, 4, 4, 34), (7, 5, 5, 35), (7, 6, 6, 36), (7, 7, 7, 37), (7, 8, 10, 38),  # tropical
]

# Nomes das 38 zonas (Jungkunst et al. 2021, Tab. 1).
LEGENDA = {
    1: "Polar ice", 2: "Polar desert",
    3: "Subpolar dry tundra", 4: "Subpolar moist tundra", 5: "Subpolar wet tundra", 6: "Subpolar rain tundra",
    7: "Boreal desert", 8: "Boreal dry bush", 9: "Boreal moist forest", 10: "Boreal wet forest",
    11: "Boreal rain forest",
    12: "Cool temperate desert", 13: "Cool temperate desert bush", 14: "Cool temperate steppe",
    15: "Cool temperate moist forest", 16: "Cool temperate wet forest", 17: "Cool temperate rain forest",
    18: "Warm temperate desert", 19: "Warm temperate desert bush", 20: "Warm temperate thorn steppe",
    21: "Warm temperate dry forest", 22: "Warm temperate moist forest", 23: "Warm temperate wet forest",
    24: "Warm temperate rain forest",
    25: "Subtropical desert", 26: "Subtropical desert bush", 27: "Subtropical thorn steppe",
    28: "Subtropical dry forest", 29: "Subtropical moist forest", 30: "Subtropical wet forest",
    31: "Subtropical rain forest",
    32: "Tropical desert", 33: "Tropical desert bush", 34: "Tropical thorn steppe",
    35: "Tropical very dry forest", 36: "Tropical dry forest", 37: "Tropical moist forest",
    38: "Tropical wet forest",
}

PALETA = [
    '#4d4d4d', '#6b6b6b', '#8a8a8a', '#a8a8a8',
    '#bdbdbd', '#c7e9c0', '#a1d99b', '#74c476',
    '#fdd0a2', '#fdae6b', '#31a354', '#238b45', '#006d2c',
    '#fdd49e', '#fdbb84', '#9ecae1', '#6baed6', '#3182bd',
    '#fee8c8', '#fdbb84', '#fdd0a2', '#9ecae1', '#6baed6', '#3182bd',
    '#fef0d9', '#fdcc8a', '#fdae6b', '#9ecae1', '#6baed6', '#3182bd',
    '#fef0d9', '#fdd49e', '#fdbb84', '#fdae6b', '#fd8d3c', '#e6550d', '#a63603', '#7f2704',
]


def carregar_normal(asset_tas: str, asset_pet: str, asset_pr: str) -> ee.Image:
    """Carrega os três assets (tas, pet, pr; 12 bandas mensais cada) e junta num único ee.Image
    de 36 bandas, com os nomes garantidos pela ordem (independe de como o GEE nomeou)."""
    assets = {"tas": asset_tas, "pet": asset_pet, "pr": asset_pr}
    imagens = []
    for var, asset_id in assets.items():
        img = ee.Image(asset_id)
        n = img.bandNames().size().getInfo()
        if n != 12:
            raise ValueError(f"O asset {asset_id} ({var}) tem {n} bandas; esperado 12 (uma por mês).")
        imagens.append(img.rename([f"{var}_{m:02d}" for m in range(1, 13)]))
    return ee.Image.cat(imagens)


def biotemperatura(tas_bandas: ee.Image, limiar_correcao=None) -> ee.Image:
    """Média anual das temperaturas mensais corrigidas por latitude, limitadas a [0, 30] °C.

    Correção igual à do script JS original, aplicada a todos os meses. Se limiar_correcao for
    um número (ex.: 24), a correção só é aplicada nos meses com t > limiar.
    """
    lat = ee.Image.pixelLonLat().select("latitude").abs()
    mensais = []
    for m in range(1, 13):
        t = tas_bandas.select(f"tas_{m:02d}")  # já em °C
        correcao = lat.multiply(3).divide(100).multiply(t.subtract(24).pow(2))
        if limiar_correcao is not None:
            correcao = correcao.where(t.lte(limiar_correcao), 0)
        tcor = t.subtract(correcao)
        mensais.append(tcor.where(tcor.lt(0), 0).where(tcor.gt(30), 30).rename("tbio"))
    return ee.ImageCollection.fromImages(mensais).mean().rename("biotemp")


def classe_temperatura(tbio: ee.Image) -> ee.Image:
    return (ee.Image(0)
            .where(tbio.lt(1.5), 1)
            .where(tbio.gte(1.5).And(tbio.lt(3)), 2)
            .where(tbio.gte(3).And(tbio.lt(6)), 3)
            .where(tbio.gte(6).And(tbio.lt(12)), 4)
            .where(tbio.gte(12).And(tbio.lt(18)), 5)
            .where(tbio.gte(18).And(tbio.lt(24)), 6)
            .where(tbio.gte(24), 7)
            .rename("temp_class"))


def classe_retp(retp: ee.Image) -> ee.Image:
    return (ee.Image(0)
            .where(retp.gte(32), 1)
            .where(retp.gte(16).And(retp.lt(32)), 2)
            .where(retp.gte(8).And(retp.lt(16)), 3)
            .where(retp.gte(4).And(retp.lt(8)), 4)
            .where(retp.gte(2).And(retp.lt(4)), 5)
            .where(retp.gte(1).And(retp.lt(2)), 6)
            .where(retp.gte(0.5).And(retp.lt(1)), 7)
            .where(retp.gte(0.25).And(retp.lt(0.5)), 8)
            .where(retp.gte(0.125).And(retp.lt(0.25)), 9)
            .where(retp.lt(0.125), 10)
            .rename("retp_class"))


def suavizar_zona(zona: ee.Image, radius: float = 1) -> ee.Image:
    """Filtro de moda (3x3, vizinhança quadrada) sobre a zona classificada.

    Mesma suavização do script JS original (`focalMode`), usada para remover ruído de pixel
    isolado antes da exportação/visualização final.
    """
    return zona.focalMode(radius=radius, kernelType="square", units="pixels")


FATOR_ETP_HOLDRIDGE = 58.93  # mm/ano por °C de biotemperatura (Holdridge 1967)


def classificar_holdridge(normal: ee.Image, limiar_correcao=None, etp: str = "penman") -> ee.Image:
    """Retorna imagem com: zone38_id, biotemp (°C), prec (mm/ano), etp (mm/ano), retp (razão).

    etp: "penman" = ETP de Penman-Monteith do CHELSA (soma das 12 bandas `pet`);
         "holdridge" = ETP de Holdridge, 58,93 x biotemperatura (a definição original, usada por
         Leemans e por Jungkunst et al. 2021). Com a de Holdridge, ~23% dos pixels do Brasil mudam
         de zona (o país fica mais úmido, sobretudo no Sul/Sudeste).
    """
    biotemp = biotemperatura(normal.select("tas_.*"), limiar_correcao)
    prec = normal.select("pr_.*").reduce(ee.Reducer.sum()).rename("prec")
    if etp == "penman":
        etp_anual = normal.select("pet_.*").reduce(ee.Reducer.sum())
    elif etp == "holdridge":
        etp_anual = biotemp.multiply(FATOR_ETP_HOLDRIDGE)
    else:
        raise ValueError(f"etp deve ser 'penman' ou 'holdridge', não {etp!r}")
    etp = etp_anual.rename("etp")
    retp = etp.divide(prec.where(prec.lt(1), 1)).rename("retp")

    t = classe_temperatura(biotemp)
    u = classe_retp(retp)

    zona = ee.Image(0).updateMask(t.gt(0).And(u.gt(0)))
    gelo = t.eq(1).And(biotemp.lt(1))
    zona = zona.where(gelo, 1).where(t.eq(1).And(gelo.Not()), 2)
    for classe_t, u_min, u_max, zona_id in TABELA_ZONAS:
        zona = zona.where(t.eq(classe_t).And(u.gte(u_min)).And(u.lte(u_max)), zona_id)
    zona = zona.rename("zone38_id").updateMask(zona.neq(0))

    return ee.Image.cat([
        zona.toByte(),
        biotemp.toFloat(),
        prec.toFloat(),
        etp.toFloat(),
        retp.toFloat(),
    ])
