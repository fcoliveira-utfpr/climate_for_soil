"""Empacota os mapas do Paraná para o upload manual no GEE: um GeoTIFF int16 de 39 bandas por variável.

Lê as seis camadas montadas por mapa_parana.py (dados/parana/saida/) e grava, por variável:
  bandas 1-13   média (temperatura em °C × 100; chuva em mm), meses 01-12 e anual
  bandas 14-26  meia-largura do intervalo de 90% (mesma unidade e escala da média)
  bandas 27-39  1 = fora da área de aplicabilidade
Nodata único −32768 em todas as bandas (o GEE aplica um só valor no upload). Se um arquivo passar
de 9,5 GB, é dividido em partes leste/oeste com divisa em múltiplo de 512 pixels, para subir como
uma imagem só pela opção "Add another file" do Code Editor.

Uso, de dentro de refinamento/:  python -B -m codigo.pacote_gee_parana
"""
import json

import numpy as np
import rasterio
from rasterio.windows import Window

from codigo.dados_temperatura import safe_path
from codigo.grade_brasil import digest

SOURCE = "dados/parana/saida"
TARGET = "dados/gee"
NODATA = -32768
LIMIT_BYTES = 9.5e9
LABELS = [f"{m:02d}" for m in range(1, 13)] + ["anual"]


def write_part(variable, sources, col0, col1, name):
    with rasterio.open(sources[0]) as ref:
        profile = {"driver": "GTiff", "width": col1 - col0, "height": ref.height, "count": 39, "dtype": "int16",
                   "nodata": NODATA, "crs": ref.crs, "transform": ref.window_transform(Window(col0, 0, col1 - col0, ref.height)),
                   "tiled": True, "blockxsize": 512, "blockysize": 512, "compress": "DEFLATE", "predictor": 2, "BIGTIFF": "YES"}
    path = safe_path(f"{TARGET}/{name}")
    names = [f"{kind}_{label}" for kind in ("media", "inc90", "aoa") for label in LABELS]
    with rasterio.open(path, "w", **profile) as out:
        for index, label in enumerate(names, 1):
            out.set_band_description(index, label)
        handles = [rasterio.open(s) for s in sources]
        try:
            for row in range(0, profile["height"], 512):
                for col in range(col0, col1, 512):
                    window = Window(col, row, min(512, col1 - col), min(512, profile["height"] - row))
                    blocks = []
                    for handle in handles:
                        data = handle.read(window=window)
                        wide = data.astype(np.int32)  # sem isso o NumPy 2 converte −32768 para 0 em bandas uint8
                        blocks.append(np.where(wide == handle.nodata, NODATA, wide).astype(np.int16))
                    out.write(np.concatenate(blocks), window=Window(col - col0, row, window.width, window.height))
        finally:
            for handle in handles:
                handle.close()
        out.update_tags(experimental="true", variable=variable, band_order=",".join(names),
                        scale=("0.01 degC for media and inc90" if variable == "temperatura" else "1 mm for media and inc90"),
                        nodata=str(NODATA))
    return path


def verify(sources, parts, n=400, seed=7):
    """Confere pixels sorteados (dentro e fora do estado) entre o pacote e as camadas de origem."""
    rng = np.random.default_rng(seed)
    handles = [rasterio.open(s) for s in sources]
    packs = [rasterio.open(p) for p in parts]
    try:
        offset = 0
        for pack in packs:
            for _ in range(n // len(packs)):
                r, c = int(rng.integers(0, pack.height)), int(rng.integers(0, pack.width))
                window = Window(c + offset, r, 1, 1)
                expected = np.concatenate([np.where((v := h.read(window=window)[:, 0, 0].astype(np.int64)) == h.nodata, NODATA, v)
                                           for h in handles])
                got = pack.read(window=Window(c, r, 1, 1))[:, 0, 0].astype(np.int64)
                if not np.array_equal(expected, got):
                    raise ValueError(f"Pacote diverge da origem no pixel ({r}, {c + offset}).")
            offset += pack.width
    finally:
        for h in handles + packs:
            h.close()


def main():
    report = {}
    for variable in ("temperatura", "chuva"):
        sources = [safe_path(f"{SOURCE}/parana_{variable}_{kind}_30m.tif") for kind in ("media", "incerteza90", "fora_aoa")]
        with rasterio.open(sources[0]) as ref:
            width = ref.width
        path = write_part(variable, sources, 0, width, f"parana_{variable}_30m.tif")
        parts = [path]
        if path.stat().st_size > LIMIT_BYTES:
            path.unlink()
            middle = (width // 2 // 512) * 512
            parts = [write_part(variable, sources, 0, middle, f"parana_{variable}_30m_oeste.tif"),
                     write_part(variable, sources, middle, width, f"parana_{variable}_30m_leste.tif")]
        verify(sources, parts)
        report[variable] = [{"file": p.name, "bytes": p.stat().st_size, "sha256": digest(p)} for p in parts]
        print(variable, [(p.name, round(p.stat().st_size / 1e9, 2)) for p in parts], flush=True)
    safe_path(f"{TARGET}/parana_pacote.json").write_text(json.dumps(report, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
