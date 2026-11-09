"""Extrai séries mensais de três bases nas estações de desenvolvimento (C1/C12).

Somente leitura remota. Conserva pixels mascarados como ausentes, sem preencher
litoral, reamostrar uma grade fina ou consultar respostas do teste reservado.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from codigo.dados_temperatura import ROOT, safe_path
from codigo.modelos import prepare, reserve_test

SOURCES = {
    "xavier": "projects/ee-alexandrexavier/assets/BR-DWGD_Monthly",
    "era5": "ECMWF/ERA5_LAND/MONTHLY_AGGR",
    "terraclimate": "IDAHO_EPSCOR/TERRACLIMATE",
}
SOURCE_BANDS = {"xavier": ["Tmax", "Tmin"], "era5": ["temperature_2m"],
                "terraclimate": ["tmmx", "tmmn"]}
MONTHS = pd.period_range("1991-01", "2020-12", freq="M")


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def validate_calendar(timestamps):
    periods = pd.to_datetime(timestamps, unit="ms", utc=True).tz_localize(None).to_period("M")
    if not periods.equals(MONTHS):
        raise ValueError("A base deve conter exatamente os 360 meses ordenados de 1991–2020.")
    return [f"m{p.year}_{p.month:02d}" for p in periods]


def decode_batch(features, station_ids, bands, source):
    properties = [f["properties"] for f in features]
    ids = [p.get("station_id") for p in properties]
    if len(ids) != len(set(ids)) or set(ids) != set(station_ids):
        raise ValueError("Extração perdeu, duplicou ou acrescentou estações.")
    if len(bands) != len(MONTHS):
        raise ValueError("Número de meses divergente.")
    records = []
    for props in properties:
        for band, period in zip(bands, MONTHS):
            value = props.get(band)
            # Propriedade omitida/null indica pixel mascarado; nunca converter em zero.
            value = np.nan if value is None else float(value)
            if not np.isnan(value) and (not np.isfinite(value) or not -50 <= value <= 60):
                raise ValueError(f"{source}: temperatura incompatível com °C; revisar escala/offset.")
            records.append({"station_id": props["station_id"], "year": period.year,
                            "month": period.month, "source": source, "grid_c": value})
    return pd.DataFrame(records)


def temperature_image(image, source):
    import ee
    if source == "era5":
        result = image.select("temperature_2m").subtract(273.15)
    elif source == "terraclimate":
        result = image.select("tmmx").add(image.select("tmmn")).multiply(0.05)
    elif source == "xavier":
        # A coleção do autor usa multiplicador E offset por banda/imagem.
        def scaled(band):
            return image.select(band).multiply(ee.Number(image.get(f"BAND_{band}_MULT"))).add(
                ee.Number(image.get(f"BAND_{band}_ADD")))
        result = scaled("Tmax").add(scaled("Tmin")).divide(2)
    else:
        raise ValueError(f"Base desconhecida: {source}")
    return result.rename("temperature_c").copyProperties(image, ["system:time_start", "system:index"])


def main():
    import ee
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project")
    parser.add_argument("--batch-size", type=int, default=12)
    args = parser.parse_args()
    if not 1 <= args.batch_size <= 20:
        parser.error("Usar lotes de 1 a 20 estações.")
    source_file = safe_path("dados/processados/normais_covariaveis.csv")
    data = prepare(pd.read_csv(source_file, dtype={"station_id": str}))
    held = reserve_test(data)
    stations = data.loc[~held, ["station_id", "latitude", "longitude"]].drop_duplicates("station_id")
    credentials = ee.data.get_persistent_credentials()
    project = args.project or credentials.quota_project_id
    if not project:
        raise ValueError("Informe --project; credencial sem quota_project_id.")
    ee.Initialize(credentials=credentials, project=project)
    ee.data.setDeadline(60000)
    ee.data.setMaxRetries(1)
    outputs, metadata = [], {}
    for name, asset in SOURCES.items():
        collection = (ee.ImageCollection(asset).filterDate("1991-01-01", "2021-01-01")
                      .sort("system:time_start"))
        dates = collection.aggregate_array("system:time_start").getInfo()
        bands = validate_calendar(dates)
        first = ee.Image(collection.first()).select(SOURCE_BANDS[name])
        if name == "xavier":
            for band in SOURCE_BANDS[name]:
                for suffix in ("MULT", "ADD"):
                    key = f"BAND_{band}_{suffix}"
                    if collection.aggregate_count(key).getInfo() != len(MONTHS):
                        raise ValueError(f"Xavier: metadado {key} ausente em algum mês.")
        settings = {
            "asset": ee.data.getAsset(asset), "first_image": first.getInfo(),
            "timestamps": dates, "input_sha256": sha256(source_file),
            "script_sha256": sha256(__file__), "stations": stations.to_dict("records"),
            "batch_size": args.batch_size,
            "sampling": "first at native projection and transform; no focal fill or resampling",
        }
        fingerprint = hashlib.sha256(json.dumps(settings, sort_keys=True).encode()).hexdigest()
        cache = safe_path(ROOT / ".local/bases_gee" / fingerprint[:16])
        cache.mkdir(parents=True, exist_ok=True)
        stack = collection.map(lambda image: temperature_image(image, name)).toBands().rename(bands)
        native_grid = settings["first_image"]["bands"][0]
        for offset in range(0, len(stations), args.batch_size):
            batch = stations.iloc[offset:offset + args.batch_size]
            checkpoint = safe_path(cache / f"lote_{offset:04d}.json")
            if checkpoint.exists():
                features = json.loads(checkpoint.read_text(encoding="utf-8"))
            else:
                points = ee.FeatureCollection([
                    ee.Feature(ee.Geometry.Point([r.longitude, r.latitude]), {"station_id": r.station_id})
                    for r in batch.itertuples(index=False)
                ])
                query = stack.reduceRegions(collection=points, reducer=ee.Reducer.first(),
                                            crs=native_grid["crs"],
                                            crsTransform=native_grid["crs_transform"], tileScale=2)
                features = query.getInfo()["features"]
                # Validar antes de aceitar o checkpoint.
                decode_batch(features, batch.station_id, bands, name)
                checkpoint.write_text(json.dumps(features, ensure_ascii=False), encoding="utf-8")
            outputs.append(decode_batch(features, batch.station_id, bands, name))
            print(f"{name}: {min(offset + args.batch_size, len(stations))}/{len(stations)} estações", flush=True)
        metadata[name] = settings
    frame = pd.concat(outputs, ignore_index=True).sort_values(["source", "station_id", "year", "month"])
    output = safe_path("dados/bases/bases_mensais.csv")
    output.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(output, index=False, float_format="%.10g")
    manifest = {
        "created_utc": datetime.now(timezone.utc).isoformat(), "project": project,
        "earthengine_api": ee.__version__, "output_sha256": sha256(output),
        "input_sha256": sha256(source_file), "sources": metadata,
        "n_development_stations": len(stations), "reserved_stations_not_sampled": data.loc[held].station_id.nunique(),
        "missing_by_source": frame.groupby("source").grid_c.apply(lambda x: int(x.isna().sum())).to_dict(),
        "units": "degC", "period": "1991-2020",
    }
    safe_path(output.with_suffix(".manifesto.json")).write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({k: manifest[k] for k in ("n_development_stations", "missing_by_source")}), flush=True)


if __name__ == "__main__":
    main()
