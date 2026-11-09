from shapely.geometry import box, shape
from shapely.ops import unary_union
from codigo.grade_brasil import tiles_for_geometry
from codigo.geotiff import validate_grid
from affine import Affine
import pytest


def test_crosses_utm_zone_and_equator_without_reusing_curitiba_crs():
    tiles = tiles_for_geometry(box(-48.02, -.02, -47.98, .02), tile_pixels=64)
    assert {x['crs'] for x in tiles} == {'EPSG:32622','EPSG:32623','EPSG:32722','EPSG:32723'}
    assert len({x['tile_id'] for x in tiles}) == len(tiles)
    for tile in tiles:
        validate_grid(Affine(*tile['transform']), tile['crs'])
    for crs in {x['crs'] for x in tiles}:
        pieces = [shape(x['geometry']) for x in tiles if x['crs'] == crs]
        assert sum(p.area for p in pieces) == pytest.approx(unary_union(pieces).area, rel=1e-10)


def test_small_island_is_included_and_empty_tiles_are_excluded():
    tiles = tiles_for_geometry(box(-32.001, -3.001, -32, -3), tile_pixels=4096)
    assert tiles
    assert all(tile['country_area_m2'] > 0 for tile in tiles)
    assert sum(tile['country_area_m2'] for tile in tiles) < 20000
