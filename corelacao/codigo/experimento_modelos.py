"""O que colocar no lugar do Köppen nos modelos do MapBiomas Solo?

Random forest com as covariáveis das matrizes de treino do MapBiomas (base comum) e, em cada cenário, uma
forma diferente de representar o clima:

    A  Köppen IPEF (dummies L1-L3, como hoje)          E   clima contínuo (CHELSA + BHC)
    B  sem clima                                       F1  zonas homogêneas k-means (dummies)
    C  Holdridge ETH (dummies L1 + L2)                 F2  um RF por zona homogênea k-means
    D  Thornthwaite CAD 100 mm (dummies L1 + L2)       F3  zonas supervisionadas (árvore no clima,
                                                           ajustada dentro da dobra) como dummies
                                                       F4  um RF por zona supervisionada

Validação: blocos espaciais de 2° (5 dobras), mesmas dobras para todos os cenários em cada repetição ->
diferenças pareadas em relação ao cenário A. Saída só agregada em resultados/tabelas/experimento_*.csv.
"""
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.tree import DecisionTreeRegressor

import comparar_climas as cc
import experimento_dados as ed
import zonas_clima as zc

ROOT = Path(__file__).resolve().parents[1]
TABELAS = ROOT / 'resultados' / 'tabelas'

RESPOSTAS = {'log_soc': ('soc', 'soc_g_m2'), 'argila': ('textura', 'argila_alvo'),
             'areia': ('textura', 'areia_alvo'), 'silte': ('textura', 'silte_alvo')}
CLIMA_CONTINUO = ['clim_t_media', 'clim_t_mes_frio', 'clim_t_mes_quente', 'clim_biotemp', 'clim_p_anual',
                  'clim_p_mes_seco', 'clim_p_sazonalidade', 'clim_etp_anual', 'clim_etp_p', 'clim_def_anual',
                  'clim_exc_anual', 'clim_im']
CENARIOS = {
    'A': 'Köppen IPEF (hoje)', 'B': 'Sem clima', 'C': 'Holdridge ETH', 'D': 'Thornthwaite L2',
    'E': 'Clima contínuo', 'F1': 'Zonas k-means (covariável)', 'F2': 'Zonas k-means (um RF por zona)',
    'F3': 'Zonas supervisionadas (covariável)', 'F4': 'Zonas supervisionadas (um RF por zona)',
}
DUMMIES = {'A': ['koppen_ipef_l1', 'koppen_ipef_l2', 'koppen_ipef_l3'],
           'C': ['holdridge_l1', 'holdridge_eth_l2'], 'D': ['th100_l1', 'th100_l2'], 'F1': ['zona_k10']}
K_ZONAS = 10
N_REPETICOES = 3
N_DOBRAS = 5
TAM_BLOCO = 2.0
SEMENTE = 2026
N_MIN_ZONA = 300          # zona com menos locais de treino usa o modelo global
PARAMS_RF = dict(n_estimators=200, max_features=0.33, min_samples_leaf=2, n_jobs=-1)


def base_covariaveis(df):
    extras = set(CLIMA_CONTINUO) | set(ed.leg.COLUNAS_CLIMA) | {'soc_g_m2', 'zona_k10'} | \
        {c for c in df.columns if c.endswith('_alvo')}
    return [c for c in ed.covariaveis(df) if c not in extras and pd.api.types.is_numeric_dtype(df[c])]


def dummies(df, cols):
    return pd.get_dummies(df[cols].astype('string'), prefix=cols, dtype=float)


def rf(semente):
    return RandomForestRegressor(random_state=semente, **PARAMS_RF)


def ajustar_prever(x_tr, y_tr, x_te, semente):
    med = x_tr.median()
    m = rf(semente).fit(x_tr.fillna(med).to_numpy(), y_tr)
    return m.predict(x_te.fillna(med).to_numpy())


def zonas_supervisionadas(clima_tr, y_tr, clima_te, n_zonas=K_ZONAS):
    """Árvore de regressão (multivariada se y tem várias colunas) sobre o clima contínuo, ajustada só no
    treino: as folhas são as zonas. Devolve a zona do treino e do teste."""
    y = np.asarray(y_tr, float).reshape(len(clima_tr), -1)
    y = (y - y.mean(0)) / y.std(0)
    arvore = DecisionTreeRegressor(max_leaf_nodes=n_zonas, min_samples_leaf=max(50, len(y) // 50),
                                   random_state=SEMENTE).fit(clima_tr, y)
    return arvore.apply(clima_tr), arvore.apply(clima_te)


def prever_estratificado(x_tr, y_tr, z_tr, x_te, z_te, semente):
    """Um RF por zona; zona com poucos locais de treino usa o RF global (base + dummies da zona)."""
    pred = np.empty(len(x_te))
    zd_tr = pd.get_dummies(pd.Series(z_tr).astype(str), prefix='z', dtype=float)
    zd_te = pd.get_dummies(pd.Series(z_te).astype(str), prefix='z', dtype=float).reindex(columns=zd_tr.columns,
                                                                                        fill_value=0)
    glob = None
    for z in np.unique(z_te):
        te = z_te == z
        tr = z_tr == z
        if tr.sum() >= N_MIN_ZONA:
            pred[te] = ajustar_prever(x_tr[tr], y_tr[tr], x_te[te], semente)
        else:
            if glob is None:
                xg_tr = pd.concat([x_tr.reset_index(drop=True), zd_tr], axis=1)
                med = xg_tr.median()
                glob = (rf(semente).fit(xg_tr.fillna(med).to_numpy(), y_tr), med)
            xg_te = pd.concat([x_te.reset_index(drop=True), zd_te.reset_index(drop=True)], axis=1)[te]
            pred[te] = glob[0].predict(xg_te.fillna(glob[1]).to_numpy())
    return pred


def rodar_base(nome_base, df, respostas):
    """Todos os cenários para as respostas de uma base (soc ou textura), com as mesmas dobras."""
    df = df[df[CLIMA_CONTINUO].notna().all(axis=1)].reset_index(drop=True)
    for c in ed.leg.COLUNAS_CLIMA:
        df = df[df[c].notna()]
    df = df.reset_index(drop=True)
    cent, media, dp = zc.carregar(K_ZONAS)
    df['zona_k10'] = zc.atribuir(df, cent, media, dp)
    base = base_covariaveis(df)
    x_base = df[base].astype(float)
    x = {'B': x_base, 'E': pd.concat([x_base, df[CLIMA_CONTINUO]], axis=1)}
    for cen, cols in DUMMIES.items():
        x[cen] = pd.concat([x_base, dummies(df, cols)], axis=1)
    ys = {r: (np.log(df[col].to_numpy(float)) if r == 'log_soc' else df[col].to_numpy(float))
          for r, col in respostas.items()}
    y_multi = np.column_stack(list(ys.values()))       # textura: zonas supervisionadas conjuntas
    grupos = cc.grupos_espaciais(df.longitude.to_numpy(), df.latitude.to_numpy(), TAM_BLOCO)
    rng = np.random.default_rng(SEMENTE)
    print(f'[{nome_base}] {len(df)} locais, {len(base)} covariáveis-base', flush=True)

    linhas = []
    for rep in range(N_REPETICOES):
        dobras = cc.sortear_dobras(grupos, N_DOBRAS, rng)
        preds = {(r, c): np.empty(len(df)) for r in ys for c in CENARIOS}
        for f in range(N_DOBRAS):
            t0 = time.time()
            te, tr = dobras == f, dobras != f
            clima_tr, clima_te = df.loc[tr, CLIMA_CONTINUO], df.loc[te, CLIMA_CONTINUO]
            zs_tr, zs_te = zonas_supervisionadas(clima_tr, y_multi[tr], clima_te)
            zs = np.empty(len(df), dtype=int)
            zs[tr], zs[te] = zs_tr, zs_te
            x['F3'] = pd.concat([x_base, pd.get_dummies(pd.Series(zs).astype(str), prefix='zs', dtype=float)],
                                axis=1)
            for r, y in ys.items():
                for c in ('A', 'B', 'C', 'D', 'E', 'F1', 'F3'):
                    preds[(r, c)][te] = ajustar_prever(x[c][tr], y[tr], x[c][te], SEMENTE + rep)
                preds[(r, 'F2')][te] = prever_estratificado(x_base[tr], y[tr], df.zona_k10.to_numpy()[tr],
                                                            x_base[te], df.zona_k10.to_numpy()[te], SEMENTE + rep)
                preds[(r, 'F4')][te] = prever_estratificado(x_base[tr], y[tr], zs_tr, x_base[te], zs_te,
                                                            SEMENTE + rep)
            print(f'  rep {rep + 1} dobra {f + 1}: {time.time() - t0:5.0f}s', flush=True)
        for (r, c), p in preds.items():
            y = ys[r]
            linhas.append({'resposta': r, 'cenario': c, 'rep': rep, 'r2': cc.r2(y, p),
                           'rmse': float(np.sqrt(np.mean((y - p) ** 2)))})
    return pd.DataFrame(linhas)


def resumir(det):
    out = []
    for (r, c), g in det.groupby(['resposta', 'cenario']):
        a = det[(det.resposta == r) & (det.cenario == 'A')].set_index('rep')
        d = g.set_index('rep')
        dr2 = d.r2 - a.r2
        drm = d.rmse - a.rmse
        out.append({'resposta': r, 'cenario': c, 'descricao': CENARIOS[c], 'r2': d.r2.mean(),
                    'rmse': d.rmse.mean(), 'delta_r2_vs_A': dr2.mean(), 'delta_r2_min': dr2.min(),
                    'delta_r2_max': dr2.max(), 'delta_rmse_vs_A': drm.mean(),
                    'delta_rmse_pct_vs_A': 100 * (d.rmse / a.rmse - 1).mean()})
    return pd.DataFrame(out)


def main():
    TABELAS.mkdir(parents=True, exist_ok=True)
    soc, tex = ed.carregar_experimento()
    det = pd.concat([
        rodar_base('soc', soc, {'log_soc': 'soc_g_m2'}),
        rodar_base('textura', tex, {r: col for r, (b, col) in RESPOSTAS.items() if b == 'textura'}),
    ])
    det.to_csv(TABELAS / 'experimento_repeticoes.csv', index=False)
    res = resumir(det)
    res.to_csv(TABELAS / 'experimento_resumo.csv', index=False)
    print(res.pivot_table(index='cenario', columns='resposta', values='r2').round(3).to_string())


if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == 'rapido':      # teste de fumaça: 1 repetição, 20 árvores
        N_REPETICOES = 1
        PARAMS_RF['n_estimators'] = 20
    main()
