"""Compara coleções diária/mensal Xavier em pontos públicos, sem estações de teste."""
import calendar
import json
import pandas as pd
from codigo.dados_temperatura import safe_path
from codigo.grade_brasil import digest

DAILY='projects/ee-alexandrexavier/assets/BR-DWGD'
MONTHLY='projects/ee-alexandrexavier/assets/BR-DWGD_Monthly'


def main():
    import ee
    credentials=ee.data.get_persistent_credentials()
    ee.Initialize(credentials=credentials,project=credentials.quota_project_id or 'mcp-gee')
    ee.data.setDeadline(120000);ee.data.setMaxRetries(1)
    points=[('Brasilia',-47.8825,-15.7942),('Curitiba',-49.2733,-25.4284),('Manaus',-60.0217,-3.1190)]
    features=ee.FeatureCollection([ee.Feature(ee.Geometry.Point([lon,lat]),{'point':name}) for name,lon,lat in points])
    rows=[];metadata=[]
    for year,month in ((1991,1),(2010,1),(2020,7)):
        start=pd.Timestamp(year,month,1);end=start+pd.offsets.MonthBegin(1)
        daily=ee.ImageCollection(DAILY).filterDate(str(start.date()),str(end.date()))
        monthly=ee.ImageCollection(MONTHLY).filterDate(str(start.date()),str(end.date()))
        n=calendar.monthrange(year,month)[1]
        times=daily.aggregate_array('system:time_start').getInfo()
        if len(set(times))!=n or monthly.size().getInfo()!=1:raise ValueError('Calendário incompleto ou duplicado.')
        images=[]
        for band,aggregation in (('pr','sum'),('Tmax','mean'),('Tmin','mean')):
            def decode(image):
                return image.select(band).multiply(ee.Number(image.get(f'BAND_{band}_MULT'))).add(ee.Number(image.get(f'BAND_{band}_ADD')))
            for collection,count in ((daily,n),(monthly,1)):
                for suffix in ('MULT','ADD'):
                    if collection.aggregate_count(f'BAND_{band}_{suffix}').getInfo()!=count:raise ValueError('Escala ausente.')
            decoded=daily.map(decode)
            aggregate=decoded.sum() if aggregation=='sum' else decoded.mean()
            images.extend([aggregate.updateMask(decoded.count().eq(n)).rename(f'{band}_daily'),
                           decode(ee.Image(monthly.first())).rename(f'{band}_monthly')])
        first=ee.Image(daily.first());projection=first.select('pr').projection().getInfo()
        sampled=ee.Image.cat(images).reduceRegions(collection=features,reducer=ee.Reducer.first(),
            crs=projection['crs'],crsTransform=projection['transform']).getInfo()['features']
        for feature in sampled:
            props=feature['properties']
            for band in ('pr','Tmax','Tmin'):
                a,b=props.get(f'{band}_daily'),props.get(f'{band}_monthly')
                rows.append({'point':props['point'],'year':year,'month':month,'variable':band,
                    'daily_aggregated':a,'monthly_product':b,'monthly_minus_daily':None if a is None or b is None else b-a})
        metadata.append({'year':year,'month':month,'daily_timestamps':times,'projection':projection,
            'daily_first_properties':first.toDictionary().getInfo(),
            'monthly_properties':ee.Image(monthly.first()).toDictionary().getInfo()})
        print(f'Xavier diário/mensal: {year}-{month:02d} concluído',flush=True)
    pd.DataFrame(rows).to_csv(safe_path('resultados/tabelas/xavier_diario_mensal_amostra.csv'),index=False)
    safe_path('dados/bases/xavier_calendario_metadata.json').write_text(json.dumps(metadata,indent=2),encoding='utf-8')
    safe_path('resultados/tabelas/xavier_diario_mensal_amostra.json').write_text(json.dumps({
        'daily':DAILY,'monthly':MONTHLY,'script_sha256':digest(__file__),'points':points,
        'monthly_equals_daily_assumed':False,'purpose':'unit/calendar/source equivalence check; no station evaluation',
        'metadata_sha256':digest(safe_path('dados/bases/xavier_calendario_metadata.json'))},indent=2),encoding='utf-8')


if __name__=='__main__':main()
