"""Junta os 39 GeoTIFFs do piloto de Curitiba numa imagem de 39 bandas para subir no GEE.

Confere o SHA256 de cada arquivo de dados/piloto/ contra o manifesto do piloto, converte a
temperatura de int16 x 0,01 para °C e grava dados/gee/piloto_curitiba_30m_39bandas.tif
(float32, DEFLATE, a mesma grade UTM 22S de 30 m), com um manifesto JSON ao lado.
Depois de gravar, relê o arquivo e confere banda a banda contra as fontes.

Não sobe nada no GEE: o upload e o compartilhamento são manuais, pelo Code Editor
(ver gee/visualizar_piloto.js e gee/descricao_piloto_curitiba.md).

Uso, de dentro de refinamento/:  python -B -m codigo.pacote_gee_piloto [--sobrescrever]
"""
import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import rasterio

ROOT = Path(__file__).resolve().parents[1]
PILOT = ROOT / "dados" / "piloto"
MANIFEST = PILOT / "manifesto_curitiba_M5_lightgbm_correction.json"
OUT_DIR = ROOT / "dados" / "gee"
OUT = OUT_DIR / "piloto_curitiba_30m_39bandas.tif"
OUT_MANIFEST = OUT_DIR / "piloto_curitiba_30m_39bandas.manifesto.json"
SUFFIX = "_curitiba_M5_lightgbm_correction.tiff"
PERIODS = [f"{month:02d}" for month in range(1, 13)] + ["anual"]
# (prefixo do arquivo, prefixo da banda, unidade, fator para a unidade física, significado)
LAYERS = [
    ("temperatura_media_30m", "temp", "degC", 0.01, "temperatura média do ar, (Tmax + Tmin)/2, normal 1991-2020"),
    ("dispersao_modelos_30m", "disp", "degC", 1.0, "desvio padrão entre 5 modelos; não é intervalo de previsão"),
    ("fora_faixa_treino_30m", "fora", "flag", 1.0, "1 = alguma covariável fora do mínimo/máximo do treino"),
]
NODATA = -9999.0


def sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def read_sources():
    """Lê e confere as 39 fontes; devolve bandas em unidade física, nomes, metadados e grade."""
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    expected = manifest["outputs"]
    if len(expected) != 39:
        raise ValueError("O manifesto do piloto deve listar 39 arquivos.")
    bands, records, grid = [], [], None
    for file_prefix, band_prefix, unit, factor, meaning in LAYERS:
        for period in PERIODS:
            filename = f"{file_prefix}_{period}{SUFFIX}"
            path = PILOT / filename
            digest = sha256(path)
            if expected.get(filename) != digest:
                raise ValueError(f"SHA256 diferente do manifesto do piloto: {filename}")
            with rasterio.open(path) as source:
                current = (source.crs, source.transform, source.width, source.height)
                if grid is None:
                    grid = current
                elif current != grid:
                    raise ValueError(f"Grade diferente das demais: {filename}")
                values = source.read(1, masked=True)
            if np.ma.getmaskarray(values).any():
                raise ValueError(f"O piloto não deveria ter pixel vazio: {filename}")
            physical = (values.astype("float64") * factor).astype("float32")
            bands.append(np.ma.filled(physical, NODATA))
            records.append({"band": len(records) + 1, "name": f"{band_prefix}_{period}", "unit": unit,
                            "meaning": meaning, "source": filename, "source_sha256": digest,
                            "min": round(float(physical.min()), 4), "max": round(float(physical.max()), 4)})
    return bands, records, grid, manifest


def write_package(bands, records, grid, manifest):
    crs, transform, width, height = grid
    profile = {"driver": "GTiff", "width": width, "height": height, "count": len(bands), "dtype": "float32",
               "crs": crs, "transform": transform, "nodata": NODATA, "compress": "deflate",
               "tiled": True, "blockxsize": 256, "blockysize": 256, "interleave": "band"}
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with rasterio.open(OUT, "w", **profile) as target:
        for index, (values, record) in enumerate(zip(bands, records), start=1):
            target.write(values, index)
            target.set_band_description(index, record["name"])
            target.update_tags(index, unit=record["unit"], source=record["source"])
        target.update_tags(
            experimental="true",
            status="previa experimental, nao validada",
            region="Curitiba, recorte de 12 x 12 km",
            method="M5 LightGBM corrigindo o CHELSA",
            period="1991-2020",
            band_order=",".join(record["name"] for record in records),
            attribution=manifest["attribution"],
        )


def verify_package(bands, records):
    with rasterio.open(OUT) as package:
        if package.count != len(bands):
            raise ValueError("O pacote não tem 39 bandas.")
        for index, (values, record) in enumerate(zip(bands, records), start=1):
            if package.descriptions[index - 1] != record["name"]:
                raise ValueError(f"Nome divergente na banda {index}.")
            if not np.array_equal(package.read(index), values):
                raise ValueError(f"Valores divergentes na banda {index} ({record['name']}).")


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--sobrescrever", action="store_true", help="regrava o pacote se ele já existir")
    args = parser.parse_args()
    if OUT.exists() and not args.sobrescrever:
        raise SystemExit(f"{OUT.relative_to(ROOT)} já existe; use --sobrescrever para gravar de novo.")
    bands, records, grid, manifest = read_sources()
    write_package(bands, records, grid, manifest)
    verify_package(bands, records)
    summary = {
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "status": "experimental_preview_not_validated_product",
        "output": OUT.name,
        "output_sha256": sha256(OUT),
        "output_bytes": OUT.stat().st_size,
        "dtype": "float32",
        "nodata": NODATA,
        "crs": grid[0].to_string(),
        "pixel_m": 30,
        "width": grid[2],
        "height": grid[3],
        "pilot_manifest_sha256": sha256(MANIFEST),
        "script_sha256": sha256(Path(__file__)),
        "bands": records,
        "gee_upload": "manual pelo Code Editor; nomes das bandas aplicados por gee/visualizar_piloto.js",
        "attribution": manifest["attribution"],
    }
    OUT_MANIFEST.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"{OUT.relative_to(ROOT)}: {len(bands)} bandas, {summary['output_bytes'] / 1e6:.1f} MB, conferido banda a banda.")
    for record in records:
        print(f"  b{record['band']:<3} {record['name']:<11} {record['min']:>9.4f} {record['max']:>9.4f} {record['unit']}")


if __name__ == "__main__":
    main()
