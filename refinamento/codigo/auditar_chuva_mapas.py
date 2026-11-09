"""Audita arquivos efetivos de chuva e separa janelas parciais de tiles completos."""
import json
import numpy as np
import pandas as pd
import rasterio
from affine import Affine
from rasterio.features import geometry_mask
from rasterio.windows import Window, transform as window_transform
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from codigo.dados_temperatura import safe_path
from codigo.grade_brasil import digest
from codigo.mapa_chuva import LABELS,LAYERS,WINDOW


def main():
    inventory=json.loads(safe_path('dados/brasil/grade.json').read_text(encoding='utf-8'))
    rows=[];max_error=0.;figure_done=False
    for tile in inventory['tiles']:
        folder=safe_path(f'dados/brasil/chuva/{tile["tile_id"]}')
        manifest=folder/'manifesto.json'
        if not manifest.exists():continue
        state=json.loads(manifest.read_text(encoding='utf-8'))
        valid_count=0;files=[]
        for kind,(dtype,nodata) in LAYERS.items():
            for label in LABELS:
                path=folder/f'{kind}_30m_{label}_{tile["tile_id"]}.tif';files.append(path)
                with rasterio.open(path) as source:
                    if (source.dtypes!=(dtype,) or source.nodata!=nodata or source.shape!=(tile['height'],tile['width'])
                        or str(source.crs)!=tile['crs'] or source.transform!=Affine(*tile['transform'])
                        or source.tags().get('signature')!=state['signature']):raise ValueError('GeoTIFF divergente do manifesto.')
                if state['status'].startswith('complete') and digest(path)!=state['output_sha256'][path.name]:
                    raise ValueError('Hash do produto completo divergente.')
        for key,entry in state['windows'].items():
            row,col=map(int,key.split('_'))
            height,width=min(WINDOW,tile['height']-row),min(WINDOW,tile['width']-col)
            window=Window(col,row,width,height)
            inside=geometry_mask([tile['geometry']],(height,width),window_transform(window,Affine(*tile['transform'])),invert=True)
            arrays={}
            for kind in LAYERS:
                values=[]
                for label in LABELS:
                    with rasterio.open(folder/f'{kind}_30m_{label}_{tile["tile_id"]}.tif') as source:
                        values.append(source.read(1,window=window))
                arrays[kind]=np.stack(values)
            masks=[arrays[kind]!=nodata for kind,(_,nodata) in LAYERS.items()]
            valid=masks[0][0]
            if any(not np.array_equal(mask,np.broadcast_to(valid,mask.shape)) for mask in masks):
                raise ValueError('Máscaras divergentes entre meses ou camadas.')
            if np.any(valid&~inside) or valid.sum()!=entry['valid_pixels'] or inside.sum()!=entry['country_pixels']:
                raise ValueError('Contagem/máscara territorial incorreta.')
            if valid.any():
                rain=arrays['precipitacao'].astype(float)
                error=np.abs(rain[12,valid]-rain[:12,valid].sum(axis=0)).max()
                max_error=max(max_error,float(error))
                if error>6.5:raise ValueError('Anual incompatível com soma mensal e quantização.')
                if not np.isfinite(arrays['dispersao_chuva'][:,valid]).all() or np.any(arrays['dispersao_chuva'][:,valid]<0):
                    raise ValueError('Dispersão inválida.')
                if not np.isin(arrays['fora_faixa_chuva'][:,valid],[0,1]).all():raise ValueError('Flag inválida.')
                if not figure_done:
                    fig,ax=plt.subplots(figsize=(7,6))
                    im=ax.imshow(np.where(valid,rain[12],np.nan),cmap='Blues',extent=[0,width*.03,height*.03,0])
                    fig.colorbar(im,ax=ax,label='Precipitação anual (mm)')
                    ax.set_xlabel('Distância leste (km)');ax.set_ylabel('Distância sul (km)')
                    ax.set_title(f'Chuva experimental — janela {key}\n{tile["tile_id"]}; não representa o Brasil completo')
                    fig.tight_layout();fig.savefig(safe_path('resultados/figuras/chuva_primeira_janela.png'),dpi=160);plt.close(fig)
                    figure_done=True
            valid_count+=int(valid.sum())
        rows.append({'tile_id':tile['tile_id'],'status':state['status'],'processed_windows':len(state['windows']),
                     'valid_pixels':valid_count,'output_bytes':sum(p.stat().st_size for p in files)})
    frame=pd.DataFrame(rows)
    frame.to_csv(safe_path('resultados/tabelas/brasil_progresso_chuva.csv'),index=False)
    complete=sum(r['status']=='complete_experimental' for r in rows)
    report={'planned_tiles':len(inventory['tiles']),'complete_rainfall_tiles':complete,
        'partial_rainfall_tiles':sum(r['status']=='partial_experimental' for r in rows),
        'processed_windows':sum(r['processed_windows'] for r in rows),'valid_pixels':sum(r['valid_pixels'] for r in rows),
        'annual_quantization_max_error_mm':max_error,'national_rainfall_complete':complete==len(inventory['tiles']),
        'scientifically_validated_national_product':False}
    safe_path('resultados/tabelas/brasil_auditoria_chuva.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report,indent=2))


if __name__=='__main__':main()
