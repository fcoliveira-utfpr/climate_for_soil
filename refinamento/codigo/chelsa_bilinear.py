"""C10: CHELSA reamostrado por interpolação bilinear, para tirar os degraus de 1 km dos mapas.

Os mapas mostravam degraus nas bordas das células do CHELSA porque a covariável era copiada para
30 m pelo vizinho mais próximo. Interpolar o CHELSA (uma covariável de grade) não é interpolar
estações, então continua dentro da regra do projeto. Para manter treino e mapa coerentes, o valor
bilinear também é extraído nas estações (no pixel de 30 m da estação, na zona UTM dela) e os
modelos são comparados com as duas versões nas mesmas dobras.

Subcomandos (de dentro de refinamento/):
  python -B -m codigo.chelsa_bilinear extrair --project ID   (GEE, só leitura)
  python -B -m codigo.chelsa_bilinear comparar               (local, validação espacial)
"""
import argparse
import json
import os

import numpy as np
import pandas as pd
from sklearn.model_selection import GridSearchCV, GroupKFold

from codigo import covariaveis_gee, modelos, modelos_chuva
from codigo.covariaveis_chuva_gee import SOURCES
from codigo.dados_temperatura import safe_path
from codigo.grade_brasil import digest

OUTPUT = "dados/brasil/chelsa_bilinear_estacoes.csv"
TEMP_INPUT = "dados/brasil/normais_covariaveis_20261106.csv"
MONTHS = [f"b{m}" for m in range(1, 13)]


def ativo():
    """A versão bilinear vale quando CHELSA_BILINEAR=1 (usado pela calibração, pelo preparo e pelo teste)."""
    return os.environ.get("CHELSA_BILINEAR", "0") == "1"


def aplicar(frame, variable):
    """Troca a covariável CHELSA pela versão bilinear extraída nas estações."""
    table = pd.read_csv(safe_path(OUTPUT), dtype={"station_id": str})
    column, source = ("chelsa_c", "tas_bilinear_c") if variable == "temperatura" else ("chelsa_mm", "pr_bilinear_mm")
    merged = frame.drop(columns=[column]).merge(table[["station_id", "month", source]].rename(columns={source: column}),
                                               on=["station_id", "month"], how="left", validate="many_to_one")
    if merged[column].isna().any():
        raise ValueError("Estação sem CHELSA bilinear; rode a extração de novo.")
    return merged[frame.columns]


def extrair(args):
    import ee
    ee.Initialize(project=args.project)
    temp = pd.read_csv(safe_path(TEMP_INPUT), dtype={"station_id": str})
    rain, _ = modelos_chuva.prepare()
    stations = pd.concat([temp[["station_id", "latitude", "longitude"]], rain[["station_id", "latitude", "longitude"]]])
    stations = stations.drop_duplicates("station_id").reset_index(drop=True)
    tas = ee.Image(covariaveis_gee.CHELSA).select(MONTHS).rename([f"tas_{m:02d}" for m in range(1, 13)]).resample("bilinear")
    pr = ee.Image(SOURCES["chelsa"]).select(MONTHS).rename([f"pr_{m:02d}" for m in range(1, 13)]).resample("bilinear")
    image = tas.addBands(pr)
    stations["crs"] = [covariaveis_gee.utm_crs(lat, lon) for lat, lon in zip(stations.latitude, stations.longitude)]
    records = []
    for crs, group in stations.groupby("crs"):
        for start in range(0, len(group), 400):
            part = group.iloc[start:start + 400]
            points = ee.FeatureCollection([ee.Feature(ee.Geometry.Point([float(r.longitude), float(r.latitude)]),
                                                      {"station_id": r.station_id}) for r in part.itertuples()])
            sampled = image.reduceRegions(collection=points, reducer=ee.Reducer.first(), crs=crs, scale=30).getInfo()
            for feature in sampled["features"]:
                props = feature["properties"]
                for m in range(1, 13):
                    records.append({"station_id": props["station_id"], "month": m,
                                    "tas_bilinear_c": props.get(f"tas_{m:02d}"), "pr_bilinear_mm": props.get(f"pr_{m:02d}")})
            print(f"{crs}: {min(start + 400, len(group))}/{len(group)} estações", flush=True)
    table = pd.DataFrame(records).sort_values(["station_id", "month"])
    path = safe_path(OUTPUT)
    table.to_csv(path, index=False)
    manifest = {"assets": {"tas": covariaveis_gee.CHELSA, "pr": SOURCES["chelsa"]},
                "asset_metadata": {"tas": ee.data.getAsset(covariaveis_gee.CHELSA), "pr": ee.data.getAsset(SOURCES["chelsa"])},
                "resampling": "bilinear in native CHELSA grid; sampled at the station 30 m pixel in its UTM zone",
                "stations": int(table.station_id.nunique()), "missing": int(table[["tas_bilinear_c", "pr_bilinear_mm"]].isna().sum().sum()),
                "output_sha256": digest(path), "script_sha256": digest(__file__), "project": args.project}
    path.with_suffix(".json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps({k: manifest[k] for k in ("stations", "missing")}))


def _cv_temperature(data):
    held = modelos.reserve_test(data)
    development = data.loc[~held].reset_index(drop=True)
    features = modelos.feature_columns(development)
    groups = modelos.spatial_blocks(development, 2)
    rows = []
    for repeat in range(3):
        for fold, (a, b) in enumerate(GroupKFold(n_splits=5, shuffle=True, random_state=42 + repeat).split(development, groups=groups)):
            train, test = development.iloc[a], development.iloc[b]
            estimator, parameters = modelos.model_candidates(42 + repeat)["M5_lightgbm"]
            search = GridSearchCV(estimator, parameters, cv=GroupKFold(n_splits=3), scoring="neg_root_mean_squared_error", n_jobs=1)
            search.fit(train[features], train.temperature_c - train.chelsa_c, groups=groups[a])
            rows.append(test[["station_id", "month", "temperature_c"]].assign(
                block=groups[b], repeat=repeat, fold=fold, prediction=search.predict(test[features]) + test.chelsa_c.to_numpy()))
    return pd.concat(rows, ignore_index=True)


def _cv_rain(data):
    from codigo.incerteza_aplicabilidade import RAIN_MONTH_FEATURES, rain_month_fit
    development = data.loc[~data.reserved].reset_index(drop=True)
    groups = modelos.spatial_blocks(development, 2)
    rows = []
    for repeat in range(3):
        for fold, (a, b) in enumerate(GroupKFold(n_splits=5, shuffle=True, random_state=42 + repeat).split(development, groups=groups)):
            train, test = development.iloc[a], development.iloc[b]
            for month in range(1, 13):
                source, target = train[train.month == month], test[test.month == month]
                model = rain_month_fit(source, modelos.spatial_blocks(source, 2), 42 + repeat)
                rows.append(target[["station_id", "month", "precipitation_mm"]].assign(
                    block=modelos.spatial_blocks(target, 2), repeat=repeat, fold=fold,
                    prediction=model.predict(target[RAIN_MONTH_FEATURES])))
    return pd.concat(rows, ignore_index=True).rename(columns={"precipitation_mm": "temperature_c"})


def comparar(args):
    temp = modelos.prepare(pd.read_csv(safe_path(TEMP_INPUT), dtype={"station_id": str}))
    rain, _ = modelos_chuva.prepare()
    outputs = {}
    for variable, data, runner, unit in (("temperatura", temp, _cv_temperature, "degC"), ("chuva", rain, _cv_rain, "mm")):
        near = runner(data).assign(method="CHELSA_vizinho")
        bil = runner(aplicar(data, variable)).assign(method="CHELSA_bilinear")
        both = pd.concat([near, bil], ignore_index=True)
        diff = modelos.paired_intervals(both, reference_method="CHELSA_vizinho")
        rmse = both.groupby(["method", "repeat"]).apply(
            lambda f: float(np.sqrt(np.mean((f.prediction - f.temperature_c) ** 2))), include_groups=False).groupby("method").mean()
        diff.assign(rmse_medio=diff.method.map(rmse), unit=unit).to_csv(
            safe_path(f"resultados/tabelas/c10_chelsa_bilinear_{variable}.csv"), index=False)
        outputs[variable] = diff.assign(rmse_medio=diff.method.map(rmse)).round(4).to_dict("records")
        print(variable, diff.assign(rmse_medio=diff.method.map(rmse)).round(4).to_string(index=False), flush=True)
    safe_path("resultados/tabelas/c10_chelsa_bilinear.json").write_text(json.dumps(
        {"results": outputs, "input_sha256": digest(safe_path(OUTPUT)), "script_sha256": digest(__file__),
         "rule": "adotar bilinear se o intervalo da diferença incluir zero ou for negativo"}, indent=2), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("extrair")
    p.add_argument("--project", required=True)
    sub.add_parser("comparar")
    args = parser.parse_args()
    {"extrair": extrair, "comparar": comparar}[args.command](args)


if __name__ == "__main__":
    main()
