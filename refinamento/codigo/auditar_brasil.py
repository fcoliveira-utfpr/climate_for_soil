"""Audita progresso real dos tiles sem confundir arquivos parciais com entrega."""
import json
import numpy as np
import pandas as pd
import rasterio
from rasterio.features import geometry_mask
from rasterio.windows import Window, transform as window_transform
from affine import Affine
from codigo.dados_temperatura import safe_path
from codigo.grade_brasil import digest
from codigo.mapa_brasil import output_paths, WINDOW_PIXELS
from codigo.mapa_piloto import month_weights


def main():
    inventory = json.loads(safe_path('dados/brasil/grade.json').read_text(encoding='utf-8'))
    rows = []
    for tile in inventory['tiles']:
        folder = safe_path(f'dados/brasil/temperatura/{tile["tile_id"]}')
        manifest = folder/'manifesto.json'
        row = {'tile_id':tile['tile_id'],'status':'not_started','windows_processed':0,
               'valid_pixels':0,'output_bytes':0,'annual_quantization_max_error_c':0.}
        if manifest.exists():
            state = json.loads(manifest.read_text(encoding='utf-8'))
            paths = output_paths(folder,tile['tile_id'])
            if state['status'].startswith('complete'):
                for filename,expected in state['output_sha256'].items():
                    if digest(folder/filename) != expected:
                        raise ValueError('Hash de tile concluído divergente.')
            annual_path = paths['temperatura_media'][12]
            valid_total, outside, max_error = 0, 0, 0.
            with rasterio.open(annual_path) as source:
                if source.scales != (.01,) or source.transform != Affine(*tile['transform']):
                    raise ValueError('Escala/grade anual divergente.')
                for _,window in source.block_windows(1):
                    raster = source.read(1,window=window,masked=True)
                    valid = ~np.ma.getmaskarray(raster)
                    valid_total += int(valid.sum())
                    if valid.any():
                        inside = geometry_mask([tile['geometry']],raster.shape,
                            window_transform(window,source.transform),invert=True)
                        outside += int((valid & ~inside).sum())
            for key, detail in state['windows'].items():
                if not detail['valid_pixels']:
                    continue
                r,c = map(int,key.split('_'))
                window = Window(c,r,min(WINDOW_PIXELS,tile['width']-c),min(WINDOW_PIXELS,tile['height']-r))
                arrays = []
                for path in paths['temperatura_media']:
                    with rasterio.open(path) as source:
                        arrays.append(source.read(1,window=window,masked=True)*.01)
                if any(not np.array_equal(np.ma.getmaskarray(x),np.ma.getmaskarray(arrays[0])) for x in arrays):
                    raise ValueError('Máscaras mensais/anuais divergentes.')
                difference = np.abs(arrays[12]-sum(w*x for w,x in zip(month_weights(),arrays[:12])))
                max_error = max(max_error,float(difference.max()))
            if valid_total != sum(w['valid_pixels'] for w in state['windows'].values()) or outside or max_error > .010001:
                raise ValueError('Contagem, máscara territorial ou anual inconsistente.')
            row.update(status=state['status'],windows_processed=len(state['windows']),valid_pixels=valid_total,
                       output_bytes=sum(path.stat().st_size for files in paths.values() for path in files),
                       annual_quantization_max_error_c=max_error)
        rows.append(row)
    table = pd.DataFrame(rows)
    table.to_csv(safe_path('resultados/tabelas/brasil_progresso_temperatura.csv'),index=False)
    report = {'planned_tiles':len(rows),'complete_temperature_tiles':int(table.status.eq('complete_experimental').sum()),
              'partial_temperature_tiles':int(table.status.eq('partial_experimental').sum()),
              'tiles_with_missing_covariates':int(table.status.eq('complete_with_missing_covariates').sum()),
              'processed_windows':int(table.windows_processed.sum()),'valid_temperature_pixels':int(table.valid_pixels.sum()),
              'output_bytes':int(table.output_bytes.sum()),'national_temperature_complete':bool(table.status.eq('complete_experimental').all()),
              'rainfall_maps_produced':False,'scientifically_validated_national_product':False,
              'annual_quantization_max_error_c':float(table.annual_quantization_max_error_c.max())}
    safe_path('resultados/tabelas/brasil_auditoria_producao.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report,indent=2))


if __name__=='__main__':
    main()
