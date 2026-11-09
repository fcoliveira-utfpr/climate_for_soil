"""GeoTIFF experimental de temperatura com pixels de 30 m em CRS métrico.

O raster guarda inteiros em centésimos de °C. No GEE, aplicar explicitamente
``image.multiply(0.01)`` após a ingestão; não presumir aplicação dos metadados.
Este módulo não treina modelos, publica assets nem produz COG.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import rasterio
from affine import Affine
from rasterio.crs import CRS


ROOT = Path(__file__).resolve().parents[1]
NODATA = -32768
SCALE = 0.01


def _local_path(path: str | Path) -> Path:
    result = Path(path).resolve()
    if not result.is_relative_to(ROOT):
        raise ValueError("O arquivo deve permanecer dentro de refinamento/.")
    return result


def validate_grid(transform: Affine, crs: str | CRS) -> CRS:
    """Valida CRS métrico e grade norte-acima de 30 m com origem comum."""
    parsed_crs = CRS.from_user_input(crs)
    if not parsed_crs.is_projected:
        raise ValueError("Pixels de 30 m exigem CRS projetado; EPSG:4326 usa graus.")
    unit, factor = parsed_crs.linear_units_factor
    if unit.lower() not in {"metre", "meter", "metres", "meters", "m"} or not np.isclose(
        factor, 1.0, rtol=0, atol=1e-12
    ):
        raise ValueError("O CRS projetado deve usar metros.")
    if not isinstance(transform, Affine):
        raise TypeError("transform deve ser affine.Affine.")
    if not np.isfinite(tuple(transform)).all():
        raise ValueError("A transformação deve conter apenas valores finitos.")
    if not np.allclose(
        [transform.a, transform.b, transform.d, transform.e],
        [30.0, 0.0, 0.0, -30.0], rtol=0, atol=1e-9,
    ):
        raise ValueError("A grade deve ter pixels de 30 x 30 m, sem rotação e norte acima.")
    origin = np.array([transform.c, transform.f]) / 30.0
    if not np.allclose(origin, np.rint(origin), rtol=0, atol=1e-9):
        raise ValueError("A origem deve ser múltipla de 30 m nos dois eixos.")
    return parsed_crs


def write_temperature_geotiff(
    path: str | Path,
    values: np.ndarray,
    transform: Affine,
    crs: str | CRS,
    *,
    period: str,
    method: str,
    experimental: bool = True,
) -> Path:
    """Grava um tile 2D em °C; NaN, infinito e pixels mascarados viram nodata.

    Não sobrescreve arquivos existentes. Valores que não cabem em int16 após
    multiplicar por 100 são rejeitados; -32768 fica reservado para nodata.
    Os 30 m são unidades da projeção, sujeitos à distorção do CRS escolhido.
    A projeção deve ser adequada à região (por exemplo, sua zona UTM).
    """
    output = _local_path(path)
    if output.suffix.lower() not in {".tif", ".tiff"}:
        raise ValueError("Use extensão .tif ou .tiff.")
    if output.exists():
        raise FileExistsError(f"O arquivo já existe: {output}")
    parsed_crs = validate_grid(transform, crs)
    if not isinstance(period, str) or not period.strip():
        raise ValueError("Informe o período representado pelo tile.")
    if not isinstance(method, str) or not method.strip():
        raise ValueError("Informe o método que gerou o tile.")
    array = np.ma.asarray(values, dtype=np.float64)
    if array.ndim != 2 or 0 in array.shape:
        raise ValueError("values deve ser uma matriz 2D não vazia.")
    valid = ~np.ma.getmaskarray(array) & np.isfinite(array.data)
    encoded = np.full(array.shape, NODATA, dtype=np.int16)
    # Conferir antes da multiplicação evita overflow em entradas muito grandes.
    if np.any(np.abs(array.data[valid]) > 327.67):
        raise ValueError("Temperatura fora da faixa int16 reservada para dados.")
    encoded[valid] = np.rint(array.data[valid] / SCALE).astype(np.int16)
    output.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(
        output, "w", driver="GTiff", height=array.shape[0], width=array.shape[1],
        count=1, dtype="int16", crs=parsed_crs, transform=transform,
        nodata=NODATA, compress="DEFLATE", predictor=2, tiled=True,
        blockxsize=256, blockysize=256,
    ) as target:
        target.write(encoded, 1)
        target.scales = (SCALE,)
        target.offsets = (0.0,)
        target.set_band_description(1, "temperatura_media")
        target.set_band_unit(1, "degC")
        metadata = {
            "units": "degC", "scale_factor": SCALE, "add_offset": 0,
            "period": period.strip(), "method": method.strip(),
            "experimental": str(bool(experimental)).lower(),
            "grid_resolution_m": 30, "grid_origin": "0,0",
            "cog": "false", "gee_pyramiding_policy": "mean",
        }
        target.update_tags(**metadata)
        target.update_tags(1, **metadata)
    return output


def inspect_geotiff(path: str | Path) -> dict:
    """Lê metadados e valida a grade sem carregar os pixels na memória."""
    with rasterio.open(_local_path(path)) as source:
        validate_grid(source.transform, source.crs)
        return {
            "path": str(source.name), "crs": source.crs.to_string(),
            "width": source.width, "height": source.height, "count": source.count,
            "dtype": list(source.dtypes), "resolution": list(source.res),
            "transform": list(source.transform)[:6], "nodata": source.nodata,
            "scales": list(source.scales), "offsets": list(source.offsets),
            "tags": source.tags(),
        }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Inspeciona um GeoTIFF de grade métrica de 30 m.")
    parser.add_argument("path", type=Path)
    print(json.dumps(inspect_geotiff(parser.parse_args().path), indent=2, ensure_ascii=False))
