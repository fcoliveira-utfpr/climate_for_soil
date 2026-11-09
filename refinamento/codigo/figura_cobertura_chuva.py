"""Cobertura agregada de chuva; não representa mapa interpolado ou validado."""
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from codigo.dados_temperatura import safe_path


def main():
    source = safe_path('resultados/tabelas/chuva_sensibilidade_cobertura.csv')
    coverage = pd.read_csv(source).sort_values('minimum_years')
    fig, ax = plt.subplots(figsize=(8, 5))
    labels = [f'{int(r.minimum_years)} anos\n({r.coverage_fraction:.0%})'
              for r in coverage.itertuples()]
    bars = ax.bar(labels, coverage.stations_12_months, color='#147d64', width=.6)
    ax.bar_label(bars, padding=5, fmt='%d')
    ax.set_ylim(0, max(1, coverage.stations_12_months.max()) * 1.2)
    ax.set_ylabel('Estações com as 12 normais mensais elegíveis')
    ax.set_xlabel('Cobertura mínima por mês no período 1991–2020')
    ax.set_title('Chuva observada — sensibilidade à cobertura temporal')
    ax.grid(axis='y', alpha=.2)
    ax.set_axisbelow(True)
    fig.text(.5, .02, 'Mês exige todos os dias válidos; sem preenchimento adicional.\n'
             'Controle inicial: homogeneidade e independência ainda pendentes.',
             ha='center', fontsize=9)
    fig.tight_layout(rect=(0, .09, 1, 1))
    fig.savefig(safe_path('resultados/figuras/chuva_cobertura.png'), dpi=170)
    plt.close(fig)


if __name__ == '__main__':
    main()
