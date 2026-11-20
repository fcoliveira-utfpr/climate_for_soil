"""Confere a imagem do Brasil calculada no GEE contra o mapa do Paraná produzido localmente.

Recria no GEE (Python) as mesmas contas de gee/brasil_30m.js e amostra pixels sorteados do Paraná na grade
UTM 22S de 30 m do mapa local. Diferenças pequenas são esperadas: o GEE calcula a declividade e o
reamostramento do relevo na própria grade de saída. Uso: python -B -m codigo.conferir_brasil_gee --project ID
"""
import argparse
import json

import numpy as np
import rasterio

from codigo.dados_temperatura import safe_path


def imagens(ee, C):
    col = ee.ImageCollection("COPERNICUS/DEM/GLO30_2024_1").select("DEM")
    dem = col.mosaic().setDefaultProjection(col.first().projection()).resample("bilinear")
    slope = ee.Terrain.slope(dem)
    ll = ee.Image.pixelLonLat()
    tas = ee.Image("projects/fcoliveira/assets/CHELSA/chelsa_brasil_tas_normal_1991_2020").resample("bilinear")
    pr = ee.Image("projects/fcoliveira/assets/CHELSA/chelsa_brasil_pr_normal_1991_2020").resample("bilinear")
    def load(n):
        tab = "arvores_temp" if n.startswith("temp") else "arvores_chuva_" + n.split("_")[1]
        arv = ee.FeatureCollection(f"{C['pasta']}/{tab}").filter(ee.Filter.eq("modelo", n)).aggregate_array("arvore")
        return ee.Classifier.decisionTreeEnsemble(arv).setOutputMode("REGRESSION")
    out = []
    for m in (1, 7):
        ang = 2 * np.pi * (m - 1) / 12
        s, c = float(np.sin(ang)), float(np.cos(ang))
        lat = ll.select("latitude")
        b = {"latitude": lat, "longitude": ll.select("longitude"), "month_sin": ee.Image.constant(s),
             "month_cos": ee.Image.constant(c), "latitude_sin": lat.multiply(s), "latitude_cos": lat.multiply(c),
             "dem_elevation_m": dem, "slope_deg": slope, "chelsa_c": tas.select(f"b{m}")}
        x = ee.Image.cat([b[f].rename(f) for f in C["temp_features"]])
        out.append(x.classify(load("temp_principal"), "p").add(tas.select(f"b{m}")).rename(f"t{m:02d}"))
        logc = pr.select(f"b{m}").add(1).log()
        b = {"latitude": lat, "longitude": ll.select("longitude"), "elevation_30": dem, "slope_30": slope, "chelsa_mm": logc}
        x = ee.Image.cat([b[f].rename(f) for f in C["chuva_features"]])
        sm = C["chuva_smearing"][f"{m:02d}"][0]
        out.append(x.classify(load(f"chuva_{m:02d}_principal"), "p").add(logc).exp().multiply(sm).subtract(1).max(0)
                   .rename(f"p{m:02d}"))
    return ee.Image.cat(out)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", required=True)
    args = parser.parse_args()
    import ee
    ee.Initialize(project=args.project)
    text = safe_path("gee/brasil_30m.js").read_text(encoding="utf-8")
    C = json.loads(text.split("var C = ", 1)[1].split(";\n", 1)[0])
    img = imagens(ee, C)
    rng = np.random.default_rng(11)
    t = rasterio.open(safe_path("dados/parana/saida/parana_temperatura_media_30m.tif"))
    p = rasterio.open(safe_path("dados/parana/saida/parana_chuva_media_30m.tif"))
    feats, local = [], []
    while len(feats) < 200:
        r, c = int(rng.integers(0, t.height)), int(rng.integers(0, t.width))
        w = ((r, r + 1), (c, c + 1))
        tv, pv = t.read((1, 7), window=w)[:, 0, 0], p.read((1, 7), window=w)[:, 0, 0]
        if tv[0] == t.nodata:
            continue
        x, y = t.xy(r, c)
        feats.append(ee.Feature(ee.Geometry.Point([x, y], "EPSG:32722"), {"i": len(local)}))
        local.append([tv[0] / 100, pv[0], tv[1] / 100, pv[1]])
    tr = list(t.transform)[:6]
    res = img.sampleRegions(ee.FeatureCollection(feats), scale=30, projection=ee.Projection("EPSG:32722", tr),
                            geometries=False).getInfo()["features"]
    local = np.array(local)
    g = np.array([[f["properties"][k] for k in ("t01", "p01", "t07", "p07")] for f in res])
    idx = [f["properties"]["i"] for f in res]
    d = g - local[idx]
    rep = {}
    for j, nome in enumerate(("temperatura_jan_C", "chuva_jan_mm", "temperatura_jul_C", "chuva_jul_mm")):
        rep[nome] = {"pixels": len(idx), "dif_media": float(d[:, j].mean()), "dif_abs_mediana": float(np.median(np.abs(d[:, j]))),
                     "dif_abs_p95": float(np.quantile(np.abs(d[:, j]), 0.95)), "dif_abs_max": float(np.abs(d[:, j]).max())}
    safe_path("resultados/tabelas/brasil_gee_x_parana.json").write_text(json.dumps(rep, indent=2), encoding="utf-8")
    print(json.dumps(rep, indent=2))


if __name__ == "__main__":
    main()
