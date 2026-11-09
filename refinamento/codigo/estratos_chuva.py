"""C9 de chuva: região, bioma, altitude e mês nas predições de desenvolvimento."""
import io
import json
import zipfile
import pandas as pd
import shapefile
from shapely.geometry import Point,shape
from pyproj import CRS,Transformer
from codigo.modelos_chuva import prepare
from codigo.consolidar_chuva import read_run
from codigo.dados_temperatura import safe_path
from codigo.grade_brasil import BOUNDARY,digest
from codigo.regioes_temperatura import REGIONS
from codigo.metricas import metricas


def main():
    data,coverage=prepare();stations=data.loc[~data.reserved].drop_duplicates('station_id')
    boundary=safe_path(BOUNDARY)
    collection=json.loads(boundary.read_text(encoding='utf-8'))
    regions=[(REGIONS[str(f['properties']['codarea'])[0]],shape(f['geometry'])) for f in collection['features']]
    biomes_path=safe_path('dados/brasil/biomas_2025.zip')
    with zipfile.ZipFile(biomes_path) as archive:
        def content(suffix):return archive.read(next(n for n in archive.namelist() if n.endswith(suffix)))
        projection=CRS.from_wkt(content('.prj').decode())
        reader=shapefile.Reader(shp=io.BytesIO(content('.shp')),dbf=io.BytesIO(content('.dbf')),encoding='utf-8')
        biomes=[(r.record['NM_BIOMA'],shape(r.shape.__geo_interface__)) for r in reader.iterShapeRecords()]
    transformer=Transformer.from_crs('EPSG:4326',projection,always_xy=True)
    rows=[]
    for station in stations.itertuples():
        entry={'station_id':station.station_id,'elevation_m':station.elevation_30}
        for label,polygons,point in [('region',regions,Point(station.longitude,station.latitude)),
                                    ('biome',biomes,Point(*transformer.transform(station.longitude,station.latitude)))]:
            found={name for name,polygon in polygons if polygon.covers(point)}
            entry[label]=next(iter(found)) if len(found)==1 else 'sem_atribuicao_univoca'
        rows.append(entry)
    assignments=pd.DataFrame(rows)
    assignments['altitude']=pd.cut(assignments.elevation_m,[-float('inf'),200,500,1000,float('inf')],
                                   labels=['ate_200m','200_500m','500_1000m','acima_1000m']).astype(str)
    assignments.to_csv(safe_path('dados/chuva/estratos_estacoes.csv'),index=False)
    audits={}
    for block in (1,2):
        base,_=read_run(f'M2_{block}graus_30m_base');frames=[base]
        for method in ('M4','M5','M6'):
            suffix=f'{method}_{block}graus_30m_base'
            if not safe_path(f'dados/chuva/predicoes_{suffix}.json').exists():continue
            frame,meta=read_run(suffix)
            if meta['hashes']!=coverage['hashes']:raise ValueError('Dados diferentes na comparação.')
            frames.append(frame.loc[frame.method.str.startswith(method)])
        frame,_=read_run(f'M5_{block}graus_30m_satelite')
        frames.append(frame.loc[frame.method.eq('M5_correction')].assign(method='M5_correction_CHIRPS'))
        predictions=pd.concat(frames,ignore_index=True)
        if not set(predictions.station_id)<=set(assignments.station_id):raise ValueError('Predição fora do desenvolvimento.')
        combined=predictions.merge(assignments,on='station_id',validate='many_to_one')
        scores=[];counts=[]
        for stratum in ('region','biome','altitude','month'):
            for (value,method,repeat),frame in combined.groupby([stratum,'method','repeat'],observed=True):
                entry={'stratum':stratum,'value':str(value),'method':method,'repeat':repeat,'n_stations':frame.station_id.nunique()}
                publish=entry['n_stations']>=5 and value!='sem_atribuicao_univoca'
                counts.append({**entry,'published':publish})
                if publish:scores.append({**entry,**metricas(frame.precipitation_mm,frame.prediction)})
        pd.DataFrame(scores).to_csv(safe_path(f'resultados/tabelas/chuva_c9_{block}graus.csv'),index=False)
        pd.DataFrame(counts).to_csv(safe_path(f'resultados/tabelas/chuva_c9_cobertura_{block}graus.csv'),index=False)
        audits[str(block)]=list(predictions.method.unique())
    report={**coverage,'holdout_scored':False,'boundary_sha256':digest(boundary),'biomes_sha256':digest(biomes_path),
            'script_sha256':digest(__file__),'minimum_stations_to_publish':5,'methods':audits,
            'stations_by_biome':assignments.biome.value_counts().to_dict(),
            'stations_by_region':assignments.region.value_counts().to_dict(),
            'limitation':'Descriptive stratification; no subgroup-specific independent validation.'}
    safe_path('resultados/tabelas/chuva_c9.json').write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding='utf-8')


if __name__=='__main__':main()
