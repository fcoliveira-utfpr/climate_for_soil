"""Extrai CHELSA e relevo nas estações, por consultas GEE somente de leitura.

Nenhum export, upload ou asset é criado. A resposta observada usa anos válidos
que podem diferir entre estação/mês e da normal completa CHELSA 1991–2020.
O Copernicus é um DSM (inclui vegetação/edificações), não terreno descoberto.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import inspect
import json
from pathlib import Path

import numpy as np
import pandas as pd

try:
    from .dados_temperatura import ROOT, safe_path
except ImportError:
    from dados_temperatura import ROOT, safe_path

CHELSA = "projects/fcoliveira/assets/CHELSA/chelsa_brasil_tas_normal_1991_2020"
DEM = "COPERNICUS/DEM/GLO30_2024_1"
TRANSFORM = [30, 0, 0, 0, -30, 0]
BUFFER_M = 2500
MAX_PIXELS = 4096
MONTH_BANDS = [f"b{i}" for i in range(1, 13)]
TERRAIN_BANDS = ["dem_elevation_m", "coarse_elevation_m", "slope_deg"]
HELPER_VERSION = "1.0.0"


def hash_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def utm_crs(latitude: float, longitude: float) -> str:
    if not -80 <= latitude <= 84 or not -180 <= longitude <= 180:
        raise ValueError("Coordenadas fora do domínio UTM.")
    zone = min(60, int(np.floor((longitude + 180) / 6)) + 1)
    return f"EPSG:{(32600 if latitude >= 0 else 32700) + zone}"


def selecionar_mensais(normals: pd.DataFrame) -> pd.DataFrame:
    """Somente estações com todos os 12 meses finitos, sem selecionar por erro."""
    required = ["station_id", "latitude", "longitude", "elevation_m", "month", "temperature_c"]
    if not set(required).issubset(normals.columns):
        raise ValueError(f"Colunas obrigatórias: {required}")
    data = normals.loc[normals.month != 0].copy()
    if not data.month.isin(range(1, 13)).all() or data.duplicated(["station_id", "month"]).any():
        raise ValueError("Mês inválido ou chave estação/mês duplicada.")
    if data.station_id.isna().any():
        raise ValueError("ID de estação ausente.")
    for column in ("latitude", "longitude", "elevation_m"):
        if data.groupby("station_id")[column].nunique(dropna=False).gt(1).any():
            raise ValueError(f"{column} varia entre meses de uma estação.")
    counts = data.loc[np.isfinite(data.temperature_c)].groupby("station_id").month.nunique()
    data = data.loc[data.station_id.isin(counts[counts == 12].index)].copy()
    if data.empty:
        raise ValueError("Nenhuma estação com 12 meses válidos.")
    if not np.isfinite(data[["latitude", "longitude", "elevation_m"]]).all().all():
        raise ValueError("Estação selecionada sem coordenadas ou altitude válidas.")
    return data.sort_values(["station_id", "month"]).reset_index(drop=True)


def construir_imagens(region, crs, transform=None):
    """Stack reutilizável em ponto ou tile: b1…b12 e as três TERRAIN_BANDS.

    Use CRS UTM WGS84 e transformação com origem múltipla de 30 m para
    reproduzir os pixels de treino. O recorte recebe margem de 2,5 km antes
    de calcular slope e agregar o DSM. Não reprojeta o Brasil inteiro.
    CHELSA/z_grade são reamostrados por vizinho mais próximo; o DSM usa
    bilinear antes do slope em 30 m. z_grade agrega todos os subpixels com
    pesos de máscara/sobreposição, como documenta reduceResolution(mean).
    """
    import ee
    transform = TRANSFORM if transform is None else transform
    fine_projection = ee.Projection(crs, transform)
    region_margin = region.buffer(BUFFER_M)
    collection = ee.ImageCollection(DEM).filterBounds(region_margin).select("DEM")
    native_projection = ee.Image(collection.first()).projection()
    native = collection.mosaic().setDefaultProjection(native_projection).clip(region_margin)
    fine = native.resample("bilinear").reproject(fine_projection).rename("dem_elevation_m")
    slope = ee.Terrain.slope(fine).rename("slope_deg")
    chelsa = ee.Image(CHELSA).select(MONTH_BANDS)
    coarse = (native.reduceResolution(reducer=ee.Reducer.mean(), bestEffort=False, maxPixels=MAX_PIXELS)
              .reproject(chelsa.select("b1").projection()).rename("coarse_elevation_m"))
    return fine.addBands([coarse, slope, chelsa]).reproject(fine_projection).clip(region)


def extrair_lote(stations: pd.DataFrame) -> list[dict]:
    """Uma consulta curta; cada estação usa sua projeção e janela locais."""
    import ee
    features = []
    for row in stations.itertuples(index=False):
        point = ee.Geometry.Point([float(row.longitude), float(row.latitude)])
        crs = utm_crs(float(row.latitude), float(row.longitude))
        # Construir imagem com região de 60 m evita mascarar o centro do pixel
        # que contém o ponto; o buffer maior da composição cobre as vizinhanças.
        image = construir_imagens(point.buffer(60), crs)
        values = image.reduceRegion(reducer=ee.Reducer.first(), geometry=point,
                                    crs=crs, crsTransform=TRANSFORM, maxPixels=16)
        features.append(ee.Feature(None, values).set({"station_id": str(row.station_id), "utm_crs": crs}))
    response = ee.FeatureCollection(features).getInfo()
    return [feature["properties"] for feature in response["features"]]


def juntar_covariaveis(monthly: pd.DataFrame, values: list[dict]) -> pd.DataFrame:
    terrain = pd.DataFrame(values)
    needed = ["station_id", *MONTH_BANDS, *TERRAIN_BANDS]
    if not set(needed).issubset(terrain.columns):
        raise ValueError("Extração incompleta: alguma banda não foi obtida.")
    if terrain.station_id.duplicated().any() or set(terrain.station_id) != set(monthly.station_id):
        raise ValueError("Extração não corresponde exatamente às estações selecionadas.")
    # GEE representa pixel mascarado como ausência/null; normalize antes do
    # isfinite para rejeitar a extração incompleta com erro explícito.
    numeric_columns = MONTH_BANDS + TERRAIN_BANDS
    terrain[numeric_columns] = terrain[numeric_columns].apply(pd.to_numeric, errors="coerce")
    if not np.isfinite(terrain[MONTH_BANDS + TERRAIN_BANDS]).all().all():
        raise ValueError("Extração contém ausências; não substituir por outro método.")
    if not terrain[MONTH_BANDS].map(lambda x: -40 <= x <= 55).all().all():
        raise ValueError("CHELSA fora da faixa plausível em °C: revisar escala/unidade.")
    if not terrain.slope_deg.between(0, 90).all():
        raise ValueError("Declividade fora de 0–90 graus.")
    long = terrain.melt(id_vars=["station_id", *TERRAIN_BANDS], value_vars=MONTH_BANDS,
                        var_name="band", value_name="chelsa_c")
    long["month"] = long.band.str[1:].astype(int)
    return monthly.merge(long.drop(columns="band"), on=["station_id", "month"],
                         validate="one_to_one", how="left")


def main():
    import ee
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--entrada", default="dados/processados/normais_temperatura.csv")
    parser.add_argument("--saida", default="dados/processados/normais_covariaveis.csv")
    parser.add_argument("--project", help="Padrão: quota_project_id da credencial já configurada.")
    parser.add_argument("--batch-size", type=int, default=20)
    args = parser.parse_args()
    if not 1 <= args.batch_size <= 20:
        raise ValueError("Usar lotes entre 1 e 20 estações.")
    source, target = safe_path(args.entrada), safe_path(args.saida)
    monthly = selecionar_mensais(pd.read_csv(source, dtype={"station_id": str}))
    stations = monthly[["station_id", "latitude", "longitude", "elevation_m"]].drop_duplicates("station_id")
    credentials = ee.data.get_persistent_credentials()
    project = args.project or credentials.quota_project_id
    if not project:
        raise ValueError("Defina --project; a credencial não possui quota_project_id.")
    ee.Initialize(credentials=credentials, project=project)
    ee.data.setDeadline(60000)
    metadata = ee.data.getAsset(CHELSA)
    if [band["id"] for band in metadata["bands"]] != MONTH_BANDS:
        raise ValueError("O asset CHELSA não contém b1…b12 na ordem esperada.")
    dem_metadata = ee.data.getAsset(DEM)
    settings = {"chelsa_asset": CHELSA, "dem_collection": DEM, "chelsa_metadata": metadata,
        "dem_metadata": dem_metadata, "utm_transform": TRANSFORM, "buffer_m": BUFFER_M,
        "reduce_resolution_max_pixels": MAX_PIXELS, "best_effort": False,
        "source_sha256": hash_file(source), "script_sha256": hash_file(Path(__file__)),
        "helper_version": HELPER_VERSION,
        "helper_sha256": hashlib.sha256(inspect.getsource(construir_imagens).encode()).hexdigest(),
        "earthengine_api_version": ee.__version__}
    fingerprint = hashlib.sha256(json.dumps(settings, sort_keys=True).encode()).hexdigest()
    cache = safe_path(ROOT / ".local" / "covariaveis_gee" / fingerprint[:16])
    cache.mkdir(parents=True, exist_ok=True)
    values = []
    for offset in range(0, len(stations), args.batch_size):
        batch = stations.iloc[offset:offset + args.batch_size]
        batch_key = hashlib.sha256("|".join(batch.station_id).encode()).hexdigest()[:16]
        checkpoint = safe_path(cache / f"lote_{batch_key}.json")
        if checkpoint.exists():
            result = json.loads(checkpoint.read_text(encoding="utf-8"))
        else:
            result = extrair_lote(batch)
            checkpoint.write_text(json.dumps(result, indent=2), encoding="utf-8")
        values.extend(result)
        print(f"Covariáveis: {len(values)}/{len(stations)} estações", flush=True)
    output = juntar_covariaveis(monthly, values)
    target.parent.mkdir(parents=True, exist_ok=True)
    output.to_csv(target, index=False, float_format="%.10g")
    manifest = {**settings, "project": project, "created_utc": datetime.now(timezone.utc).isoformat(),
        "output_sha256": hash_file(target), "stations": len(stations), "monthly_rows": len(output),
        "station_ids": list(stations.station_id), "batch_size": args.batch_size,
        "units": {"chelsa_c": "degC", "dem_elevation_m": "m EGM2008", "coarse_elevation_m": "m EGM2008", "slope_deg": "degrees"},
        "chelsa_unit_evidence": "climas/dados_chelsa/assets_utilizados.md; valores amostrados plausíveis; asset não tem propriedade unit",
        "chelsa_period": "1991-2020", "chelsa_resampling": "nearest on UTM 30m grid",
        "dem_resampling": "bilinear from native DSM to local WGS84 UTM 30m grid",
        "slope_method": "ee.Terrain.slope after explicit local projection; four connected neighbors",
        "coarse_elevation_method": "native DSM reduceResolution(mean), mask/overlap weights, exact native CHELSA projection; no bestEffort",
        "station_utm_crs": {value["station_id"]: value["utm_crs"] for value in values},
        "limitations": ["C11: média de extremos observada não equivale necessariamente à média CHELSA.",
                        "C12: anos válidos observados podem diferir da normal completa 1991–2020.",
                        "Copernicus DSM inclui edificações e vegetação; época 2010–2020; datum da altitude da estação não confirmado.",
                        "z_grade é aproximação via Copernicus agregado, não o DEM original usado pelo CHELSA."],
        "sources": ["https://developers.google.com/earth-engine/datasets/catalog/COPERNICUS_DEM_GLO30_2024_1",
                    "https://developers.google.com/earth-engine/guides/resample",
                    "https://developers.google.com/earth-engine/apidocs/ee-terrain-slope"],
        "attribution": "produced using Copernicus WorldDEM-30 © DLR e.V. 2010-2014 and © Airbus Defence and Space GmbH 2014-2018 provided under COPERNICUS by the European Union and ESA; all rights reserved"}
    safe_path(target.with_suffix(".manifesto.json")).write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Salvo: {target.relative_to(ROOT)}; {len(output)} linhas mensais. Sem exportação ou escrita remota.")


if __name__ == "__main__":
    main()
