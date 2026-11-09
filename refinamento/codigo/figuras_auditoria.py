"""Figuras agregadas de C1 e do ensaio parcial C12; sem dados por estação."""
import os

from codigo.dados_temperatura import ROOT

os.environ["MPLCONFIGDIR"] = str(ROOT / ".local/matplotlib")
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


def main():
    tables, figures = ROOT / "resultados/tabelas", ROOT / "resultados/figuras"
    frame = pd.read_csv(tables / "c1_modelos_2graus.csv")
    means = frame.loc[frame.scope.eq("global")].groupby("method").rmse.mean()
    names = ["M0_xavier", "M5_lightgbm", "M4_random_forest", "M2_linear", "M0_chelsa",
             "M1_lapse_fixo", "MX_mensal_referencia", "M0_era5", "M0_terraclimate"]
    labels = ["Xavier publicado*", "LightGBM + CHELSA", "Random forest + CHELSA",
              "Regressão linear", "CHELSA", "Gradiente fixo", "MX mensal aproximado",
              "ERA5-Land", "TerraClimate"]
    fig, ax = plt.subplots(figsize=(10, 6.3), layout="constrained")
    bars = ax.barh(labels, means.reindex(names), color=["#ad6c2f"] + ["#24564b"] * 3 + ["#7294a4"] * 5)
    ax.bar_label(bars, fmt="%.3f", padding=4, fontsize=10)
    ax.invert_yaxis()
    ax.set(xlabel="RMSE mensal (°C) — menor é melhor", xlim=(0, 1.48),
           title="Temperatura 1991–2020: quatro bases e modelos existentes")
    ax.spines[["top", "right"]].set_visible(False)
    fig.supxlabel("98 estações com todas as bases · validação em blocos de 2° · média de 3 repetições\n"
                  "*Xavier pode ter usado estas estações. Comparação não independente.\n"
                  "Treinos originais mantidos; 18 estações reservadas continuam sem avaliação.", fontsize=10)
    fig.savefig(figures / "c1_quatro_bases.png", dpi=160)
    plt.close(fig)

    frame = pd.read_csv(tables / "c12_falhas_artificiais.csv")
    methods = ["available_years", "difference", "regression_fill"]
    scenarios = ["random_24", "recent_24", "first_10", "recent_10"]
    panel = frame[frame.source.eq("era5")].pivot(index="scenario", columns="method", values="rmse")
    fig, ax = plt.subplots(figsize=(10, 5.8), layout="constrained")
    for i, (method, label, color) in enumerate(zip(methods,
            ["Média dos anos retidos", "Método das diferenças", "Regressão com ERA5-Land"],
            ["#ad6c2f", "#24564b", "#7294a4"])):
        bars = ax.bar(np.arange(len(scenarios)) + (i - 1) * 0.25,
                      panel.loc[scenarios, method], width=0.25, label=label, color=color)
        ax.bar_label(bars, fmt="%.3f", padding=3, fontsize=8)
    ax.set(xticks=np.arange(len(scenarios)),
           xticklabels=["24 anos aleatórios", "1997–2020", "1991–2000", "2011–2020"],
           ylabel="RMSE da normal estimada (°C)", ylim=(0, 0.52),
           title="Falhas artificiais: efeito de usar apenas parte dos 30 anos")
    ax.spines[["top", "right"]].set_visible(False)
    ax.legend(frameon=False, fontsize=9, loc="upper left")
    fig.supxlabel("250 séries estação-mês · 43 estações de desenvolvimento · referência temporal ERA5-Land\n"
                  "30 máscaras no cenário aleatório; uma nos demais. Não testa falhas diárias.\n"
                  "Experimento em séries longas: resultado não valida automaticamente estações curtas.", fontsize=10)
    fig.savefig(figures / "c12_falhas_artificiais.png", dpi=160)
    plt.close(fig)
    print("Figuras C1/C12 gravadas em resultados/figuras.")


if __name__ == "__main__":
    main()
