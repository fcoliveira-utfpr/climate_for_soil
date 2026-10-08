"""Etapa 7d: trajetórias de SOC 1985-2024 nos locais do painel (§5.1 do plano).

1. Fidelidade: a trajetória do cenário Köppen (reprodução da produção) contra o SOC oficial da C3 nos mesmos
   locais e anos (concordância por local-ano, por ano e da tendência por local).
2. Efeito do clima no tempo: para cada cenário, tendência 1985-2024 por local (inclinação, t/ha por década),
   variação ano a ano e diferença em relação ao Köppen.
3. Resposta às mudanças de uso: conversões vegetação natural -> agropecuária e pastagem -> lavoura,
   detectadas pelas idades de uso do painel; variação prevista entre o ano anterior e 5 anos depois.
4. Locais com coletas em anos diferentes (verdade de campo para a variação temporal): contagem na matriz
   bruta e, se houver, variação observada × prevista.

Saídas: resultados/tabelas/trajetorias_*.csv e resultados/figuras/trajetorias_*.png

Uso: python trajetorias.py
"""
import json

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

import config as cfg
from metricas import error_statistics

BIOMAS = ['Amazonia', 'Caatinga', 'Cerrado', 'Mata_Atlantica', 'Pampa', 'Pantanal']
ROTULOS = {'koppen_ipef': 'Köppen IPEF', 'sem_clima': 'Sem clima', 'zonas_k10': 'Zonas k10',
           'holdridge_eth': 'Holdridge ETH', 'th_cadsolo': 'Thornthwaite CAD solo',
           'cont_chelsa': 'Contínuo CHELSA', 'cont_decenal': 'Contínuo decenal', 'cont_ambos': 'Contínuo ambos'}
HORIZONTE = 5          # anos depois da conversão


def inclinacao(df, col):
    """Inclinação OLS por local (t/ha por década)."""
    x = df.year - df.year.mean()
    g = df.assign(_x=x, _xy=x * df[col], _xx=x * x).groupby('ponto_id')
    return 10 * (g._xy.sum() - g._x.sum() * g[col].mean()) / (g._xx.sum() - g._x.sum() ** 2 / g.size())


def carregar():
    pred = pd.read_parquet(cfg.DADOS / 'painel_predicoes.parquet')
    of = pd.read_parquet(cfg.DADOS / 'soc_oficial_c3.parquet')
    usos = ['vegNatural', 'agropecuaria', 'pastagem', 'lavouras']
    p = pd.read_parquet(cfg.PAINEL, columns=['ponto_id', 'year'] + usos + BIOMAS)
    p['bioma'] = p[BIOMAS].idxmax(axis=1)
    d = pred.merge(of, on=['ponto_id', 'year']).merge(p.drop(columns=BIOMAS), on=['ponto_id', 'year'])
    cenarios = [c for c in pred.columns if c not in ('ponto_id', 'year')]
    return d.sort_values(['ponto_id', 'year']).reset_index(drop=True), cenarios


def fidelidade(d):
    linhas = [dict(recorte='local-ano', **error_statistics(d.soc_oficial_t_ha.to_numpy(), d.koppen_ipef.to_numpy()))]
    anual = d.groupby('year')[['soc_oficial_t_ha', 'koppen_ipef']].mean()
    linhas.append(dict(recorte='média anual', **error_statistics(anual.soc_oficial_t_ha.to_numpy(),
                                                                 anual.koppen_ipef.to_numpy())))
    inc = pd.DataFrame({'oficial': inclinacao(d, 'soc_oficial_t_ha'), 'koppen': inclinacao(d, 'koppen_ipef')})
    linhas.append(dict(recorte='inclinação por local', **error_statistics(inc.oficial.to_numpy(), inc.koppen.to_numpy())))
    for b, g in d.groupby('bioma'):
        linhas.append(dict(recorte=f'local-ano {b}', **error_statistics(g.soc_oficial_t_ha.to_numpy(), g.koppen_ipef.to_numpy())))
    tab = pd.DataFrame(linhas)
    tab['r'] = [np.corrcoef(d.soc_oficial_t_ha, d.koppen_ipef)[0, 1], np.corrcoef(anual.soc_oficial_t_ha, anual.koppen_ipef)[0, 1],
                inc.corr().iloc[0, 1]] + [np.corrcoef(g.soc_oficial_t_ha, g.koppen_ipef)[0, 1] for _, g in d.groupby('bioma')]
    return tab, anual


def efeito_clima(d, cenarios):
    inc = pd.DataFrame({c: inclinacao(d, c) for c in cenarios + ['soc_oficial_t_ha']})
    var = d.groupby('ponto_id')[cenarios + ['soc_oficial_t_ha']].agg(lambda s: s.diff().abs().mean())
    linhas = []
    for c in cenarios:
        linhas.append({'cenario': c, 'soc_medio': d[c].mean(), 'inclinacao_media': inc[c].mean(),
                       'inclinacao_mediana': inc[c].median(), 'r_inclinacao_koppen': inc[c].corr(inc.koppen_ipef),
                       'r_inclinacao_oficial': inc[c].corr(inc.soc_oficial_t_ha),
                       'variacao_anual_media': var[c].mean(),
                       'dif_media_koppen': (d[c] - d.koppen_ipef).mean(),
                       'dif_abs_media_koppen': (d[c] - d.koppen_ipef).abs().mean()})
    linhas.append({'cenario': 'soc_oficial', 'soc_medio': d.soc_oficial_t_ha.mean(),
                   'inclinacao_media': inc.soc_oficial_t_ha.mean(), 'inclinacao_mediana': inc.soc_oficial_t_ha.median(),
                   'r_inclinacao_koppen': inc.soc_oficial_t_ha.corr(inc.koppen_ipef), 'r_inclinacao_oficial': 1.0,
                   'variacao_anual_media': var.soc_oficial_t_ha.mean()})
    return pd.DataFrame(linhas)


def conversoes(d, cenarios):
    """Eventos: ano t em que o uso muda (idade da classe nova = 1 e a da antiga era > 0 em t-1)."""
    g = d.groupby('ponto_id')
    ant = {c: g[c].shift(1) for c in ('vegNatural', 'pastagem')}
    eventos = {
        'natural -> agropecuária': (ant['vegNatural'] > 0) & (d.vegNatural == 0) & (d.agropecuaria > 0),
        'pastagem -> lavoura': (ant['pastagem'] > 0) & (d.pastagem == 0) & (d.lavouras > 0),
    }
    linhas = []
    for nome, ev in eventos.items():
        idx = d.index[ev.fillna(False)]
        for c in cenarios + ['soc_oficial_t_ha']:
            antes = g[c].shift(1).loc[idx]
            depois = g[c].shift(-HORIZONTE).loc[idx]
            delta = (depois - antes).dropna()
            linhas.append({'evento': nome, 'cenario': c, 'n': len(delta), 'delta_medio_t_ha': delta.mean(),
                           'delta_mediano_t_ha': delta.median()})
    return pd.DataFrame(linhas)


def coletas_repetidas():
    b = pd.read_parquet(cfg.MATRIZ_BRUTA, columns=['id', 'ano', 'profundidade', 'carbono_gm2_qmap', 'longitude',
                                                   'latitude', 'PSEUDOROCK_index', 'PSEUDOSAND_index'])
    b = b[~b.id.str.startswith('trep') & (b.PSEUDOROCK_index == 0) & (b.PSEUDOSAND_index == 0)]
    b['local'] = b.longitude.round(4).astype(str) + '_' + b.latitude.round(4).astype(str)
    anos = b.groupby('local').ano.nunique()
    b30 = b[b.profundidade == 30]
    anos30 = b30.groupby('local').ano.nunique()
    return pd.DataFrame([{'recorte': 'todas as profundidades', 'locais': len(anos), 'com_2_ou_mais_anos': int((anos >= 2).sum()),
                          'com_3_ou_mais_anos': int((anos >= 3).sum())},
                         {'recorte': 'profundidade 30 cm', 'locais': len(anos30), 'com_2_ou_mais_anos': int((anos30 >= 2).sum()),
                          'com_3_ou_mais_anos': int((anos30 >= 3).sum())}])


def figuras(d, cenarios, anual):
    cfg.FIGURAS.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(9, 5))
    media = d.groupby('year')[cenarios + ['soc_oficial_t_ha']].mean()
    ax.plot(media.index, media.soc_oficial_t_ha, 'k-', lw=2.5, label='SOC oficial C3')
    for c in cenarios:
        ax.plot(media.index, media[c], lw=1.8 if c == 'koppen_ipef' else 1.1,
                ls='--' if c == 'koppen_ipef' else '-', label=ROTULOS.get(c, c))
    ax.set(xlabel='ano', ylabel='SOC 0-30 cm (t/ha), média dos locais', title='Trajetória média 1985-2024')
    ax.legend(fontsize=8, ncol=2)
    fig.tight_layout()
    fig.savefig(cfg.FIGURAS / 'trajetorias_media.png', dpi=150)
    plt.close(fig)

    biomas = sorted(d.bioma.unique())
    fig, axs = plt.subplots(2, 3, figsize=(13, 7), sharex=True)
    for ax, b in zip(axs.flat, biomas):
        mb = d[d.bioma == b].groupby('year')[cenarios + ['soc_oficial_t_ha']].mean()
        ax.plot(mb.index, mb.soc_oficial_t_ha, 'k-', lw=2.2)
        for c in cenarios:
            ax.plot(mb.index, mb[c], lw=1.5 if c == 'koppen_ipef' else 0.9, ls='--' if c == 'koppen_ipef' else '-')
        ax.set_title(f'{b} ({d[d.bioma == b].ponto_id.nunique()} locais)', fontsize=10)
    fig.legend(['SOC oficial C3'] + [ROTULOS.get(c, c) for c in cenarios], loc='lower center', ncol=5, fontsize=8)
    fig.supylabel('SOC 0-30 cm (t/ha)')
    fig.tight_layout(rect=(0, 0.07, 1, 1))
    fig.savefig(cfg.FIGURAS / 'trajetorias_biomas.png', dpi=150)
    plt.close(fig)


def main():
    d, cenarios = carregar()
    cfg.TABELAS.mkdir(parents=True, exist_ok=True)
    fid, anual = fidelidade(d)
    fid.to_csv(cfg.TABELAS / 'trajetorias_fidelidade.csv', index=False, float_format='%.4g')
    ef = efeito_clima(d, cenarios)
    ef.to_csv(cfg.TABELAS / 'trajetorias_efeito_clima.csv', index=False, float_format='%.4g')
    cv = conversoes(d, cenarios)
    cv.to_csv(cfg.TABELAS / 'trajetorias_conversoes.csv', index=False, float_format='%.4g')
    rep = coletas_repetidas()
    rep.to_csv(cfg.TABELAS / 'trajetorias_coletas_repetidas.csv', index=False)
    figuras(d, cenarios, anual)
    pd.set_option('display.width', 220)
    for nome, t in [('Fidelidade (Köppen x oficial)', fid), ('Efeito do clima', ef), ('Conversões', cv),
                    ('Coletas repetidas', rep)]:
        print(f'\n== {nome}\n{t.round(3).to_string(index=False)}')


if __name__ == '__main__':
    main()
