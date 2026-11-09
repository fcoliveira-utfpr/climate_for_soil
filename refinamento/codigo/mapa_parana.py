"""Mapas de 30 m do Paraná inteiro: temperatura média do ar e chuva, normal 1991-2020.

Grade única WGS 84 / UTM 22S (EPSG:32722), pixel de 30 m, origem em múltiplos de 30 m, cobrindo
todo o estado (a faixa oeste, na zona 21, fica na zona 22 estendida; distorção de escala < 0,2%).
Cada pixel sai dos modelos candidatos aplicados às covariáveis do próprio pixel, sem interpolar
estações: LightGBM corrigindo o CHELSA (temperatura, como mapa_brasil.py) e um LightGBM por mês
corrigindo log1p(CHELSA) (chuva, a melhor estratégia na comparação C7), treinados nas estações de
desenvolvimento.

Camadas por variável, 13 bandas cada (meses 01-12 e anual):
  media          temperatura em int16 × 0,01 °C | chuva em uint16, mm
  incerteza90    meia-largura do intervalo de 90% calibrado na validação espacial
                 (mensal: k × dispersão entre 5 modelos; anual: largura constante) | uint16
  fora_aoa       1 = pixel fora da área de aplicabilidade (Meyer & Pebesma, 2021) | uint8
O anual da temperatura é a média dos meses ponderada pelos dias; o da chuva é a soma dos meses.

Subcomandos (de dentro de refinamento/):
  python -B -m codigo.mapa_parana preparar [--chelsa-bilinear]
  python -B -m codigo.mapa_parana produzir --project ID [--worker I --workers N] [--max-windows M]
  python -B -m codigo.mapa_parana montar
"""
from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import rasterio
from affine import Affine
from pyproj import Transformer
from rasterio.features import geometry_mask
from rasterio.io import MemoryFile
from scipy.spatial import cKDTree
from shapely import wkb
from shapely.geometry import box, mapping, shape
from shapely.ops import transform as shapely_transform
from sklearn.model_selection import GroupKFold

from codigo import chelsa_bilinear, covariaveis_gee, mapa_chuva, mapa_piloto, modelos, modelos_chuva
from codigo.covariaveis_chuva_gee import SOURCES
from codigo.dados_temperatura import safe_path
from codigo.geotiff import validate_grid
from codigo.grade_brasil import digest
from codigo.incerteza_aplicabilidade import (RAIN_MONTH_FEATURES, aoa_threshold, conformal_quantile, inner_fold_ids,
                                             rain_month_fit)

CRS = "EPSG:32722"
PIXEL = 30
WINDOW = 512
UF_CODE = "41"
FOLDER = Path("dados/parana")
PREP = FOLDER / "preparo.joblib"
WINDOWS = FOLDER / "janelas"
OUTPUT = FOLDER / "saida"
TEMP_INPUT = "dados/brasil/normais_covariaveis_20261106.csv"
MONTHS = [f"{m:02d}" for m in range(1, 13)]
LABELS = MONTHS + ["anual"]
BANDS = [f"tas_{m}" for m in MONTHS] + [f"pr_{m}" for m in MONTHS] + ["elevation", "slope"]
LAYERS = {  # nome: (dtype, nodata, escala de leitura, unidade)
    "temperatura_media": ("int16", -32768, 0.01, "degC"),
    "temperatura_incerteza90": ("uint16", 65535, 0.01, "degC"),
    "temperatura_fora_aoa": ("uint8", 255, 1, "flag"),
    "chuva_media": ("uint16", 65535, 1, "mm"),
    "chuva_incerteza90": ("uint16", 65535, 1, "mm"),
    "chuva_fora_aoa": ("uint8", 255, 1, "flag"),
}


# ------------------------------------------------------------------------- grade
def parana_polygon():
    features = json.loads(safe_path("dados/brasil/limites_uf_ibge.geojson").read_text(encoding="utf-8"))["features"]
    geometry = shape(next(f["geometry"] for f in features if str(f["properties"].get("codarea")) == UF_CODE))
    project = Transformer.from_crs("EPSG:4326", CRS, always_xy=True).transform
    return shapely_transform(project, geometry)


def build_grid(polygon):
    minx, miny, maxx, maxy = polygon.bounds
    x0 = np.floor(minx / PIXEL) * PIXEL
    y0 = np.ceil(maxy / PIXEL) * PIXEL
    width = int(np.ceil((maxx - x0) / PIXEL))
    height = int(np.ceil((y0 - miny) / PIXEL))
    transform = Affine(PIXEL, 0, x0, 0, -PIXEL, y0)
    validate_grid(transform, CRS)
    windows = []
    for row in range(0, height, WINDOW):
        for col in range(0, width, WINDOW):
            h, w = min(WINDOW, height - row), min(WINDOW, width - col)
            left, top = x0 + col * PIXEL, y0 - row * PIXEL
            if box(left, top - h * PIXEL, left + w * PIXEL, top).intersects(polygon):
                windows.append((row, col, h, w))
    return {"crs": CRS, "transform": list(transform)[:6], "width": width, "height": height, "windows": windows}


# ------------------------------------------------------------------- referências
def aoa_reference(train_x, importance, groups):
    mean = train_x.mean()
    scale = train_x.std(ddof=0).replace(0, 1)
    weights = np.asarray(importance, float)
    weights = weights / weights.sum()
    z_train = ((train_x - mean) / scale).to_numpy() * weights
    mean_distance, threshold = aoa_threshold(z_train, inner_fold_ids(len(train_x), groups))
    return {"mean": mean.to_numpy(), "scale": scale.to_numpy(), "weights": weights, "z_train": z_train,
            "mean_distance": float(mean_distance), "threshold": float(threshold), "columns": list(train_x.columns)}


def rain_by_month(development):
    """Um modelo, 5 membros e uma referência de AOA por mês (semente 42, blocos de 2°)."""
    months = {}
    for month in range(1, 13):
        source = development[development.month == month].reset_index(drop=True)
        blocks = modelos.spatial_blocks(source, 2)
        model = rain_month_fit(source, blocks, 42)
        folds_inner = inner_fold_ids(len(source), blocks)
        members = [rain_month_fit(source.iloc[folds_inner != k], blocks[folds_inner != k], 42) for k in range(5)]
        months[month] = {"model": model, "members": members, "selected": model.complexity,
                         "aoa": aoa_reference(model.design(source[RAIN_MONTH_FEATURES]),
                                              model.estimator_.booster_.feature_importance("gain"), blocks)}
    return months


def calibration(variable):
    cv = pd.read_csv(safe_path(f"dados/modelagem/incerteza_aoa_{variable}_2graus.csv"), dtype={"station_id": str})
    variable = variable.replace("_bilinear", "")
    k90 = conformal_quantile(np.abs(cv.prediction - cv.observed) / np.maximum(cv.sd, 1e-9))
    if variable == "temperatura":
        weights = mapa_piloto.month_weights()
        cv = cv.assign(w=lambda x: np.asarray(weights)[x.month - 1])
        annual = cv.assign(o=cv.observed * cv.w, p=cv.prediction * cv.w).groupby(["repeat", "station_id"])[["o", "p"]].sum()
    else:
        annual = cv.groupby(["repeat", "station_id"]).agg(o=("observed", "sum"), p=("prediction", "sum"))
    q90 = conformal_quantile(np.abs(annual.p - annual.o))
    return {"k90_monthly": float(k90), "q90_annual": float(q90)}


def preparar(args):
    folder = safe_path(FOLDER)
    folder.mkdir(parents=True, exist_ok=True)
    polygon = parana_polygon()
    grid = build_grid(polygon)
    source = safe_path(TEMP_INPUT)
    suffix = "_bilinear" if args.chelsa_bilinear else ""
    temp_data = pd.read_csv(source, dtype={"station_id": str})
    if args.chelsa_bilinear:
        temp_data = chelsa_bilinear.aplicar(temp_data, "temperatura")
    temp_model, temp_members, temp_dev, temp_meta = mapa_piloto.fit_development(temp_data, "M5_lightgbm", "correction")
    temp_features = modelos.feature_columns(temp_dev)
    temp_groups = modelos.spatial_blocks(temp_dev, 2)
    rain_data, rain_report = modelos_chuva.prepare()
    if args.chelsa_bilinear:
        rain_data = chelsa_bilinear.aplicar(rain_data, "chuva")
    rain_dev = rain_data.loc[~rain_data.reserved].reset_index(drop=True)
    rain_months = rain_by_month(rain_dev)
    preparo = {
        "grid": grid, "polygon_wkb": polygon.wkb, "chelsa_bilinear": bool(args.chelsa_bilinear),
        "temperatura": {"model": temp_model, "members": temp_members, "features": temp_features,
                        "aoa": aoa_reference(temp_dev[temp_features], temp_model.booster_.feature_importance("gain"), temp_groups),
                        **calibration("temperatura" + suffix), "metadata": temp_meta},
        "chuva": {"months": rain_months, "features": RAIN_MONTH_FEATURES, **calibration("chuva_por_mes" + suffix),
                  "development_stations": sorted(rain_dev.station_id.unique().tolist())},
    }
    joblib.dump(preparo, safe_path(PREP))
    manifest = {
        "status": "experimental_not_validated", "crs": CRS, "pixel_m": PIXEL, "window_pixels": WINDOW,
        "width": grid["width"], "height": grid["height"], "transform": grid["transform"],
        "windows": len(grid["windows"]), "chelsa_bilinear": bool(args.chelsa_bilinear),
        "parana_area_km2": polygon.area / 1e6,
        "temperature": {"input": TEMP_INPUT, "input_sha256": digest(source), "selected": temp_meta["selected_parameters"],
                        "development_stations": len(temp_meta["development_stations"]),
                        "reserved_unscored": len(temp_meta["reserved_unscored_stations"]),
                        "k90_monthly": preparo["temperatura"]["k90_monthly"], "q90_annual_c": preparo["temperatura"]["q90_annual"],
                        "aoa_threshold": preparo["temperatura"]["aoa"]["threshold"]},
        "rain": {"development_stations": len(preparo["chuva"]["development_stations"]), "input_hashes": rain_report["hashes"],
                 "k90_monthly": preparo["chuva"]["k90_monthly"], "q90_annual_mm": preparo["chuva"]["q90_annual"],
                 "model": "LightGBM por mês corrigindo log1p(CHELSA)",
                 "selected_complexity": [preparo["chuva"]["months"][m]["selected"] for m in range(1, 13)],
                 "aoa_threshold_by_month": [preparo["chuva"]["months"][m]["aoa"]["threshold"] for m in range(1, 13)]},
        "code_sha256": {"mapa_parana": digest(Path(__file__)), **{name: digest(Path(module.__file__)) for name, module in
                        [("modelos", modelos), ("mapa_piloto", mapa_piloto), ("modelos_chuva", modelos_chuva),
                         ("mapa_chuva", mapa_chuva), ("covariaveis_gee", covariaveis_gee)]}},
        "prep_sha256": digest(safe_path(PREP)),
    }
    safe_path(FOLDER / "manifesto.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps({k: manifest[k] for k in ("width", "height", "windows", "parana_area_km2", "chelsa_bilinear")}, indent=2))
    print("temperatura:", json.dumps(manifest["temperature"]))
    print("chuva:", json.dumps(manifest["rain"]))


# ----------------------------------------------------------------------- produção
def window_transform(grid, row, col):
    t = Affine(*grid["transform"])
    return Affine(PIXEL, 0, t.c + col * PIXEL, 0, -PIXEL, t.f - row * PIXEL)


def download(ee, transform, width, height, bilinear):
    region = ee.Geometry.Rectangle([transform.c, transform.f - height * PIXEL, transform.c + width * PIXEL, transform.f],
                                   proj=CRS, geodesic=False)
    projection = ee.Projection(CRS, list(transform)[:6])
    margin = region.buffer(covariaveis_gee.BUFFER_M)
    collection = ee.ImageCollection(covariaveis_gee.DEM).filterBounds(margin).select("DEM")
    native = collection.mosaic().setDefaultProjection(ee.Image(collection.first()).projection()).clip(margin)
    fine = native.resample("bilinear").reproject(projection).rename("elevation")
    slope = ee.Terrain.slope(fine).rename("slope")
    tas = ee.Image(covariaveis_gee.CHELSA).select(covariaveis_gee.MONTH_BANDS).rename([f"tas_{m}" for m in MONTHS])
    pr = ee.Image(SOURCES["chelsa"]).select(covariaveis_gee.MONTH_BANDS).rename([f"pr_{m}" for m in MONTHS])
    if bilinear:
        tas, pr = tas.resample("bilinear"), pr.resample("bilinear")
    image = tas.addBands(pr).addBands([fine, slope]).reproject(projection).clip(region).toFloat().unmask(-9999)
    url = image.getDownloadURL({"format": "GEO_TIFF", "crs": CRS, "crs_transform": list(transform)[:6],
                                "dimensions": [width, height]})
    import requests
    with requests.get(url, timeout=(20, 300), stream=True) as response:
        response.raise_for_status()
        payload = b"".join(response.iter_content(1024 * 1024))
    with MemoryFile(payload) as memory, memory.open() as data:
        if (data.count, data.height, data.width) != (len(BANDS), height, width):
            raise ValueError("Download com dimensões inesperadas.")
        if data.crs != rasterio.crs.CRS.from_string(CRS) or data.transform != transform:
            raise ValueError("Download em grade diferente da pedida.")
        values = data.read().astype(np.float64)
    values[values == -9999] = np.nan
    return values, hashlib.sha256(payload).hexdigest()


def dissimilarity(frame, reference):
    z = ((frame.to_numpy(float) - reference["mean"]) / reference["scale"]) * reference["weights"]
    if "tree" not in reference:
        reference["tree"] = cKDTree(reference["z_train"])
    return reference["tree"].query(z)[0] / reference["mean_distance"]


def predict_temperature(cov, lat, lon, part):
    n = len(lat)
    frames = []
    for month in range(1, 13):
        sine, cosine = np.sin(2 * np.pi * (month - 1) / 12), np.cos(2 * np.pi * (month - 1) / 12)
        frames.append(pd.DataFrame({"latitude": lat, "longitude": lon, "month_sin": sine, "month_cos": cosine,
                                    "latitude_sin": lat * sine, "latitude_cos": lat * cosine,
                                    "dem_elevation_m": cov[24], "slope_deg": cov[25], "chelsa_c": cov[month - 1]}))
    frame = pd.concat(frames, ignore_index=True)[part["features"]]
    chelsa = frame.chelsa_c.to_numpy()
    prediction = (part["model"].predict(frame) + chelsa).reshape(12, n)
    ensemble = np.stack([m.predict(frame) + chelsa for m in part["members"]]).reshape(len(part["members"]), 12, n)
    outside = (dissimilarity(frame, part["aoa"]) > part["aoa"]["threshold"]).reshape(12, n)
    if not np.isfinite(prediction).all() or np.abs(prediction).max() > 327:
        raise ValueError("Temperatura prevista não finita ou fora do int16.")
    weights = np.asarray(mapa_piloto.month_weights())[:, None]
    mean = np.vstack([prediction, (prediction * weights).sum(axis=0)])
    halfwidth = np.vstack([part["k90_monthly"] * ensemble.std(axis=0, ddof=1), np.full(n, part["q90_annual"])])
    flag = np.vstack([outside, outside.any(axis=0)])
    return np.rint(mean * 100).astype(np.int16), np.minimum(np.rint(halfwidth * 100), 65534).astype(np.uint16), flag.astype(np.uint8)


def predict_rain(cov, lat, lon, part):
    n = len(lat)
    prediction, spread, outside = np.empty((12, n)), np.empty((12, n)), np.empty((12, n), bool)
    for month in range(1, 13):
        unit = part["months"][month]
        frame = pd.DataFrame({"latitude": lat, "longitude": lon, "elevation_30": cov[24], "slope_30": cov[25],
                              "chelsa_mm": cov[11 + month]})[part["features"]]
        prediction[month - 1] = unit["model"].predict(frame)
        spread[month - 1] = np.stack([m.predict(frame) for m in unit["members"]]).std(axis=0, ddof=1)
        outside[month - 1] = dissimilarity(unit["model"].design(frame), unit["aoa"]) > unit["aoa"]["threshold"]
    annual = prediction.sum(axis=0)
    if not np.isfinite(prediction).all() or prediction.min() < 0 or np.rint(annual).max() >= 65535:
        raise ValueError("Chuva prevista inválida ou fora do uint16.")
    mean = np.vstack([prediction, annual])
    halfwidth = np.vstack([part["k90_monthly"] * spread, np.full(n, part["q90_annual"])])
    flag = np.vstack([outside, outside.any(axis=0)])
    return np.rint(mean).astype(np.uint16), np.minimum(np.rint(halfwidth), 65534).astype(np.uint16), flag.astype(np.uint8)


def process_window(ee, preparo, polygon, row, col, h, w):
    transform = window_transform(preparo["grid"], row, col)
    inside = geometry_mask([mapping(polygon)], (h, w), transform, invert=True)
    arrays = {name: np.full((13, h, w), nodata, dtype=dtype) for name, (dtype, nodata, _, _) in LAYERS.items()}
    fingerprint = None
    valid = np.zeros((h, w), bool)
    if inside.any():
        values, fingerprint = download(ee, transform, w, h, preparo["chelsa_bilinear"])
        valid = inside & np.isfinite(values).all(axis=0)
        if valid.any():
            if np.any(values[24:, valid][1] < 0) or np.any(values[24:, valid][1] > 90):
                raise ValueError("Declividade fora da faixa física.")
            r, c = np.where(valid)
            x, y = transform * (c + 0.5, r + 0.5)
            lon, lat = Transformer.from_crs(CRS, "EPSG:4326", always_xy=True).transform(x, y)
            cov = values[:, valid]
            for prefix, function in (("temperatura", predict_temperature), ("chuva", predict_rain)):
                mean, halfwidth, flag = function(cov, lat, lon, preparo[prefix])
                arrays[f"{prefix}_media"][:, valid] = mean
                arrays[f"{prefix}_incerteza90"][:, valid] = halfwidth
                arrays[f"{prefix}_fora_aoa"][:, valid] = flag
    return arrays, int(inside.sum()), int(valid.sum()), fingerprint


def produzir(args):
    import ee
    preparo = joblib.load(safe_path(PREP))
    manifest = json.loads(safe_path(FOLDER / "manifesto.json").read_text(encoding="utf-8"))
    if manifest["prep_sha256"] != digest(safe_path(PREP)):
        raise ValueError("Preparo diferente do manifesto; rode preparar de novo.")
    polygon = wkb.loads(preparo["polygon_wkb"])
    folder = safe_path(WINDOWS)
    folder.mkdir(parents=True, exist_ok=True)
    ee.Initialize(project=args.project)
    ee.data.setDeadline(300000)
    temp_manifest = json.loads(safe_path(TEMP_INPUT).with_suffix(".manifesto.json").read_text(encoding="utf-8"))
    for key, asset in (("chelsa_metadata", covariaveis_gee.CHELSA), ("dem_metadata", covariaveis_gee.DEM)):
        if ee.data.getAsset(asset) != temp_manifest[key]:
            raise ValueError(f"Fonte remota mudou desde a extração do treino: {asset}. Reextraia as covariáveis.")
    ordered = preparo["grid"]["windows"][::-1] if args.reverse else preparo["grid"]["windows"]
    mine = [w for i, w in enumerate(ordered) if i % args.workers == args.worker]
    done = 0
    for row, col, h, w in mine:
        path = folder / f"janela_{row:05d}_{col:05d}.npz"
        if path.exists():
            continue
        start = time.time()
        for attempt in range(4):
            try:
                arrays, inside, valid, fingerprint = process_window(ee, preparo, polygon, row, col, h, w)
                break
            except Exception as error:  # rede ou GEE: tenta de novo com espera crescente
                if attempt == 3:
                    raise
                print(f"janela {row}_{col}: tentativa {attempt + 1} falhou ({type(error).__name__}); repetindo", flush=True)
                time.sleep(15 * (attempt + 1))
        temporary = path.with_suffix(".tmp.npz")
        np.savez_compressed(temporary, row=row, col=col, inside=inside, valid=valid,
                            fingerprint=fingerprint or "", **arrays)
        temporary.replace(path)
        done += 1
        print(f"worker {args.worker}: janela {row}_{col} validos {valid}/{inside} em {time.time() - start:.0f}s", flush=True)
        if args.max_windows and done >= args.max_windows:
            break


# ----------------------------------------------------------------------- montagem
def montar(args):
    preparo = joblib.load(safe_path(PREP))
    grid = preparo["grid"]
    transform = Affine(*grid["transform"])
    out = safe_path(OUTPUT)
    out.mkdir(parents=True, exist_ok=True)
    files = {name: out / f"parana_{name}_30m.tif" for name in LAYERS}
    handles = {}
    for name, (dtype, nodata, scale, unit) in LAYERS.items():
        handle = rasterio.open(files[name], "w", driver="GTiff", width=grid["width"], height=grid["height"], count=13,
                               dtype=dtype, nodata=nodata, crs=CRS, transform=transform, tiled=True, blockxsize=512,
                               blockysize=512, compress="DEFLATE", predictor=2 if dtype != "uint8" else 1, BIGTIFF="YES")
        for band, label in enumerate(LABELS, 1):
            handle.set_band_description(band, f"{name.split('_', 1)[1]}_{label}")
        handle.scales = (scale,) * 13
        handle.update_tags(experimental="true", normal_period="1991-2020", units=unit, scale_factor=scale,
                           region="Parana (IBGE)", gee_pyramiding_policy="mode" if unit == "flag" else "mean",
                           method="LightGBM corrigindo o CHELSA; sem interpolacao de estacoes")
        handles[name] = handle
    expected = {(r, c) for r, c, _, _ in grid["windows"]}
    found, inside_total, valid_total = set(), 0, 0
    for path in sorted(safe_path(WINDOWS).glob("janela_*.npz")):
        if ".tmp" in path.name:
            continue
        with np.load(path) as data:
            row, col = int(data["row"]), int(data["col"])
            found.add((row, col))
            inside_total += int(data["inside"])
            valid_total += int(data["valid"])
            for name in LAYERS:
                block = data[name]
                window = rasterio.windows.Window(col, row, block.shape[2], block.shape[1])
                handles[name].write(block, window=window)
    for handle in handles.values():
        handle.close()
    missing = sorted(expected - found)
    stats = {}
    for name, (dtype, nodata, scale, unit) in LAYERS.items():
        with rasterio.open(files[name]) as data:
            band = data.read(13, masked=True)
            stats[name] = {"anual_min": float(band.min() * scale) if band.count() else None,
                           "anual_max": float(band.max() * scale) if band.count() else None,
                           "anual_mean": float(band.mean() * scale) if band.count() else None}
    report = {"status": "complete_experimental" if not missing and valid_total == inside_total else "partial_experimental",
              "windows_expected": len(expected), "windows_found": len(found), "windows_missing": len(missing),
              "pixels_inside_parana": inside_total, "pixels_valid": valid_total,
              "outputs": {name: {"file": files[name].name, "bytes": files[name].stat().st_size} for name in LAYERS},
              "annual_stats": stats}
    if args.hash:
        for name in LAYERS:
            report["outputs"][name]["sha256"] = digest(files[name])
    safe_path(FOLDER / "montagem.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("preparar")
    p.add_argument("--chelsa-bilinear", action="store_true")
    p = sub.add_parser("produzir")
    p.add_argument("--project", required=True)
    p.add_argument("--worker", type=int, default=0)
    p.add_argument("--workers", type=int, default=1)
    p.add_argument("--max-windows", type=int)
    p.add_argument("--reverse", action="store_true", help="percorre as janelas de trás para frente (mais processos sem conflito)")
    p = sub.add_parser("montar")
    p.add_argument("--hash", action="store_true")
    args = parser.parse_args()
    {"preparar": preparar, "produzir": produzir, "montar": montar}[args.command](args)


if __name__ == "__main__":
    main()
