"""Etapa 1: cenários do capítulo 6 e partições novas de validação.

Testa, em partições V2/V4 que não foram usadas para escolher as variáveis (relatório v4), o conjunto curto
(temperatura decenal + CDD + ARM com a CAD do solo) e o híbrido (temperatura decenal + balanço hídrico
estático 1991-2020), contra a temperatura decenal sozinha, o contínuo decenal do v2, o Köppen IPEF e o
controle sem clima.

Parte da matriz do relatório v4 (clima_decenal/dados/matriz_cd.parquet = trainingFinal reconstruída + as
variáveis decenais cd_* + as normais clim_* do CHELSA) e troca as dobras espaciais fold_v2_1..3 por uma
partição nova (mesmo procedimento do v2, semente 2027). A V3 continua com os períodos fixos; nela só mudam
as sementes dos modelos (VAL_SEMENTE).

Saídas: clima_final/dados/matriz_final.parquet (restrita), codigo/cenarios_final.json e
resultados/tabelas/particoes.csv (linhas por dobra e concordância com a partição antiga)

Uso: python cenarios_final.py
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / 'climas' / 'analise_espaco_tempo' / 'codigo'))
from cenarios import dobras  # noqa: E402

DADOS = RAIZ / 'clima_final' / 'dados'
TAB = RAIZ / 'clima_final' / 'resultados' / 'tabelas'
MATRIZ_V4 = RAIZ / 'clima_decenal' / 'dados' / 'matriz_cd.parquet'
CENARIOS_V2 = RAIZ / 'climas' / 'analise_espaco_tempo' / 'codigo' / 'cenarios.json'
SEMENTE_DOBRAS = 2027

TEMPERATURA = ['cd_t_media', 'cd_tmax_media', 'cd_tmin_media', 'cd_t_mes_quente', 'cd_t_mes_frio', 'cd_amplitude',
               'cd_biotemp']
CURTO = ['dec_cdd', 'cd_arm_csolo']
# balanço hídrico estático: as normais hídricas do CHELSA que a seleção aninhada do v2 manteve no modelo final
HIDRICO_ESTATICO = ['clim_p_anual', 'clim_p_mes_seco', 'clim_p_sazonalidade', 'clim_etp_anual', 'clim_def_anual']


def concordancia(a, b):
    """Fração dos pares de blocos que ficam juntos (ou separados) nas duas partições (índice de Rand)."""
    a, b = np.asarray(a), np.asarray(b)
    ja, jb = a[:, None] == a[None, :], b[:, None] == b[None, :]
    iu = np.triu_indices(len(a), 1)
    return (ja[iu] == jb[iu]).mean()


def main():
    DADOS.mkdir(parents=True, exist_ok=True)
    TAB.mkdir(parents=True, exist_ok=True)
    m = pd.read_parquet(MATRIZ_V4)
    v2 = json.loads(CENARIOS_V2.read_text(encoding='utf-8'))
    antigas = m[['bloco', 'fold_v2_1', 'fold_v2_2', 'fold_v2_3']].copy()
    m = dobras(m.drop(columns=['fold_v2_1', 'fold_v2_2', 'fold_v2_3']), semente=SEMENTE_DOBRAS)
    assert (m.bloco == antigas.bloco).all()

    linhas = []
    por_bloco = pd.concat([antigas, m[['fold_v2_1', 'fold_v2_2', 'fold_v2_3']].add_prefix('nova_')], axis=1)
    por_bloco = por_bloco.groupby('bloco').first()
    for r in (1, 2, 3):
        cont = m[f'fold_v2_{r}'].value_counts().sort_index()
        linhas.append({'rep': r, **{f'linhas_dobra_{k}': int(v) for k, v in cont.items()},
                       'rand_com_antiga_mesma_rep': concordancia(por_bloco[f'fold_v2_{r}'], por_bloco[f'nova_fold_v2_{r}'])})
    pd.DataFrame(linhas).to_csv(TAB / 'particoes.csv', index=False, float_format='%.3f')

    cenarios = {
        'koppen_ipef': v2['cenarios']['koppen_ipef'],
        'sem_clima': [],
        'cont_decenal': v2['cenarios']['cont_decenal'],
        'temperatura': TEMPERATURA,
        'curto': TEMPERATURA + CURTO,
        'hibrido': TEMPERATURA + HIDRICO_ESTATICO,
        'hibrido_curto': TEMPERATURA + CURTO + HIDRICO_ESTATICO,
    }
    faltam = [c for c in v2['base'] + sum(cenarios.values(), []) if c not in m.columns]
    assert not faltam, faltam
    m.to_parquet(DADOS / 'matriz_final.parquet', index=False)
    Path(__file__).with_name('cenarios_final.json').write_text(
        json.dumps({'base': v2['base'], 'cenarios': cenarios}, indent=1, ensure_ascii=False), encoding='utf-8')
    print(pd.DataFrame(linhas).round(3).to_string(index=False))
    print({k: len(v) for k, v in cenarios.items()})


if __name__ == '__main__':
    main()
