"""O contrato do GeoTIFF é verificado com pixels conhecidos, sem dados climáticos."""

import numpy as np
import pytest
import rasterio
from affine import Affine

from codigo.geotiff import ROOT, inspect_geotiff, write_temperature_geotiff


GRID = Affine(30, 0, 300000, 0, -30, 7500000)


def write(path, values=None, transform=GRID, crs="EPSG:31983"):
    return write_temperature_geotiff(
        path, np.array([[20.126, -4.3]]) if values is None else values,
        transform, crs, period="1991-2020; mes=01", method="teste_sintetico",
    )


def test_roundtrip_values_and_metadata(tmp_path):
    path = write(tmp_path / "temperatura.tiff")
    with rasterio.open(path) as source:
        np.testing.assert_array_equal(source.read(1), [[2013, -430]])
        np.testing.assert_allclose(source.read(1) * source.scales[0], [[20.13, -4.3]])
        assert source.dtypes == ("int16",)
        assert source.scales == (0.01,)
        assert source.offsets == (0.0,)
        assert source.nodata == -32768
        assert source.transform == GRID
        assert source.res == (30.0, 30.0)
        assert source.crs.to_epsg() == 31983
        assert source.compression.name.lower() == "deflate"
        assert source.units == ("degC",)
        assert source.tags()["experimental"] == "true"
        assert source.tags()["period"] == "1991-2020; mes=01"
        assert source.tags(1)["method"] == "teste_sintetico"
        assert source.tags()["cog"] == "false"
    assert inspect_geotiff(path)["resolution"] == [30.0, 30.0]


def test_nodata_mask_preserves_zero_and_masked_pixels(tmp_path):
    data = np.ma.array([[0.0, np.nan, np.inf, 12.0]], mask=[[False, False, False, True]])
    path = write(tmp_path / "masked.tif", data)
    with rasterio.open(path) as source:
        np.testing.assert_array_equal(source.read(1), [[0, -32768, -32768, -32768]])
        np.testing.assert_array_equal(source.read(1, masked=True).mask, [[False, True, True, True]])


@pytest.mark.parametrize("crs", ["EPSG:4326", "EPSG:2263"])
def test_rejects_degrees_and_feet(tmp_path, crs):
    with pytest.raises(ValueError, match="CRS|metros"):
        write(tmp_path / "invalid.tif", crs=crs)
    assert not (tmp_path / "invalid.tif").exists()


@pytest.mark.parametrize("transform", [
    Affine(90, 0, 300000, 0, -90, 7500000),
    Affine(30, 1, 300000, 0, -30, 7500000),
    Affine(30, 0, 300001, 0, -30, 7500000),
    Affine(30, 0, 300000, 0, 30, 7500000),
])
def test_rejects_wrong_grid(tmp_path, transform):
    with pytest.raises(ValueError, match="grade|origem"):
        write(tmp_path / "invalid.tif", transform=transform)


@pytest.mark.parametrize("value", [327.68, -327.68, 1e308])
def test_overflow_and_reserved_nodata_rejected(tmp_path, value):
    with pytest.raises(ValueError, match="int16"):
        write(tmp_path / "overflow.tif", np.array([[value]]))


def test_cannot_write_outside_refinamento():
    with pytest.raises(ValueError, match="refinamento"):
        write(ROOT.parent / "never_created.tif")


def test_existing_file_not_overwritten(tmp_path):
    path = write(tmp_path / "preserved.tif")
    with pytest.raises(FileExistsError):
        write(path, np.array([[99.0]]))
    with rasterio.open(path) as source:
        np.testing.assert_array_equal(source.read(1), [[2013, -430]])
