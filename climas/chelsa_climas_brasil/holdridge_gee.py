# -*- coding: utf-8 -*-
"""Classificação de zonas de vida de Holdridge (38 zonas) no Earth Engine (API Python).

Entrada: três assets separados (um por variável: tas, pet, pr), cada um com 12 bandas mensais,
gerados por gerar_normal_multibanda.py. As bandas já estão em unidades físicas (tas em °C; pet e
pr em mm/mês): não há offset/fator a aplicar (nem -273,15 nem divisões por 10/100).
"""
import ee

# (classe de temperatura, classe RETP mínima, classe RETP máxima, id da zona) - mesma tabela do script JS original
TABELA_ZONAS = [
    (2, 1, 4, 3), (2, 5, 6, 4), (2, 7, 7, 5), (2, 8, 10, 6),
    (3, 1, 3, 7), (3, 4, 4, 8), (3, 5, 5, 9), (3, 6, 7, 10), (3, 8, 10, 11),
    (4, 1, 3, 12), (4, 4, 4, 13), (4, 5, 5, 14), (4, 6, 6, 15), (4, 7, 7, 16), (4, 8, 10, 17),
    (5, 1, 3, 18), (5, 4, 4, 19), (5, 5, 5, 20), (5, 6, 6, 21), (5, 7, 7, 22), (5, 8, 8, 23), (5, 9, 10, 24),
    (6, 1, 3, 25), (6, 4, 4, 26), (6, 5, 5, 27), (6, 6, 6, 28), (6, 7, 7, 29), (6, 8, 8, 30), (6, 9, 10, 31),
    (7, 1, 3, 32), (7, 4, 4, 33), (7, 5, 5, 34), (7, 6, 6, 35), (7, 7, 7, 36), (7, 8, 8, 37), (7, 9, 10, 38),
]

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


def classificar_holdridge(normal: ee.Image, limiar_correcao=None) -> ee.Image:
    """Retorna imagem com: zone38_id, biotemp (°C), prec (mm/ano), etp (mm/ano), retp (razão)."""
    biotemp = biotemperatura(normal.select("tas_.*"), limiar_correcao)
    prec = normal.select("pr_.*").reduce(ee.Reducer.sum()).rename("prec")
    etp = normal.select("pet_.*").reduce(ee.Reducer.sum()).rename("etp")
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
