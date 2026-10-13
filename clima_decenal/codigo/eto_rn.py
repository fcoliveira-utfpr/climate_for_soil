"""Etapa 2: ETo de Penman-Monteith FAO-56 mensal a partir do saldo de radiação (Rn), com a agrometeorologiapy.

Para cada mês de cada ano (1961-2022), com as médias mensais do Xavier (baixar_xavier.py):
    Qo   irradiancia_extraterrestre(lat, declinacao_solar(NDA), angulo_horario_nascer, fator_correcao_distancia),
         no dia 15 do mês
    Qg_cs = (0,75 + 2e-5 z) Qo                                       (FAO-56, eq. 37; z = altitude, ETOPO1)
    BOC  = boc_saldo(Rs, r=0.23)                                      (albedo da grama de referência)
    BOL  = bol_saldo(Tmax, Tmin, ea, min(Rs, Qg_cs), Qg_cs)          (Rs/Rso <= 1, FAO-56, eq. 39)
    Rn   = saldo_radiacao(BOC, BOL)
    G    = 0,14 (T_mês - T_mês anterior)                             (FAO-56, eq. 44)
    es   = [es_tetens(Tmax) + es_tetens(Tmin)] / 2; ea = ea_umidade(es, UR)   (FAO-56, eq. 12 e 19)
    Delta = declive_pressao_vapor(Tmed); gamma = constante_psicrometrica(patm_altitude(z))
    ETo  = eto_penman_monteith_fao56(Rn, G, Tmed, u2, es, ea, Delta, gamma) x dias do mês
Meses sem dado (depois de 07/2020) ficam NaN.

Saída (fora do git): clima_decenal/dados/eto_rn/<ano>.npz com ETo (mm/mês), Rn e Rs (MJ/m² dia, média do mês),
DPV (kPa) e Tmed (°C), cada um (12, 393, 391); e a conferência com a ETo do Xavier em
clima_decenal/resultados/tabelas/conferencia_eto.csv

Uso: python eto_rn.py
"""
import calendar
import json
from pathlib import Path

import numpy as np
import pandas as pd

from agrometeorologiapy.energia import boc_saldo, bol_saldo, saldo_radiacao
from agrometeorologiapy.evapotranspiracao import declive_pressao_vapor, eto_penman_monteith_fao56
from agrometeorologiapy.radiacao import (angulo_horario_nascer, declinacao_solar, fator_correcao_distancia,
                                         irradiancia_extraterrestre, nda)
from agrometeorologiapy.umidade import constante_psicrometrica, ea_umidade, es_tetens, patm_altitude

RAIZ = Path(__file__).resolve().parents[2]
DADOS = RAIZ / 'clima_decenal' / 'dados'
MENSAL = DADOS / 'xavier_mensal'
SAIDA = DADOS / 'eto_rn'
XAVIER_ETO = RAIZ / 'climas_tempo' / 'dados' / 'xavier_mensal'     # ETo pronta do Xavier (conferência)
TAB = RAIZ / 'clima_decenal' / 'resultados' / 'tabelas'
ANOS = range(1961, 2023)


def grade():
    g = json.loads((XAVIER_ETO / 'grade.json').read_text())['affineTransform']
    h, w = 393, 391
    lat = g['translateY'] + g['scaleY'] * (np.arange(h) + 0.5)
    return np.repeat(lat[:, None], w, axis=1)


def qo_mensal(lat, ano):
    """Irradiância extraterrestre (MJ/m² dia) no dia 15 de cada mês, (12, H, W)."""
    out = []
    for m in range(1, 13):
        n = nda(15, m, ano)
        dec = declinacao_solar(n)
        hn = angulo_horario_nascer(lat, dec)
        out.append(irradiancia_extraterrestre(lat, dec, hn, fator_correcao_distancia(n)))
    return np.stack(out)


def eto_ano(d, z, lat, ano, tmed_dez_anterior):
    Tmax, Tmin, UR, Rs, u2 = d['Tmax'], d['Tmin'], d['UR'], d['Rs'], d['u2']
    Tmed = (Tmax + Tmin) / 2
    qo = qo_mensal(lat, ano)
    qcs = (0.75 + 2e-5 * z) * qo
    es = (es_tetens(Tmax) + es_tetens(Tmin)) / 2
    ea = ea_umidade(es, UR)
    rn = saldo_radiacao(boc_saldo(Rs, r=0.23), bol_saldo(Tmax, Tmin, ea, np.minimum(Rs, qcs), qcs))
    t_ant = np.concatenate([tmed_dez_anterior[None], Tmed[:-1]])
    G = 0.14 * (Tmed - t_ant)
    G = np.where(np.isfinite(G), G, 0.0)
    gamma = constante_psicrometrica(patm_altitude(z))
    eto_dia = eto_penman_monteith_fao56(rn, G, Tmed, u2, es, ea, declive_pressao_vapor(Tmed), gamma)
    dias = np.array([calendar.monthrange(ano, m)[1] for m in range(1, 13)])[:, None, None]
    return {'ETo': (np.maximum(eto_dia, 0) * dias).astype(np.float32), 'Rn': rn.astype(np.float32),
            'Rs': Rs.astype(np.float32), 'DPV': (es - ea).astype(np.float32), 'Tmed': Tmed.astype(np.float32)}


def main():
    SAIDA.mkdir(parents=True, exist_ok=True)
    TAB.mkdir(parents=True, exist_ok=True)
    z = np.load(DADOS / 'altitude.npy')
    lat = grade()
    t_dez = np.full(z.shape, np.nan, np.float32)
    conf = []
    for ano in ANOS:
        d = np.load(MENSAL / f'{ano}.npz')
        with np.errstate(invalid='ignore'):
            r = eto_ano(d, z, lat, ano, t_dez)
        np.savez_compressed(SAIDA / f'{ano}.npz', **r)
        t_dez = r['Tmed'][-1]
        x = np.load(XAVIER_ETO / f'{ano}.npz')['ETo']
        ok = np.isfinite(r['ETo']) & np.isfinite(x)
        if ok.any():
            a, b = r['ETo'][ok], x[ok]
            conf.append({'ano': ano, 'eto_rn_media': a.mean(), 'eto_xavier_media': b.mean(),
                         'dif_media': (a - b).mean(), 'dif_rel_pct': 100 * (a - b).mean() / b.mean(),
                         'r': np.corrcoef(a, b)[0, 1], 'rmse': np.sqrt(((a - b) ** 2).mean())})
        print(ano, 'ok', flush=True)
    conf = pd.DataFrame(conf)
    conf.to_csv(TAB / 'conferencia_eto.csv', index=False, float_format='%.4g')
    print(conf.describe().round(3).to_string())


if __name__ == '__main__':
    main()
