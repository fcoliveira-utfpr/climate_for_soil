"""Extrai grades mensais de chuva nas estações elegíveis, com checkpoints.

Leitura remota; valores mascarados permanecem NaN. Não usa observações para
ajustar as grades. CHELSA em mm/mês; ERA5 metros -> mm; CHIRPS soma pentadal/30.
"""
import argparse
import hashlib
import json
import numpy as np
import pandas as pd
from codigo.dados_temperatura import safe_path
from codigo.grade_brasil import digest

SOURCES = {'chelsa':'projects/fcoliveira/assets/CHELSA/chelsa_brasil_pr_normal_1991_2020',
           'era5':'ECMWF/ERA5_LAND/MONTHLY_AGGR',
           'chirps':'UCSB-CHG/CHIRPS/PENTAD',
           'xavier':'projects/ee-alexandrexavier/assets/BR-DWGD_Monthly'}
BANDS = [f'm{month:02d}' for month in range(1,13)]


def decode(features, ids):
    props = [f['properties'] for f in features]
    actual = [p.get('station_id') for p in props]
    if len(actual)!=len(set(actual)) or set(actual)!=set(ids):
        raise ValueError('Extração perdeu ou duplicou estações.')
    rows = []
    for p in props:
        for month,band in enumerate(BANDS,1):
            v = p.get(band)
            v = np.nan if v is None else float(v)
            if not np.isnan(v) and (not np.isfinite(v) or v<0 or v>4000):
                raise ValueError('Normal de chuva fora da faixa; revisar fonte e escala.')
            rows.append({'station_id':p['station_id'],'month':month,'grid_mm':v})
    return pd.DataFrame(rows)


def stack_for(name):
    import ee
    asset = SOURCES[name]
    if name=='chelsa':
        image=ee.Image(asset).select([f'b{i}' for i in range(1,13)]).rename(BANDS)
        return image, image.select(0).projection(), {'period':'1991-2020','unit_evidence':'climas/dados_chelsa/assets_utilizados.md'}
    collection=ee.ImageCollection(asset).filterDate('1991-01-01','2021-01-01').sort('system:time_start')
    times=collection.aggregate_array('system:time_start').getInfo()
    dates=pd.to_datetime(times,unit='ms',utc=True).tz_localize(None)
    if dates.duplicated().any():
        raise ValueError('Datas duplicadas na grade.')
    periods=dates.to_period('M')
    expected=pd.period_range('1991-01','2020-12',freq='M')
    counts=pd.Series(1,index=periods).groupby(level=0).sum().reindex(expected,fill_value=0)
    if not counts.eq(6 if name=='chirps' else 1).all():
        raise ValueError('Grade não contém os 360 meses completos esperados.')
    band={'era5':'total_precipitation_sum','chirps':'precipitation','xavier':'pr'}[name]
    projection=ee.Image(collection.first()).select(band).projection()
    if name=='xavier':
        for key in ('BAND_pr_MULT','BAND_pr_ADD'):
            if collection.aggregate_count(key).getInfo()!=360:
                raise ValueError('Xavier sem escala/offset em todos os meses.')
        collection=collection.map(lambda i:i.select('pr').multiply(ee.Number(i.get('BAND_pr_MULT')))
                                  .add(ee.Number(i.get('BAND_pr_ADD'))).copyProperties(i,['system:time_start']))
    images=[]
    for month in range(1,13):
        subset=collection.filter(ee.Filter.calendarRange(month,month,'month')).select(band)
        value=subset.sum().divide(30) if name=='chirps' else subset.mean()
        if name=='era5': value=value.multiply(1000)
        # Não aceitar um pixel cuja série tenha meses/pentadas mascarados.
        required=180 if name=='chirps' else 30
        images.append(value.updateMask(subset.count().eq(required)).rename(f'm{month:02d}'))
    return ee.Image.cat(images),projection,{'timestamps':times,'monthly_record_counts':counts.tolist()}


def main():
    import ee
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',choices=SOURCES,required=True)
    parser.add_argument('--batch-size',type=int,default=200)
    args=parser.parse_args()
    if not 1<=args.batch_size<=300: raise ValueError('Lote deve ter 1–300 estações.')
    source=safe_path('dados/processados/normais_precipitacao.csv')
    manifest=json.loads(source.with_suffix('.manifesto.json').read_text(encoding='utf-8'))
    if digest(source)!=manifest['output_sha256']: raise ValueError('Normais alteradas.')
    data=pd.read_csv(source,dtype={'station_id':str})
    stations=data.loc[data.month.eq(0)&data.precipitation_mm.notna(),['station_id','latitude','longitude']].sort_values('station_id')
    credentials=ee.data.get_persistent_credentials()
    ee.Initialize(credentials=credentials,project=credentials.quota_project_id or 'mcp-gee')
    ee.data.setDeadline(120000);ee.data.setMaxRetries(1)
    stack,projection,calendar=stack_for(args.source)
    grid=projection.getInfo()
    settings={'source':args.source,'asset':ee.data.getAsset(SOURCES[args.source]),
              'input_sha256':digest(source),'script_sha256':digest(__file__),
              'grid':grid,'calendar':calendar,'batch_size':args.batch_size,
              'sampling':'native pixel containing station, no resampling or filling'}
    key=hashlib.sha256(json.dumps(settings,sort_keys=True).encode()).hexdigest()[:16]
    cache=safe_path(f'.local/chuva_gee/{key}');cache.mkdir(parents=True,exist_ok=True)
    outputs=[]
    for start in range(0,len(stations),args.batch_size):
        batch=stations.iloc[start:start+args.batch_size]
        checkpoint=cache/f'{start:05d}.json'
        if checkpoint.exists(): features=json.loads(checkpoint.read_text(encoding='utf-8'))
        else:
            points=ee.FeatureCollection([ee.Feature(ee.Geometry.Point([r.longitude,r.latitude]),
                     {'station_id':r.station_id}) for r in batch.itertuples()])
            features=stack.reduceRegions(collection=points,reducer=ee.Reducer.first(),
                     crs=grid['crs'],crsTransform=grid['transform'],tileScale=4).getInfo()['features']
            decode(features,batch.station_id)
            checkpoint.write_text(json.dumps(features),encoding='utf-8')
        outputs.append(decode(features,batch.station_id))
        print(f'{args.source}: {min(start+args.batch_size,len(stations))}/{len(stations)}',flush=True)
    result=pd.concat(outputs,ignore_index=True)
    path=safe_path(f'dados/chuva/{args.source}_normais.csv');path.parent.mkdir(parents=True,exist_ok=True)
    result.to_csv(path,index=False,float_format='%.10g')
    path.with_suffix('.json').write_text(json.dumps({**settings,'output_sha256':digest(path),
        'stations':len(stations),'missing_values':int(result.grid_mm.isna().sum()),'units':'mm/month',
        'warning':'Station independence from grids is unproven; Xavier monthly/daily equivalence pending.'},indent=2),encoding='utf-8')


if __name__=='__main__':main()
