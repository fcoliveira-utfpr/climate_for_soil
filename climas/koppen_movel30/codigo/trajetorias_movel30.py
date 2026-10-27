"""Etapa 6b: trajetórias de SOC 1985-2024 do Köppen móvel de 30 anos contra o Köppen IPEF e o SOC oficial.

Junta as predições do painel do `koppen_movel30` (prever_painel.R e prever_painel_gee.py com VAL_*) às do
`koppen_ipef` do relatório v2 (mesmo modelo, mesma semente) e ao SOC oficial da C3. Usa as funções do
relatório v2 (climas/analise_espaco_tempo/codigo/trajetorias.py): tendência por local, variação ano a ano,
diferença para o Köppen IPEF e resposta às conversões de uso. Acrescenta a comparação entre os locais que
mudaram de classe em 1985-2024 e os que não mudaram, e a diferença móvel - IPEF em torno do ano da mudança.

Saídas: resultados/tabelas/trajetorias_movel30_*.csv e resultados/figuras/trajetorias_movel30*.png

Uso: python trajetorias_movel30.py
"""
import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

RAIZ = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(RAIZ / 'climas' / 'analise_espaco_tempo' / 'codigo'))
import config as cfg  # noqa: E402
from trajetorias import BIOMAS, conversoes, efeito_clima, inclinacao  # noqa: E402

DADOS = RAIZ / 'climas' / 'dados_koppen_movel30'
PASTA = Path(__file__).resolve().parents[1] / 'resultados'
TAB, FIG = PASTA / 'tabelas', PASTA / 'figuras'
MODELOS = {'ranger': '', 'mapa': '_gee'}
CEN = ['koppen_ipef', 'koppen_movel30']
ROTULOS = {'koppen_ipef': 'Köppen IPEF', 'koppen_movel30': 'Köppen móvel 30 anos', 'soc_oficial_t_ha': 'SOC oficial C3'}
JANELA = 5             # anos antes e depois da mudança de classe
CLASSE = [c for c in json.loads(Path(__file__).with_name('cenarios_movel30.json').read_text(encoding='utf-8'))
          ['cenarios']['koppen_movel30'] if c.startswith('xkm_l3_')]


def carregar(suf):
    v2 = pd.read_parquet(cfg.DADOS / f'painel_predicoes{suf}.parquet', columns=['ponto_id', 'year', 'koppen_ipef'])
    novo = pd.read_parquet(DADOS / f'painel_predicoes{suf}.parquet')
    of = pd.read_parquet(cfg.DADOS / 'soc_oficial_c3.parquet')
    usos = ['vegNatural', 'agropecuaria', 'pastagem', 'lavouras']
    p = pd.read_parquet(cfg.PAINEL, columns=['ponto_id', 'year'] + usos + BIOMAS)
    p['bioma'] = p[BIOMAS].idxmax(axis=1)
    cls = pd.read_parquet(DADOS / 'painel_movel30.parquet', columns=['ponto_id', 'year'] + CLASSE)
    cls['classe'] = cls[CLASSE].idxmax(axis=1).str.removeprefix('xkm_l3_')
    d = (v2.merge(novo, on=['ponto_id', 'year']).merge(of, on=['ponto_id', 'year'])
         .merge(p.drop(columns=BIOMAS), on=['ponto_id', 'year']).merge(cls[['ponto_id', 'year', 'classe']], on=['ponto_id', 'year']))
    d = d.sort_values(['ponto_id', 'year']).reset_index(drop=True)
    d['mudou'] = d.groupby('ponto_id').classe.transform('nunique') > 1
    return d


def por_grupo(d):
    """Tendência, variação anual e diferença para o IPEF nos locais que mudaram de classe e nos que não."""
    linhas = []
    for mudou, g in d.groupby('mudou'):
        inc = pd.DataFrame({c: inclinacao(g, c) for c in CEN + ['soc_oficial_t_ha']})
        var = g.groupby('ponto_id')[CEN + ['soc_oficial_t_ha']].agg(lambda s: s.diff().abs().mean())
        for c in CEN + ['soc_oficial_t_ha']:
            linhas.append({'locais': 'mudaram de classe' if mudou else 'não mudaram', 'n_locais': g.ponto_id.nunique(),
                           'serie': c, 'soc_medio': g[c].mean(), 'inclinacao_media': inc[c].mean(),
                           'r_inclinacao_oficial': inc[c].corr(inc.soc_oficial_t_ha),
                           'variacao_anual_media': var[c].mean(),
                           'dif_media_ipef': (g[c] - g.koppen_ipef).mean(),
                           'dif_abs_media_ipef': (g[c] - g.koppen_ipef).abs().mean()})
    return pd.DataFrame(linhas)


def eventos_mudanca(d):
    """Diferença móvel - IPEF e SOC oficial de JANELA anos antes a JANELA anos depois de cada mudança de classe."""
    d = d.copy()
    d['dif'] = d.koppen_movel30 - d.koppen_ipef
    g = d.groupby('ponto_id')
    ev = d.index[(g.classe.shift(1) != d.classe) & g.classe.shift(1).notna()]
    linhas = []
    for i in ev:
        ini = d.at[i, 'ponto_id']
        for k in range(-JANELA, JANELA + 1):
            j = i + k
            if 0 <= j < len(d) and d.at[j, 'ponto_id'] == ini:
                linhas.append({'evento': i, 'transicao': f'{d.at[i - 1, "classe"]} -> {d.at[i, "classe"]}', 'k': k,
                               'dif': d.at[j, 'dif'], 'oficial': d.at[j, 'soc_oficial_t_ha']})
    e = pd.DataFrame(linhas)
    base = e[e.k == -1].set_index('evento')
    e['dif_rel'] = e.dif - e.evento.map(base.dif)
    e['oficial_rel'] = e.oficial - e.evento.map(base.oficial)
    return e


def figura(d, e, suf):
    fig, axs = plt.subplots(1, 3, figsize=(15, 4.5))
    for ax, (mudou, g) in zip(axs[:2], d.groupby('mudou')):
        media = g.groupby('year')[CEN + ['soc_oficial_t_ha']].mean()
        ax.plot(media.index, media.soc_oficial_t_ha, 'k-', lw=2.2, label=ROTULOS['soc_oficial_t_ha'])
        ax.plot(media.index, media.koppen_ipef, '--', lw=1.6, label=ROTULOS['koppen_ipef'])
        ax.plot(media.index, media.koppen_movel30, '-', lw=1.4, label=ROTULOS['koppen_movel30'])
        ax.set(xlabel='ano', ylabel='SOC 0-30 cm (t/ha), média dos locais',
               title=f'{"Mudaram" if mudou else "Não mudaram"} de classe ({g.ponto_id.nunique()} locais)')
        ax.legend(fontsize=8)
    r = e.groupby('k')[['dif_rel', 'oficial_rel']].mean()
    axs[2].axhline(0, color='0.6', lw=0.8)
    axs[2].axvline(-0.5, color='0.6', lw=0.8, ls=':')
    axs[2].plot(r.index, r.dif_rel, 'o-', label='móvel - IPEF')
    axs[2].plot(r.index, r.oficial_rel, 's-', color='k', label='SOC oficial')
    axs[2].set(xlabel='anos em relação à mudança de classe', ylabel='variação desde o ano anterior à mudança (t/ha)',
               title=f'Em torno das mudanças de classe ({e.evento.nunique()} eventos)')
    axs[2].legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(FIG / f'trajetorias_movel30{suf}.png', dpi=150)
    plt.close(fig)


def main():
    pd.set_option('display.width', 220)
    ef, gr, cv, ev = [], [], [], []
    for modelo, suf in MODELOS.items():
        d = carregar(suf)
        ef.append(efeito_clima(d, CEN).assign(modelo=modelo))
        gr.append(por_grupo(d).assign(modelo=modelo))
        cv.append(conversoes(d, CEN).assign(modelo=modelo))
        e = eventos_mudanca(d)
        ev.append(e.groupby('k')[['dif_rel', 'oficial_rel']].mean().reset_index().assign(modelo=modelo, eventos=e.evento.nunique()))
        figura(d, e, suf)
    for nome, t in [('efeito_clima', ef), ('grupos', gr), ('conversoes', cv), ('eventos', ev)]:
        t = pd.concat(t, ignore_index=True)
        t = t[['modelo'] + [c for c in t.columns if c != 'modelo']]
        t.to_csv(TAB / f'trajetorias_movel30_{nome}.csv', index=False, float_format='%.4g')
        print(f'\n== {nome}\n{t.round(3).to_string(index=False)}')


if __name__ == '__main__':
    main()
