"""C9: métricas por bioma IBGE 2025, mantendo ambiguidade territorial explícita."""
import io
import json
import zipfile
import pandas as pd
import shapefile
from pyproj import CRS,Transformer
from shapely.geometry import Point,shape
from codigo import modelos
from codigo.dados_temperatura import safe_path
from codigo.grade_brasil import digest
from codigo.metricas import metricas

URL='https://geoftp.ibge.gov.br/informacoes_ambientais/estudos_ambientais/biomas/vetores/2025_Biomas-e-Sistema-Costeiro-Marinho-do-Brasil-1-250000_shp.zip'


def main():
    import requests
    path=safe_path('dados/brasil/biomas_2025.zip')
    if not path.exists():
        response=requests.get(URL,timeout=(15,120));response.raise_for_status();path.write_bytes(response.content)
    with zipfile.ZipFile(path) as archive:
        def content(suffix):return archive.read(next(n for n in archive.namelist() if n.endswith(suffix)))
        projection=CRS.from_wkt(content('.prj').decode())
        reader=shapefile.Reader(shp=io.BytesIO(content('.shp')),dbf=io.BytesIO(content('.dbf')),encoding='utf-8')
        polygons=[(r.record['NM_BIOMA'],shape(r.shape.__geo_interface__)) for r in reader.iterShapeRecords()]
    transformer=Transformer.from_crs('EPSG:4326',projection,always_xy=True)
    source=safe_path('dados/processados/normais_covariaveis.csv')
    data=modelos.prepare(pd.read_csv(source,dtype={'station_id':str}))
    development=data.loc[~modelos.reserve_test(data)].drop_duplicates('station_id')
    rows=[]
    for station in development.itertuples():
        point=Point(*transformer.transform(station.longitude,station.latitude))
        found={name for name,polygon in polygons if polygon.covers(point)}
        rows.append({'station_id':station.station_id,'biome':next(iter(found)) if len(found)==1 else 'sem_atribuicao_univoca'})
    assignments=pd.DataFrame(rows);assignments.to_csv(safe_path('dados/brasil/biomas_estacoes.csv'),index=False)
    for block in (1,2):
        predictions=pd.read_csv(safe_path(f'dados/bases/predicoes_c1_{block}graus.csv'),dtype={'station_id':str})
        if not set(predictions.station_id)<=set(development.station_id):raise ValueError('Inclui teste reservado.')
        combined=predictions.merge(assignments,on='station_id',validate='many_to_one')
        scores=[];coverage=[]
        for (biome,method,repeat),frame in combined.groupby(['biome','method','repeat']):
            item={'biome':biome,'method':method,'repeat':repeat,'n_stations':frame.station_id.nunique()}
            published=item['n_stations']>=5 and biome!='sem_atribuicao_univoca'
            coverage.append({**item,'published':published})
            if published:scores.append({**item,**metricas(frame.temperature_c,frame.prediction)})
        pd.DataFrame(scores).to_csv(safe_path(f'resultados/tabelas/c9_biomas_{block}graus.csv'),index=False)
        pd.DataFrame(coverage).to_csv(safe_path(f'resultados/tabelas/c9_biomas_cobertura_{block}graus.csv'),index=False)
    report={'boundary_source':URL,'boundary_sha256':digest(path),'source_crs':projection.to_string(),
            'input_sha256':digest(source),'script_sha256':digest(__file__),'holdout_scored':False,
            'development_by_biome':assignments.biome.value_counts().to_dict(),'minimum_stations_to_publish':5,
            'limitation':'biome boundary at 1:250000, not a 30m territorial certification; rainfall pending'}
    safe_path('resultados/tabelas/c9_biomas.json').write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding='utf-8')
    print(json.dumps(report,indent=2,ensure_ascii=False))


if __name__=='__main__':main()
