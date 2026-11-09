"""Figuras das análises de 08/11/2026: C15 completo, incerteza calibrada, C11 em vários anos e C3/C7 da chuva.

Lê só tabelas agregadas de resultados/tabelas/ e grava PNGs em resultados/figuras/.
Uso, de dentro de refinamento/:  python -B -m codigo.figuras_finalizacao
"""
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from codigo.dados_temperatura import safe_path

MODEL, REF, XAVIER = "#24564b", "#7294a4", "#ad6c2f"
TABLES = "resultados/tabelas"


def mean_rmse(path, scope_column, scope):
    table = pd.read_csv(safe_path(f"{TABLES}/{path}"))
    return table[table[scope_column] == scope].groupby("method").rmse.mean()


def barh(ax, values, labels, colors, unit, title):
    order = np.argsort(values)[::-1]
    bars = ax.barh([labels[i] for i in order], [values[i] for i in order], color=[colors[i] for i in order])
    for bar, i in zip(bars, order):
        ax.text(bar.get_width(), bar.get_y() + bar.get_height() / 2, f" {values[i]:.3f}" if unit == "°C" else f" {values[i]:.2f}",
                va="center", fontsize=9)
    ax.set_xlabel(f"RMSE mensal ({unit}), blocos de 2°")
    ax.set_title(title, fontsize=11)
    ax.set_xlim(0, max(values) * 1.18)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)


def c15(figures):
    t = mean_rmse("c15_mx_temperatura_2graus.csv", "scope", "global")
    r = mean_rmse("c15_mx_chuva_2graus.csv", "scope", "monthly")
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.6))
    names = [("M5_lightgbm", "LightGBM corrigindo o CHELSA", MODEL), ("M0_chelsa", "CHELSA", REF),
             ("MX_gamma_global", "MX: IDW, gradiente recalibrado", XAVIER), ("MX_mensal_referencia", "MX: IDW, −6,5 °C/km", XAVIER)]
    barh(axes[0], [t[n] for n, _, _ in names], [l for _, l, _ in names], [c for _, _, c in names], "°C", "Temperatura (102 estações)")
    names = [("M5_correction", "LightGBM corrigindo o CHELSA", MODEL), ("M0_chirps", "CHIRPS", REF), ("M0_chelsa", "CHELSA", REF),
             ("M0_era5", "ERA5-Land", REF), ("MX_adw", "MX: ADW (Xavier, chuva)", XAVIER), ("MX_idw", "MX: IDW", XAVIER)]
    barh(axes[1], [r[n] for n, _, _ in names], [l for _, l, _ in names], [c for _, _, c in names], "mm", "Chuva (1.878 estações)")
    fig.suptitle("C15: modelos contra o método do Xavier reproduzido nas mesmas dobras", fontsize=12)
    fig.text(0.5, 0.01, "MX: 5 estações de treino mais próximas; gradiente de pares a até 90 km; ADW com CDD estimada no treino. "
             "Teste reservado não usado.", ha="center", fontsize=8.5)
    fig.tight_layout(rect=(0, 0.04, 1, 0.95))
    fig.savefig(figures / "c15_mx_completo.png", dpi=160)
    plt.close(fig)


def coverage(figures):
    rows = []
    for variable, label in (("temperatura", "Temperatura"), ("chuva", "Chuva (harmônicos)"), ("chuva_por_mes", "Chuva (um modelo por mês)")):
        table = pd.read_csv(safe_path(f"{TABLES}/incerteza_cobertura_{variable}_2graus.csv"))
        rows.append((label, table.coverage_naive_1645sd.mean(), table.coverage_conformal_normalized.mean()))
    fig, ax = plt.subplots(figsize=(8.5, 4.4))
    x = np.arange(len(rows))
    ax.bar(x - 0.18, [r[1] for r in rows], 0.36, color=REF, label="Ingênuo: previsão ± 1,645 × dispersão")
    ax.bar(x + 0.18, [r[2] for r in rows], 0.36, color=MODEL, label="Calibrado (conforme): previsão ± k × dispersão")
    for i, r in enumerate(rows):
        ax.text(i - 0.18, r[1] + 0.02, f"{100 * r[1]:.0f}%", ha="center", fontsize=9)
        ax.text(i + 0.18, r[2] + 0.02, f"{100 * r[2]:.0f}%", ha="center", fontsize=9)
    ax.axhline(0.9, color="#555555", lw=1, ls="--")
    ax.text(len(rows) - 0.55, 0.915, "meta: 90%", fontsize=8.5, color="#555555")
    ax.set_xticks(x, [r[0] for r in rows])
    ax.set_ylim(0, 1.08)
    ax.set_ylabel("Cobertura do intervalo de 90%")
    ax.set_title("Incerteza: a dispersão entre modelos subestima o erro; calibrada, cobre 90%", fontsize=11)
    ax.legend(fontsize=8.5, loc="upper left", frameon=False)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    fig.text(0.5, 0.01, "Validação espacial em blocos de 2°, 5 dobras × 3 repetições; k de cada dobra estimado nas outras dobras.",
             ha="center", fontsize=8.5)
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    fig.savefig(figures / "incerteza_cobertura.png", dpi=160)
    plt.close(fig)


def c11(figures):
    table = pd.read_csv(safe_path(f"{TABLES}/c11_definicoes_multianual.csv"))
    table = table[table.scope == "year"]
    fig, ax = plt.subplots(figsize=(8, 4.2))
    for method, label, color in (("mean_extremes", "(Tmax + Tmin)/2", XAVIER), ("mean_compensated", "Compensada operacional", MODEL)):
        part = table[table.method == method].sort_values("year")
        ax.plot(part.year, part.bias, marker="o", color=color, lw=2, label=label)
        for year, bias in zip(part.year, part.bias):
            ax.text(year, bias + 0.04, f"{bias:+.2f}", ha="center", fontsize=8.5)
    ax.axhline(0, color="#888888", lw=0.8)
    ax.set_xticks(sorted(table.year.unique()))
    ax.set_ylabel("Viés contra a média de 24 h (°C)")
    ax.set_ylim(-0.2, 1.05)
    ax.set_title("C11: diferença entre definições de temperatura média, INMET 2008-2024", fontsize=11)
    ax.legend(frameon=False, fontsize=9)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    fig.text(0.5, 0.01, "Meses com ≥ 80% de dias completos em estações automáticas. Entre estações, o desvio da média de extremos "
             "vai de +0,1 a +1,6 °C.", ha="center", fontsize=8.5)
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    fig.savefig(figures / "c11_multianual.png", dpi=160)
    plt.close(fig)


def rain_methods(figures):
    base = mean_rmse("chuva_metodos_2graus.csv", "scope", "monthly")
    gwr = mean_rmse("chuva_M3_2graus_30m_base.csv", "scope", "monthly")
    c7 = pd.read_csv(safe_path(f"{TABLES}/chuva_c7_c8_2graus.csv"))
    per_month = c7[(c7.scope == "monthly") & (c7.method == "M5_per_month_100pct")].rmse.mean()
    names = [("CHIRPS", base["M0_chirps"], REF), ("LightGBM, um modelo por mês", per_month, MODEL),
             ("Random forest, direta", base["M4_direct"], MODEL), ("Híbrido (linear + LightGBM)", base["M6_correction"], MODEL),
             ("LightGBM, correção, harmônicos", base["M5_correction"], MODEL), ("LightGBM, direta", base["M5_direct"], MODEL),
             ("Random forest, correção", base["M4_correction"], MODEL), ("GWR (M3)", gwr["M3_correction"], MODEL),
             ("CHELSA", base["M0_chelsa"], REF), ("Regressão linear", base["M2_correction"], MODEL), ("ERA5-Land", base["M0_era5"], REF)]
    fig, ax = plt.subplots(figsize=(9, 5.2))
    barh(ax, [v for _, v, _ in names], [n for n, _, _ in names], [c for _, _, c in names], "mm", "Chuva 1991-2020: todos os métodos (1.878 estações)")
    fig.text(0.5, 0.01, "Verde: métodos testados; azul: grades. O CHIRPS usa pluviômetros na calibração; independência não comprovada.",
             ha="center", fontsize=8.5)
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    fig.savefig(figures / "chuva_metodos_completo_2graus.png", dpi=160)
    plt.close(fig)


def main():
    figures = safe_path("resultados/figuras")
    c15(figures)
    coverage(figures)
    c11(figures)
    rain_methods(figures)
    print("figuras: c15_mx_completo.png, incerteza_cobertura.png, c11_multianual.png, chuva_metodos_completo_2graus.png")


if __name__ == "__main__":
    main()
