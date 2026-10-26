"""Etapa 2: Köppen dinâmico por média móvel de 30 anos, do Xavier (BR-DWGD), para cada ano de 1985 a 2024.

Para o ano Y: normal mensal de temperatura e chuva sobre os anos Y-30 a Y-1 disponíveis (o Xavier começa em
1961; no GEE a temperatura vai até 07/2020 e a chuva até 2022), classificada com
`classificacao_koppen_grade` da agrometeorologiapy e filtro de moda 3 x 3 (como no capítulo 3). Os anos com
janela incompleta ficam registrados em n_anos_T e n_anos_P (mínimo de anos entre os meses, no Brasil).

Reaproveita o download mensal e as funções do capítulo 3 (climas_tempo/codigo/classificar.py).

Saídas (fora do git), em climas/dados_koppen_movel30/:
    koppen_movel30.npz   koppen (40, 393, 391) com o id 1-31 (0 = sem dado), anos, n_anos_T, n_anos_P
    grade.npz            lat, lon, máscara do Brasil e a transformação afim da grade

Uso: python classificar_movel30.py
"""
import sys
from pathlib import Path

import numpy as np

from agrometeorologiapy.classificacao_climatica import classificacao_koppen_grade

RAIZ = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(RAIZ / 'climas_tempo' / 'codigo'))
import classificar as cap3  # noqa: E402  (carregar, grade, normal, moda3x3)

DADOS = RAIZ / 'climas' / 'dados_koppen_movel30'
ANOS = range(1985, 2025)
JANELA = 30


def koppen(T, P, lat, valido):
    T, P = (np.where(valido, x, np.nan) for x in (T, P))
    return cap3.moda3x3(classificacao_koppen_grade(T, P, lat)['id'], valido)


def main():
    DADOS.mkdir(parents=True, exist_ok=True)
    T, P, _ = cap3.carregar()                       # (ano, 12, 393, 391), anos 1961-2022
    transf, h, w, lon, lat = cap3.grade()
    brasil = np.isfinite(P).all(axis=(0, 1))
    anos_dados = np.array(list(cap3.ANOS_DADOS))
    np.savez_compressed(DADOS / 'grade.npz', lat=lat, lon=lon, brasil=brasil, transf=np.array(transf)[:6])
    cls, n_T, n_P = [], [], []
    for ano in ANOS:
        idx = np.where((anos_dados >= ano - JANELA) & (anos_dados <= ano - 1))[0]
        tn, nt = cap3.normal(T, idx)
        pn, npr = cap3.normal(P, idx)
        cls.append(koppen(tn, pn, lat, brasil))
        n_T.append(int(nt[brasil].min())), n_P.append(int(npr[brasil].min()))
        print(f'{ano}: janela {ano - JANELA}-{ano - 1}, anos com T {n_T[-1]}, com chuva {n_P[-1]}', flush=True)
    np.savez_compressed(DADOS / 'koppen_movel30.npz', koppen=np.stack(cls).astype(np.uint8),
                        anos=np.array(list(ANOS)), n_anos_T=n_T, n_anos_P=n_P)


if __name__ == '__main__':
    main()
