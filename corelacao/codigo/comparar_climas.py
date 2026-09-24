"""Qual classificação climática serve melhor de base para estimar SOC e textura?

Cada sistema/nível é usado como único preditor: a estimativa de um local é a média da sua classe
nos locais de treino. A métrica principal é o R² fora da amostra com validação cruzada em blocos
espaciais (a média da classe é calculada sem os locais do bloco testado); o ω² é o tamanho de
efeito descritivo (dentro da amostra, já descontado o número de classes).

Todos os sistemas são avaliados nos mesmos locais e nas mesmas dobras, então as diferenças de R²
entre eles são pareadas (repetição a repetição).

Saída: resultados/tabelas/*.csv (só agregados; os dados por ponto são restritos e ficam em .local/).
"""
from pathlib import Path

import numpy as np
import pandas as pd

import legendas as leg
from preparar_dados import carregar_bases

ROOT = Path(__file__).resolve().parents[1]
TABELAS = ROOT / 'resultados' / 'tabelas'

# resposta -> (base, coluna, rótulo)
RESPOSTAS = {
    'log_soc': ('soc', 'soc_g_m2', 'log(SOC)'),
    'argila': ('textura', 'argila', 'Argila (%)'),
    'areia': ('textura', 'areia', 'Areia (%)'),
    'silte': ('textura', 'silte', 'Silte (%)'),
}
# esquema de validação -> tamanho do bloco espacial em graus (None = dobras aleatórias por local)
ESQUEMAS = {'aleatoria': None, 'bloco_1': 1.0, 'bloco_2': 2.0, 'bloco_5': 5.0}
ESQUEMA_PRINCIPAL = 'bloco_2'
N_DOBRAS = 5
N_REPETICOES = 50
SEMENTE = 2026
N_MIN_PUBLICAR = 5


# ---------------------------------------------------------------------------------------------
# Métricas
# ---------------------------------------------------------------------------------------------
def codificar(classes):
    """Classes (texto) -> inteiros 0..k-1."""
    cod, uniq = pd.factorize(pd.Series(classes), sort=True)
    return cod.astype(np.int64), len(uniq)


def omega2(y, cod, k):
    """ω² da ANOVA de um fator: fração da variância explicada pelas classes, já descontado o
    ganho esperado só por haver k classes (ao contrário do η², que sempre cresce com k)."""
    n = len(y)
    if k < 2:
        return 0.0
    cont = np.bincount(cod, minlength=k)
    medias = np.bincount(cod, weights=y, minlength=k) / np.maximum(cont, 1)
    ss_t = np.sum((y - y.mean()) ** 2)
    ss_b = np.sum(cont * (medias - y.mean()) ** 2)
    ms_w = (ss_t - ss_b) / (n - k)
    return float((ss_b - (k - 1) * ms_w) / (ss_t + ms_w))


def grupos_espaciais(lon, lat, tamanho):
    """Id do bloco espacial de cada local (quadrículas de `tamanho` graus); None = cada local
    é o seu próprio grupo (validação aleatória)."""
    if tamanho is None:
        return np.arange(len(lon))
    gx = np.floor(np.asarray(lon) / tamanho).astype(np.int64)
    gy = np.floor(np.asarray(lat) / tamanho).astype(np.int64)
    return pd.factorize(pd.Series(gx * 100000 + gy))[0]


def sortear_dobras(grupos, n_dobras, rng):
    """Distribui os grupos (blocos) ao acaso entre as dobras; todo local de um bloco cai na
    mesma dobra."""
    n_grupos = grupos.max() + 1
    dobra_do_grupo = rng.permutation(n_grupos) % n_dobras
    return dobra_do_grupo[grupos]


def prever_media_da_classe(y, cod, k, dobras, n_dobras):
    """Estimativa fora da amostra: média da classe nos locais de treino; classe ausente no
    treino recebe a média geral do treino."""
    pred = np.empty_like(y)
    for f in range(n_dobras):
        teste = dobras == f
        treino = ~teste
        cont = np.bincount(cod[treino], minlength=k)
        soma = np.bincount(cod[treino], weights=y[treino], minlength=k)
        geral = y[treino].mean()
        medias = np.where(cont > 0, soma / np.maximum(cont, 1), geral)
        pred[teste] = medias[cod[teste]]
    return pred


def r2(y, pred):
    return float(1 - np.sum((y - pred) ** 2) / np.sum((y - y.mean()) ** 2))


def r2_repeticoes(y, codigos, lon, lat, tamanho, n_rep=N_REPETICOES, n_dobras=N_DOBRAS, semente=SEMENTE):
    """R² fora da amostra de cada preditor em cada repetição do sorteio das dobras.
    codigos: {nome: (cod, k)}. Retorna DataFrame (repetição x preditor). Mesmas dobras para
    todos os preditores em cada repetição -> diferenças pareadas."""
    rng = np.random.default_rng(semente)
    grupos = grupos_espaciais(lon, lat, tamanho)
    linhas = []
    for _ in range(n_rep):
        dobras = sortear_dobras(grupos, n_dobras, rng)
        linhas.append({nome: r2(y, prever_media_da_classe(y, cod, k, dobras, n_dobras))
                       for nome, (cod, k) in codigos.items()})
    return pd.DataFrame(linhas)


# ---------------------------------------------------------------------------------------------
# Execução
# ---------------------------------------------------------------------------------------------
def amostra_comum(df, col_y):
    """Só locais com classe em todos os sistemas/níveis: todos avaliados nos mesmos pontos."""
    ok = df[leg.COLUNAS_CLIMA].notna().all(axis=1) & df[col_y].notna()
    return df[ok].reset_index(drop=True), int((~ok).sum())


def diagnostico_koppen(df, y, resp):
    """Por que o Köppen CHELSA difere do IPEF: concordância, versões híbridas (CHELSA com uma das
    discordâncias trocada pela resposta do IPEF) e temperatura do mês mais frio na fronteira A/C."""
    ipef = df.koppen_ipef_l3.str.replace('Bsh', 'BSh')
    ch = df.koppen_chelsa_l3
    lon, lat = df.longitude.to_numpy(), df.latitude.to_numpy()

    concord = (pd.crosstab(ipef.rename('ipef_l3'), ch.rename('chelsa_l3')).stack()
               .rename('n').reset_index().query('n > 0').assign(resposta=resp))

    ambos_a = (ipef.str[0] == 'A') & (ch.str[0] == 'A')
    grupo_dif = ipef.str[0] != ch.str[0]
    versoes = {
        'Köppen IPEF L3': ipef,
        'Köppen CHELSA L3': ch,
        'CHELSA com o grupo do IPEF onde discordam (A x C/B)': ch.where(~grupo_dif, ipef),
        'CHELSA com o subtipo do IPEF dentro do grupo A (Am/Aw...)': ch.where(~ambos_a, ipef),
    }
    reps = r2_repeticoes(y, {k: codificar(v) for k, v in versoes.items()}, lon, lat,
                         ESQUEMAS[ESQUEMA_PRINCIPAL])
    hibridos = pd.DataFrame({'resposta': resp, 'versao': list(versoes), 'r2_bloco_2': reps.mean().values,
                             'ic_inf': reps.quantile(0.025).values, 'ic_sup': reps.quantile(0.975).values})

    grupos = {'IPEF C, CHELSA A': (ipef.str[0] == 'C') & (ch.str[0] == 'A'),
              'IPEF C, CHELSA C': (ipef.str[0] == 'C') & (ch.str[0] == 'C'),
              'IPEF A, CHELSA A': ambos_a}
    col = RESPOSTAS[resp][1]
    fator = 0.01 if resp == 'log_soc' else 1
    fronteira = []
    for nome, m in grupos.items():
        t = df.loc[m, 'tas_mes_mais_frio']
        linha = {'resposta': resp, 'grupo': nome, 'n': int(m.sum()),
                 'mediana_resposta': df.loc[m, col].median() * fator}
        linha.update({f'tfrio_p{q}': t.quantile(q / 100) for q in (10, 25, 50, 75, 90)})
        linha['pct_tfrio_18_19'] = 100 * t.between(18, 19, inclusive='left').mean()
        fronteira.append(linha)
    return concord, hibridos, pd.DataFrame(fronteira)


def main():
    TABELAS.mkdir(parents=True, exist_ok=True)
    soc, tex = carregar_bases()
    bases = {'soc': soc, 'textura': tex}

    desempenho, diferencas, classes, amostra = [], [], [], []
    concord, hibridos, fronteira = [], [], []
    for resp, (base, col, rotulo) in RESPOSTAS.items():
        df, n_fora = amostra_comum(bases[base], col)
        y = np.log(df[col].to_numpy(float)) if resp == 'log_soc' else df[col].to_numpy(float)
        codigos = {c: codificar(df[c]) for c in leg.COLUNAS_CLIMA}
        lon, lat = df.longitude.to_numpy(), df.latitude.to_numpy()

        # concentração espacial da amostra (caixas aproximadas de RO e RS; blocos de 2° mais densos)
        cont_b2 = np.sort(np.bincount(grupos_espaciais(lon, lat, 2.0)))[::-1]
        caixa_ro = (lon >= -66.9) & (lon <= -59.7) & (lat >= -13.8) & (lat <= -7.9)
        caixa_rs = (lat < -27.1) & (lon > -57.7)
        amostra.append({'resposta': resp, 'rotulo': rotulo, 'locais': len(df),
                        'excluidos_sem_classe': n_fora,
                        **{f'blocos_{e}': int(grupos_espaciais(lon, lat, t).max() + 1)
                           for e, t in ESQUEMAS.items() if t is not None},
                        'pct_regiao_rondonia': 100 * caixa_ro.mean(),
                        'pct_rio_grande_do_sul': 100 * caixa_rs.mean(),
                        'pct_20_blocos_2_mais_densos': 100 * cont_b2[:20].sum() / len(df)})

        c_, h_, f_ = diagnostico_koppen(df, y, resp)
        concord.append(c_); hibridos.append(h_); fronteira.append(f_)

        reps = {e: r2_repeticoes(y, codigos, lon, lat, t) for e, t in ESQUEMAS.items()}
        for c, (cod, k) in codigos.items():
            sistema, nivel, descricao = leg.NIVEIS[c]
            linha = {'resposta': resp, 'sistema': sistema, 'nivel': nivel, 'descricao': descricao,
                     'coluna': c, 'n_classes': k, 'omega2': omega2(y, cod, k)}
            for e, r in reps.items():
                linha[f'r2_{e}'] = r[c].mean()
                linha[f'r2_{e}_ic_inf'] = r[c].quantile(0.025)
                linha[f'r2_{e}_ic_sup'] = r[c].quantile(0.975)
            desempenho.append(linha)

        # diferenças pareadas em relação ao melhor preditor no esquema principal
        r = reps[ESQUEMA_PRINCIPAL]
        melhor = r.mean().idxmax()
        for c in leg.COLUNAS_CLIMA:
            d = r[melhor] - r[c]
            diferencas.append({'resposta': resp, 'melhor': melhor, 'coluna': c,
                               'sistema': leg.NIVEIS[c][0], 'nivel': leg.NIVEIS[c][1],
                               'delta_r2': d.mean(), 'ic_inf': d.quantile(0.025),
                               'ic_sup': d.quantile(0.975), 'prop_melhor_vence': (d > 0).mean()})

        # médias por classe (interpretação); SOC em Mg/ha (1 g/m² = 0,01 Mg/ha)
        valor = df[col] * (0.01 if resp == 'log_soc' else 1)
        for c in leg.COLUNAS_CLIMA:
            g = valor.groupby(df[c])
            t = pd.DataFrame({'n': g.size(), 'mediana': g.median(), 'media': g.mean()})
            # classes com poucos locais: não publicar o valor (seria quase o dado de um ponto, restrito)
            t.loc[t.n < N_MIN_PUBLICAR, ['mediana', 'media']] = np.nan
            t = t.reset_index().rename(columns={c: 'classe'})
            classes.append(t.assign(resposta=resp, coluna=c, sistema=leg.NIVEIS[c][0],
                                    nivel=leg.NIVEIS[c][1]))
        print(f'{resp}: {len(df)} locais, melhor = {melhor} (R² {r[melhor].mean():.3f})')

    pd.DataFrame(amostra).to_csv(TABELAS / 'amostra.csv', index=False)
    pd.concat(concord).to_csv(TABELAS / 'koppen_concordancia.csv', index=False)
    pd.concat(hibridos).to_csv(TABELAS / 'koppen_hibridos.csv', index=False)
    pd.concat(fronteira).to_csv(TABELAS / 'koppen_fronteira.csv', index=False)
    pd.DataFrame(desempenho).to_csv(TABELAS / 'desempenho.csv', index=False)
    pd.DataFrame(diferencas).to_csv(TABELAS / 'diferencas_pareadas.csv', index=False)
    cols = ['resposta', 'sistema', 'nivel', 'coluna', 'classe', 'n', 'mediana', 'media']
    pd.concat(classes)[cols].to_csv(TABELAS / 'classes.csv', index=False)


if __name__ == '__main__':
    main()
