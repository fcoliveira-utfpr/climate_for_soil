"""Figuras dos mapas do Paraná (lidos em resolução reduzida, só para visualização).

Uso, de dentro de refinamento/:  python -B -m codigo.figuras_parana
"""
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import rasterio
from rasterio.enums import Resampling

from codigo.dados_temperatura import safe_path

SOURCE = "dados/parana/saida"
FACTOR = 12  # 30 m × 12 = 360 m na figura


def read(name, band):
    with rasterio.open(safe_path(f"{SOURCE}/parana_{name}_30m.tif")) as data:
        shape = (data.height // FACTOR, data.width // FACTOR)
        values = data.read(band, out_shape=shape, resampling=Resampling.average,
                           masked=True).astype(float)
        scale = data.scales[band - 1]
        extent = (data.bounds.left / 1000, data.bounds.right / 1000, data.bounds.bottom / 1000, data.bounds.top / 1000)
    return values * scale, extent


def panel(ax, values, extent, title, cmap, unit, vmin=None, vmax=None):
    image = ax.imshow(values, extent=extent, cmap=cmap, vmin=vmin, vmax=vmax, interpolation="nearest")
    ax.set_title(title, fontsize=11)
    ax.set_xticks([])
    ax.set_yticks([])
    plt.colorbar(image, ax=ax, fraction=0.035, pad=0.02, label=unit)


def main():
    figures = safe_path("resultados/figuras")
    t, extent = read("temperatura_media", 13)
    p, _ = read("chuva_media", 13)
    fig, axes = plt.subplots(1, 2, figsize=(15, 5.6))
    panel(axes[0], t, extent, "Temperatura média anual 1991-2020", "RdYlBu_r", "°C",
          np.nanpercentile(t.compressed(), 1), np.nanpercentile(t.compressed(), 99))
    panel(axes[1], p, extent, "Chuva anual 1991-2020", "Blues", "mm",
          np.nanpercentile(p.compressed(), 1), np.nanpercentile(p.compressed(), 99))
    fig.suptitle("Paraná, pixel de 30 m (figura reamostrada a 360 m) · prévia experimental", fontsize=12)
    fig.text(0.5, 0.01, "UTM 22S. LightGBM corrigindo o CHELSA (temperatura) e um LightGBM por mês (chuva); sem interpolação "
             "de estações. Fontes: CHELSA, Copernicus DEM, Xavier et al. (2022).", ha="center", fontsize=8.5)
    fig.tight_layout(rect=(0, 0.03, 1, 0.95))
    fig.savefig(figures / "parana_anual.png", dpi=150)
    plt.close(fig)

    jan, _ = read("temperatura_media", 1)
    jul, _ = read("temperatura_media", 7)
    pjan, _ = read("chuva_media", 1)
    pjul, _ = read("chuva_media", 7)
    fig, axes = plt.subplots(2, 2, figsize=(14, 9.5))
    panel(axes[0, 0], jan, extent, "Temperatura de janeiro", "RdYlBu_r", "°C")
    panel(axes[0, 1], jul, extent, "Temperatura de julho", "RdYlBu_r", "°C")
    panel(axes[1, 0], pjan, extent, "Chuva de janeiro", "Blues", "mm")
    panel(axes[1, 1], pjul, extent, "Chuva de julho", "Blues", "mm")
    fig.suptitle("Paraná: verão e inverno, normal 1991-2020 (prévia experimental)", fontsize=12)
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    fig.savefig(figures / "parana_janeiro_julho.png", dpi=130)
    plt.close(fig)

    ti, _ = read("temperatura_incerteza90", 1)
    pi, _ = read("chuva_incerteza90", 1)
    ta, _ = read("temperatura_fora_aoa", 13)
    pa, _ = read("chuva_fora_aoa", 13)
    fig, axes = plt.subplots(2, 2, figsize=(14, 9.5))
    panel(axes[0, 0], ti, extent, "Temperatura: meia-largura do intervalo de 90% (janeiro)", "Oranges", "°C")
    panel(axes[0, 1], pi, extent, "Chuva: meia-largura do intervalo de 90% (janeiro)", "Oranges", "mm")
    panel(axes[1, 0], ta, extent, "Temperatura: fração fora da área de aplicabilidade (algum mês)", "Reds", "fração", 0, 1)
    panel(axes[1, 1], pa, extent, "Chuva: fração fora da área de aplicabilidade (algum mês)", "Reds", "fração", 0, 1)
    fig.suptitle("Paraná: incerteza calibrada e área de aplicabilidade", fontsize=12)
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    fig.savefig(figures / "parana_incerteza_aoa.png", dpi=130)
    plt.close(fig)
    print("figuras: parana_anual.png, parana_janeiro_julho.png, parana_incerteza_aoa.png")


if __name__ == "__main__":
    main()
