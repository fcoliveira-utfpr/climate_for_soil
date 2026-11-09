"""Testes das peças novas de 08/11/2026 (sem depender dos dados cedidos)."""
import numpy as np
import pandas as pd
import pytest
from affine import Affine
from shapely.geometry import box

from codigo import homogeneidade, incerteza_aplicabilidade as ia, mapa_parana, mx_completo


def test_bearing_points_north_east_south():
    assert mx_completo.bearing(0, 0, 1, 0) == pytest.approx(0, abs=1e-9)
    assert mx_completo.bearing(0, 0, 0, 1) == pytest.approx(np.pi / 2, abs=1e-9)
    assert abs(mx_completo.bearing(0, 0, -1, 0)) == pytest.approx(np.pi, abs=1e-9)


def _rain_frame(points, values):
    rows = []
    for month in range(1, 13):
        for (lat, lon), value in zip(points, values):
            rows.append({"latitude": lat, "longitude": lon, "month": month, "precipitation_mm": value})
    return pd.DataFrame(rows)


def test_adw_reduces_weight_of_clustered_stations():
    # Três estações juntas ao norte (valor 10) e uma isolada ao sul (valor 100), à mesma distância.
    points = [(1.0, 0.0), (1.0, 0.01), (1.0, -0.01), (-1.0, 0.0), (0.0, 1.0)]
    values = [10, 10, 10, 100, 50]
    train = _rain_frame(points, values)
    test = _rain_frame([(0.0, 0.0)], [0])
    idw, adw = mx_completo.mx_rain(train, test, cdd=300.0)
    # O termo angular favorece a estação isolada: o ADW fica acima do IDW.
    assert adw[0] > idw[0]
    assert np.allclose(idw, idw[0]) and np.allclose(adw, adw[0])


def test_gamma_from_pairs_recovers_known_gradient():
    pairs = pd.DataFrame({"first": [f"a{i}" for i in range(40)], "second": [f"b{i}" for i in range(40)],
                          "dz": np.linspace(-500, 500, 40)})
    for m in range(1, 13):
        pairs[f"dt_{m:02d}"] = -0.006 * pairs.dz
    pooled, monthly, n = mx_completo.gamma_from_pairs(pairs, excluded={"a0"})
    assert n == 39 and pooled == pytest.approx(-0.006) and np.allclose(monthly, -0.006)


def test_pettitt_and_snht_find_step():
    rng = np.random.default_rng(0)
    series = np.r_[rng.normal(0, 0.1, 15), rng.normal(1.0, 0.1, 15)]
    position, p = homogeneidade.pettitt(series)
    k, statistic = homogeneidade.snht(series)
    assert position == 14 and p < 0.01
    assert k == 15 and statistic > homogeneidade.snht_critical(30)


def test_snht_has_no_empty_segment():
    series = np.r_[5.0, np.zeros(19)]
    k, _ = homogeneidade.snht(series)
    assert 1 <= k <= len(series) - 1


def test_conformal_quantile_finite_sample_rank():
    values = np.arange(1, 11)  # 10 valores
    assert ia.conformal_quantile(values, 0.9) == 10  # ceil(11 × 0,9) = 10
    assert ia.conformal_quantile(values, 0.5) == 6


def test_aoa_threshold_and_dissimilarity_flag_far_points():
    rng = np.random.default_rng(1)
    z_train = rng.normal(size=(200, 3))
    folds = np.arange(200) % 5
    mean_distance, threshold = ia.aoa_threshold(z_train, folds)
    near = ia.dissimilarity(z_train, z_train[:5] + 1e-3, mean_distance)
    far = ia.dissimilarity(z_train, np.full((1, 3), 25.0), mean_distance)
    assert np.all(near < threshold) and far[0] > threshold


def test_parana_grid_is_metric_and_aligned():
    polygon = box(500000, 7100000, 560000, 7150000)
    grid = mapa_parana.build_grid(polygon)
    transform = Affine(*grid["transform"])
    assert transform.a == 30 and transform.e == -30
    assert transform.c % 30 == 0 and transform.f % 30 == 0
    minx, miny, maxx, maxy = polygon.bounds
    assert transform.c <= minx and transform.c + grid["width"] * 30 >= maxx
    assert transform.f >= maxy and transform.f - grid["height"] * 30 <= miny
    assert grid["width"] - (maxx - minx) / 30 < 2 and grid["height"] - (maxy - miny) / 30 < 2
    assert all(h <= 512 and w <= 512 for _, _, h, w in grid["windows"])
    covered = sum(h * w for _, _, h, w in grid["windows"])
    assert covered == grid["width"] * grid["height"]


def test_window_transform_offsets():
    grid = {"transform": [30, 0, 600000, 0, -30, 7200000]}
    t = mapa_parana.window_transform(grid, 512, 1024)
    assert (t.c, t.f) == (600000 + 1024 * 30, 7200000 - 512 * 30)


def test_pacote_parana_keeps_nodata_for_uint8_and_uint16(tmp_path, monkeypatch):
    import rasterio
    from codigo import pacote_gee_parana as pacote
    profile = {"driver": "GTiff", "width": 4, "height": 3, "count": 13, "crs": "EPSG:32722",
               "transform": Affine(30, 0, 600000, 0, -30, 7200000)}
    layers = [("int16", -32768, 2150), ("uint16", 65535, 80), ("uint8", 255, 1)]
    sources = []
    for i, (dtype, nodata, value) in enumerate(layers):
        data = np.full((13, 3, 4), value, dtype=dtype)
        data[:, 0, 0] = nodata  # pixel fora do estado
        path = tmp_path / f"camada{i}.tif"
        with rasterio.open(path, "w", dtype=dtype, nodata=nodata, **profile) as out:
            out.write(data)
        sources.append(path)
    target = tmp_path / "pacote"
    target.mkdir()
    monkeypatch.setattr(pacote, "TARGET", str(target))
    path = pacote.write_part("temperatura", sources, 0, 4, "teste.tif")
    with rasterio.open(path) as result:
        values = result.read()
    assert values.dtype == np.int16 and values.shape[0] == 39
    assert np.all(values[:, 0, 0] == -32768)  # nodata em todas as bandas, inclusive as uint8
    assert np.all(values[:13, 1, 1] == 2150) and np.all(values[13:26, 1, 1] == 80) and np.all(values[26:, 1, 1] == 1)
    pacote.verify(sources, [path], n=12)
