"""Peças comuns da fase 1: covariáveis por cenário, dobras espaciais, modelos e transformações."""
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor, RandomForestRegressor

import config as cfg
import dados


def base(df, excluir=()):
    """Covariáveis do MapBiomas comuns a todos os cenários (sem clima)."""
    fora = set(dados.CLIMA_COLS) | {'zona_k10', 'soc_g_m2'} | set(excluir)
    if cfg.SEM_C2:
        fora |= set(cfg.TEXTURA_C2)
    return [c for c in dados.covariaveis(df) if c not in fora and pd.api.types.is_numeric_dtype(df[c])]


def clima(df, cenario, categorias=None):
    """Colunas de clima do cenário: dummies (com as mesmas categorias em treino e teste) ou numéricas."""
    _, cols, tipo = cfg.CENARIOS[cenario]
    if tipo is None:
        return pd.DataFrame(index=df.index)
    if tipo == 'numerico':
        return df[cols].astype(float)
    d = pd.get_dummies(df[cols].astype('string'), prefix=cols, dtype=float)
    return d.reindex(columns=categorias, fill_value=0.0) if categorias is not None else d


def categorias(cenario, *dfs):
    """Todas as dummies possíveis do cenário (união dos conjuntos), para alinhar colunas."""
    _, cols, tipo = cfg.CENARIOS[cenario]
    if tipo != 'dummies':
        return None
    return sorted(set().union(*[clima(d, cenario).columns for d in dfs]))


# --- Dobras espaciais compartilhadas (mesmo bloco -> mesma dobra, na textura e no SOC) ---------------
def chave_bloco(df):
    gx = np.floor(df.longitude.to_numpy() / cfg.TAM_BLOCO).astype(int)
    gy = np.floor(df.latitude.to_numpy() / cfg.TAM_BLOCO).astype(int)
    return pd.Series(gx.astype(str), index=df.index) + '_' + pd.Series(gy.astype(str), index=df.index)


def sortear_dobras(chaves, rng):
    """chaves: todas as chaves de bloco (união das bases). Devolve {chave: dobra}."""
    uniq = np.array(sorted(set(chaves)))
    dobra = rng.permutation(len(uniq)) % cfg.N_DOBRAS
    return dict(zip(uniq, dobra))


# --- Modelos --------------------------------------------------------------------------------------------
def gbm(semente):
    return HistGradientBoostingRegressor(random_state=semente, **cfg.PARAMS_GBM)


def rf(semente):
    return RandomForestRegressor(random_state=semente, **cfg.PARAMS_RF)


def razoes_para_pct(la, ls):
    """Razões log (ln((x+1)/(argila+1))) -> % de areia, silte e argila na terra fina, com fechamento em
    100 (mesma expressão do script do MapBiomas: argila = 1 / (1 + e^la + e^ls))."""
    ea, es = np.exp(la), np.exp(ls)
    argila = 1 / (1 + ea + es)
    return 100 * ea * argila, 100 * es * argila, 100 * argila


def r2(y, p):
    y, p = np.asarray(y, float), np.asarray(p, float)
    return float(1 - np.sum((y - p) ** 2) / np.sum((y - y.mean()) ** 2))


def rmse(y, p):
    return float(np.sqrt(np.mean((np.asarray(y, float) - np.asarray(p, float)) ** 2)))
