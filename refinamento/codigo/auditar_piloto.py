"""Confere os GeoTIFFs efetivamente gravados; publica somente resumo agregado."""
import json

import numpy as np
import pandas as pd
import rasterio

from codigo.mapa_piloto import PILOT, CRS, SIZE, month_weights, pilot_transform, sha256
from codigo.modelos import ROOT, local_path


def require(condition, message):
    if not condition:
        raise ValueError(message)


def main():
    manifest_path = local_path(PILOT / "manifesto_curitiba_M5_lightgbm_correction.json")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    outputs = manifest["outputs"]
    require(len(outputs) == 39, "O piloto deve conter 39 produtos.")
    train = set(manifest["training"]["development_stations"])
    held = set(manifest["training"]["reserved_unscored_stations"])
    require(len(train) == 102 and len(held) == 18 and train.isdisjoint(held), "Partição de treino/teste divergente.")
    records, arrays = [], {}
    for filename, digest in outputs.items():
        path = local_path(PILOT / filename)
        require(sha256(path) == digest, f"Hash divergente: {filename}")
        temperature = filename.startswith("temperatura_media")
        flag = filename.startswith("fora_faixa_treino")
        dtype, nodata = ("int16", -32768) if temperature else (("uint8", 255) if flag else ("float32", -9999))
        with rasterio.open(path) as raster:
            require(raster.crs.to_string() == CRS and raster.transform == pilot_transform(), f"Grade divergente: {filename}")
            require((raster.count, raster.width, raster.height) == (1, SIZE, SIZE), f"Dimensões divergentes: {filename}")
            require(raster.dtypes == (dtype,) and raster.nodata == nodata, f"Tipo/nodata divergente: {filename}")
            require(raster.compression.value.upper() == "DEFLATE", f"Compressão divergente: {filename}")
            require(raster.scales == ((0.01,) if temperature else (1.0,)) and raster.offsets == (0.0,), f"Escala divergente: {filename}")
            require(raster.tags().get("experimental") == "true", f"Estado experimental ausente: {filename}")
            values = raster.read(1, masked=True)
            require(not np.ma.getmaskarray(values).any(), f"Pixel ausente: {filename}")
            values = np.asarray(values, dtype=float) * raster.scales[0]
        require(np.isfinite(values).all(), f"Pixel não finito: {filename}")
        if flag:
            require(np.isin(values, [0, 1]).all(), f"Flag inválida: {filename}")
        elif not temperature:
            require((values >= 0).all(), f"Dispersão negativa: {filename}")
        arrays[filename] = values
        records.append({"file": filename, "pixels": values.size, "resolution_m": 30,
                        "crs": CRS, "min": values.min(), "max": values.max(), "mean": values.mean(),
                        "unit": "flag" if flag else "degC", "sha256": digest})
    suffix = "curitiba_M5_lightgbm_correction.tiff"
    monthly = np.stack([arrays[f"temperatura_media_30m_{month:02d}_{suffix}"] for month in range(1, 13)])
    expected = np.tensordot(month_weights(), monthly, axes=(0, 0))
    actual = arrays[f"temperatura_media_30m_anual_{suffix}"]
    maximum_error = float(np.max(np.abs(actual - expected)))
    require(maximum_error <= 0.01000001, "Anual difere dos meses além da quantização de 0,01°C.")
    flag_union = np.maximum.reduce([arrays[f"fora_faixa_treino_30m_{month:02d}_{suffix}"] for month in range(1, 13)])
    require(np.array_equal(flag_union, arrays[f"fora_faixa_treino_30m_anual_{suffix}"]), "Flag anual não é união das mensais.")
    output = local_path(ROOT / "resultados" / "tabelas" / "auditoria_piloto.csv")
    pd.DataFrame(records).to_csv(output, index=False)
    print(f"39 GeoTIFFs conferidos; erro máximo anual por quantização: {maximum_error:.6f} °C.")


if __name__ == "__main__":
    main()
