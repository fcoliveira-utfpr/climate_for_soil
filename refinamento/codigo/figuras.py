"""Figuras dos resultados agregados e da prévia local, sem publicar estações."""
from pathlib import Path
import os

ROOT = Path(__file__).resolve().parents[1]
os.environ["MPLCONFIGDIR"] = str(ROOT / ".local" / "matplotlib")

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import rasterio

from codigo.mapa_piloto import month_weights


def comparison(output):
    sources = [("direct", "Previsão direta"), ("correction", "Correção da grade")]
    names = ["M0_chelsa", "M1_lapse_fixo", "M2_linear", "M4_random_forest", "M5_lightgbm", "MX_mensal_referencia"]
    labels = ["CHELSA", "Gradiente fixo", "Regressão linear", "Random forest", "LightGBM", "MX mensal"]
    fig, ax = plt.subplots(figsize=(9, 5.2), layout="constrained")
    for index, (formulation, label) in enumerate(sources):
        frame = pd.read_csv(ROOT / "resultados" / "tabelas" / f"modelos_exploratorios_2graus_grade_{formulation}.csv")
        values = frame[frame.scope.eq("global")].groupby("method").rmse.mean().reindex(names)
        bars = ax.bar(np.arange(len(names)) + (index - 0.5) * 0.36, values, 0.36,
                      label=label, color=["#6a9ab0", "#24564b"][index])
        ax.bar_label(bars, fmt="%.3f", fontsize=8, padding=3)
    ax.set(xticks=np.arange(len(names)), xticklabels=labels, ylabel="RMSE médio (°C)", ylim=(0, 1.0),
           title="Temperatura mensal 1991–2020 — ensaio exploratório")
    ax.tick_params(axis="x", labelsize=9)
    ax.spines[["right", "top"]].set_visible(False)
    ax.legend(frameon=False, loc="upper left")
    fig.supxlabel("102 estações de desenvolvimento · blocos de 2° · 5 dobras × 3 repetições\n"
                  "18 estações reservadas sem avaliação; definições térmicas e anos observados ainda em revisão.", fontsize=9)
    fig.savefig(output / "comparacao_modelos.png", dpi=180)
    plt.close(fig)


def pilot(output):
    folder = ROOT / "dados" / "piloto"
    stem = "anual_curitiba_M5_lightgbm_correction.tiff"
    with rasterio.open(folder / f"temperatura_media_30m_{stem}") as source:
        predicted = source.read(1, masked=True) * source.scales[0] + source.offsets[0]
        bounds = source.bounds
    with rasterio.open(folder / "covariaveis.tiff") as source:
        baseline = np.tensordot(month_weights(), source.read()[:12], axes=(0, 0))
    with rasterio.open(folder / f"dispersao_modelos_30m_{stem}") as source:
        spread = source.read(1, masked=True)
    extent = [bounds.left / 1000, bounds.right / 1000, bounds.bottom / 1000, bounds.top / 1000]
    vmin, vmax = min(baseline.min(), predicted.min()), max(baseline.max(), predicted.max())
    delta = predicted - baseline
    limit = np.max(np.abs(delta))
    fig, axes = plt.subplots(2, 2, figsize=(10, 9), layout="constrained")
    panels = [(baseline, "CHELSA na grade do piloto", "°C", "YlOrRd", vmin, vmax),
              (predicted, "LightGBM — correção do CHELSA", "°C", "YlOrRd", vmin, vmax),
              (delta, "Correção: modelo menos CHELSA", "°C", "RdBu_r", -limit, limit),
              (spread, "Dispersão entre 5 modelos de treino", "°C", "viridis", 0, spread.max())]
    for ax, (values, title, unit, cmap, lo, hi) in zip(axes.flat, panels):
        display = ax.imshow(values, extent=extent, origin="upper", cmap=cmap, vmin=lo, vmax=hi,
                            interpolation="nearest")
        ax.set(title=title, xlabel="Leste UTM (km)", ylabel="Norte UTM (km)")
        ax.ticklabel_format(style="plain", useOffset=False)
        fig.colorbar(display, ax=ax, shrink=0.82, label=unit)
    fig.suptitle("Curitiba · temperatura anual 1991–2020\nPrévia experimental · 12 × 12 km · pixel de 30 m", fontsize=14)
    fig.supxlabel("WGS84 / UTM 22S · sem validação do detalhe em 30 m\n"
                  "Dispersão entre modelos não é intervalo de previsão. Fontes: CHELSA e Copernicus DEM.", fontsize=9)
    fig.savefig(output / "previa_curitiba_anual.png", dpi=180)
    plt.close(fig)


def main():
    output = ROOT / "resultados" / "figuras"
    output.mkdir(parents=True, exist_ok=True)
    comparison(output)
    pilot(output)
    print("Figuras salvas em resultados/figuras.")


if __name__ == "__main__":
    main()
