"""Etapa 2: ETo de Penman-Monteith FAO-56 mensal pelo saldo de radiação (Rn), com a agrometeorologiapy, a partir
do Xavier v3.2.4 (1961-2025). Mesmo cálculo de clima_decenal/codigo/eto_rn.py (relatório v4):

    Qo    irradiância extraterrestre no dia 15 do mês
    Qg_cs = (0,75 + 2e-5 z) Qo; BOC = boc_saldo(Rs, r=0.23); BOL = bol_saldo(Tmax, Tmin, ea, min(Rs, Qg_cs), Qg_cs)
    Rn    = saldo_radiacao(BOC, BOL); G = 0,14 (T_mês - T_mês anterior)
    ETo   = eto_penman_monteith_fao56(Rn, G, Tmed, u2, es, ea, Delta, gamma) x dias do mês

A altitude (ETOPO1, média no pixel de 0,1°) e a latitude da grade são as já calculadas
(clima_decenal/dados/altitude.npy e climas_tempo/dados/grade.npz).

Saída (fora do git): C4/dados/eto_rn/<ano>.npz (ETo, Rn, Rs, DPV, Tmed: (12, 393, 391)) e
C4/resultados/tabelas/conferencia_eto.csv (contra a ETo do próprio Xavier v3.2.4)

Uso: python eto_rn.py
"""
import calendar
from pathlib import Path

import numpy as np
import pandas as pd

from agrometeorologiapy.energia import boc_saldo, bol_saldo, saldo_radiacao
from agrometeorologiapy.evapotranspiracao import declive_pressao_vapor, eto_penman_monteith_fao56
from agrometeorologiapy.radiacao import (angulo_horario_nascer, declinacao_solar, fator_correcao_distancia,
                                         irradiancia_extraterrestre, nda)
from agrometeorologiapy.umidade import constante_psicrometrica, ea_umidade, es_tetens, patm_altitude

RAIZ = Path(__file__).resolve().parents[2]
DADOS = RAIZ / 'C4' / 'dados'
MENSAL = DADOS / 'xavier_mensal'
SAIDA = DADOS / 'eto_rn'
TAB = RAIZ / 'C4' / 'resultados' / 'tabelas'
ANOS = range(1961, 2026)


def qo_mensal(lat, ano):
    out = []
    for m in range(1, 13):
        n = nda(15, m, ano)
        dec = declinacao_solar(n)
        out.append(irradiancia_extraterrestre(lat, dec, angulo_horario_nascer(lat, dec), fator_correcao_distancia(n)))
    return np.stack(out)


def eto_ano(d, z, lat, ano, tmed_dez_anterior):
    Tmax, Tmin, UR, Rs, u2 = d['Tmax'], d['Tmin'], d['UR'], d['Rs'], d['u2']
    Tmed = (Tmax + Tmin) / 2
    qcs = (0.75 + 2e-5 * z) * qo_mensal(lat, ano)
    es = (es_tetens(Tmax) + es_tetens(Tmin)) / 2
    ea = ea_umidade(es, UR)
    rn = saldo_radiacao(boc_saldo(Rs, r=0.23), bol_saldo(Tmax, Tmin, ea, np.minimum(Rs, qcs), qcs))
    t_ant = np.concatenate([tmed_dez_anterior[None], Tmed[:-1]])
    G = np.nan_to_num(0.14 * (Tmed - t_ant), nan=0.0)
    gamma = constante_psicrometrica(patm_altitude(z))
    eto_dia = eto_penman_monteith_fao56(rn, G, Tmed, u2, es, ea, declive_pressao_vapor(Tmed), gamma)
    dias = np.array([calendar.monthrange(ano, m)[1] for m in range(1, 13)])[:, None, None]
    return {'ETo': (np.maximum(eto_dia, 0) * dias).astype(np.float32), 'Rn': rn.astype(np.float32),
            'Rs': Rs.astype(np.float32), 'DPV': (es - ea).astype(np.float32), 'Tmed': Tmed.astype(np.float32)}


def main():
    SAIDA.mkdir(parents=True, exist_ok=True)
    TAB.mkdir(parents=True, exist_ok=True)
    z = np.load(RAIZ / 'clima_decenal' / 'dados' / 'altitude.npy')
    lat = np.load(RAIZ / 'climas_tempo' / 'dados' / 'grade.npz')['lat']
    t_dez = np.full(z.shape, np.nan, np.float32)
    conf = []
    for ano in ANOS:
        d = np.load(MENSAL / f'{ano}.npz')
        with np.errstate(invalid='ignore'):
            r = eto_ano(d, z, lat, ano, t_dez)
        np.savez_compressed(SAIDA / f'{ano}.npz', **r)
        t_dez = r['Tmed'][-1]
        ok = np.isfinite(r['ETo']) & np.isfinite(d['ETo_xavier'])
        a, b = r['ETo'][ok], d['ETo_xavier'][ok]
        conf.append({'ano': ano, 'eto_rn_media': a.mean(), 'eto_xavier_media': b.mean(), 'dif_media': (a - b).mean(),
                     'dif_rel_pct': 100 * (a - b).mean() / b.mean(), 'r': np.corrcoef(a, b)[0, 1],
                     'rmse': np.sqrt(((a - b) ** 2).mean())})
    conf = pd.DataFrame(conf)
    conf.to_csv(TAB / 'conferencia_eto.csv', index=False, float_format='%.4g')
    print(conf.describe().round(3).to_string())


if __name__ == '__main__':
    main()
