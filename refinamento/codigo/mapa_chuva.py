"""Primeira produção de chuva na grade nacional: janelas retomáveis, experimental."""
import argparse
import hashlib
import json
import shutil
import numpy as np
import pandas as pd
import requests
import rasterio
from rasterio.io import MemoryFile
from rasterio.features import geometry_mask
from rasterio.windows import Window, transform as window_transform
from affine import Affine
from pyproj import Transformer
from sklearn.model_selection import GroupKFold, GridSearchCV
from codigo import modelos_chuva, estimadores_adicionais, modelos
from codigo.modelos_chuva import RainRegressor, prepare
from codigo.covariaveis_chuva_gee import SOURCES
from codigo.covariaveis_gee import DEM
from codigo.dados_temperatura import safe_path
from codigo.grade_brasil import digest
from codigo.geotiff import validate_grid

LABELS = [f'{m:02d}' for m in range(1,13)] + ['anual']
FEATURES = ['latitude','longitude','elevation_30','slope_30','month_sin','month_cos','chelsa_mm']
LAYERS = {'precipitacao': ('uint16',65535), 'dispersao_chuva': ('float32',-9999.),
          'fora_faixa_chuva': ('uint8',255)}
WINDOW = 512


def predict(cov, transform, crs, inside, model, members, development):
    validate_grid(transform, crs)
    if cov.shape != (14,*inside.shape) or len(members)<2:
        raise ValueError('Dimensões ou ensemble inválidos.')
    valid = inside & np.isfinite(cov).all(axis=0)
    if np.any(cov[:12,valid]<0) or np.any(cov[13,valid]<0) or np.any(cov[13,valid]>90):
        raise ValueError('Covariáveis fora da faixa física.')
    arrays = {kind:np.full((13,*inside.shape),nodata,dtype=dtype) for kind,(dtype,nodata) in LAYERS.items()}
    if not valid.any(): return arrays, 0
    row,col = np.where(valid)
    x,y = transform @ (col+.5,row+.5)
    lon,lat = Transformer.from_crs(crs,'EPSG:4326',always_xy=True).transform(x,y)
    lower,upper = development[FEATURES].min(),development[FEATURES].max()
    annual = np.zeros(len(row)); annual_members = np.zeros((len(members),len(row)))
    annual_flag = np.zeros(len(row),dtype=np.uint8)
    for month in range(1,13):
        angle = 2*np.pi*(month-1)/12
        frame = pd.DataFrame({'latitude':lat,'longitude':lon,'elevation_30':cov[12,valid],
            'slope_30':cov[13,valid],'month_sin':np.sin(angle),'month_cos':np.cos(angle),
            'chelsa_mm':cov[month-1,valid]})[FEATURES]
        values = model.predict(frame)
        ensemble = np.stack([member.predict(frame) for member in members])
        if (not np.isfinite(values).all() or not np.isfinite(ensemble).all()
            or np.any(values<0) or np.any(ensemble<0) or np.any(np.rint(values)>=65535)):
            raise ValueError('Predição inválida ou excede uint16; nada deve ser truncado.')
        flag = ((frame<lower)|(frame>upper)).any(axis=1).to_numpy().astype(np.uint8)
        arrays['precipitacao'][month-1,valid] = np.rint(values).astype(np.uint16)
        arrays['dispersao_chuva'][month-1,valid] = ensemble.std(axis=0,ddof=1)
        arrays['fora_faixa_chuva'][month-1,valid] = flag
        annual += values; annual_members += ensemble; annual_flag |= flag
    if np.any(np.rint(annual)>=65535): raise ValueError('Anual excede uint16.')
    arrays['precipitacao'][12,valid] = np.rint(annual).astype(np.uint16)
    arrays['dispersao_chuva'][12,valid] = annual_members.std(axis=0,ddof=1)
    arrays['fora_faixa_chuva'][12,valid] = annual_flag
    return arrays,int(valid.sum())


def fit(data):
    development = data.loc[~data.reserved].reset_index(drop=True)
    groups = modelos.spatial_blocks(development,2)
    def fit_one(frame, blocks):
        search = GridSearchCV(RainRegressor(method='M5',formulation='correction'),
            {'complexity':[7,15]},cv=GroupKFold(n_splits=3),scoring='neg_root_mean_squared_error',
            n_jobs=1,error_score='raise')
        search.fit(frame[FEATURES],frame.precipitation_mm,groups=blocks)
        return search.best_estimator_
    model = fit_one(development,groups)
    members = [fit_one(development.iloc[a],groups[a]) for a,_ in
               GroupKFold(n_splits=5,shuffle=True,random_state=42).split(development,groups=groups)]
    return model,members,development


def download(ee, tile, transform, width, height):
    region = ee.Geometry.Rectangle([transform.c,transform.f-height*30,transform.c+width*30,transform.f],
                                  proj=tile['crs'],geodesic=False)
    collection = ee.ImageCollection(DEM).filterBounds(region.buffer(3000)).select('DEM')
    native = collection.mosaic().setDefaultProjection(ee.Image(collection.first()).projection())
    fine = native.resample('bilinear').reproject(crs=tile['crs'],crsTransform=[30,0,0,0,-30,0])
    image = ee.Image(SOURCES['chelsa']).select([f'b{i}' for i in range(1,13)]).addBands([
        fine.rename('elevation_30'),ee.Terrain.slope(fine).rename('slope_30')]).toFloat().unmask(-9999)
    url = image.getDownloadURL({'format':'GEO_TIFF','crs':tile['crs'],
        'crs_transform':list(transform)[:6],'dimensions':[width,height]})
    try:
        with requests.get(url,timeout=(15,120),stream=True) as response:
            response.raise_for_status(); parts=[]; size=0
            for part in response.iter_content(1024*1024):
                size+=len(part)
                if size>32*1024**2: raise ValueError('Download excedeu 32 MiB.')
                parts.append(part)
    except requests.RequestException:
        raise RuntimeError('Download falhou; URL assinada omitida.') from None
    payload=b''.join(parts)
    with MemoryFile(payload) as memory, memory.open() as source:
        if source.shape!=(height,width) or source.count!=14 or source.transform!=transform or str(source.crs)!=tile['crs']:
            raise ValueError('Grade remota diferente da solicitada.')
        values=source.read(masked=True).astype(float).filled(np.nan)
    values[values==-9999]=np.nan
    return values,hashlib.sha256(payload).hexdigest()


def save(path, state):
    temporary=path.with_suffix('.tmp')
    temporary.write_text(json.dumps(state,indent=2),encoding='utf-8');temporary.replace(path)


def main():
    import ee
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tile',required=True)
    parser.add_argument('--max-windows',type=int)
    args=parser.parse_args()
    if args.max_windows is not None and args.max_windows<1:parser.error('Limite deve ser positivo.')
    inventory=json.loads(safe_path('dados/brasil/grade.json').read_text(encoding='utf-8'))
    matches=[t for t in inventory['tiles'] if t['tile_id']==args.tile]
    if len(matches)!=1:parser.error('Tile inexistente ou duplicado.')
    tile=matches[0];validate_grid(Affine(*tile['transform']),tile['crs'])
    data,coverage=prepare()
    credentials=ee.data.get_persistent_credentials()
    ee.Initialize(credentials=credentials,project=credentials.quota_project_id or 'mcp-gee')
    ee.data.setDeadline(120000);ee.data.setMaxRetries(1)
    remote={name:ee.data.getAsset(asset) for name,asset in [('chelsa',SOURCES['chelsa']),('dem',DEM)]}
    terrain=json.loads(safe_path('dados/chuva/relevo_escalas.json').read_text(encoding='utf-8'))
    climate=json.loads(safe_path('dados/chuva/chelsa_normais.json').read_text(encoding='utf-8'))
    if remote['dem']!=terrain['dem_metadata'] or remote['chelsa']!=climate['asset']:
        raise ValueError('Fonte remota mudou desde o treino.')
    provenance={'tile':tile,'coverage':coverage,'remote':remote,'script_sha256':digest(__file__),
        'model_script_sha256':digest(modelos_chuva.__file__),'estimators_sha256':digest(estimadores_adicionais.__file__),
        'partition_script_sha256':digest(modelos.__file__),'boundary_sha256':inventory['boundary_sha256']}
    signature=hashlib.sha256(json.dumps(provenance,sort_keys=True).encode()).hexdigest()
    folder=safe_path(f'dados/brasil/chuva/{args.tile}');folder.mkdir(parents=True,exist_ok=True)
    statepath=folder/'manifesto.json'
    state={'signature':signature,'status':'partial_experimental','provenance':provenance,'windows':{},'holdout_scored':False}
    if statepath.exists():
        state=json.loads(statepath.read_text(encoding='utf-8'))
        if state['signature']!=signature:raise ValueError('Treino/código/grade alterados; retomada recusada.')
        if state['status'].startswith('complete'):
            for name,sha in state['output_sha256'].items():
                if digest(folder/name)!=sha:raise ValueError('Produto concluído alterado.')
            print('Tile concluído e hashes conferidos.');return
    if shutil.disk_usage(folder).free<tile['width']*tile['height']*13*7+5*1024**3:
        raise RuntimeError('Espaço insuficiente para este tile e margem operacional.')
    paths={kind:[folder/f'{kind}_30m_{label}_{args.tile}.tif' for label in LABELS] for kind in LAYERS}
    if state['windows'] and any(not p.exists() for files in paths.values() for p in files):
        raise ValueError('Arquivo perdido após janela concluída.')
    model,members,development=fit(data)
    state['training']={'method':'M5_correction','complexity':model.complexity,
        'member_complexities':[m.complexity for m in members],'smearing':model.smearing_,
        'purpose':'engineering candidate; not scientifically selected final model'}
    save(statepath,state)
    for kind,files in paths.items():
        dtype,nodata=LAYERS[kind]
        for label,path in zip(LABELS,files):
            if path.exists():
                with rasterio.open(path) as source:
                    if (source.tags().get('signature')!=signature or source.shape!=(tile['height'],tile['width'])
                        or source.transform!=Affine(*tile['transform']) or str(source.crs)!=tile['crs']
                        or source.dtypes!=(dtype,) or source.nodata!=nodata):raise ValueError('Arquivo incompatível.')
                continue
            with rasterio.open(path,'w',driver='GTiff',width=tile['width'],height=tile['height'],count=1,
                dtype=dtype,nodata=nodata,crs=tile['crs'],transform=Affine(*tile['transform']),tiled=True,
                blockxsize=256,blockysize=256,compress='DEFLATE',BIGTIFF='IF_SAFER') as target:
                target.set_band_unit(1,'1' if kind=='fora_faixa_chuva' else 'mm')
                target.set_band_description(1,kind)
                target.update_tags(signature=signature,experimental='true',normal_period='1991-2020',month=label,
                    method='M5_correction',scale_factor=1,annual_definition='sum of unrounded monthly predictions',
                    interpretation='experimental; SD_not_PI; range_flag_not_AOA',
                    gee_pyramiding_policy='sample' if kind=='fora_faixa_chuva' else 'mean')
    processed=0
    for row in range(0,tile['height'],WINDOW):
        for col in range(0,tile['width'],WINDOW):
            key=f'{row}_{col}'
            if key in state['windows']:continue
            height,width=min(WINDOW,tile['height']-row),min(WINDOW,tile['width']-col)
            window=Window(col,row,width,height);transform=window_transform(window,Affine(*tile['transform']))
            inside=geometry_mask([tile['geometry']],(height,width),transform,invert=True)
            entry={'country_pixels':int(inside.sum()),'valid_pixels':0}
            if inside.any():
                cov,sha=download(ee,tile,transform,width,height)
                arrays,count=predict(cov,transform,tile['crs'],inside,model,members,development)
                for kind,files in paths.items():
                    for index,path in enumerate(files):
                        with rasterio.open(path,'r+') as target:target.write(arrays[kind][index],1,window=window)
                entry.update(valid_pixels=count,covariates_sha256=sha)
            state['windows'][key]=entry;save(statepath,state);processed+=1
            print(f'Chuva {args.tile}: janela {key}, válidos {entry["valid_pixels"]}/{entry["country_pixels"]}',flush=True)
            if args.max_windows and processed>=args.max_windows:return
    state['country_pixels']=sum(w['country_pixels'] for w in state['windows'].values())
    state['valid_pixels']=sum(w['valid_pixels'] for w in state['windows'].values())
    state['status']='complete_experimental' if state['valid_pixels']==state['country_pixels'] else 'complete_with_missing_covariates'
    state['output_sha256']={p.name:digest(p) for files in paths.values() for p in files}
    state['output_bytes']=sum(p.stat().st_size for files in paths.values() for p in files)
    save(statepath,state)


if __name__=='__main__':main()
