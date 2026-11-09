"""Produz tiles experimentais de temperatura de 30 m, por janelas retomáveis.

Usa a grade nacional IBGE/UTM e os modelos atuais. Não declara validação final,
não publica assets e não confunde tiles parciais com cobertura nacional.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path

from affine import Affine
import numpy as np
import pandas as pd
from pyproj import Transformer
import rasterio
from rasterio.features import geometry_mask
from rasterio.io import MemoryFile
from rasterio.windows import Window, transform as window_transform
import requests

from codigo import covariaveis_gee, modelos, mapa_piloto
from codigo.dados_temperatura import safe_path
from codigo.geotiff import validate_grid
from codigo.grade_brasil import digest
from codigo.mapa_piloto import BANDS, fit_development, month_weights

WINDOW_PIXELS = 512  # 15 float32 bands < 32 MiB, limite síncrono do GEE.
LABELS = [f'{m:02d}' for m in range(1, 13)] + ['anual']
LAYERS = {'temperatura_media': ('int16', -32768, .01),
          'dispersao_modelos': ('float32', -9999., 1.),
          'fora_faixa_treino': ('uint8', 255, 1.)}


def predict_window(covariates, transform, crs, inside, estimator, members, development):
    """Mantém nodata onde faltar qualquer covariável, inclusive dentro do país."""
    validate_grid(transform, crs)
    if covariates.shape != (15, *inside.shape) or len(members) < 2:
        raise ValueError('Bandas/dimensões ou conjunto de modelos inválidos.')
    valid = inside & np.isfinite(covariates).all(axis=0)
    if np.any(valid & ((covariates[:12].min(axis=0) < -40) | (covariates[:12].max(axis=0) > 55))):
        raise ValueError('CHELSA fora da faixa física; conferir unidades.')
    if np.any(valid & ((covariates[14] < 0) | (covariates[14] > 90))):
        raise ValueError('Declividade fora da faixa física.')
    arrays = {name: np.full((13, *inside.shape), nodata, dtype=dtype)
              for name, (dtype, nodata, _) in LAYERS.items()}
    if not valid.any():
        return arrays, int(inside.sum()), 0
    row, col = np.where(valid)
    x, y = transform * (col+.5, row+.5)
    lon, lat = Transformer.from_crs(crs, 'EPSG:4326', always_xy=True).transform(x, y)
    features = modelos.feature_columns(development)
    lower, upper = development[features].min(), development[features].max()
    annual = np.zeros(len(row))
    annual_members = np.zeros((len(members), len(row)))
    annual_flag = np.zeros(len(row), dtype=np.uint8)
    for month, weight in enumerate(month_weights(), 1):
        sine, cosine = np.sin(2*np.pi*(month-1)/12), np.cos(2*np.pi*(month-1)/12)
        frame = pd.DataFrame({'latitude': lat, 'longitude': lon, 'month_sin': sine,
            'month_cos': cosine, 'latitude_sin': lat*sine, 'latitude_cos': lat*cosine,
            'dem_elevation_m': covariates[12][valid], 'slope_deg': covariates[14][valid],
            'chelsa_c': covariates[month-1][valid]})[features]
        prediction = estimator.predict(frame) + frame.chelsa_c.to_numpy()
        ensemble = np.stack([member.predict(frame) + frame.chelsa_c.to_numpy() for member in members])
        if not np.isfinite(prediction).all() or not np.isfinite(ensemble).all() or np.max(np.abs(prediction)) > 327.67:
            raise ValueError('Predição não finita ou fora do armazenamento int16.')
        flag = ((frame < lower) | (frame > upper)).any(axis=1).to_numpy().astype(np.uint8)
        arrays['temperatura_media'][month-1][valid] = np.rint(prediction*100).astype(np.int16)
        arrays['dispersao_modelos'][month-1][valid] = ensemble.std(axis=0, ddof=1)
        arrays['fora_faixa_treino'][month-1][valid] = flag
        annual += weight*prediction
        annual_members += weight*ensemble
        annual_flag |= flag
    arrays['temperatura_media'][12][valid] = np.rint(annual*100).astype(np.int16)
    arrays['dispersao_modelos'][12][valid] = annual_members.std(axis=0, ddof=1)
    arrays['fora_faixa_treino'][12][valid] = annual_flag
    return arrays, int(inside.sum()), int(valid.sum())


def download_window(ee, tile, transform, width, height):
    region = ee.Geometry.Rectangle([transform.c, transform.f-height*30,
                                   transform.c+width*30, transform.f],
                                  proj=tile['crs'], geodesic=False)
    image = covariaveis_gee.construir_imagens(region, tile['crs'], list(transform)[:6]).select(BANDS).toFloat().unmask(-9999)
    try:
        url = image.getDownloadURL({'format': 'GEO_TIFF', 'crs': tile['crs'],
                                   'crs_transform': list(transform)[:6], 'dimensions': [width, height]})
        with requests.get(url, timeout=(15, 120), stream=True) as response:
            response.raise_for_status()
            chunks, total = [], 0
            for chunk in response.iter_content(1024*1024):
                total += len(chunk)
                if total > 32*1024*1024:
                    raise ValueError('Janela excedeu 32 MiB.')
                chunks.append(chunk)
    except requests.RequestException:
        raise RuntimeError('Download GEE falhou; URL assinada omitida.') from None
    payload = b''.join(chunks)
    with MemoryFile(payload) as memory, memory.open() as source:
        if (source.count, source.height, source.width) != (15, height, width):
            raise ValueError('Download com dimensões inesperadas.')
        if source.crs != rasterio.crs.CRS.from_string(tile['crs']) or source.transform != transform:
            raise ValueError('Download em grade diferente da solicitada.')
        if any(source.descriptions) and tuple(source.descriptions) != tuple(BANDS):
            raise ValueError('Ordem de bandas divergente.')
        values = source.read(masked=True).astype(float).filled(np.nan)
    values[values == -9999] = np.nan
    return values, hashlib.sha256(payload).hexdigest()


def atomic_json(path, content):
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(content, indent=2), encoding='utf-8')
    temporary.replace(path)


def output_paths(folder, tile_id):
    return {name: [folder / f'{name}_30m_{label}_{tile_id}.tif' for label in LABELS] for name in LAYERS}


def create_outputs(paths, tile, signature):
    validate_grid(Affine(*tile['transform']), tile['crs'])
    for kind, files in paths.items():
        dtype, nodata, scale = LAYERS[kind]
        for label, path in zip(LABELS, files):
            if path.exists():
                with rasterio.open(path) as source:
                    if (source.tags().get('signature') != signature or source.width != tile['width']
                        or source.height != tile['height'] or source.count != 1
                        or source.transform != Affine(*tile['transform'])
                        or source.crs != rasterio.crs.CRS.from_string(tile['crs'])
                        or source.dtypes[0] != dtype or source.nodata != nodata):
                        raise ValueError('Arquivo existente incompatível com esta execução.')
                continue
            with rasterio.open(path, 'w', driver='GTiff', width=tile['width'], height=tile['height'],
                               count=1, dtype=dtype, nodata=nodata, crs=tile['crs'],
                               transform=Affine(*tile['transform']), tiled=True, blockxsize=256,
                               blockysize=256, compress='DEFLATE', BIGTIFF='IF_SAFER') as target:
                target.scales = (scale,)
                target.offsets = (0.,)
                target.set_band_description(1, kind)
                target.set_band_unit(1, '1' if kind == 'fora_faixa_treino' else 'degC')
                target.update_tags(signature=signature, experimental='true', normal_period='1991-2020',
                    month=label, scale_factor=scale, add_offset=0, method='M5_lightgbm/correction',
                    interpretation='experimental_not_validated; SD_not_PI; range_flag_not_AOA',
                    gee_pyramiding_policy='sample' if kind == 'fora_faixa_treino' else 'mean')


def main():
    import ee
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tile', required=True, help='ID em resultados/tabelas/brasil_tiles.csv')
    parser.add_argument('--max-windows', type=int, help='Limite operacional; tile permanece parcial.')
    parser.add_argument('--project')
    parser.add_argument('--input', default='dados/processados/normais_covariaveis.csv')
    args = parser.parse_args()
    if args.max_windows is not None and args.max_windows < 1:
        parser.error('--max-windows deve ser positivo.')
    inventory = json.loads(safe_path('dados/brasil/grade.json').read_text(encoding='utf-8'))
    selected = [tile for tile in inventory['tiles'] if tile['tile_id'] == args.tile]
    if len(selected) != 1:
        parser.error('Tile ausente ou duplicado no inventário.')
    tile = selected[0]
    source = safe_path(args.input)
    provenance = json.loads(source.with_suffix('.manifesto.json').read_text(encoding='utf-8'))
    if provenance['output_sha256'] != digest(source) or provenance['script_sha256'] != digest(covariaveis_gee.__file__):
        raise ValueError('Treino ou helper divergente da extração original.')
    signature_data = {'tile': tile, 'input_sha256': digest(source), 'script_sha256': digest(__file__),
                      'input_manifest_sha256': digest(source.with_suffix('.manifesto.json')),
                      'modelos_sha256': digest(modelos.__file__), 'helper_sha256': digest(covariaveis_gee.__file__),
                      'pilot_helper_sha256': digest(mapa_piloto.__file__),
                      'boundary_sha256': inventory['boundary_sha256'], 'window_pixels': WINDOW_PIXELS}
    signature = hashlib.sha256(json.dumps(signature_data, sort_keys=True).encode()).hexdigest()
    folder = safe_path(f'dados/brasil/temperatura/{tile["tile_id"]}')
    folder.mkdir(parents=True, exist_ok=True)
    state_path = folder / 'manifesto.json'
    paths = output_paths(folder, tile['tile_id'])
    state = {'signature': signature, 'status': 'partial_experimental', 'windows': {},
             'tile_id': tile['tile_id'], 'provenance': signature_data}
    if state_path.exists():
        state = json.loads(state_path.read_text(encoding='utf-8'))
        if state['signature'] != signature:
            raise ValueError('Retomada incompatível: treino, código ou grade mudou.')
        if state['status'].startswith('complete'):
            for filename, expected in state['output_sha256'].items():
                if digest(folder/filename) != expected:
                    raise ValueError('Tile concluído com arquivo alterado.')
            print('Tile concluído e hashes conferidos.')
            return
        if state['windows'] and any(not path.exists() for files in paths.values() for path in files):
            raise ValueError('Retomada perdeu arquivo de uma janela concluída.')
    # Reserva conservadora para um tile; não presume que o país inteiro caiba.
    needed = tile['width']*tile['height']*13*7 + 5*1024**3
    if shutil.disk_usage(folder).free < needed:
        raise RuntimeError('Espaço insuficiente para um tile e margem operacional de 5 GiB.')
    credentials = ee.data.get_persistent_credentials()
    ee.Initialize(credentials=credentials, project=args.project or credentials.quota_project_id or 'mcp-gee')
    ee.data.setDeadline(120000)
    ee.data.setMaxRetries(1)
    for key, asset in [('chelsa_metadata', covariaveis_gee.CHELSA), ('dem_metadata', covariaveis_gee.DEM)]:
        if ee.data.getAsset(asset) != provenance[key]:
            raise ValueError('Fonte remota mudou desde a extração do treino.')
    model, members, development, training = fit_development(
        pd.read_csv(source, dtype={'station_id': str}), 'M5_lightgbm', 'correction')
    state['training'] = training
    atomic_json(state_path, state)
    create_outputs(paths, tile, signature)
    processed = 0
    for row in range(0, tile['height'], WINDOW_PIXELS):
        for col in range(0, tile['width'], WINDOW_PIXELS):
            key = f'{row}_{col}'
            if key in state['windows']:
                continue
            height, width = min(WINDOW_PIXELS, tile['height']-row), min(WINDOW_PIXELS, tile['width']-col)
            window = Window(col, row, width, height)
            transform = window_transform(window, Affine(*tile['transform']))
            inside = geometry_mask([tile['geometry']], (height, width), transform, invert=True)
            entry = {'country_pixels': int(inside.sum()), 'valid_pixels': 0}
            if inside.any():
                values, fingerprint = download_window(ee, tile, transform, width, height)
                arrays, country_count, valid_count = predict_window(values, transform, tile['crs'], inside,
                                                                   model, members, development)
                for kind, files in paths.items():
                    for index, path in enumerate(files):
                        with rasterio.open(path, 'r+') as target:
                            target.write(arrays[kind][index], 1, window=window)
                entry.update(country_pixels=country_count, valid_pixels=valid_count, covariates_sha256=fingerprint)
            state['windows'][key] = entry
            atomic_json(state_path, state)
            processed += 1
            print(f'{tile["tile_id"]}: janela {key}, validos {entry["valid_pixels"]}/{entry["country_pixels"]}', flush=True)
            if args.max_windows and processed >= args.max_windows:
                print('Limite de janelas atingido; estado parcial salvo para retomada.', flush=True)
                return
    state['country_pixels'] = sum(w['country_pixels'] for w in state['windows'].values())
    state['valid_pixels'] = sum(w['valid_pixels'] for w in state['windows'].values())
    state['status'] = ('complete_experimental' if state['valid_pixels'] == state['country_pixels']
                       else 'complete_with_missing_covariates')
    state['output_sha256'] = {path.name: digest(path) for files in paths.values() for path in files}
    state['output_bytes'] = sum(path.stat().st_size for files in paths.values() for path in files)
    atomic_json(state_path, state)
    print(json.dumps({key: state[key] for key in ('status', 'country_pixels', 'valid_pixels', 'output_bytes')}))


if __name__ == '__main__':
    main()
