"""Etapa 3: métricas do capítulo 6 (partições novas) e ganhos pareados entre os cenários.

Para cada modelo (ranger validado e modelo do mapa), esquema e recorte, calcula as métricas do MapBiomas
(error_statistics, t/ha) por repetição e o ganho de MEC pareado (mesma repetição e mesmas dobras) de cada
cenário sobre três referências: o Köppen IPEF (produção), o contínuo decenal do v2 e a temperatura decenal do
v4.

Saídas: resultados/tabelas/final_metricas.csv (por repetição) e final_resumo.csv (médias e ganhos com mínimo e
máximo nas repetições)

Uso: python metricas_final.py
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / 'climas' / 'analise_espaco_tempo' / 'codigo'))
from metricas import error_statistics  # noqa: E402

DADOS = RAIZ / 'clima_final' / 'dados'
TAB = RAIZ / 'clima_final' / 'resultados' / 'tabelas'
MODELOS = {'ranger': DADOS / 'oof_ranger', 'mapa': DADOS / 'oof_mapa'}
REFERENCIAS = {'koppen': 'koppen_ipef', 'decenal': 'cont_decenal', 'temperatura': 'temperatura'}


def main():
    cenarios = json.loads(Path(__file__).with_name('cenarios_final.json').read_text(encoding='utf-8'))['cenarios']
    m = pd.read_parquet(DADOS / 'matriz_final.parquet',
                        columns=['id', 'carbono_gm2_qmap', 'profundidade', 'PSEUDOROCK_index', 'PSEUDOSAND_index'])
    real = (~m.id.str.startswith('trep') & (m.PSEUDOROCK_index == 0) & (m.PSEUDOSAND_index == 0)).to_numpy()
    p30 = (m.profundidade == 30).to_numpy()
    obs = m.carbono_gm2_qmap.to_numpy() / 100
    recortes = {'0-30 cm, amostras reais': real & p30, '0-30 cm': p30, 'todas': np.ones(len(m), bool)}
    linhas = []
    for modelo, pasta in MODELOS.items():
        for cen in cenarios:
            for esq in ('v2', 'v3', 'v4'):
                arq = pasta / f'{cen}_{esq}_direta.parquet'
                if not arq.exists():
                    print('falta:', arq)
                    continue
                o = pd.read_parquet(arq)
                i = o.linha.to_numpy() - 1
                for recorte, mask in recortes.items():
                    for rep, g in o.assign(_i=i).groupby('rep'):
                        sel = mask[g._i.to_numpy()]
                        e = error_statistics(obs[g._i.to_numpy()][sel], g.pred.to_numpy()[sel] / 100)
                        linhas.append({'modelo': modelo, 'cenario': cen, 'esquema': esq, 'recorte': recorte, 'rep': rep, **e})
    met = pd.DataFrame(linhas)
    TAB.mkdir(parents=True, exist_ok=True)
    met.to_csv(TAB / 'final_metricas.csv', index=False, float_format='%.4g')

    chave = ['modelo', 'esquema', 'recorte', 'rep']
    resumo = met.groupby(['modelo', 'cenario', 'esquema', 'recorte'])[['mec', 'rmse', 'mae', 'me', 'slope']].mean()
    for nome, ref in REFERENCIAS.items():
        r = met[met.cenario == ref][chave + ['mec']].rename(columns={'mec': 'ref'})
        g = met.merge(r, on=chave).assign(d=lambda x: x.mec - x.ref)
        agg = g.groupby(['modelo', 'cenario', 'esquema', 'recorte']).d.agg(['mean', 'min', 'max'])
        resumo[[f'ganho_{nome}', f'min_{nome}', f'max_{nome}']] = agg.reindex(resumo.index).to_numpy()
    resumo = resumo.reset_index()
    resumo.to_csv(TAB / 'final_resumo.csv', index=False, float_format='%.4g')

    pd.set_option('display.width', 220)
    r = resumo[resumo.recorte == '0-30 cm, amostras reais']
    for modelo in MODELOS:
        for nome in REFERENCIAS:
            t = r[r.modelo == modelo].pivot(index='cenario', columns='esquema', values=f'ganho_{nome}')
            mn = r[r.modelo == modelo].pivot(index='cenario', columns='esquema', values=f'min_{nome}')
            mx = r[r.modelo == modelo].pivot(index='cenario', columns='esquema', values=f'max_{nome}')
            mec = r[r.modelo == modelo].pivot(index='cenario', columns='esquema', values='mec')
            fmt = mec.round(3).astype(str) + ' (' + t.map(lambda v: f'{v:+.3f}') + ' [' + mn.map(lambda v: f'{v:+.3f}') \
                + '; ' + mx.map(lambda v: f'{v:+.3f}') + '])'
            print(f'\n== {modelo}, amostras reais 0-30 cm: MEC (ganho sobre {nome} [mín; máx])\n{fmt.loc[list(cenarios)].to_string()}')


if __name__ == '__main__':
    main()
