"""Inventário nacional de tiles métricos por zona UTM e hemisfério (IBGE).

Nenhum retângulo envolvente é tratado como território. Cada tile conserva a
interseção com o país e sua zona; a máscara é aplicada na produção por pixel.
"""
from __future__ import annotations

import hashlib
import json
import math
import shutil
from datetime import datetime, timezone

import pandas as pd
from pyproj import Transformer
import requests
from shapely import segmentize
from shapely.geometry import box, mapping, shape
from shapely.ops import transform, unary_union

from codigo.dados_temperatura import safe_path

BOUNDARY_URL = ('https://servicodados.ibge.gov.br/api/v3/malhas/paises/BR'
                '?formato=application/vnd.geo+json&qualidade=maxima&intrarregiao=UF')
BOUNDARY = 'dados/brasil/limites_uf_ibge.geojson'
TILE_PIXELS = 4096
RESOLUTION = 30


def digest(path):
    with open(path, 'rb') as handle:
        return hashlib.file_digest(handle, 'sha256').hexdigest()


def boundary():
    path = safe_path(BOUNDARY)
    if not path.exists():
        response = requests.get(BOUNDARY_URL, timeout=(15, 60))
        response.raise_for_status()
        content = response.json()
        if len(content.get('features', [])) != 27:
            raise ValueError('A malha deve conter 27 UFs.')
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(content), encoding='utf-8')
    content = json.loads(path.read_text(encoding='utf-8'))
    if len(content.get('features', [])) != 27:
        raise ValueError('Cache da malha não contém 27 UFs.')
    geometry = unary_union([shape(f['geometry']) for f in content['features']])
    if geometry.is_empty or not geometry.is_valid:
        raise ValueError('Geometria nacional vazia/inválida.')
    return geometry


def tiles_for_geometry(country, tile_pixels=TILE_PIXELS):
    if not isinstance(tile_pixels, int) or tile_pixels < 1:
        raise ValueError('Dimensão de tile deve ser inteiro positivo.')
    size = tile_pixels * RESOLUTION
    west, south, east, north = country.bounds
    first = max(1, int(math.floor((west + 180) / 6)) + 1)
    last = min(60, int(math.floor((east + 180) / 6)) + 1)
    tiles = []
    for zone in range(first, last + 1):
        for hemisphere, lat_min, lat_max, epsg in [('S', -80, 0, 32700), ('N', 0, 84, 32600)]:
            clip = country.intersection(box(-180 + 6*(zone-1), lat_min, -180 + 6*zone, lat_max))
            if clip.is_empty or clip.area == 0:
                continue
            crs = f'EPSG:{epsg + zone}'
            project = Transformer.from_crs('EPSG:4326', crs, always_xy=True)
            # Densificar meridianos/limites antes de projetar evita cordas longas.
            projected = transform(project.transform, segmentize(clip, .01))
            left, bottom, right, top = projected.bounds
            for col in range(math.floor(left/size), math.ceil(right/size)):
                for row in range(math.floor(bottom/size), math.ceil(top/size)):
                    xmin, ymin = col*size, row*size
                    piece = projected.intersection(box(xmin, ymin, xmin+size, ymin+size))
                    if piece.is_empty or piece.area == 0:
                        continue
                    tiles.append({'tile_id': f'utm{zone:02d}{hemisphere}_{col}_{row}',
                                  'crs': crs, 'width': tile_pixels, 'height': tile_pixels,
                                  'transform': [30, 0, xmin, 0, -30, ymin+size],
                                  'country_area_m2': float(piece.area), 'geometry': mapping(piece)})
    return sorted(tiles, key=lambda tile: tile['tile_id'])


def main():
    country = boundary()
    tiles = tiles_for_geometry(country)
    private = safe_path('dados/brasil/grade.json')
    document = {'boundary_url': BOUNDARY_URL, 'boundary_sha256': digest(safe_path(BOUNDARY)),
                'script_sha256': digest(__file__), 'pixel_size_m': RESOLUTION,
                'tile_pixels': TILE_PIXELS, 'tiles': tiles}
    private.write_text(json.dumps(document), encoding='utf-8')
    pd.DataFrame([{k: v for k, v in tile.items() if k != 'geometry'} for tile in tiles]).to_csv(
        safe_path('resultados/tabelas/brasil_tiles.csv'), index=False)
    pixels = sum(tile['country_area_m2'] for tile in tiles) / 900
    # Por variável e período: temperatura/chuva int16/uint16 + SD float32 + flag uint8.
    summary = {'created_utc': datetime.now(timezone.utc).isoformat(),
               'status': 'inventory_only_no_national_maps_generated', 'tiles': len(tiles),
               'utm_crs': sorted({tile['crs'] for tile in tiles}),
               'estimated_country_pixels': round(pixels),
               'uncompressed_climate_only_bytes': round(pixels*13*2*2),
               'uncompressed_with_auxiliary_bytes': round(pixels*13*2*7),
               'uncompressed_temperature_annual_with_auxiliary_bytes': round(pixels*7),
               'free_bytes': shutil.disk_usage(private.parent).free,
               'inventory_sha256': digest(private), 'boundary_sha256': document['boundary_sha256'],
               'boundary_url': BOUNDARY_URL,
               'limitations': ['Bytes por pixels do territorio; headers, margens de tiles e caches adicionais.',
                               'Tamanho comprimido depende de teste real; nao pressuposto.',
                               'Malha API IBGE; fronteira nao certificada a 30 m.',
                               'UTM por zona/hemisferio; nao aplicar CRS de Curitiba ao pais inteiro.',
                               'Inventario nao demonstra cobertura climatica nem valida modelos.']}
    safe_path('resultados/tabelas/brasil_capacidade.json').write_text(json.dumps(summary, indent=2), encoding='utf-8')
    print(json.dumps({k: v for k, v in summary.items() if k not in ('limitations', 'utm_crs')}, indent=2))


if __name__ == '__main__':
    main()
