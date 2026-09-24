"""Classificação climática de Thornthwaite (1948) sobre a normal CHELSA 1991-2020.

Diferente de holdridge_gee.py / koppen_gee.py, o cálculo é local (numpy): o balanço hídrico
climatológico (Thornthwaite & Mather, 1955) vem da biblioteca agrometeorologiapy, que não roda
no GEE. O GEE só é usado para rasterizar o AWC (tabela de polígonos de solo) na grade do CHELSA.

Tabelas 2-5 conforme Thornthwaite (1948) / Aparecido et al. (2016), com as correções em relação
ao script JS (TerraClimate) anterior:
  - Tabela 4: limite B3'/B2' é 855 mm (série de múltiplos de 142,5), não 885.
  - Tabela 3, climas secos: excedente maior no verão é "w" e no inverno é "s" (estava invertido).
  - Tabela 5: concentração estival com o verão de 3 meses da Tabela 1 (não out-mar, 6 meses).
  - Inverno ponderado: 1/3 jun + jul + ago + 2/3 set (espelho do verão; estava 2/3 jun).
  - Excedente: EXC do BHC (antes, escoamento 'ro' do TerraClimate como aproximação).
  - Hemisfério norte (lat > 0): verão e inverno trocados.
"""

import numpy as np
import rasterio
from rasterio.windows import Window

import agrometeorologiapy as amp

# ---------------------------------------------------------------------------
# Estações ponderadas (Tabela 1, Aparecido et al. 2016): verão astronômico do hemisfério sul
# = 1/3 dez + jan + fev + 2/3 mar; inverno = 1/3 jun + jul + ago + 2/3 set. Índice 0 = janeiro.
# ---------------------------------------------------------------------------
PESOS_VERAO_SUL = np.zeros(12)
PESOS_VERAO_SUL[[11, 0, 1, 2]] = [1 / 3, 1, 1, 2 / 3]
PESOS_INVERNO_SUL = np.zeros(12)
PESOS_INVERNO_SUL[[5, 6, 7, 8]] = [1 / 3, 1, 1, 2 / 3]

# ---------------------------------------------------------------------------
# Legendas (código numérico -> letra)
# ---------------------------------------------------------------------------
LEG_UMIDADE = {1: "A", 2: "B4", 3: "B3", 4: "B2", 5: "B1", 6: "C2", 7: "C1", 8: "D", 9: "E"}
LEG_SUBTIPO = {1: "r", 2: "s", 3: "w", 4: "s2", 5: "w2",   # úmidos (Im >= 0), pela deficiência
               6: "d", 7: "s", 8: "w", 9: "s2", 10: "w2"}  # secos (Im < 0), pelo excedente
LEG_TERMICA = {1: "A'", 2: "B4'", 3: "B3'", 4: "B2'", 5: "B1'", 6: "C2'", 7: "C1'", 8: "D'", 9: "E'"}
LEG_CONCENTRACAO = {1: "a'", 2: "b4'", 3: "b3'", 4: "b2'", 5: "b1'", 6: "c2'", 7: "c1'", 8: "d'"}

NOME_UMIDADE = {"A": "Superúmido", "B4": "Úmido", "B3": "Úmido", "B2": "Úmido", "B1": "Úmido",
                "C2": "Subúmido úmido", "C1": "Subúmido seco", "D": "Semiárido", "E": "Árido"}

# Paleta da classe de umidade (do seco para o úmido invertido: 1 = A ... 9 = E), igual ao script JS.
PALETA_UMIDADE = ["#4575b4", "#abd9e9", "#a6d96a", "#fee08b", "#fec44f",
                  "#fe9929", "#ec7014", "#cc4c02", "#8c2d04"]


# ---------------------------------------------------------------------------
# Classificação (arrays numpy; funciona em qualquer formato espacial)
# ---------------------------------------------------------------------------
def _faixas(x, limites, codigos):
    """Código da faixa [limites[i], limites[i+1]) de x; NaN -> 0."""
    idx = np.digitize(x, limites)
    out = np.asarray(codigos, dtype=np.uint8)[idx]
    return np.where(np.isfinite(x), out, 0).astype(np.uint8)


def classe_umidade(im):
    """Tabela 2: Im = Ih - 0,6 Ia."""
    # faixas: <-40 E | -40..-20 D | -20..0 C1 | 0..20 C2 | 20..40 B1 | ... | >=100 A
    return _faixas(im, [-40, -20, 0, 20, 40, 60, 80, 100], [9, 8, 7, 6, 5, 4, 3, 2, 1])


def subtipo(im, ia, ih, def_verao, def_inverno, exc_verao, exc_inverno):
    """Tabela 3: úmidos (Im >= 0) pela deficiência (Ia); secos (Im < 0) pelo excedente (Ih)."""
    umido = im >= 0
    def_v = def_verao > def_inverno   # deficiência de verão -> s
    exc_v = exc_verao > exc_inverno   # excedente de verão -> w
    out = np.zeros(im.shape, dtype=np.uint8)
    # úmidos
    out[umido & (ia < 16.7)] = 1
    out[umido & (ia >= 16.7) & (ia < 33.3) & def_v] = 2
    out[umido & (ia >= 16.7) & (ia < 33.3) & ~def_v] = 3
    out[umido & (ia >= 33.3) & def_v] = 4
    out[umido & (ia >= 33.3) & ~def_v] = 5
    # secos
    seco = im < 0
    out[seco & (ih < 10)] = 6
    out[seco & (ih >= 10) & (ih < 20) & ~exc_v] = 7
    out[seco & (ih >= 10) & (ih < 20) & exc_v] = 8
    out[seco & (ih >= 20) & ~exc_v] = 9
    out[seco & (ih >= 20) & exc_v] = 10
    return out


def eficiencia_termica(pety):
    """Tabela 4: ETP anual (mm)."""
    return _faixas(pety, [142, 285, 427, 570, 712, 855, 997, 1140], [9, 8, 7, 6, 5, 4, 3, 2, 1])


def concentracao_estival(petr):
    """Tabela 5: % da ETP anual concentrada nos 3 meses de verão."""
    return _faixas(petr, [48, 51.9, 56.3, 61.6, 68, 76.3, 88], [1, 2, 3, 4, 5, 6, 7, 8])


def classificar(pet, pr, cad, lat):
    """BHC + classificação para um bloco.

    pet, pr : (12, ...) mm/mês. cad : (...) mm. lat : (...) graus.
    Retorna dict de arrays (...): códigos uint8 (umidade, subtipo, termica, concentracao) e as
    variáveis float32 (pety, def_anual, exc_anual, ih, ia, im).
    """
    valido = np.isfinite(cad) & np.all(np.isfinite(pet), axis=0) & np.all(np.isfinite(pr), axis=0)
    shape = cad.shape
    saida = {k: np.zeros(shape, np.uint8) for k in ("umidade", "subtipo", "termica", "concentracao")}
    saida.update({k: np.full(shape, np.nan, np.float32)
                  for k in ("pety", "def_anual", "exc_anual", "ih", "ia", "im")})
    if not valido.any():
        return saida

    P, ETP, CAD, LAT = pr[:, valido], pet[:, valido], cad[valido], lat[valido]
    bh = amp.balanco_hidrico_climatologico_grade(P, ETP, CAD)

    norte = LAT > 0
    w_verao = np.where(norte, PESOS_INVERNO_SUL[:, None], PESOS_VERAO_SUL[:, None])
    w_inverno = np.where(norte, PESOS_VERAO_SUL[:, None], PESOS_INVERNO_SUL[:, None])

    pety = ETP.sum(0)
    pety_seguro = np.maximum(pety, 1)
    def_anual, exc_anual = bh["DEF"].sum(0), bh["EXC"].sum(0)
    ih = 100 * exc_anual / pety_seguro
    ia = 100 * def_anual / pety_seguro
    im = ih - 0.6 * ia
    petr = 100 * (ETP * w_verao).sum(0) / pety_seguro

    cod = {
        "umidade": classe_umidade(im),
        "subtipo": subtipo(im, ia, ih,
                           (bh["DEF"] * w_verao).sum(0), (bh["DEF"] * w_inverno).sum(0),
                           (bh["EXC"] * w_verao).sum(0), (bh["EXC"] * w_inverno).sum(0)),
        "termica": eficiencia_termica(pety),
        "concentracao": concentracao_estival(petr),
    }
    for k, v in cod.items():
        saida[k][valido] = v
    for k, v in {"pety": pety, "def_anual": def_anual, "exc_anual": exc_anual,
                 "ih": ih, "ia": ia, "im": im}.items():
        saida[k][valido] = v
    return saida


def codigo_completo(umidade, subtipo_, termica, concentracao):
    """Tipo climático por extenso, ex.: "B2rA'a'" (0 em qualquer código -> "")."""
    if 0 in (umidade, subtipo_, termica, concentracao):
        return ""
    return (LEG_UMIDADE[umidade] + LEG_SUBTIPO[subtipo_]
            + LEG_TERMICA[termica] + LEG_CONCENTRACAO[concentracao])


# ---------------------------------------------------------------------------
# Processamento do raster em faixas de linhas (a grade inteira não cabe na memória)
# ---------------------------------------------------------------------------
BANDAS_SAIDA = ["umidade", "subtipo", "termica", "concentracao",
                "pety", "def_anual", "exc_anual", "ih", "ia", "im"]


def processar_raster(arq_pet, arq_pr, cad, mascara, arq_saida, linhas_por_bloco=200):
    """Roda `classificar` sobre a grade inteira e grava um GeoTIFF float32 de 10 bandas
    (BANDAS_SAIDA; códigos 0 = sem dado, variáveis NaN = sem dado).

    cad : float (CAD fixa, mm) ou array 2D (mm) na grade do CHELSA, NaN = sem dado.
    mascara : array 2D bool (True = classificar), na grade do CHELSA.
    """
    with rasterio.open(arq_pet) as fpet, rasterio.open(arq_pr) as fpr:
        altura, largura = fpet.height, fpet.width
        perfil = fpet.profile.copy()
        perfil.update(count=len(BANDAS_SAIDA), dtype="float32", nodata=np.nan,
                      compress="deflate", predictor=3, tiled=True, blockxsize=512, blockysize=512)
        transform = fpet.transform
        with rasterio.open(arq_saida, "w", **perfil) as dst:
            dst.descriptions = tuple(BANDAS_SAIDA)
            for lin0 in range(0, altura, linhas_por_bloco):
                n = min(linhas_por_bloco, altura - lin0)
                janela = Window(0, lin0, largura, n)
                pet = fpet.read(window=janela, masked=True).filled(np.nan).astype(float)
                pr = fpr.read(window=janela, masked=True).filled(np.nan).astype(float)
                if np.isscalar(cad):
                    cad_bl = np.full((n, largura), float(cad))
                else:
                    cad_bl = cad[lin0:lin0 + n].astype(float)
                cad_bl = np.where(mascara[lin0:lin0 + n], cad_bl, np.nan)
                linhas = lin0 + np.arange(n) + 0.5
                lat = np.broadcast_to((transform.f + transform.e * linhas)[:, None], (n, largura))
                res = classificar(pet, pr, cad_bl, lat)
                for i, nome in enumerate(BANDAS_SAIDA, start=1):
                    banda = res[nome].astype("float32")
                    if i <= 4:  # códigos: 0 (sem dado) -> NaN, igual às variáveis
                        banda[banda == 0] = np.nan
                    dst.write(banda, i, window=janela)


# ---------------------------------------------------------------------------
# AWC (GEE): tabela de polígonos de solo -> imagem na grade do CHELSA
# ---------------------------------------------------------------------------
AWC_ROCHA = 0.025  # m³/m³; afloramentos de rocha recebem o menor AWC do asset (CAD = 25 mm com z = 1 m)


def awc_imagem(asset_awc, brasil):
    """ee.Image de 2 bandas: 'awc_mm_m' (AWC x 1000, mm de água por m de solo; corpos d'água
    sem dado) e 'brasil' (1 dentro do contorno do país)."""
    import ee

    fc = ee.FeatureCollection(asset_awc)
    rocha = fc.filter(ee.Filter.eq("ordem", "AFLORAMENTOS DE ROCHAS")).map(
        lambda f: f.set("AWC", AWC_ROCHA))
    solos = fc.filter(ee.Filter.notNull(["AWC"]))
    # paint (e não reduceToImage): bem mais leve no GEE para ~95 mil polígonos.
    awc = (ee.Image().float().paint(solos.merge(rocha), "AWC")
           .multiply(1000).rename("awc_mm_m"))
    mascara_br = ee.Image(0).paint(brasil, 1).rename("brasil")
    return awc.addBands(mascara_br).toFloat()
