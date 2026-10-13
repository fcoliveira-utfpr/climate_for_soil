"""Etapa 4a: classes climáticas do Xavier nos pontos de SOC e matriz dos cenários do capítulo 3.

Parte da matriz do relatório v2 (climas/dados_espaco_tempo/matriz_cenarios.parquet = trainingFinal, com as
covariáveis da produção, as dobras V2/V3/V4 e os climas do capítulo 1) e acrescenta, para cada sistema do
Xavier (Köppen, Holdridge ETP original, Thornthwaite CAD do solo, zonas k10 reajustadas no Xavier; todos com
moda 3 x 3), duas versões:
    <sistema>_est  normal 1991-2020 (estática)
    <sistema>_dec  normal da década da linha (1985-1994, 1995-2004, 2005-2014, 2015-2024), pelo ano da linha
A diferença entre as duas isola o efeito de o clima mudar no tempo, com a mesma fonte e o mesmo sistema.

Dummies hierárquicas, como as do Köppen na produção:
    Köppen        L1 (A, B, C), L2 (Af, Am, As, Aw, BS, BW, Cf, Cs, Cw), L3 (classe)
    Holdridge     L1 (faixa térmica: tropical, subtropical, temperado quente...), L2 (zona de vida)
    Thornthwaite  L1 (classe de umidade), L2 (umidade + subtipo)
    k10           zona
Dummies com menos de 30 ocorrências são descartadas (regra do R 26). Ponto em pixel sem dado (litoral) recebe
a classe do pixel válido mais próximo.

Saídas: climas_tempo/dados/matriz_cap3.parquet (restrita) e climas_tempo/codigo/cenarios_cap3.json

Uso: python cenarios_tempo.py
"""
import json
import re
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.spatial import cKDTree

from agrometeorologiapy.classificacao_climatica import HOLDRIDGE_ZONAS_EN, KOPPEN_CLASSES, TH_SUBTIPO, TH_UMIDADE

RAIZ = Path(__file__).resolve().parents[2]
DADOS = RAIZ / 'climas_tempo' / 'dados'
MATRIZ_V2 = RAIZ / 'climas' / 'dados_espaco_tempo' / 'matriz_cenarios.parquet'
CENARIOS_V2 = RAIZ / 'climas' / 'analise_espaco_tempo' / 'codigo' / 'cenarios.json'
SAIDA_JSON = Path(__file__).with_name('cenarios_cap3.json')
MIN_OCORRENCIAS = 30
FAIXAS_HOLDRIDGE = [(1, 2, 'polar'), (3, 6, 'subpolar'), (7, 11, 'boreal'), (12, 17, 'temperado_frio'),
                    (18, 24, 'temperado_quente'), (25, 31, 'subtropical'), (32, 38, 'tropical')]


def _nome(s):
    return re.sub(r'[^0-9A-Za-z_]+', '_', str(s)).strip('_')


def niveis(sistema, codigo):
    """Códigos -> DataFrame com os níveis hierárquicos (strings; '' = sem classe)."""
    c = pd.Series(codigo)
    if sistema == 'koppen':
        l3 = c.map(KOPPEN_CLASSES).fillna('')
        l2 = l3.str[:2]
        return pd.DataFrame({'l1': l3.str[:1], 'l2': l2, 'l3': l3})
    if sistema == 'holdridge':
        faixa = c.map(lambda z: next((n for a, b, n in FAIXAS_HOLDRIDGE if a <= z <= b), ''))
        return pd.DataFrame({'l1': faixa, 'l2': c.map(lambda z: f'{z} {HOLDRIDGE_ZONAS_EN.get(z, "")}' if z else '')})
    if sistema == 'thornthwaite':
        u = (c // 100).map(TH_UMIDADE).fillna('')
        sub = (c % 100).map(TH_SUBTIPO).fillna('')
        return pd.DataFrame({'l1': u, 'l2': u + sub})
    if sistema == 'k10':
        return pd.DataFrame({'l1': c.map(lambda z: f'zona_{z}' if z else '')})
    raise ValueError(sistema)


def dummies(df_niveis, prefixo):
    blocos = []
    for nivel in df_niveis:
        d = pd.get_dummies(df_niveis[nivel].replace('', np.nan), prefix=f'{prefixo}_{nivel}', dtype=int)
        d.columns = [_nome(x) for x in d.columns]
        blocos.append(d.loc[:, d.sum() >= MIN_OCORRENCIAS])
    return pd.concat(blocos, axis=1)


def indices_pixel(lon, lat, g):
    """Pixel de cada ponto; fora do Brasil / sem dado -> pixel válido mais próximo."""
    glon, glat, br = g['lon'], g['lat'], g['brasil']
    lin = np.clip(np.floor((glat[0, 0] + 0.05 - lat) / 0.1).astype(int), 0, br.shape[0] - 1)
    col = np.clip(np.floor((lon - (glon[0, 0] - 0.05)) / 0.1).astype(int), 0, br.shape[1] - 1)
    fora = ~br[lin, col]
    if fora.any():
        vl, vc = np.where(br)
        arv = cKDTree(np.c_[glon[vl, vc], glat[vl, vc]])
        _, i = arv.query(np.c_[lon[fora], lat[fora]])
        lin[fora], col[fora] = vl[i], vc[i]
    return lin, col, int(fora.sum())


def main():
    g = np.load(DADOS / 'grade.npz')
    dec = np.load(DADOS / 'classes_decadas.npz')
    est = np.load(DADOS / 'classes_1991_2020.npz')
    m = pd.read_parquet(MATRIZ_V2)
    meta = json.loads(CENARIOS_V2.read_text(encoding='utf-8'))
    lin, col, n_fora = indices_pixel(m.longitude.to_numpy(), m.latitude.to_numpy(), g)
    decada = np.searchsorted([1995, 2005, 2015], m.year.to_numpy(), side='right')      # 0..3
    print(f'{len(m)} linhas; {n_fora} em pixel sem dado (usado o vizinho válido mais próximo)')
    print('linhas por década:', pd.Series(decada).value_counts().sort_index().to_dict())

    novos, cenarios = [], {}
    for s in ('koppen', 'holdridge', 'thornthwaite', 'k10'):
        cod_est = est[s][lin, col]
        cod_dec = dec[s][decada, lin, col]
        for versao, cod in (('est', cod_est), ('dec', cod_dec)):
            d = dummies(niveis(s, cod), f'x{s[:2]}_{versao}')
            novos.append(d)
            cenarios[f'{s}_{versao}'] = list(d.columns)
        mud = 100 * (cod_est != cod_dec).mean()
        print(f'  {s}: classe da década difere da 1991-2020 em {mud:.1f}% das linhas; '
              f'{len(cenarios[s + "_est"])} / {len(cenarios[s + "_dec"])} dummies')
    saida = pd.concat([m] + novos, axis=1)
    saida.to_parquet(DADOS / 'matriz_cap3.parquet', index=False)
    SAIDA_JSON.write_text(json.dumps({'base': meta['base'], 'cenarios': cenarios}, indent=1, ensure_ascii=False),
                          encoding='utf-8')
    print(f'-> {DADOS / "matriz_cap3.parquet"} ({saida.shape[1]} colunas), {SAIDA_JSON.name}')


if __name__ == '__main__':
    main()
