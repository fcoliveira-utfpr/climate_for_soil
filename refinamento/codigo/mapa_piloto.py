"""Prévia experimental de 12 km em Curitiba; não publica assets nem avalia teste.

As temperaturas não constituem produto validado. SD entre modelos das dobras
mede sensibilidade ao treino, não intervalo de previsão. A flag min/max não é
uma área de aplicabilidade multivariada formal.
"""
from __future__ import annotations

import argparse
import calendar
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

from affine import Affine
import numpy as np
import pandas as pd
from pyproj import Transformer
import rasterio
import requests
from sklearn.base import clone
from sklearn.model_selection import GridSearchCV, GroupKFold

from codigo import covariaveis_gee, modelos
from codigo.geotiff import ROOT, validate_grid, write_temperature_geotiff

CRS = "EPSG:32722"
SIZE = 400
BANDS = [*covariaveis_gee.MONTH_BANDS, *covariaveis_gee.TERRAIN_BANDS]
PILOT = ROOT / "dados" / "piloto"
METHODS = ("M2_linear", "M4_random_forest", "M5_lightgbm")


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def pilot_transform():
    x, y = Transformer.from_crs("EPSG:4326", CRS, always_xy=True).transform(-49.27, -25.43)
    left = np.floor((x - SIZE * 15) / 30) * 30
    top = np.ceil((y + SIZE * 15) / 30) * 30
    return Affine(30, 0, float(left), 0, -30, float(top))


def month_weights():
    days = np.array([sum(calendar.monthrange(year, month)[1] for year in range(1991, 2021))
                     for month in range(1, 13)], dtype=float)
    return days / days.sum()


def validate_covariates(path, transform, size=SIZE):
    """Recusa máscara/falhas para que a prévia tenha cobertura integral explícita."""
    with rasterio.open(modelos.local_path(path)) as source:
        validate_grid(source.transform, source.crs)
        if source.crs != rasterio.crs.CRS.from_string(CRS) or source.transform != transform:
            raise ValueError("Covariáveis fora da projeção/grade solicitada.")
        if (source.width, source.height, source.count) != (size, size, len(BANDS)):
            raise ValueError("Dimensões ou quantidade de bandas das covariáveis incorretas.")
        descriptions = source.descriptions
        if any(descriptions) and tuple(descriptions) != tuple(BANDS):
            raise ValueError("Ordem das bandas das covariáveis divergente.")
        data = source.read(masked=True).astype(float).filled(np.nan)
    data[data == -9999] = np.nan
    if not np.isfinite(data).all():
        raise ValueError("Covariáveis com pixels ausentes; a prévia exige cobertura completa.")
    if not ((data[:12] >= -40) & (data[:12] <= 55)).all():
        raise ValueError("CHELSA fora da faixa plausível em °C; conferir escala.")
    if not ((data[-1] >= 0) & (data[-1] <= 90)).all():
        raise ValueError("Declividade fora da faixa 0–90 graus.")
    return data


def download_covariates(transform, station_manifest, project=None):
    """Consulta GEE de leitura. Não registra URL assinada ou credenciais."""
    import ee
    directory = modelos.local_path(PILOT)
    credentials = ee.data.get_persistent_credentials()
    project = project or credentials.quota_project_id
    if not project:
        raise ValueError("Informe --project: credencial sem projeto configurado.")
    ee.Initialize(credentials=credentials, project=project)
    ee.data.setDeadline(60000)
    transform_list = list(transform)[:6]
    settings = {
        "crs": CRS, "transform": transform_list, "width": SIZE, "height": SIZE,
        "bands": BANDS, "chelsa_asset": covariaveis_gee.CHELSA,
        "dem_collection": covariaveis_gee.DEM, "buffer_m": covariaveis_gee.BUFFER_M,
        "helper_sha256": sha256(covariaveis_gee.__file__),
        "station_manifest_sha256": sha256(station_manifest),
        "chelsa_metadata": ee.data.getAsset(covariaveis_gee.CHELSA),
        "dem_metadata": ee.data.getAsset(covariaveis_gee.DEM),
    }
    station_provenance = json.loads(station_manifest.read_text(encoding="utf-8"))
    for field in ("chelsa_metadata", "dem_metadata"):
        if settings[field] != station_provenance.get(field):
            raise ValueError("Fontes GEE mudaram desde a extração das estações; atualizar a extração.")
    directory.mkdir(parents=True, exist_ok=True)
    output = modelos.local_path(directory / "covariaveis.tiff")
    cache = modelos.local_path(directory / "covariaveis.manifesto.json")
    if output.exists() or cache.exists():
        if not output.exists() or not cache.exists():
            raise ValueError("Cache de covariáveis incompleto; revisar os arquivos locais.")
        stored = json.loads(cache.read_text(encoding="utf-8"))
        if stored.get("settings") != settings or stored.get("sha256") != sha256(output):
            raise ValueError("Cache de covariáveis incompatível com a grade/fontes atuais.")
        return validate_covariates(output, transform), stored
    left, top = transform.c, transform.f
    region = ee.Geometry.Rectangle(
        [left, top - SIZE * 30, left + SIZE * 30, top], proj=CRS, geodesic=False
    )
    image = covariaveis_gee.construir_imagens(region, CRS, transform_list).select(BANDS).toFloat().unmask(-9999)
    try:
        url = image.getDownloadURL({"format": "GEO_TIFF", "crs": CRS,
                                   "crs_transform": transform_list, "dimensions": [SIZE, SIZE]})
        with requests.get(url, timeout=(15, 60), stream=True) as response:
            response.raise_for_status()
            chunks, total = [], 0
            for chunk in response.iter_content(1024 * 1024):
                total += len(chunk)
                if total > 32 * 1024 * 1024:
                    raise ValueError("Download excedeu 32 MiB; revisar região/bandas.")
                chunks.append(chunk)
    except requests.RequestException:
        raise RuntimeError("Falha HTTP no download GEE; URL assinada omitida.") from None
    output.write_bytes(b"".join(chunks))
    data = validate_covariates(output, transform)
    stored = {"settings": settings, "sha256": sha256(output),
              "created_utc": datetime.now(timezone.utc).isoformat()}
    cache.write_text(json.dumps(stored, indent=2, ensure_ascii=False), encoding="utf-8")
    return data, stored


def fit_development(data, method, formulation):
    if method not in METHODS or formulation not in {"direct", "correction"}:
        raise ValueError("Método ou formulação inválido.")
    data = modelos.prepare(data)
    if "chelsa_c" not in data:
        raise ValueError("O piloto exige as covariáveis reais de grade.")
    features = modelos.feature_columns(data)
    if not set(features).issubset(data) or not np.isfinite(data[features]).all().all():
        raise ValueError("Covariáveis incompletas nas estações.")
    held = modelos.reserve_test(data)
    development = data.loc[~held].reset_index(drop=True)
    groups = modelos.spatial_blocks(development, 2)
    if len(np.unique(groups)) < 5:
        raise ValueError("O piloto exige cinco blocos de desenvolvimento para dispersão.")
    response = development.temperature_c.copy()
    if formulation == "correction":
        response -= development.chelsa_c
    estimator, parameters = modelos.model_candidates(42)[method]
    best = {}
    if parameters:
        search = GridSearchCV(estimator, parameters, cv=GroupKFold(n_splits=3),
                              scoring="neg_root_mean_squared_error", n_jobs=1)
        search.fit(development[features], response, groups=groups)
        estimator, best = search.best_estimator_, search.best_params_
    else:
        estimator.fit(development[features], response)
    fold_models = []
    split = GroupKFold(n_splits=5, shuffle=True, random_state=42)
    for training, _ in split.split(development, groups=groups):
        member = clone(estimator).fit(development.iloc[training][features], response.iloc[training])
        fold_models.append(member)
    metadata = {
        "method": method, "formulation": formulation, "features": features,
        "selected_parameters": best, "estimator_parameters": estimator.get_params(),
        "development_stations": sorted(development.station_id.unique().tolist()),
        "reserved_unscored_stations": sorted(data.loc[held, "station_id"].unique().tolist()),
        "test_seed": 20261018, "spatial_block_degrees": 2,
        "hyperparameter_folds": 3, "dispersion_models": 5,
        "dispersion_parameters": "Fixed hyperparameters selected on all development data; no holdout used",
    }
    return estimator, fold_models, development, metadata


def pixel_features(covariates, transform, month):
    if month not in range(1, 13):
        raise ValueError("Mês deve estar entre 1 e 12.")
    height, width = covariates.shape[1:]
    row, col = np.indices((height, width))
    x = transform.c + (col + 0.5) * 30
    y = transform.f - (row + 0.5) * 30
    longitude, latitude = Transformer.from_crs(CRS, "EPSG:4326", always_xy=True).transform(x, y)
    angle = 2 * np.pi * (month - 1) / 12
    sine, cosine = np.sin(angle), np.cos(angle)
    return pd.DataFrame({
        "latitude": latitude.ravel(), "longitude": longitude.ravel(),
        "month_sin": sine, "month_cos": cosine,
        "latitude_sin": latitude.ravel() * sine, "latitude_cos": latitude.ravel() * cosine,
        "dem_elevation_m": covariates[12].ravel(), "chelsa_c": covariates[month - 1].ravel(),
        "slope_deg": covariates[14].ravel(),
    })


def predict_tile(covariates, transform, estimator, fold_models, development, formulation):
    features = modelos.feature_columns(development)
    lower, upper = development[features].min(), development[features].max()
    shape = covariates.shape[1:]
    temperatures, dispersions, flags = [], [], []
    annual_members = np.zeros((len(fold_models), *shape), dtype=float)
    weights = month_weights()
    for month in range(1, 13):
        frame = pixel_features(covariates, transform, month)[features]
        offset = frame.chelsa_c.to_numpy() if formulation == "correction" else 0
        temperatures.append((estimator.predict(frame) + offset).reshape(shape))
        members = np.stack([(model.predict(frame) + offset).reshape(shape) for model in fold_models])
        dispersions.append(members.std(axis=0, ddof=1))
        annual_members += weights[month - 1] * members
        flags.append(((frame < lower) | (frame > upper)).any(axis=1).to_numpy().reshape(shape).astype(np.uint8))
    temperatures.append(np.tensordot(weights, np.stack(temperatures), axes=(0, 0)))
    dispersions.append(annual_members.std(axis=0, ddof=1))
    flags.append(np.maximum.reduce(flags))
    return np.stack(temperatures), np.stack(dispersions), np.stack(flags)


def write_auxiliary(path, data, transform, *, kind, method, period):
    path = modelos.local_path(path)
    if path.exists():
        raise FileExistsError(f"Arquivo existente: {path}")
    validate_grid(transform, CRS)
    if kind not in {"sd_between_models", "outside_training_range"}:
        raise ValueError("Tipo auxiliar inválido.")
    if data.ndim != 2 or not np.isfinite(data).all():
        raise ValueError("Raster auxiliar exige matriz 2D finita.")
    flag = kind == "outside_training_range"
    if flag and not np.isin(data, [0, 1]).all():
        raise ValueError("Flag deve conter apenas 0/1.")
    if not flag and (data < 0).any():
        raise ValueError("Desvio padrão não pode ser negativo.")
    dtype, nodata = ("uint8", 255) if flag else ("float32", -9999.0)
    path.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(path, "w", driver="GTiff", width=data.shape[1], height=data.shape[0],
                       count=1, dtype=dtype, nodata=nodata, crs=CRS, transform=transform,
                       compress="DEFLATE", tiled=True, blockxsize=256, blockysize=256) as target:
        target.write(data.astype(dtype), 1)
        target.set_band_description(1, kind)
        target.set_band_unit(1, "1" if flag else "degC")
        target.scales, target.offsets = (1.0,), (0.0,)
        target.update_tags(kind=kind, experimental="true", method=method, period=period,
                           units="flag" if flag else "degC", scale_factor=1, add_offset=0,
                           gee_pyramiding_policy="sample" if flag else "mean",
                           interpretation="univariate_min_max_not_AOA" if flag else "model_dispersion_not_prediction_interval")
    return path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", default="dados/processados/normais_covariaveis.csv", type=modelos.local_path)
    parser.add_argument("--method", choices=METHODS, default="M5_lightgbm")
    parser.add_argument("--formulation", choices=["direct", "correction"], default="correction")
    parser.add_argument("--project")
    args = parser.parse_args()
    source = modelos.local_path(args.input)
    source_manifest = source.with_suffix(".manifesto.json")
    provenance = json.loads(source_manifest.read_text(encoding="utf-8"))
    if provenance.get("output_sha256") != sha256(source):
        raise ValueError("Tabela de treino divergente de seu manifesto de covariáveis.")
    if provenance.get("script_sha256") != sha256(covariaveis_gee.__file__):
        raise ValueError("Helper de covariáveis mudou desde extração das estações; refazer extração.")
    labels = [f"{month:02d}" for month in range(1, 13)] + ["anual"]
    suffix = f"curitiba_{args.method}_{args.formulation}"
    outputs = {kind: [modelos.local_path(PILOT / f"{kind}_30m_{label}_{suffix}.tiff") for label in labels]
               for kind in ["temperatura_media", "dispersao_modelos", "fora_faixa_treino"]}
    manifest_path = modelos.local_path(PILOT / f"manifesto_{suffix}.json")
    if manifest_path.exists() or any(path.exists() for paths in outputs.values() for path in paths):
        raise FileExistsError("Produtos do piloto já existem; não serão sobrescritos.")
    transform = pilot_transform()
    covariates, cache = download_covariates(transform, source_manifest, args.project)
    data = pd.read_csv(source, dtype={"station_id": str})
    estimator, members, development, training = fit_development(data, args.method, args.formulation)
    temperature, sd, flag = predict_tile(covariates, transform, estimator, members, development, args.formulation)
    if not np.isfinite(temperature).all() or np.max(np.abs(temperature)) > 327.67 or not np.isfinite(sd).all():
        raise ValueError("Previsões inválidas; nenhum mapa de temperatura foi gravado.")
    for index, label in enumerate(labels):
        period = f"1991-2020; month={label}"
        write_temperature_geotiff(outputs["temperatura_media"][index], temperature[index], transform, CRS,
                                  period=period, method=f"{args.method}/{args.formulation}", experimental=True)
        write_auxiliary(outputs["dispersao_modelos"][index], sd[index], transform,
                        kind="sd_between_models", method=args.method, period=period)
        write_auxiliary(outputs["fora_faixa_treino"][index], flag[index], transform,
                        kind="outside_training_range", method=args.method, period=period)
    manifest = {
        "status": "experimental_preview_not_validated_product", "created_utc": datetime.now(timezone.utc).isoformat(),
        "training": training, "normal_period": "1991-2020", "temperature_definition": "midpoint_Tmax_Tmin",
        "input_sha256": sha256(source), "input_manifest_sha256": sha256(source_manifest),
        "script_sha256": sha256(__file__), "modeling_script_sha256": sha256(modelos.__file__),
        "covariates": cache, "crs": CRS, "transform": list(transform)[:6],
        "width": SIZE, "height": SIZE, "annual_month_weights": month_weights().tolist(),
        "annual_definition": "weighted monthly predictions using day counts 1991-2020",
        "outside_training_range_fraction": flag.mean(axis=(1, 2)).tolist(),
        "temperature_range_c": [float(temperature.min()), float(temperature.max())],
        "outputs": {path.name: sha256(path) for paths in outputs.values() for path in paths},
        "limitations": ["C11/C12/C13 unresolved; not validated at 30 m.",
                        "SD is dispersion of five fold-trained models, not prediction uncertainty.",
                        "Range flag is univariate min/max, not formal multivariate AOA.",
                        "Five fold models use hyperparameters selected on development; holdout never fitted.",
                        "No station holdout scores used or exported; no remote writes."],
        "attribution": provenance.get("attribution"),
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Prévia experimental: {sum(map(len, outputs.values()))} GeoTIFFs em dados/piloto; sem publicação.")


if __name__ == "__main__":
    main()
