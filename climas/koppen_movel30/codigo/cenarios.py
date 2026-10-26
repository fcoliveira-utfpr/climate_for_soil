"""Etapa 4: Köppen móvel de 30 anos nos pontos de SOC e matriz do cenário `koppen_movel30`.

Parte da matriz do relatório v2 (climas/dados_espaco_tempo/matriz_cenarios.parquet = trainingFinal
reconstruída, com as covariáveis da produção, as dobras V2/V3/V4 e o Köppen IPEF) e acrescenta o Köppen do
**ano de cada linha** (janela dos 30 anos anteriores), em dummies hierárquicas L1 (A, B, C), L2 (Af, Am, As,
Aw, BS, BW, Cf, Cs, Cw) e L3 (classe), como as do Köppen na produção. Dummies com menos de 30 ocorrências são
descartadas (regra do R 26). Ponto em pixel sem dado (litoral) recebe a classe do pixel válido mais próximo.
Mesmas funções do capítulo 3 (climas_tempo/codigo/cenarios_tempo.py).

A referência (`koppen_ipef`) não é recalculada: as predições fora da amostra dela já existem no relatório v2
(climas/dados_espaco_tempo/oof e oof_gee), com as mesmas dobras.

Saídas: climas/dados_koppen_movel30/matriz_movel30.parquet (restrita) e codigo/cenarios_movel30.json

Uso: python cenarios.py
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

RAIZ = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(RAIZ / 'climas_tempo' / 'codigo'))
from cenarios_tempo import dummies, indices_pixel, niveis  # noqa: E402

DADOS = RAIZ / 'climas' / 'dados_koppen_movel30'
MATRIZ_V2 = RAIZ / 'climas' / 'dados_espaco_tempo' / 'matriz_cenarios.parquet'
CENARIOS_V2 = RAIZ / 'climas' / 'analise_espaco_tempo' / 'codigo' / 'cenarios.json'
SAIDA_JSON = Path(__file__).with_name('cenarios_movel30.json')


def main():
    g = np.load(DADOS / 'grade.npz')
    k = np.load(DADOS / 'koppen_movel30.npz')
    m = pd.read_parquet(MATRIZ_V2)
    meta = json.loads(CENARIOS_V2.read_text(encoding='utf-8'))
    lin, col, n_fora = indices_pixel(m.longitude.to_numpy(), m.latitude.to_numpy(), g)
    anos = k['anos']
    i_ano = np.clip(m.year.to_numpy(), anos[0], anos[-1]) - anos[0]
    cod = k['koppen'][i_ano, lin, col]
    print(f'{len(m)} linhas; {n_fora} em pixel sem dado (usado o vizinho válido mais próximo)')

    # quanto a classe do ano difere da janela 1991-2020 (o "estático" do Xavier) e quantas classes cada local teve
    cod_2021 = k['koppen'][list(anos).index(2021), lin, col]
    serie = k['koppen'][:, lin, col]                                   # (40 anos, linhas)
    n_classes = np.array([len(np.unique(serie[:, j][serie[:, j] > 0])) for j in range(serie.shape[1])])
    print(f'classe do ano difere da janela 1991-2020 em {100 * (cod != cod_2021).mean():.1f}% das linhas')
    print('linhas por número de classes que o local teve em 1985-2024:',
          pd.Series(n_classes).value_counts().sort_index().to_dict())

    d = dummies(niveis('koppen', cod), 'xkm')
    saida = pd.concat([m, d], axis=1)
    saida.to_parquet(DADOS / 'matriz_movel30.parquet', index=False)
    SAIDA_JSON.write_text(json.dumps({'base': meta['base'], 'cenarios': {'koppen_movel30': list(d.columns)}},
                                     indent=1, ensure_ascii=False), encoding='utf-8')
    print(f'koppen_movel30: {d.shape[1]} dummies -> {DADOS / "matriz_movel30.parquet"}, {SAIDA_JSON.name}')


if __name__ == '__main__':
    main()
