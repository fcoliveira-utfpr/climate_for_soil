"""Importancia marginal de Koppen L2 vs. Holdridge L2, dentro do MESMO modelo, por
permutacao em bloco - nao decide um "vencedor" fixo entre os dois sistemas para o
pipeline inteiro; mede, para cada variavel-resposta, o quanto cada bloco de dummies
climaticas pesa quando os dois entram juntos no random forest (M4-equivalente:
clima + relevo, e tambem textura para SOC), avaliado fora da amostra nos blocos
espaciais de 2 graus que regressoes_corrigidas.py ja usa. CV aleatorio infla a
importancia porque classes climaticas sao espacialmente agrupadas (ver secao 9 do
notebook: R2 do RF cai de 0,41 no aleatorio para ~0,25 nos blocos de 5 graus).

Permutacao em BLOCO (todas as dummies de um sistema embaralhadas juntas, com a mesma
permutacao de linhas) e nao coluna a coluna: permutar uma dummy por vez deixaria
combinacoes invalidas (duas classes "ativas" ou nenhuma) e sub/superestimaria a
contribuicao real do sistema.
"""
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import r2_score
from sklearn.model_selection import GroupKFold

from preparar_dados import RES, carregar_bases
from regressoes_corrigidas import grupos_espaciais
from graficos_relatorio import barras, save

SEED = 42
N_REPEATS = 20


def montar_features(df, com_textura):
    koppen = pd.get_dummies(df.koppen_l2, prefix='koppen_l2', dtype=float)
    holdridge = pd.get_dummies(df.HLZ_L2, prefix='HLZ_L2', dtype=float)
    relevo = df[['elevation', 'latitude']].astype(float)
    partes = [koppen, holdridge, relevo]
    if com_textura:
        partes.append(df[['areia', 'argila']].astype(float))
    X = pd.concat(partes, axis=1)
    bloco_de = {}
    for c in X.columns:
        if c.startswith('koppen_l2_'): bloco_de[c] = 'Köppen L2'
        elif c.startswith('HLZ_L2_'): bloco_de[c] = 'Holdridge L2'
        elif c in ('areia', 'argila'): bloco_de[c] = 'Textura'
        else: bloco_de[c] = 'Relevo'
    return X, bloco_de


def importancia_em_bloco(model, X, y, bloco_de, rng):
    """Queda de R2 ao embaralhar, juntas, todas as colunas de um bloco - nao uma de cada vez."""
    grupos = {}
    for col, bloco in bloco_de.items():
        grupos.setdefault(bloco, []).append(col)
    base = r2_score(y, model.predict(X))
    linhas = []
    for bloco, cols in grupos.items():
        quedas = []
        for _ in range(N_REPEATS):
            Xp = X.copy()
            perm = rng.permutation(len(X))
            Xp.loc[:, cols] = X[cols].to_numpy()[perm]
            quedas.append(base - r2_score(y, model.predict(Xp)))
        linhas.append({'bloco': bloco, 'queda_r2_media': float(np.mean(quedas)),
                       'queda_r2_dp': float(np.std(quedas))})
    return linhas, base


def rodar(df, variavel, rotulo, log, com_textura):
    cols_necessarias = [variavel, 'koppen_l2', 'HLZ_L2', 'elevation', 'latitude']
    if com_textura:
        cols_necessarias += ['areia', 'argila']
    sub = df.dropna(subset=cols_necessarias).reset_index(drop=True)
    if log:
        sub = sub[sub[variavel] > 0].reset_index(drop=True)
    X, bloco_de = montar_features(sub, com_textura)
    y = np.log(sub[variavel]) if log else sub[variavel]
    groups = grupos_espaciais(sub, 2)
    rng = np.random.default_rng(SEED)
    resultado = []
    for fold, (train, test) in enumerate(GroupKFold(5).split(X, y, groups), 1):
        model = RandomForestRegressor(n_estimators=200, min_samples_leaf=5, random_state=SEED, n_jobs=2)
        model.fit(X.iloc[train], y.iloc[train])
        linhas, base_r2 = importancia_em_bloco(model, X.iloc[test], y.iloc[test], bloco_de, rng)
        for linha in linhas:
            resultado.append({'variavel_pt': rotulo, 'fold': fold, 'n_teste': len(test),
                              'r2_base_fold': base_r2, **linha})
        print(f'  {rotulo} fold {fold}: R2 base={base_r2:.3f}  ' +
              ', '.join(f"{l['bloco']}={l['queda_r2_media']:+.3f}" for l in linhas), flush=True)
    return pd.DataFrame(resultado)


def grafico(resumo):
    pivot = resumo.pivot(index='variavel_pt', columns='bloco', values='queda_r2_media')
    order = ['areia', 'silte', 'argila', 'SOC']
    pivot = pivot.loc[order]
    fig, ax = plt.subplots(figsize=(8.2, 4.6))
    barras(ax, np.arange(4), pivot['Köppen L2'].fillna(0), pivot['Holdridge L2'].fillna(0),
          order, ['Köppen L2', 'Holdridge L2'])
    ax.axhline(0, color='#888', lw=.8)
    ax.set_title('Contribuição marginal de cada sistema climático, no mesmo modelo')
    ax.set_ylabel('Queda de R² ao\nembaralhar o bloco (OOF)')
    save(fig, 'rel_importancia_climatica.png')


def main():
    tex, soc, joint = carregar_bases()
    partes = [rodar(tex, var, var, log=False, com_textura=False) for var in ['areia', 'silte', 'argila']]
    partes.append(rodar(joint, 'soc_g_m2', 'SOC', log=True, com_textura=True))
    completo = pd.concat(partes, ignore_index=True)
    completo.to_csv(RES / 'importancia_climatica_folds.csv', index=False)

    resumo = (completo.groupby(['variavel_pt', 'bloco'], as_index=False)
             .agg(queda_r2_media=('queda_r2_media', 'mean'),
                  queda_r2_dp=('queda_r2_media', 'std'),
                  r2_base_medio=('r2_base_fold', 'mean'),
                  n_folds=('fold', 'nunique')))
    resumo['queda_pct_do_r2'] = 100 * resumo.queda_r2_media / resumo.r2_base_medio
    resumo.to_csv(RES / 'importancia_climatica.csv', index=False)

    grafico(resumo)
    print()
    print(resumo.round(4).to_string(index=False))


if __name__ == '__main__':
    main()
