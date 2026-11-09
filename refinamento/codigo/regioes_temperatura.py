"""C9: métricas das mesmas predições por grande região, com limites IBGE."""
import json
import pandas as pd
from shapely.geometry import Point, shape
from codigo import modelos
from codigo.dados_temperatura import safe_path
from codigo.grade_brasil import BOUNDARY, digest
from codigo.metricas import metricas

REGIONS = {'1':'Norte','2':'Nordeste','3':'Sudeste','4':'Sul','5':'Centro-Oeste'}


def main():
    boundary_path = safe_path(BOUNDARY)
    collection = json.loads(boundary_path.read_text(encoding='utf-8'))
    polygons = [(str(f['properties']['codarea']), shape(f['geometry'])) for f in collection['features']]
    source = safe_path('dados/processados/normais_covariaveis.csv')
    normals = modelos.prepare(pd.read_csv(source,dtype={'station_id':str}))
    development = normals.loc[~modelos.reserve_test(normals)].drop_duplicates('station_id')
    assignments = []
    for station in development.itertuples():
        codes = [code for code, polygon in polygons if polygon.covers(Point(station.longitude,station.latitude))]
        regions = {REGIONS[code[0]] for code in codes}
        assignments.append({'station_id':station.station_id,
                            'region':next(iter(regions)) if len(regions)==1 else 'sem_atribuicao_univoca'})
    assignments = pd.DataFrame(assignments)
    assignments.to_csv(safe_path('dados/brasil/regioes_estacoes.csv'),index=False)
    for block in (1,2):
        path = safe_path(f'dados/bases/predicoes_c1_{block}graus.csv')
        predictions = pd.read_csv(path,dtype={'station_id':str})
        if not set(predictions.station_id) <= set(development.station_id):
            raise ValueError('Predições incluem estações fora do desenvolvimento.')
        paired = predictions.merge(assignments,on='station_id',validate='many_to_one')
        rows, coverage = [], []
        for (region,method,repeat), frame in paired.groupby(['region','method','repeat']):
            n = frame.station_id.nunique()
            entry = {'region':region,'method':method,'repeat':repeat,'n_stations':n}
            coverage.append({**entry,'published':n>=5 and region!='sem_atribuicao_univoca'})
            if n>=5 and region!='sem_atribuicao_univoca':
                rows.append({**entry,**metricas(frame.temperature_c,frame.prediction)})
        pd.DataFrame(rows).to_csv(safe_path(f'resultados/tabelas/c9_regioes_{block}graus.csv'),index=False)
        pd.DataFrame(coverage).to_csv(safe_path(f'resultados/tabelas/c9_regioes_cobertura_{block}graus.csv'),index=False)
    report = {'boundary_sha256':digest(boundary_path),'normals_sha256':digest(source),
              'script_sha256':digest(__file__),'holdout_scored':False,
              'development_by_region':assignments.region.value_counts().to_dict(),
              'biomes_completed':False,'minimum_stations_to_publish':5}
    safe_path('resultados/tabelas/c9_regioes.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report,indent=2))


if __name__=='__main__':
    main()
