"""Capítulo 2: outros algoritmos nas mesmas condições (matriz = trainingFinal, mesmas covariáveis, mesmas
dobras V2/V3/V4 com 3 repetições), para ver se algum chega mais perto do carbono medido.

Cenários: os 4 melhores do capítulo 1 e o Köppen (referência). As referências de algoritmo já existem:
ranger validado (oof/) e modelo do mapa, smileRandomForest emulado (oof_gee/). Candidatos:
- rf_ajustado: random forest do scikit-learn, 500 árvores, 1/3 das variáveis por divisão, folha mínima 5;
- lgbm_l2 e lgbm_tweedie: LightGBM (perda quadrática e Tweedie), taxa 0,03, 31 folhas, subamostragem de
  linhas 0,8 e de colunas 0,5;
- xgb: XGBoost (histograma), profundidade 6, taxa 0,03, subamostragem 0,8/0,5.
Nos boostings, o número de árvores sai de parada antecipada num conjunto interno com 20% dos blocos
espaciais do TREINO da dobra (o teste não é visto); depois o modelo é reajustado em todo o treino.
Combinação (média do ranger e de um GBM) é calculada nas métricas, sem ajuste extra.

Saída: climas/dados_espaco_tempo/oof_cap2/<algoritmo>__<cenario>__<esquema>.parquet (formato do
validacao.R, linha contada a partir de 1). Combinações já gravadas são puladas.

Uso: python capitulo2.py rodar [algoritmos separados por vírgula]
     python capitulo2.py metricas
"""
import json
import sys
import time

import lightgbm as lgb
import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.ensemble import RandomForestRegressor

import config as cfg
from metricas import error_statistics
from validacao_gee import particoes

CENARIOS = ['koppen_ipef', 'cont_decenal', 'cont_sel', 'th_cadsolo', 'cont_chelsa']
SEL_CAP2 = ['clim_t_media', 'clim_biotemp', 'clim_p_anual', 'clim_p_mes_seco', 'clim_p_sazonalidade',
            'clim_etp_anual', 'clim_def_anual', 'dec_prec']      # cont_sel do modelo final (capítulo 1)
ALGORITMOS = ['rf_ajustado', 'lgbm_l2', 'lgbm_tweedie', 'xgb']
PASTA = cfg.DADOS / 'oof_cap2'
MAX_ARVORES = 4000


def _interno(blocos_treino, semente):
    """20% dos blocos do treino para a parada antecipada."""
    u = np.unique(blocos_treino)
    rng = np.random.default_rng(semente)
    return np.isin(blocos_treino, rng.choice(u, max(1, int(round(0.2 * len(u)))), replace=False))


def ajustar_prever(alg, X, y, tr, te, blocos, semente):
    Xtr, ytr = X[tr], y[tr]
    if alg == 'rf_ajustado':
        rf = RandomForestRegressor(500, max_features=1 / 3, min_samples_leaf=5, n_jobs=-1, random_state=semente)
        return rf.fit(Xtr, ytr).predict(X[te])
    val = _interno(blocos[tr], semente)
    if alg.startswith('lgbm'):
        par = dict(learning_rate=0.03, num_leaves=31, min_child_samples=20, subsample=0.8, subsample_freq=1,
                   colsample_bytree=0.5, reg_lambda=1.0, n_jobs=16, random_state=semente, verbose=-1,
                   objective='tweedie' if alg == 'lgbm_tweedie' else 'regression')
        m = lgb.LGBMRegressor(n_estimators=MAX_ARVORES, **par)
        m.fit(Xtr[~val], ytr[~val], eval_set=[(Xtr[val], ytr[val])],
              callbacks=[lgb.early_stopping(100, verbose=False)])
        n = max(50, int(m.best_iteration_ / 0.8))           # um pouco mais de dados no reajuste
        return lgb.LGBMRegressor(n_estimators=n, **par).fit(Xtr, ytr).predict(X[te])
    if alg == 'xgb':
        par = dict(learning_rate=0.03, max_depth=6, min_child_weight=5, subsample=0.8, colsample_bytree=0.5,
                   reg_lambda=1.0, tree_method='hist', n_jobs=16, random_state=semente)
        m = xgb.XGBRegressor(n_estimators=MAX_ARVORES, early_stopping_rounds=100, **par)
        m.fit(Xtr[~val], ytr[~val], eval_set=[(Xtr[val], ytr[val])], verbose=False)
        n = max(50, int(m.best_iteration / 0.8))
        return xgb.XGBRegressor(n_estimators=n, **par).fit(Xtr, ytr).predict(X[te])
    raise ValueError(alg)


def rodar(algoritmos):
    meta = json.loads((cfg.PASTA / 'codigo' / 'cenarios.json').read_text(encoding='utf-8'))
    m = pd.read_parquet(cfg.DADOS / 'matriz_cenarios.parquet')
    y = m.carbono_gm2_qmap.to_numpy(float)
    blocos = m.bloco.to_numpy()
    PASTA.mkdir(exist_ok=True)
    for alg in algoritmos:
        for cen in CENARIOS:
            clima = SEL_CAP2 if cen == 'cont_sel' else meta['cenarios'][cen]
            X = m[meta['base'] + clima].to_numpy(np.float32)
            for esq in ('v2', 'v3', 'v4'):
                arq = PASTA / f'{alg}__{cen}__{esq}.parquet'
                if arq.exists():
                    continue
                t0, partes = time.time(), []
                for rep, dobra, tr, te in particoes(m, esq):
                    idx = np.where(te)[0]
                    pred = ajustar_prever(alg, X, y, tr, te, blocos, 1984 + rep * 100 + dobra)
                    partes.append(pd.DataFrame({'linha': idx + 1, 'id': m.id.to_numpy()[idx], 'rep': rep,
                                                'dobra': dobra, 'pred': pred}))
                pd.concat(partes, ignore_index=True).to_parquet(arq, index=False)
                print(f'{alg} {cen} {esq}: {time.time() - t0:.0f} s', flush=True)


def _oofs():
    """Todas as predições fora da amostra dos 5 cenários: capítulo 2 e as duas referências."""
    out = {}
    for arq in PASTA.glob('*.parquet'):
        alg, cen, esq = arq.stem.split('__')
        out[(alg, cen, esq)] = pd.read_parquet(arq)
    for alg, pasta in (('ranger_validado', 'oof'), ('modelo_mapa', 'oof_gee')):
        for cen in CENARIOS:
            for esq in ('v2', 'v3', 'v4'):
                arq = cfg.DADOS / pasta / f'{cen}_{esq}_direta.parquet'
                if arq.exists():
                    out[(alg, cen, esq)] = pd.read_parquet(arq)
    return out


def metricas():
    m = pd.read_parquet(cfg.DADOS / 'matriz_cenarios.parquet',
                        columns=['id', 'carbono_gm2_qmap', 'profundidade', 'PSEUDOROCK_index', 'PSEUDOSAND_index'])
    real = (~m.id.str.startswith('trep') & (m.PSEUDOROCK_index == 0) & (m.PSEUDOSAND_index == 0)).to_numpy()
    p30 = (m.profundidade == 30).to_numpy()
    obs = m.carbono_gm2_qmap.to_numpy() / 100
    oofs = _oofs()
    # combinações: média do ranger com cada GBM disponível
    for (alg, cen, esq), o in list(oofs.items()):
        if alg in ('lgbm_l2', 'lgbm_tweedie', 'xgb') and ('ranger_validado', cen, esq) in oofs:
            r = oofs[('ranger_validado', cen, esq)]
            j = o.merge(r[['linha', 'rep', 'pred']], on=['linha', 'rep'], suffixes=('', '_r'))
            oofs[(f'media_ranger_{alg}', cen, esq)] = j.assign(pred=(j.pred + j.pred_r) / 2)[o.columns]
    linhas = []
    for (alg, cen, esq), o in oofs.items():
        i = o.linha.to_numpy() - 1
        for recorte, mask in (('0-30 cm, amostras reais', real & p30), ('0-30 cm', p30), ('todas', None)):
            sel = np.ones(len(i), bool) if mask is None else mask[i]
            for rep, g in pd.DataFrame({'rep': o.rep.to_numpy()[sel], 'i': i[sel],
                                        'pred': o.pred.to_numpy()[sel] / 100}).groupby('rep'):
                linhas.append({'algoritmo': alg, 'cenario': cen, 'esquema': esq, 'recorte': recorte, 'rep': rep,
                               **error_statistics(obs[g.i.to_numpy()], g.pred.to_numpy())})
    met = pd.DataFrame(linhas)
    met.to_csv(cfg.TABELAS / 'cap2_metricas.csv', index=False, float_format='%.4g')
    ref = met[met.algoritmo == 'ranger_validado'].set_index(['cenario', 'esquema', 'recorte', 'rep'])
    met = met.join(ref[['mec', 'rmse', 'mae']], on=['cenario', 'esquema', 'recorte', 'rep'], rsuffix='_ranger')
    met['ganho_mec'] = met.mec - met.mec_ranger
    res = (met.groupby(['algoritmo', 'cenario', 'esquema', 'recorte'])
           .agg(mec=('mec', 'mean'), rmse=('rmse', 'mean'), mae=('mae', 'mean'), me=('me', 'mean'),
                slope=('slope', 'mean'), ganho_mec_vs_ranger=('ganho_mec', 'mean'),
                ganho_min=('ganho_mec', 'min'), ganho_max=('ganho_mec', 'max'), reps=('rep', 'size'))
           .reset_index())
    res.to_csv(cfg.TABELAS / 'cap2_resumo.csv', index=False, float_format='%.4g')
    r = res[res.recorte == '0-30 cm, amostras reais']
    pd.set_option('display.width', 250)
    print(r.pivot_table(index='algoritmo', columns=['esquema', 'cenario'], values='mec').round(3).to_string())


if __name__ == '__main__':
    etapa = sys.argv[1] if len(sys.argv) > 1 else ''
    if etapa == 'rodar':
        rodar(sys.argv[2].split(',') if len(sys.argv) > 2 else ALGORITMOS)
    elif etapa == 'metricas':
        metricas()
    else:
        print(__doc__)
