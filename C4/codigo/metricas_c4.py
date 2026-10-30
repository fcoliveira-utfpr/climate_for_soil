"""Etapa 6: métricas do C4 e comparação com o v6 (Xavier v3.2.2 x v3.2.4), nas mesmas dobras e sementes.

Junta as predições fora da amostra do C4 (temperatura e conjunto curto com o Xavier v3.2.4) às do v6 (as
referências Köppen IPEF, sem clima e contínuo decenal, que não dependem do Xavier, e a temperatura e o conjunto
curto com o Xavier v3.2.2). Para cada modelo, esquema e recorte: métricas do MapBiomas por repetição e ganhos
pareados sobre o Köppen e sobre a versão v6 do mesmo cenário (efeito só da versão do Xavier).

Saídas: resultados/tabelas/c4_metricas.csv (por repetição) e c4_resumo.csv

Uso: python metricas_c4.py
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / 'climas' / 'analise_espaco_tempo' / 'codigo'))
from metricas import error_statistics  # noqa: E402

DADOS = RAIZ / 'C4' / 'dados'
V6 = RAIZ / 'clima_final' / 'dados'
TAB = RAIZ / 'C4' / 'resultados' / 'tabelas'
# cenário no resumo: (pasta das predições, nome do arquivo)
FONTES = {
    'koppen_ipef': ('v6', 'koppen_ipef'), 'sem_clima': ('v6', 'sem_clima'), 'cont_decenal': ('v6', 'cont_decenal'),
    'temperatura_v6': ('v6', 'temperatura'), 'curto_v6': ('v6', 'curto'),
    'temperatura': ('c4', 'temperatura'), 'curto': ('c4', 'curto'),
}
PASTAS = {'ranger': {'v6': V6 / 'oof_ranger', 'c4': DADOS / 'oof_ranger'},
          'mapa': {'v6': V6 / 'oof_mapa', 'c4': DADOS / 'oof_mapa'}}
REFERENCIAS = {'koppen': lambda c: 'koppen_ipef', 'v6': lambda c: f'{c}_v6' if c in ('temperatura', 'curto') else None}


def main():
    m = pd.read_parquet(DADOS / 'matriz_c4.parquet',
                        columns=['id', 'carbono_gm2_qmap', 'profundidade', 'PSEUDOROCK_index', 'PSEUDOSAND_index'])
    real = (~m.id.str.startswith('trep') & (m.PSEUDOROCK_index == 0) & (m.PSEUDOSAND_index == 0)).to_numpy()
    p30 = (m.profundidade == 30).to_numpy()
    obs = m.carbono_gm2_qmap.to_numpy() / 100
    recortes = {'0-30 cm, amostras reais': real & p30, '0-30 cm': p30, 'todas': np.ones(len(m), bool)}
    linhas = []
    for modelo, pastas in PASTAS.items():
        for cen, (onde, nome) in FONTES.items():
            for esq in ('v2', 'v3', 'v4'):
                arq = pastas[onde] / f'{nome}_{esq}_direta.parquet'
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
    met.to_csv(TAB / 'c4_metricas.csv', index=False, float_format='%.4g')

    chave = ['modelo', 'esquema', 'recorte', 'rep']
    resumo = met.groupby(['modelo', 'cenario', 'esquema', 'recorte'])[['mec', 'rmse', 'mae', 'me', 'slope']].mean()
    for nome, ref in REFERENCIAS.items():
        partes = []
        for cen in met.cenario.unique():
            r = ref(cen)
            if r is None:
                continue
            a = met[met.cenario == cen].merge(met[met.cenario == r][chave + ['mec']].rename(columns={'mec': 'ref'}), on=chave)
            partes.append(a.assign(d=a.mec - a.ref))
        g = pd.concat(partes).groupby(['modelo', 'cenario', 'esquema', 'recorte']).d.agg(['mean', 'min', 'max'])
        resumo[[f'ganho_{nome}', f'min_{nome}', f'max_{nome}']] = g.reindex(resumo.index).to_numpy()
    resumo = resumo.reset_index()
    resumo.to_csv(TAB / 'c4_resumo.csv', index=False, float_format='%.4g')

    pd.set_option('display.width', 220)
    r = resumo[resumo.recorte == '0-30 cm, amostras reais']
    for modelo in PASTAS:
        x = r[r.modelo == modelo]
        for nome in REFERENCIAS:
            t = x.pivot(index='cenario', columns='esquema', values=f'ganho_{nome}')
            mn = x.pivot(index='cenario', columns='esquema', values=f'min_{nome}')
            mx = x.pivot(index='cenario', columns='esquema', values=f'max_{nome}')
            mec = x.pivot(index='cenario', columns='esquema', values='mec')
            fmt = mec.round(3).astype(str) + ' (' + t.map(lambda v: f'{v:+.3f}' if pd.notna(v) else '—') + ' [' \
                + mn.map(lambda v: f'{v:+.3f}' if pd.notna(v) else '') + '; ' \
                + mx.map(lambda v: f'{v:+.3f}' if pd.notna(v) else '') + '])'
            print(f'\n== {modelo}, amostras reais 0-30 cm: MEC (ganho sobre {nome} [mín; máx])\n'
                  f'{fmt.loc[list(FONTES)].to_string()}')


if __name__ == '__main__':
    main()
