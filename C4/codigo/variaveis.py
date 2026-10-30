"""Etapa 3: variáveis climáticas em média móvel de 10 anos (Y-10 a Y-1), para cada ano de 1985 a 2026, com o
Xavier v3.2.4 (todas as variáveis até 2025: as janelas ficam completas até 2026).

Mesmas variáveis cd_* de clima_decenal/codigo/variaveis.py (relatório v4): temperatura (7), chuva (5), energia
e ar (6), razões (2) e balanço hídrico com CAD 100 mm e com a CAD do solo (9 + 9), mais o CDD decenal
**cd_cdd** (média do CDD anual da janela), que no v4 vinha pronto na matriz (dec_cdd, da grade antiga, até
2022).

Saída (fora do git): C4/dados/variaveis/<ano>.npz (cada variável (393, 391)) e n_anos.csv

Uso: python variaveis.py
"""
from pathlib import Path

import numpy as np
import pandas as pd

from agrometeorologiapy.balanco_hidrico import balanco_hidrico_climatologico_grade
from agrometeorologiapy.classificacao_climatica import classificacao_holdridge_grade

RAIZ = Path(__file__).resolve().parents[2]
DADOS = RAIZ / 'C4' / 'dados'
SAIDA = DADOS / 'variaveis'
ANOS_DADOS = range(1961, 2026)
ANOS = range(1985, 2027)
LIMIAR_MES_SECO = 60.0      # mm
LIMIAR_MES_DEF = 5.0        # mm


def carregar():
    """Séries mensais (ano, 12, H, W) de cada variável e o CDD anual (ano, H, W)."""
    xs = {v: [] for v in ('Tmax', 'Tmin', 'UR', 'Rs', 'u2', 'P', 'Rn', 'ETo', 'DPV', 'CDD')}
    for a in ANOS_DADOS:
        d = np.load(DADOS / 'xavier_mensal' / f'{a}.npz')
        e = np.load(DADOS / 'eto_rn' / f'{a}.npz')
        for v in ('Tmax', 'Tmin', 'UR', 'Rs', 'u2', 'P', 'CDD'):
            xs[v].append(d[v])
        for v in ('Rn', 'ETo', 'DPV'):
            xs[v].append(e[v])
    return {v: np.stack(x) for v, x in xs.items()}


def balanco(P, ETo, cad, sufixo):
    bh = balanco_hidrico_climatologico_grade(P, ETo, cad)
    eto_a = np.maximum(ETo.sum(0), 1e-6)
    d, e, etr = bh['DEF'].sum(0), bh['EXC'].sum(0), bh['ETR'].sum(0)
    ih, ia = 100 * e / eto_a, 100 * d / eto_a
    return {f'cd_def{sufixo}': d, f'cd_exc{sufixo}': e, f'cd_etr{sufixo}': etr, f'cd_etr_eto{sufixo}': etr / eto_a,
            f'cd_ih{sufixo}': ih, f'cd_ia{sufixo}': ia, f'cd_im{sufixo}': ih - 0.6 * ia,
            f'cd_meses_def{sufixo}': (bh['DEF'] > LIMIAR_MES_DEF).sum(0).astype(float),
            f'cd_arm{sufixo}': bh['ARM'].mean(0)}


def variaveis(n, lat, cad, valido):
    Tmax, Tmin, P, ETo = n['Tmax'], n['Tmin'], n['P'], n['ETo']
    T = (Tmax + Tmin) / 2
    out = {
        'cd_t_media': T.mean(0), 'cd_tmax_media': Tmax.mean(0), 'cd_tmin_media': Tmin.mean(0),
        'cd_t_mes_quente': T.max(0), 'cd_t_mes_frio': T.min(0), 'cd_amplitude': (Tmax - Tmin).mean(0),
        'cd_biotemp': classificacao_holdridge_grade(T, P, lat)['biotemperatura'],
        'cd_p_anual': P.sum(0), 'cd_p_mes_seco': P.min(0), 'cd_p_mes_chuvoso': P.max(0),
        'cd_p_sazonalidade': P.std(0) / np.maximum(P.mean(0), 1e-6),
        'cd_meses_secos': (P < LIMIAR_MES_SECO).sum(0).astype(float),
        'cd_rs': n['Rs'].mean(0), 'cd_rn': n['Rn'].mean(0), 'cd_eto': ETo.sum(0), 'cd_ur': n['UR'].mean(0),
        'cd_dpv': n['DPV'].mean(0), 'cd_u2': n['u2'].mean(0),
        'cd_eto_p': ETo.sum(0) / np.maximum(P.sum(0), 1.0), 'cd_p_menos_eto': P.sum(0) - ETo.sum(0),
        'cd_cdd': n['CDD'],
    }
    out.update(balanco(P, ETo, np.full(lat.shape, 100.0), '_c100'))
    out.update(balanco(P, ETo, np.where(np.isfinite(cad) & (cad > 0), cad, 100.0), '_csolo'))
    return {k: np.where(valido, v, np.nan).astype(np.float32) for k, v in out.items()}


def main():
    SAIDA.mkdir(parents=True, exist_ok=True)
    g = np.load(RAIZ / 'climas_tempo' / 'dados' / 'grade.npz')
    lat, cad, brasil = g['lat'], g['cad'], g['brasil']
    X = carregar()
    anos_dados = np.array(list(ANOS_DADOS))
    registro = []
    for ano in ANOS:
        idx = np.where((anos_dados >= ano - 10) & (anos_dados <= ano - 1))[0]
        n, nanos = {}, {}
        for v, serie in X.items():
            with np.errstate(invalid='ignore'):
                n[v] = np.nanmean(serie[idx], axis=0)
            nanos[v] = int(np.isfinite(serie[idx][..., brasil]).sum(axis=0).min())
        valido = brasil & np.all([np.isfinite(n[v]).reshape(-1, *brasil.shape).all(0) for v in n], axis=0)
        with np.errstate(invalid='ignore', divide='ignore'):
            np.savez_compressed(SAIDA / f'{ano}.npz', **variaveis(n, lat, cad, valido))
        registro.append({'ano': ano, **{f'n_anos_{v}': k for v, k in nanos.items()}})
        print(ano, 'anos na janela:', {v: nanos[v] for v in ('Tmax', 'Rs', 'P', 'CDD')}, flush=True)
    pd.DataFrame(registro).to_csv(SAIDA / 'n_anos.csv', index=False)


if __name__ == '__main__':
    main()
