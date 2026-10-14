"""Etapa 5b: métricas da avaliação das variáveis decenais nas validações V2/V3/V4 (ranger e modelo do mapa).

Junta as predições fora da amostra dos cenários por grupo (clima_decenal/dados/oof_ranger e oof_mapa) às
referências do relatório v2 (Köppen IPEF, contínuo decenal com 3 variáveis e sem clima). Mesmas dobras e
repetições; error_statistics do MapBiomas em t/ha. Ganhos pareados (mesma repetição) sobre o Köppen IPEF e
sobre o contínuo decenal do v2.

Saídas: clima_decenal/resultados/tabelas/cd_metricas.csv e cd_resumo.csv

Uso: python metricas_cd.py
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / 'climas' / 'analise_espaco_tempo' / 'codigo'))
from metricas import error_statistics  # noqa: E402

DADOS_V2 = RAIZ / 'climas' / 'dados_espaco_tempo'
DADOS = RAIZ / 'clima_decenal' / 'dados'
TAB = RAIZ / 'clima_decenal' / 'resultados' / 'tabelas'
REFERENCIAS = {'koppen_ipef': 'koppen_ipef', 'cont_decenal': 'cont_decenal_v2', 'sem_clima': 'sem_clima'}
MODELOS = {'ranger': (DADOS / 'oof_ranger', DADOS_V2 / 'oof'), 'mapa': (DADOS / 'oof_mapa', DADOS_V2 / 'oof_gee')}
NOMES = {'cont_ambos': 'cd_todas', 'cont_sel': 'cd_todas_sel'}


def carregar(novos, antigos):
    out = {}
    for arq in sorted(novos.glob('*_direta.parquet')):
        cen, esq, _ = arq.stem.rsplit('_', 2)
        out[(NOMES.get(cen, cen), esq)] = pd.read_parquet(arq)
    for cen, rot in REFERENCIAS.items():
        for esq in ('v2', 'v3', 'v4'):
            arq = antigos / f'{cen}_{esq}_direta.parquet'
            if arq.exists():
                out[(rot, esq)] = pd.read_parquet(arq)
    return out


def main():
    m = pd.read_parquet(DADOS / 'matriz_cd.parquet',
                        columns=['id', 'carbono_gm2_qmap', 'profundidade', 'PSEUDOROCK_index', 'PSEUDOSAND_index'])
    real = (~m.id.str.startswith('trep') & (m.PSEUDOROCK_index == 0) & (m.PSEUDOSAND_index == 0)).to_numpy()
    p30 = (m.profundidade == 30).to_numpy()
    obs = m.carbono_gm2_qmap.to_numpy() / 100
    recortes = {'0-30 cm, amostras reais': real & p30, '0-30 cm': p30, 'todas': np.ones(len(m), bool)}
    linhas = []
    for modelo, (novos, antigos) in MODELOS.items():
        for (cen, esq), o in carregar(novos, antigos).items():
            i = o.linha.to_numpy() - 1
            for recorte, mask in recortes.items():
                sel = mask[i]
                for rep, g in pd.DataFrame({'rep': o.rep.to_numpy()[sel], 'i': i[sel],
                                            'pred': o.pred.to_numpy()[sel] / 100}).groupby('rep'):
                    linhas.append({'modelo': modelo, 'cenario': cen, 'esquema': esq, 'recorte': recorte, 'rep': rep,
                                   **error_statistics(obs[g.i.to_numpy()], g.pred.to_numpy())})
    met = pd.DataFrame(linhas)
    TAB.mkdir(parents=True, exist_ok=True)
    met.to_csv(TAB / 'cd_metricas.csv', index=False, float_format='%.4g')
    chave = ['modelo', 'esquema', 'recorte', 'rep']
    for ref, col in (('koppen_ipef', 'ganho_vs_koppen'), ('cont_decenal_v2', 'ganho_vs_decenal_v2')):
        r = met[met.cenario == ref].set_index(chave)['mec']
        met[col] = met.mec.to_numpy() - r.reindex(pd.MultiIndex.from_frame(met[chave])).to_numpy()
    resumo = (met.groupby(['modelo', 'cenario', 'esquema', 'recorte'])
              .agg(mec=('mec', 'mean'), rmse=('rmse', 'mean'), me=('me', 'mean'),
                   ganho_vs_koppen=('ganho_vs_koppen', 'mean'), gk_min=('ganho_vs_koppen', 'min'),
                   gk_max=('ganho_vs_koppen', 'max'), ganho_vs_decenal_v2=('ganho_vs_decenal_v2', 'mean'),
                   gd_min=('ganho_vs_decenal_v2', 'min'), gd_max=('ganho_vs_decenal_v2', 'max'), reps=('rep', 'size'))
              .reset_index())
    resumo.to_csv(TAB / 'cd_resumo.csv', index=False, float_format='%.4g')
    pd.set_option('display.width', 230)
    r = resumo[resumo.recorte == '0-30 cm, amostras reais']
    for modelo in MODELOS:
        x = r[r.modelo == modelo].assign(v=lambda d: d.apply(
            lambda q: f'{q.mec:.3f} (K {q.ganho_vs_koppen:+.3f} | D {q.ganho_vs_decenal_v2:+.3f} '
                      f'[{q.gd_min:+.3f}; {q.gd_max:+.3f}])', axis=1))
        print(f'\n== {modelo}: MEC amostras reais 0-30 cm (K: ganho sobre o Köppen; D: sobre o contínuo decenal v2)')
        print(x.pivot(index='cenario', columns='esquema', values='v').to_string())


if __name__ == '__main__':
    main()
