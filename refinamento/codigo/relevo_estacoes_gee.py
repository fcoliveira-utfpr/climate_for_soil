"""Relevo a 30/90/1000 m em pixels UTM consistentes; para C5 e modelagem."""
import argparse
import hashlib
import json
import pandas as pd
from codigo.dados_temperatura import safe_path
from codigo.grade_brasil import digest
from codigo.covariaveis_gee import DEM, utm_crs


def extract_local(batch, crs):
    """Limita a entrada de cada reprojeção a uma vizinhança de 3 km."""
    import ee
    features=[]
    for station in batch.itertuples():
        point=ee.Geometry.Point([station.longitude,station.latitude])
        region=point.buffer(3000)
        collection=ee.ImageCollection(DEM).filterBounds(region).select('DEM')
        native=collection.mosaic().setDefaultProjection(ee.Image(collection.first()).projection())
        fine=native.resample('bilinear').reproject(crs=crs,crsTransform=[30,0,0,0,-30,0])
        bounded=native.clip(region).resample('bilinear').reproject(crs=crs,crsTransform=[30,0,0,0,-30,0])
        values=ee.Dictionary({'station_id':station.station_id})
        for resolution in (30,90,1000):
            transform=[resolution,0,0,0,-resolution,0]
            source=bounded if resolution==1000 else fine
            elevation=fine if resolution==30 else source.reduceResolution(
                reducer=ee.Reducer.mean(),maxPixels=4096,bestEffort=False).reproject(crs=crs,crsTransform=transform)
            image=elevation.rename(f'elevation_{resolution}').addBands(ee.Terrain.slope(elevation).rename(f'slope_{resolution}'))
            values=values.combine(image.reduceRegion(reducer=ee.Reducer.first(),geometry=point,
                crs=crs,crsTransform=transform,maxPixels=16))
        features.append(ee.Feature(None,values))
    response=ee.FeatureCollection(features).getInfo()['features']
    rows=[f['properties'] for f in response]
    ids=[r['station_id'] for r in rows]
    if len(ids)!=len(set(ids)) or set(ids)!=set(batch.station_id):raise ValueError('Extração perdeu estações.')
    return rows


def main():
    import ee
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--variable',choices=['temperatura','chuva'],required=True)
    parser.add_argument('--batch-size',type=int,default=50)
    parser.add_argument('--reuse-audited-cache',action='store_true',help='Reutilizar somente os lotes identificados e hasheados no manifesto de migração.')
    args=parser.parse_args()
    if not 1<=args.batch_size<=100:raise ValueError('Lote deve ter 1–100 estações.')
    source=safe_path('dados/processados/normais_precipitacao.csv' if args.variable=='chuva'
                     else 'dados/processados/normais_covariaveis.csv')
    data=pd.read_csv(source,dtype={'station_id':str})
    if args.variable=='chuva':
        stations=data.loc[data.month.eq(0)&data.precipitation_mm.notna()].copy()
    else:stations=data.drop_duplicates('station_id').copy()
    stations['crs']=[utm_crs(r.latitude,r.longitude) for r in stations.itertuples()]
    stations=stations.sort_values(['crs','station_id'])
    c=ee.data.get_persistent_credentials();ee.Initialize(credentials=c,project=c.quota_project_id or 'mcp-gee')
    ee.data.setDeadline(120000);ee.data.setMaxRetries(1)
    metadata={'input_sha256':digest(source),'script_sha256':digest(__file__),
              'dem_metadata':ee.data.getAsset(DEM),'batch_size':args.batch_size,
              'method':'DSM bilinear at UTM30; mean aggregation at 90/1000; slope after each projection; no fill'}
    key=hashlib.sha256(json.dumps(metadata,sort_keys=True).encode()).hexdigest()[:16]
    cache=safe_path(f'.local/relevo/{key}');cache.mkdir(parents=True,exist_ok=True)
    legacy=None
    if args.reuse_audited_cache:
        if args.variable!='chuva':raise ValueError('Migração disponível somente para a chuva.')
        legacy=json.loads(safe_path('dados/chuva/relevo_cache_migracao.json').read_text(encoding='utf-8'))
        for field in ('input_sha256','dem_metadata','batch_size','method'):
            if legacy['settings'][field]!=metadata[field]:raise ValueError('Cache anterior usa outra fonte ou método.')
        expected=hashlib.sha256(json.dumps(legacy['settings'],sort_keys=True).encode()).hexdigest()[:16]
        if expected!=legacy['cache_key']:raise ValueError('Identidade do cache anterior inválida.')
    outputs=[]
    for crs,group in stations.groupby('crs'):
        for start in range(0,len(group),args.batch_size):
            batch=group.iloc[start:start+args.batch_size]
            checkpoint=cache/f'{crs.replace(":","_")}_{start:05d}.json'
            if checkpoint.exists(): rows=json.loads(checkpoint.read_text(encoding='utf-8'))
            elif legacy and checkpoint.name in legacy['files']:
                previous=safe_path(f'.local/relevo/{legacy["cache_key"]}/{checkpoint.name}')
                if digest(previous)!=legacy['files'][checkpoint.name]:raise ValueError('Lote anterior alterado.')
                rows=json.loads(previous.read_text(encoding='utf-8'))
                checkpoint.write_text(json.dumps(rows),encoding='utf-8')
            else:
                rows=[]
                for offset in range(0,len(batch),10):
                    subset=batch.iloc[offset:offset+10]
                    part=cache/f'{checkpoint.stem}_parte_{offset:03d}.json'
                    if part.exists():result=json.loads(part.read_text(encoding='utf-8'))
                    else:
                        result=extract_local(subset,crs)
                        part.write_text(json.dumps(result),encoding='utf-8')
                    rows.extend(result)
                checkpoint.write_text(json.dumps(rows),encoding='utf-8')
            ids=[r['station_id'] for r in rows]
            if len(ids)!=len(set(ids)) or set(ids)!=set(batch.station_id):raise ValueError('Cache com estações divergentes.')
            outputs.extend(rows)
            print(f'Relevo {args.variable}: {len(outputs)}/{len(stations)}',flush=True)
    result=pd.DataFrame(outputs)
    for scale in (30,90,1000):
        for prefix in ('elevation','slope'):
            column=f'{prefix}_{scale}'
            if column not in result:result[column]=float('nan')
    path=safe_path(f'dados/{"chuva" if args.variable=="chuva" else "brasil"}/relevo_escalas.csv')
    path.parent.mkdir(parents=True,exist_ok=True);result.to_csv(path,index=False,float_format='%.10g')
    path.with_suffix('.json').write_text(json.dumps({**metadata,'output_sha256':digest(path),
        'local_buffer_m':3000,'legacy_cache_provenance':legacy,
        'stations':len(stations),'missing':result.isna().sum().to_dict()},indent=2),encoding='utf-8')


if __name__=='__main__':main()
