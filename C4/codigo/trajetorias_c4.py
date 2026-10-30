"""Etapa 8: trajetórias de SOC 1985-2024 com o Xavier v3.2.4 contra o v6 (v3.2.2), o Köppen IPEF e o SOC oficial.

Junta as predições do painel do C4 (temperatura e conjunto curto com a v3.2.4) às do v6 (Köppen IPEF,
contínuo decenal e conjunto curto com a v3.2.2), todas com o modelo final de cada cenário, e usa as funções do
relatório v2 (climas/analise_espaco_tempo/codigo/trajetorias.py).

Saídas: resultados/tabelas/trajetorias_c4_efeito_clima.csv, trajetorias_c4_conversoes.csv,
trajetorias_c4_anual.csv (média anual de cada série) e resultados/figuras/trajetorias_c4.png (ranger),
trajetorias_c4_gee.png (modelo do mapa)

Uso: python trajetorias_c4.py
"""
import sys
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import pandas as pd

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / 'climas' / 'analise_espaco_tempo' / 'codigo'))
import config as cfg  # noqa: E402
from trajetorias import BIOMAS, conversoes, efeito_clima  # noqa: E402

DADOS = RAIZ / 'C4' / 'dados'
V6 = RAIZ / 'clima_final' / 'dados'
PASTA = RAIZ / 'C4' / 'resultados'
MODELOS = {'ranger': '', 'mapa': '_gee'}
SERIES = {
    'soc_oficial_t_ha': ('SOC oficial C3', '#0b0b0b', 2.4, '-'),
    'koppen_ipef': ('Köppen IPEF', '#8a8984', 1.6, '--'),
    'curto_v6': ('Conjunto curto, Xavier v3.2.2 (v6)', '#eb6834', 1.3, ':'),
    'curto': ('Conjunto curto, Xavier v3.2.4 (C4)', '#eb6834', 2.0, '-'),
}


def carregar(suf):
    v6 = pd.read_parquet(V6 / f'painel_predicoes{suf}.parquet',
                         columns=['ponto_id', 'year', 'koppen_ipef', 'cont_decenal', 'temperatura', 'curto'])
    v6 = v6.rename(columns={'temperatura': 'temperatura_v6', 'curto': 'curto_v6'})
    c4 = pd.read_parquet(DADOS / f'painel_predicoes{suf}.parquet')
    of = pd.read_parquet(cfg.DADOS / 'soc_oficial_c3.parquet')
    usos = ['vegNatural', 'agropecuaria', 'pastagem', 'lavouras']
    p = pd.read_parquet(cfg.PAINEL, columns=['ponto_id', 'year'] + usos + BIOMAS)
    p['bioma'] = p[BIOMAS].idxmax(axis=1)
    d = (v6.merge(c4, on=['ponto_id', 'year']).merge(of, on=['ponto_id', 'year'])
         .merge(p.drop(columns=BIOMAS), on=['ponto_id', 'year']))
    cenarios = ['koppen_ipef', 'cont_decenal', 'temperatura_v6', 'curto_v6', 'temperatura', 'curto']
    return d.sort_values(['ponto_id', 'year']).reset_index(drop=True), cenarios


def figura(d, nome, titulo):
    grupos = [('Brasil', d)] + [(b.replace('_', ' '), g) for b, g in d.groupby('bioma')]
    fig, axs = plt.subplots(2, 4, figsize=(17, 8))
    for ax, (rot, g) in zip(axs.flat, grupos):
        media = g.groupby('year')[list(SERIES)].mean()
        for c, (lab, cor, lw, ls) in SERIES.items():
            ax.plot(media.index, media[c], color=cor, lw=lw, ls=ls, label=lab)
        ax.set_title(f'{rot} ({g.ponto_id.nunique()} locais)', fontsize=10, color='#0b0b0b')
        for lado in ('top', 'right'):
            ax.spines[lado].set_visible(False)
        ax.tick_params(colors='#52514e', labelsize=8)
        ax.grid(axis='y', color='#e4e3df', lw=0.8)
    for ax in axs[:, 0]:
        ax.set_ylabel('SOC 0-30 cm (t/ha)', fontsize=9, color='#52514e')
    axs.flat[-1].axis('off')
    axs.flat[-1].legend(*axs.flat[0].get_legend_handles_labels(), loc='center', fontsize=10, frameon=False)
    fig.suptitle(titulo, fontsize=13, x=0.01, ha='left', color='#0b0b0b')
    fig.tight_layout()
    fig.savefig(PASTA / 'figuras' / nome, dpi=150)
    plt.close(fig)


def main():
    pd.set_option('display.width', 220)
    ef, cv, an = [], [], []
    for modelo, suf in MODELOS.items():
        d, cenarios = carregar(suf)
        ef.append(efeito_clima(d, cenarios).assign(modelo=modelo))
        cv.append(conversoes(d, cenarios).assign(modelo=modelo))
        an.append(d.groupby('year')[cenarios + ['soc_oficial_t_ha']].mean().reset_index().assign(modelo=modelo))
        nome_m = 'modelo do mapa + pós-processamento' if suf else 'ranger, sem pós-processamento'
        figura(d, f'trajetorias_c4{suf}.png', f'Trajetória do SOC 1985-2024 ({nome_m}): Xavier v3.2.2 x v3.2.4')
    for nome, t in [('efeito_clima', ef), ('conversoes', cv), ('anual', an)]:
        t = pd.concat(t, ignore_index=True)
        t = t[['modelo'] + [c for c in t.columns if c != 'modelo']]
        t.to_csv(PASTA / 'tabelas' / f'trajetorias_c4_{nome}.csv', index=False, float_format='%.4g')
        if nome != 'anual':
            print(f'\n== {nome}\n{t.round(3).to_string(index=False)}')


if __name__ == '__main__':
    main()
