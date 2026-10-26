"""Etapa 5c: métricas do Köppen móvel de 30 anos x Köppen IPEF nas validações V2/V3/V4.

Junta as predições fora da amostra do cenário novo (climas/dados_koppen_movel30/oof_ranger e oof_mapa) às do
Köppen IPEF do relatório v2 (climas/dados_espaco_tempo/oof e oof_gee): mesmas dobras e repetições. Métricas
error_statistics do MapBiomas em t/ha; ganho = MEC do koppen_movel30 − MEC do koppen_ipef na mesma repetição.

Saídas: climas/koppen_movel30/resultados/tabelas/movel30_metricas.csv e movel30_resumo.csv

Uso: python metricas.py
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

RAIZ = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(RAIZ / 'climas' / 'analise_espaco_tempo' / 'codigo'))
from metricas import error_statistics  # noqa: E402

DADOS_V2 = RAIZ / 'climas' / 'dados_espaco_tempo'
DADOS = RAIZ / 'climas' / 'dados_koppen_movel30'
TAB = Path(__file__).resolve().parents[1] / 'resultados' / 'tabelas'
MODELOS = {'ranger': (DADOS / 'oof_ranger', DADOS_V2 / 'oof'), 'mapa': (DADOS / 'oof_mapa', DADOS_V2 / 'oof_gee')}
CENARIOS = {'koppen_movel30': 0, 'koppen_ipef': 1}      # 0 = pasta nova, 1 = pasta do relatório v2


def main():
    m = pd.read_parquet(DADOS / 'matriz_movel30.parquet',
                        columns=['id', 'carbono_gm2_qmap', 'profundidade', 'PSEUDOROCK_index', 'PSEUDOSAND_index'])
    real = (~m.id.str.startswith('trep') & (m.PSEUDOROCK_index == 0) & (m.PSEUDOSAND_index == 0)).to_numpy()
    p30 = (m.profundidade == 30).to_numpy()
    obs = m.carbono_gm2_qmap.to_numpy() / 100
    recortes = {'0-30 cm, amostras reais': real & p30, '0-30 cm': p30, 'todas': np.ones(len(m), bool)}
    linhas = []
    for modelo, pastas in MODELOS.items():
        for cen, onde in CENARIOS.items():
            for esq in ('v2', 'v3', 'v4'):
                arq = pastas[onde] / f'{cen}_{esq}_direta.parquet'
                if not arq.exists():
                    print('falta:', arq)
                    continue
                o = pd.read_parquet(arq)
                i = o.linha.to_numpy() - 1
                for recorte, mask in recortes.items():
                    sel = mask[i]
                    for rep, gr in pd.DataFrame({'rep': o.rep.to_numpy()[sel], 'i': i[sel],
                                                 'pred': o.pred.to_numpy()[sel] / 100}).groupby('rep'):
                        linhas.append({'modelo': modelo, 'cenario': cen, 'esquema': esq, 'recorte': recorte,
                                       'rep': rep, **error_statistics(obs[gr.i.to_numpy()], gr.pred.to_numpy())})
    met = pd.DataFrame(linhas)
    TAB.mkdir(parents=True, exist_ok=True)
    met.to_csv(TAB / 'movel30_metricas.csv', index=False, float_format='%.4g')

    chave = ['modelo', 'esquema', 'recorte', 'rep']
    ref = met[met.cenario == 'koppen_ipef'].set_index(chave)['mec']
    met['ganho_vs_ipef'] = met.mec.to_numpy() - ref.reindex(pd.MultiIndex.from_frame(met[chave])).to_numpy()
    resumo = (met.groupby(['modelo', 'cenario', 'esquema', 'recorte'])
              .agg(mec=('mec', 'mean'), rmse=('rmse', 'mean'), me=('me', 'mean'),
                   ganho_vs_ipef=('ganho_vs_ipef', 'mean'), ganho_min=('ganho_vs_ipef', 'min'),
                   ganho_max=('ganho_vs_ipef', 'max'), reps=('rep', 'size'))
              .reset_index())
    resumo.to_csv(TAB / 'movel30_resumo.csv', index=False, float_format='%.4g')

    pd.set_option('display.width', 220)
    for recorte in ('0-30 cm, amostras reais', '0-30 cm'):
        r = resumo[resumo.recorte == recorte]
        for modelo in MODELOS:
            print(f'\n== {modelo}, {recorte}: MEC (ganho sobre o Köppen IPEF [mín; máx nas repetições])')
            x = r[r.modelo == modelo].assign(v=lambda d: d.apply(
                lambda q: f'{q.mec:.3f} ({q.ganho_vs_ipef:+.3f} [{q.ganho_min:+.3f}; {q.ganho_max:+.3f}])', axis=1))
            print(x.pivot(index='cenario', columns='esquema', values='v').to_string())


if __name__ == '__main__':
    main()
