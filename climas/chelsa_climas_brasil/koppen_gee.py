# -*- coding: utf-8 -*-
"""Classificação climática de Köppen-Geiger (31 classes) no Earth Engine (API
Python), metodologia Alvares et al. (2013).

Entrada: dois assets separados (tas e pr; 12 bandas mensais cada, a normal
1991-2020), gerados por gerar_normal_multibanda.py. As bandas já estão em
unidades físicas (tas em °C; pr em mm/mês): não há offset/fator a aplicar.
Adaptado do script JS original (base TerraClimate) para usar a normal do
CHELSA V2.1 -- tas já é a temperatura média mensal (não precisa de
(tmmx+tmmn)/2), e pet não entra nessa classificação.

Correções em relação ao script JS: (1) sazonalidade dos climas C/D (f/s/w) pelo critério de
Kottek et al. (2006) -- s e w mutuamente exclusivos e f = "nem s nem w"; antes f era "mês mais
seco >= 40 mm" e pixels com mês seco < 40 mm sem seca sazonal forte ficavam sem classe (~5% da
área C do Brasil); (2) verão e inverno trocados ao norte do equador (afeta As/Aw, o limiar do
grupo B e s/w em Roraima e no Amapá).
"""
import ee

MESES_VERAO = [10, 11, 12, 1, 2, 3]  # out-mar (hemisfério sul; trocados com o inverno ao norte do equador)
MESES_INVERNO = [4, 5, 6, 7, 8, 9]   # abr-set

LEGENDA = {
    1: "Af", 2: "Am", 3: "As", 4: "Aw",
    5: "BSh", 6: "BSk", 7: "BWh", 8: "BWk",
    9: "Cfa", 10: "Cfb", 11: "Cfc",
    12: "Csa", 13: "Csb", 14: "Csc",
    15: "Cwa", 16: "Cwb", 17: "Cwc",
    18: "Dfa", 19: "Dfb", 20: "Dfc", 21: "Dfd",
    22: "Dsa", 23: "Dsb", 24: "Dsc", 25: "Dsd",
    26: "Dwa", 27: "Dwb", 28: "Dwc", 29: "Dwd",
    30: "ET", 31: "EF",
}

PALETA = [
    "#0000FF", "#0078FF", "#46A0FF", "#96C8FF",
    "#F5A623", "#FFDA8C", "#FF0000", "#FF9696",
    "#C8FF50", "#64FF50", "#32C800",
    "#FFFF00", "#C8C800", "#969600",
    "#C8FFC8", "#96FF96", "#64C864",
    "#B4A0FA", "#8C78F0", "#6450E6", "#3C2CB4",
    "#E0C8FF", "#C8A0FF", "#B478FF", "#9650FF",
    "#D2D2FF", "#AAAAFF", "#8282FF", "#5A5AFF",
    "#B4B4B4", "#696969",
]


def carregar_normal(asset_tas: str, asset_pr: str) -> ee.Image:
    """Carrega os assets de tas e pr (12 bandas mensais cada) e junta num
    único ee.Image de 24 bandas, com os nomes garantidos pela ordem."""
    assets = {"tas": asset_tas, "pr": asset_pr}
    imagens = []
    for var, asset_id in assets.items():
        img = ee.Image(asset_id)
        n = img.bandNames().size().getInfo()
        if n != 12:
            raise ValueError(f"O asset {asset_id} ({var}) tem {n} bandas; esperado 12 (uma por mês).")
        imagens.append(img.rename([f"{var}_{m:02d}" for m in range(1, 13)]))
    return ee.Image.cat(imagens)


def _bandas_meses(normal: ee.Image, prefixo: str, meses) -> ee.Image:
    return normal.select([f"{prefixo}_{m:02d}" for m in meses])


def classificar_koppen(normal: ee.Image) -> ee.Image:
    """Retorna a imagem de classes de Köppen-Geiger (id 1-31, mascarada onde
    não classificado), mesma lógica/ordem de precedência do script JS
    original (grupo B por último, sobrepõe qualquer outro grupo)."""
    tas = normal.select("tas_.*")
    pr = normal.select("pr_.*")

    temp_anual = tas.reduce(ee.Reducer.mean()).rename("temp_anual")
    tcold = tas.reduce(ee.Reducer.min()).rename("tcold")
    thot = tas.reduce(ee.Reducer.max()).rename("thot")
    tmon10 = tas.gt(10).reduce(ee.Reducer.sum()).rename("tmon10")

    rann = pr.reduce(ee.Reducer.sum()).rename("rann")
    rdry = pr.reduce(ee.Reducer.min()).rename("rdry")

    # Estatísticas dos semestres out-mar e abr-set; ao norte do equador o verão é abr-set.
    pr_out_mar = _bandas_meses(normal, "pr", MESES_VERAO)
    pr_abr_set = _bandas_meses(normal, "pr", MESES_INVERNO)
    norte = ee.Image.pixelLonLat().select("latitude").gt(0)

    def por_hemisferio(reducer):
        out_mar, abr_set = pr_out_mar.reduce(reducer), pr_abr_set.reduce(reducer)
        return out_mar.where(norte, abr_set), abr_set.where(norte, out_mar)  # (verão, inverno)

    prec_verao_sum, prec_inverno_sum = por_hemisferio(ee.Reducer.sum())
    psdry, pwdry = por_hemisferio(ee.Reducer.min())
    pswet, pwwet = por_hemisferio(ee.Reducer.max())

    pct_verao = prec_verao_sum.divide(rann)
    pct_inverno = prec_inverno_sum.divide(rann)
    p_threshold = temp_anual.multiply(2).add(14)
    p_threshold = p_threshold.where(pct_inverno.gte(0.7), temp_anual.multiply(2))
    p_threshold = p_threshold.where(pct_verao.gte(0.7), temp_anual.multiply(2).add(28))

    grupo_a = tcold.gte(18)
    grupo_c = thot.gt(10).And(tcold.gt(-3)).And(tcold.lt(18))
    grupo_d = thot.gt(10).And(tcold.lte(-3))
    grupo_e = thot.lte(10)
    grupo_b = rann.lt(p_threshold.multiply(10))

    # --- subtipos tropicais (A) ---
    am_thr = ee.Image(100).subtract(rann.divide(25))
    af = grupo_a.And(rdry.gte(60))
    am = grupo_a.And(rdry.lt(60)).And(rdry.gte(am_thr))
    a_seca = grupo_a.And(rdry.lt(60)).And(rdry.lt(am_thr))
    a_s = a_seca.And(psdry.lt(pwdry))
    a_w = a_seca.And(psdry.gte(pwdry))

    # --- subtipos secos (B) ---
    is_bw = grupo_b.And(rann.lt(p_threshold.multiply(5)))
    is_bs = grupo_b.And(rann.gte(p_threshold.multiply(5)))
    bwh = is_bw.And(temp_anual.gte(18))
    bwk = is_bw.And(temp_anual.lt(18))
    bsh = is_bs.And(temp_anual.gte(18))
    bsk = is_bs.And(temp_anual.lt(18))

    # --- sazonalidade C/D (Kottek et al. 2006) ---
    # s: verão seco; w: inverno seco; f: nem s nem w (s e w são mutuamente exclusivos).
    is_s = psdry.lt(pwdry).And(pwwet.gt(psdry.multiply(3))).And(psdry.lt(40))
    is_w = pwdry.lt(psdry).And(pswet.gt(pwdry.multiply(10)))
    is_f = is_s.Not().And(is_w.Not())

    is_quente = thot.gte(22)
    is_temperado = is_quente.Not().And(tmon10.gte(4))
    is_curto = is_quente.Not().And(is_temperado.Not()).And(tmon10.gte(1)).And(tmon10.lt(4))
    is_muito_frio = tcold.lt(-38)

    cfa = grupo_c.And(is_f).And(is_quente)
    cfb = grupo_c.And(is_f).And(is_temperado)
    cfc = grupo_c.And(is_f).And(is_curto)
    csa = grupo_c.And(is_s).And(is_quente)
    csb = grupo_c.And(is_s).And(is_temperado)
    csc = grupo_c.And(is_s).And(is_curto)
    cwa = grupo_c.And(is_w).And(is_quente)
    cwb = grupo_c.And(is_w).And(is_temperado)
    cwc = grupo_c.And(is_w).And(is_curto)

    dfa = grupo_d.And(is_f).And(is_quente)
    dfb = grupo_d.And(is_f).And(is_temperado)
    dfc = grupo_d.And(is_f).And(is_curto)
    dfd = grupo_d.And(is_f).And(is_muito_frio)
    dsa = grupo_d.And(is_s).And(is_quente)
    dsb = grupo_d.And(is_s).And(is_temperado)
    dsc = grupo_d.And(is_s).And(is_curto)
    dsd = grupo_d.And(is_s).And(is_muito_frio)
    dwa = grupo_d.And(is_w).And(is_quente)
    dwb = grupo_d.And(is_w).And(is_temperado)
    dwc = grupo_d.And(is_w).And(is_curto)
    dwd = grupo_d.And(is_w).And(is_muito_frio)

    # --- subtipos polares (E) ---
    et = grupo_e.And(thot.gt(0))
    ef = grupo_e.And(thot.lte(0))

    klass = (ee.Image(0).rename("koppen")
             .where(af, 1).where(am, 2).where(a_s, 3).where(a_w, 4)
             .where(cfa, 9).where(cfb, 10).where(cfc, 11)
             .where(csa, 12).where(csb, 13).where(csc, 14)
             .where(cwa, 15).where(cwb, 16).where(cwc, 17)
             .where(dfa, 18).where(dfb, 19).where(dfc, 20).where(dfd, 21)
             .where(dsa, 22).where(dsb, 23).where(dsc, 24).where(dsd, 25)
             .where(dwa, 26).where(dwb, 27).where(dwc, 28).where(dwd, 29)
             .where(et, 30).where(ef, 31)
             .where(bsh, 5).where(bsk, 6).where(bwh, 7).where(bwk, 8))

    return klass.updateMask(klass.neq(0))
