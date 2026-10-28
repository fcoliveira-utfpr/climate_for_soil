"""Etapa 6: trajetórias de SOC 1985-2024 dos cenários do capítulo 6 contra o Köppen IPEF e o SOC oficial.

Usa as predições do painel (prever_painel.R e prever_painel_gee.py com VAL_*, modelo final de cada cenário na
matriz inteira) e as funções do relatório v2 (climas/analise_espaco_tempo/codigo/trajetorias.py): tendência
por local, variação ano a ano, diferença para o Köppen e resposta às conversões de uso.

Saídas: resultados/tabelas/trajetorias_final_efeito_clima.csv, trajetorias_final_conversoes.csv e
resultados/figuras/trajetorias_final.png (ranger), trajetorias_final_gee.png (modelo do mapa)

Uso: python trajetorias_final.py
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

DADOS = RAIZ / 'clima_final' / 'dados'
PASTA = RAIZ / 'clima_final' / 'resultados'
MODELOS = {'ranger': '', 'mapa': '_gee'}
# séries da figura: (rótulo, cor, espessura, estilo); as demais ficam só nas tabelas
SERIES = {
    'soc_oficial_t_ha': ('SOC oficial C3', '#0b0b0b', 2.4, '-'),
    'koppen_ipef': ('Köppen IPEF', '#8a8984', 1.6, '--'),
    'cont_decenal': ('Contínuo decenal (v2)', '#2a78d6', 1.4, '-'),
    'temperatura': ('Temperatura decenal (v4)', '#1baf7a', 1.4, '-'),
    'curto': ('Conjunto curto (v6)', '#eb6834', 1.8, '-'),
}


def carregar(suf):
    pred = pd.read_parquet(DADOS / f'painel_predicoes{suf}.parquet')
    of = pd.read_parquet(cfg.DADOS / 'soc_oficial_c3.parquet')
    usos = ['vegNatural', 'agropecuaria', 'pastagem', 'lavouras']
    p = pd.read_parquet(cfg.PAINEL, columns=['ponto_id', 'year'] + usos + BIOMAS)
    p['bioma'] = p[BIOMAS].idxmax(axis=1)
    d = pred.merge(of, on=['ponto_id', 'year']).merge(p.drop(columns=BIOMAS), on=['ponto_id', 'year'])
    cenarios = [c for c in pred.columns if c not in ('ponto_id', 'year')]
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
    axs.flat[-1].axis('off')
    axs.flat[-1].legend(*axs.flat[0].get_legend_handles_labels(), loc='center', fontsize=10, frameon=False)
    for ax in axs[:, 0]:
        ax.set_ylabel('SOC 0-30 cm (t/ha)', fontsize=9, color='#52514e')
    fig.suptitle(titulo, fontsize=13, x=0.01, ha='left', color='#0b0b0b')
    fig.tight_layout()
    fig.savefig(PASTA / 'figuras' / nome, dpi=150)
    plt.close(fig)


def main():
    pd.set_option('display.width', 220)
    ef, cv = [], []
    for modelo, suf in MODELOS.items():
        d, cenarios = carregar(suf)
        ef.append(efeito_clima(d, cenarios).assign(modelo=modelo))
        cv.append(conversoes(d, cenarios).assign(modelo=modelo))
        nome_m = 'modelo do mapa + pós-processamento' if suf else 'ranger, sem pós-processamento'
        figura(d, f'trajetorias_final{suf}.png', f'Trajetória do SOC 1985-2024 ({nome_m})')
    for nome, t in [('efeito_clima', ef), ('conversoes', cv)]:
        t = pd.concat(t, ignore_index=True)
        t = t[['modelo'] + [c for c in t.columns if c != 'modelo']]
        t.to_csv(PASTA / 'tabelas' / f'trajetorias_final_{nome}.csv', index=False, float_format='%.4g')
        print(f'\n== {nome}\n{t.round(3).to_string(index=False)}')


if __name__ == '__main__':
    main()
