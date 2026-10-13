"""Etapa 5c: importância por permutação FORA DA AMOSTRA de cada variável decenal (e de cada grupo).

Modelo com as 118 covariáveis da produção + as 39 variáveis decenais (cenário cont_ambos), random forest do
scikit-learn configurado como o ranger da validação (300 árvores, 24 variáveis por divisão, folha mínima 1,
sem limite de profundidade). Em cada dobra (repetição 1 de V2, V3 e V4), o modelo é treinado no treino e
avaliado no teste; depois cada variável (ou grupo inteiro) é embaralhada SÓ nas linhas de teste e o MEC é
recalculado. Importância = MEC original - MEC com a variável embaralhada, nas amostras reais de 0-30 cm, com
as predições de todas as dobras juntas; média de 3 embaralhamentos.

Por que fora da amostra: mede o quanto a variável ajuda a prever onde (V2), quando (V3) ou onde e quando (V4)
não houve treino, e não o quanto ela ajuda a ajustar o treino. Por que grupos: com 85 pares de variáveis com
|r| > 0,9, embaralhar uma só subestima a importância (a "gêmea" compensa); o grupo embaralhado junto mede o
peso de cada tipo de informação.

Saídas: clima_decenal/resultados/tabelas/importancia_cd.csv e resultados/figuras/importancia_cd.png

Uso: python importancia_cd.py
"""
import json
import sys
import time
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / 'climas' / 'analise_espaco_tempo' / 'codigo'))
from metricas import error_statistics  # noqa: E402
from validacao_gee import particoes  # noqa: E402

DADOS = RAIZ / 'clima_decenal' / 'dados'
RES = RAIZ / 'clima_decenal' / 'resultados'
N_PERM = 3


def mec(obs, pred):
    return error_statistics(obs, pred)['mec']


def main():
    meta = json.loads((Path(__file__).with_name('cenarios_cd.json')).read_text(encoding='utf-8'))
    grupos = {k: v for k, v in meta['cenarios'].items() if k.startswith('cd_')}
    todas = meta['cenarios']['cont_ambos']
    cols = meta['base'] + todas
    m = pd.read_parquet(DADOS / 'matriz_cd.parquet')
    X = m[cols].to_numpy(np.float32)
    y = m.carbono_gm2_qmap.to_numpy() / 100
    alvo = (~m.id.str.startswith('trep') & (m.PSEUDOROCK_index == 0) & (m.PSEUDOSAND_index == 0)
            & (m.profundidade == 30)).to_numpy()
    idx = {c: i for i, c in enumerate(cols)}
    itens = [(v, [idx[v]]) for v in todas] + [(f'GRUPO {g}', [idx[v] for v in vs]) for g, vs in grupos.items()]
    rng = np.random.default_rng(2026)
    linhas = []
    for esq in ('v2', 'v3', 'v4'):
        t0 = time.time()
        base = np.full(len(m), np.nan)
        perm = {nome: np.full((N_PERM, len(m)), np.nan) for nome, _ in itens}
        for rep, dobra, tr, te in particoes(m, esq):
            if rep != 1:
                continue
            rf = RandomForestRegressor(300, max_features=24, min_samples_leaf=1, n_jobs=-1,
                                       random_state=1984 + dobra).fit(X[tr], y[tr])
            ite = np.where(te)[0]
            base[ite] = rf.predict(X[ite])
            for nome, js in itens:
                for k in range(N_PERM):
                    Xp = X[ite].copy()
                    ordem = rng.permutation(len(ite))
                    Xp[:, js] = Xp[ordem][:, js]          # o grupo embaralhado junto (mantém a correlação interna)
                    perm[nome][k, ite] = rf.predict(Xp)
        ok = alvo & np.isfinite(base)
        m0 = mec(y[ok], base[ok])
        for nome, _ in itens:
            quedas = [m0 - mec(y[ok], perm[nome][k, ok]) for k in range(N_PERM)]
            grupo = next((g for g, vs in grupos.items() if nome in vs), nome.replace('GRUPO ', ''))
            linhas.append({'esquema': esq, 'variavel': nome, 'grupo': grupo, 'mec_modelo': m0,
                           'importancia': np.mean(quedas), 'imp_min': np.min(quedas), 'imp_max': np.max(quedas)})
        print(f'{esq}: MEC {m0:.3f}, {time.time() - t0:.0f} s', flush=True)
    tab = pd.DataFrame(linhas)
    (RES / 'tabelas').mkdir(parents=True, exist_ok=True)
    tab.to_csv(RES / 'tabelas' / 'importancia_cd.csv', index=False, float_format='%.5f')

    ind = tab[~tab.variavel.str.startswith('GRUPO')]
    ordem = ind[ind.esquema == 'v3'].sort_values('importancia').variavel.tolist()
    fig, axs = plt.subplots(1, 3, figsize=(17, 11), sharey=True)
    cores = dict(zip(grupos, plt.cm.Set2.colors))
    for ax, esq in zip(axs, ('v2', 'v3', 'v4')):
        d = ind[ind.esquema == esq].set_index('variavel').loc[ordem]
        ax.barh(range(len(d)), d.importancia, xerr=[d.importancia - d.imp_min, d.imp_max - d.importancia],
                color=[cores[g] for g in d.grupo], ecolor='0.4')
        ax.axvline(0, color='k', lw=0.6)
        ax.set_title({'v2': 'V2 espacial', 'v3': 'V3 temporal', 'v4': 'V4 espaço-tempo'}[esq])
        ax.set_xlabel('queda do MEC ao embaralhar (amostras reais 0-30 cm)')
    axs[0].set_yticks(range(len(ordem)), [v.replace('cd_', '') for v in ordem], fontsize=8)
    fig.legend(handles=[plt.Rectangle((0, 0), 1, 1, color=c) for c in cores.values()],
               labels=[g.replace('cd_', '') for g in cores], loc='lower center', ncol=5)
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    fig.savefig(RES / 'figuras' / 'importancia_cd.png', dpi=130)
    pd.set_option('display.width', 200)
    print(tab[tab.variavel.str.startswith('GRUPO')].pivot(index='variavel', columns='esquema',
                                                           values='importancia').round(4).to_string())
    print(ind.pivot(index='variavel', columns='esquema', values='importancia')
          .sort_values('v3', ascending=False).head(15).round(4).to_string())


if __name__ == '__main__':
    main()
