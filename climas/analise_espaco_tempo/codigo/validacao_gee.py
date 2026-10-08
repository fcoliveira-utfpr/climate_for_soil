"""Etapa 6d: a mesma validação de validacao.R (cenários, dobras V2/V3/V4 e 3 repetições), mas com o modelo
que gera o mapa oficial: o random forest do GEE (smileRandomForest, maxNodes 40), emulado em
fidelidade_gee.modelo_gee(). Responde se trocar o Köppen melhoraria o mapa publicado.

cont_sel: a mesma seleção aninhada (pares |r de Spearman| > 0,9 no treino da dobra; fica a mais importante,
importância por impureza média das árvores).

Saída: climas/dados_espaco_tempo/oof_gee/<cenario>_<esquema>_direta.parquet, no formato do validacao.R
(linha contada a partir de 1). Combinações já gravadas são puladas.

Uso: python validacao_gee.py [cenarios separados por vírgula | todos] [esquemas, padrão v2,v3,v4]
"""
import json
import sys
import time

import numpy as np
import pandas as pd

import config as cfg
from fidelidade_gee import modelo_gee

PASTA = cfg.DADOS / 'oof_gee'
LIMIAR_R = 0.9


def particoes(m, esquema):
    if esquema == 'v2':
        for r in (1, 2, 3):
            f = m[f'fold_v2_{r}'].to_numpy()
            for k in range(1, 6):
                yield r, k, f != k, f == k
    elif esquema == 'v3':
        p = m.periodo.to_numpy()
        for r in (1, 2, 3):
            for k in range(1, 5):
                yield r, k, p != k, p == k
    elif esquema == 'v4':
        p = m.periodo.to_numpy()
        for r in (1, 2, 3):
            f = m[f'fold_v2_{r}'].to_numpy()
            for k in range(1, 6):
                for q in range(1, 5):
                    yield r, (k - 1) * 4 + q, (f != k) & (p != q), (f == k) & (p == q)
    else:
        raise ValueError(esquema)


def selecionar(m, base, cont, treino, semente):
    X = m.loc[treino, base + cont].to_numpy(np.float32)
    rf = modelo_gee().set_params(random_state=semente).fit(X, m.carbono_gm2_qmap.to_numpy()[treino])
    imp = pd.Series(np.mean([a.feature_importances_ for a in rf.estimators_], axis=0), index=base + cont)[cont]
    r = m.loc[treino, cont].corr(method='spearman').abs().to_numpy().copy()
    r[np.tril_indices_from(r)] = 0
    pares = sorted(zip(*np.where(r > LIMIAR_R)), key=lambda ij: -r[ij])
    manter = list(cont)
    for i, j in pares:
        a, b = cont[i], cont[j]
        if a in manter and b in manter:
            manter.remove(b if imp[a] >= imp[b] else a)
    return manter


def main():
    meta = json.loads((cfg.PASTA / 'codigo' / 'cenarios.json').read_text(encoding='utf-8'))
    nomes = list(meta['cenarios']) if len(sys.argv) < 2 or sys.argv[1] == 'todos' else sys.argv[1].split(',')
    esquemas = sys.argv[2].split(',') if len(sys.argv) > 2 else ['v2', 'v3', 'v4']
    m = pd.read_parquet(cfg.DADOS / 'matriz_cenarios.parquet')
    y = m.carbono_gm2_qmap.to_numpy()
    PASTA.mkdir(exist_ok=True)
    selecoes = []
    for cen in nomes:
        clima = meta['cenarios'][cen]
        for esq in esquemas:
            arq = PASTA / f'{cen}_{esq}_direta.parquet'
            if arq.exists():
                continue
            t0, partes = time.time(), []
            for rep, dobra, tr, te in particoes(m, esq):
                semente = 1984 + rep * 100 + dobra
                cols = meta['base'] + (selecionar(m, meta['base'], clima, tr, semente) if cen == 'cont_sel' else clima)
                if cen == 'cont_sel':
                    selecoes.append({'esquema': esq, 'rep': rep, 'dobra': dobra,
                                     'mantidas': ','.join(cols[len(meta['base']):])})
                X = m[cols].to_numpy(np.float32)
                rf = modelo_gee().set_params(random_state=semente).fit(X[tr], y[tr])
                idx = np.where(te)[0]
                partes.append(pd.DataFrame({'linha': idx + 1, 'id': m.id.to_numpy()[idx], 'rep': rep, 'dobra': dobra,
                                            'pred': rf.predict(X[te])}))
            pd.concat(partes, ignore_index=True).to_parquet(arq, index=False)
            print(f'{cen} {esq}: {len(cols)} colunas, {time.time() - t0:.0f} s', flush=True)
    if selecoes:
        pd.DataFrame(selecoes).to_csv(cfg.TABELAS / 'selecao_continuas_dobras_gee.csv', index=False)


if __name__ == '__main__':
    main()
