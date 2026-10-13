"""Etapa 4c: métricas do capítulo 3 (classificações do Xavier, estáticas e decenais) nas validações V2/V3/V4.

Junta as predições fora da amostra dos cenários novos (climas_tempo/dados/oof_ranger e oof_mapa) às
referências do relatório v2 (climas/dados_espaco_tempo/oof e oof_gee): Köppen IPEF (produção), contínuo
decenal e sem clima. Mesmas dobras e repetições; métricas error_statistics do MapBiomas em t/ha.

Comparações pareadas (mesma repetição):
    ganho_vs_koppen    MEC do cenário - MEC do Köppen IPEF
    ganho_dec_vs_est   MEC da versão decenal - MEC da versão estática (1991-2020) do mesmo sistema:
                       o efeito de o clima mudar no tempo, com a mesma fonte e o mesmo sistema

Saídas: climas_tempo/resultados/tabelas/cap3_metricas.csv, cap3_resumo.csv, cap3_dec_vs_est.csv

Uso: python metricas_cap3.py
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / 'climas' / 'analise_espaco_tempo' / 'codigo'))
from metricas import error_statistics  # noqa: E402

DADOS_V2 = RAIZ / 'climas' / 'dados_espaco_tempo'
DADOS = RAIZ / 'climas_tempo' / 'dados'
TAB = RAIZ / 'climas_tempo' / 'resultados' / 'tabelas'
REFERENCIAS = ['koppen_ipef', 'cont_decenal', 'sem_clima']
MODELOS = {'ranger': (DADOS / 'oof_ranger', DADOS_V2 / 'oof'), 'mapa': (DADOS / 'oof_mapa', DADOS_V2 / 'oof_gee')}
SISTEMAS = ['koppen', 'holdridge', 'thornthwaite', 'k10']


def carregar_oofs(novos, antigos):
    out = {}
    for arq in sorted(novos.glob('*_direta.parquet')):
        cen, esq, _ = arq.stem.rsplit('_', 2)
        out[(cen, esq)] = pd.read_parquet(arq)
    for cen in REFERENCIAS:
        for esq in ('v2', 'v3', 'v4'):
            arq = antigos / f'{cen}_{esq}_direta.parquet'
            if arq.exists():
                out[(cen, esq)] = pd.read_parquet(arq)
    return out


def main():
    m = pd.read_parquet(DADOS / 'matriz_cap3.parquet',
                        columns=['id', 'carbono_gm2_qmap', 'profundidade', 'PSEUDOROCK_index', 'PSEUDOSAND_index'])
    real = (~m.id.str.startswith('trep') & (m.PSEUDOROCK_index == 0) & (m.PSEUDOSAND_index == 0)).to_numpy()
    p30 = (m.profundidade == 30).to_numpy()
    obs = m.carbono_gm2_qmap.to_numpy() / 100
    recortes = {'0-30 cm, amostras reais': real & p30, '0-30 cm': p30, 'todas': np.ones(len(m), bool)}
    linhas = []
    for modelo, (novos, antigos) in MODELOS.items():
        for (cen, esq), o in carregar_oofs(novos, antigos).items():
            i = o.linha.to_numpy() - 1
            for recorte, mask in recortes.items():
                sel = mask[i]
                for rep, g in pd.DataFrame({'rep': o.rep.to_numpy()[sel], 'i': i[sel],
                                            'pred': o.pred.to_numpy()[sel] / 100}).groupby('rep'):
                    linhas.append({'modelo': modelo, 'cenario': cen, 'esquema': esq, 'recorte': recorte, 'rep': rep,
                                   **error_statistics(obs[g.i.to_numpy()], g.pred.to_numpy())})
    met = pd.DataFrame(linhas)
    TAB.mkdir(parents=True, exist_ok=True)
    met.to_csv(TAB / 'cap3_metricas.csv', index=False, float_format='%.4g')

    chave = ['modelo', 'esquema', 'recorte', 'rep']
    ref = met[met.cenario == 'koppen_ipef'].set_index(chave)['mec']
    met['ganho_vs_koppen'] = met.mec.to_numpy() - ref.reindex(pd.MultiIndex.from_frame(met[chave])).to_numpy()
    resumo = (met.groupby(['modelo', 'cenario', 'esquema', 'recorte'])
              .agg(mec=('mec', 'mean'), rmse=('rmse', 'mean'), me=('me', 'mean'),
                   ganho_vs_koppen=('ganho_vs_koppen', 'mean'), ganho_min=('ganho_vs_koppen', 'min'),
                   ganho_max=('ganho_vs_koppen', 'max'), reps=('rep', 'size'))
              .reset_index())
    resumo.to_csv(TAB / 'cap3_resumo.csv', index=False, float_format='%.4g')

    pares = []
    for s in SISTEMAS:
        e = met[met.cenario == f'{s}_est'].set_index(chave)['mec']
        d = met[met.cenario == f'{s}_dec'].set_index(chave)['mec']
        dif = (d - e).dropna().rename('ganho').reset_index()
        for (modelo, esq, recorte), g in dif.groupby(['modelo', 'esquema', 'recorte']):
            pares.append({'sistema': s, 'modelo': modelo, 'esquema': esq, 'recorte': recorte,
                          'ganho_dec_vs_est': g.ganho.mean(), 'min': g.ganho.min(), 'max': g.ganho.max(),
                          'reps': len(g)})
    pares = pd.DataFrame(pares)
    pares.to_csv(TAB / 'cap3_dec_vs_est.csv', index=False, float_format='%.4g')

    pd.set_option('display.width', 220)
    r = resumo[resumo.recorte == '0-30 cm, amostras reais']
    for modelo in MODELOS:
        print(f'\n== {modelo}: MEC, amostras reais 0-30 cm (ganho sobre o Köppen IPEF)')
        x = r[r.modelo == modelo].assign(
            v=lambda d: d.apply(lambda q: f'{q.mec:.3f} ({q.ganho_vs_koppen:+.3f} [{q.ganho_min:+.3f}; {q.ganho_max:+.3f}])', axis=1))
        print(x.pivot(index='cenario', columns='esquema', values='v').to_string())
    print('\n== decenal - estática (mesmo sistema), amostras reais 0-30 cm')
    p = pares[pares.recorte == '0-30 cm, amostras reais'].assign(
        v=lambda d: d.apply(lambda q: f'{q.ganho_dec_vs_est:+.3f} [{q["min"]:+.3f}; {q["max"]:+.3f}]', axis=1))
    print(p.pivot_table(index=['modelo', 'sistema'], columns='esquema', values='v', aggfunc='first').to_string())


if __name__ == '__main__':
    main()
