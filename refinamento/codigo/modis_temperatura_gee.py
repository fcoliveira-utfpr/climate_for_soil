"""C6: descritores mensais MODIS LST diurno/noturno 2001–2020.

Média dos compostos de oito dias cujo início cai no mês. Não é temperatura do
ar nem normal 1991–2020. Preserva número de compostos válidos e viés de céu limpo.
"""
import hashlib
import json
import pandas as pd
from codigo import modelos
from codigo.dados_temperatura import safe_path
from codigo.grade_brasil import digest

ASSET='MODIS/061/MOD11A2'


def main():
    import ee
    source=safe_path('dados/processados/normais_covariaveis.csv')
    data=modelos.prepare(pd.read_csv(source,dtype={'station_id':str}))
    stations=data.loc[~modelos.reserve_test(data)].drop_duplicates('station_id')
    c=ee.data.get_persistent_credentials();ee.Initialize(credentials=c,project=c.quota_project_id or 'mcp-gee')
    ee.data.setDeadline(120000);ee.data.setMaxRetries(1)
    collection=ee.ImageCollection(ASSET).filterDate('2001-01-01','2021-01-01')
    projection=ee.Image(collection.first()).select('LST_Day_1km').projection().getInfo()
    images=[];counts={}
    for month in range(1,13):
        subset=collection.filter(ee.Filter.calendarRange(month,month,'month'))
        counts[month]=subset.size().getInfo()
        for period in ('Day','Night'):
            # Produzido, data quality boa, erro de emissividade <= .02 e LST <= 2 K.
            # A versão inicial QC==0 não retornou qualquer composto noturno válido.
            masked=subset.map(lambda i,p=period:i.select(f'LST_{p}_1km').multiply(.02).subtract(273.15)
                             .updateMask(i.select(f'QC_{p}').bitwiseAnd(3).lte(1)
                                 .And(i.select(f'QC_{p}').rightShift(2).bitwiseAnd(3).eq(0))
                                 .And(i.select(f'QC_{p}').rightShift(4).bitwiseAnd(3).lte(1))
                                 .And(i.select(f'QC_{p}').rightShift(6).bitwiseAnd(3).lte(1))))
            name=f'{period.lower()}_{month:02d}'
            count=masked.count()
            images.extend([masked.mean().updateMask(count.gte(20)).rename(name),count.rename(f'n_{name}')])
    stack=ee.Image.cat(images)
    settings={'asset':ee.data.getAsset(ASSET),'input_sha256':digest(source),'script_sha256':digest(__file__),
              'projection':projection,'composites_by_month':counts,'period':'2001-2020',
              'minimum_valid_composites':20,'quality':'mandatory <=1; data quality ==0; emissivity error <=.02; LST error <=2K','units':'degC',
              'holdout_sampled':False,'warning':'clear-sky surface-temperature descriptor, not air-temperature normal'}
    key=hashlib.sha256(json.dumps(settings,sort_keys=True).encode()).hexdigest()[:16]
    cache=safe_path(f'.local/modis/{key}');cache.mkdir(parents=True,exist_ok=True)
    rows=[]
    for start in range(0,len(stations),30):
        batch=stations.iloc[start:start+30];checkpoint=cache/f'{start:04d}.json'
        if checkpoint.exists():features=json.loads(checkpoint.read_text(encoding='utf-8'))
        else:
            points=ee.FeatureCollection([ee.Feature(ee.Geometry.Point([r.longitude,r.latitude]),{'station_id':r.station_id}) for r in batch.itertuples()])
            features=stack.reduceRegions(collection=points,reducer=ee.Reducer.first(),crs=projection['crs'],
                                         crsTransform=projection['transform'],tileScale=4).getInfo()['features']
            checkpoint.write_text(json.dumps(features),encoding='utf-8')
        ids=[f['properties']['station_id'] for f in features]
        if len(ids)!=len(set(ids)) or set(ids)!=set(batch.station_id):raise ValueError('Estações divergentes.')
        for f in features:
            p=f['properties']
            for month in range(1,13):
                row={'station_id':p['station_id'],'month':month}
                for period in ('day','night'):
                    row[f'lst_{period}_c']=p.get(f'{period}_{month:02d}')
                    row[f'n_{period}']=p.get(f'n_{period}_{month:02d}',0)
                rows.append(row)
        print(f'MODIS: {min(start+30,len(stations))}/{len(stations)}',flush=True)
    output=safe_path('dados/brasil/modis_temperatura.csv');pd.DataFrame(rows).to_csv(output,index=False)
    output.with_suffix('.json').write_text(json.dumps({**settings,'output_sha256':digest(output)},indent=2),encoding='utf-8')


if __name__=='__main__':main()
