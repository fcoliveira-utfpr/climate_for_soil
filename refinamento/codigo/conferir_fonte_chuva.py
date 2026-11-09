"""Pareamento amostral NPZ/asset do professor por ID exato e data, separando flags."""
import json
import numpy as np
import pandas as pd
from codigo.modelos_chuva import prepare
from codigo.dados_temperatura import safe_path,load_observations
from codigo.grade_brasil import digest

ASSET='projects/fcoliveira/assets/observados_inmet/pr'


def main():
    import ee
    credentials=ee.data.get_persistent_credentials()
    ee.Initialize(credentials=credentials,project=credentials.quota_project_id or 'mcp-gee')
    ee.data.setDeadline(120000);ee.data.setMaxRetries(1)
    metadata=ee.data.getAsset(ASSET)
    data,_=prepare()
    stations=data.loc[~data.reserved].drop_duplicates('station_id').sort_values(['latitude','longitude'])
    selected=stations.iloc[np.linspace(0,len(stations)-1,10,dtype=int)]
    source=safe_path('dados/brutos/pr.npz')
    provenance=json.loads(safe_path('dados/brutos/pr.fonte.json').read_text(encoding='utf-8'))
    if digest(source)!=provenance['sha256']:raise ValueError('NPZ alterado.')
    observed=load_observations(source)
    positions={station:i for i,station in enumerate(observed.stations.station_id)}
    date_positions={date:i for i,date in enumerate(observed.dates)}
    cache=safe_path('.local/chuva_inmet/comparacao_npz');cache.mkdir(parents=True,exist_ok=True)
    rows=[];empty=0
    for station in selected.itertuples():
        key=station.station_id
        path=cache/f'{key}.json'
        settings={'asset':metadata,'station_id':key,'years':[1991,2010,2020],'month':1}
        if path.exists():
            entry=json.loads(path.read_text(encoding='utf-8'))
            if entry['settings']!=settings:raise ValueError('Cache de outra fonte.')
            records=entry['records']
        else:
            collection=ee.FeatureCollection(ASSET).filter(ee.Filter.eq('cod_estacao',key)).filter(
                ee.Filter.inList('ano',[1991,2010,2020])).filter(ee.Filter.eq('mes',1))
            records=collection.limit(100).getInfo()['features']
            if len(records)>=100:raise ValueError('Limite atingido; não truncar amostra.')
            path.write_text(json.dumps({'settings':settings,'records':records}),encoding='utf-8')
        if not records:empty+=1
        for feature in records:
            p=feature['properties'];date=pd.to_datetime(p['system:time_start'],unit='ms',utc=True).tz_localize(None).normalize()
            if date not in date_positions or key not in positions:raise ValueError('ID/data não encontrado no NPZ.')
            rows.append({'station_id':key,'date':str(date.date()),'filled':p['preenchido'],'gee_mm':p['valor'],
                         'npz_mm':float(observed.data[date_positions[date],positions[key]])})
        print(f'Conferência fonte chuva: {len(rows)} pares consultados',flush=True)
    pairs=pd.DataFrame(rows)
    if pairs.empty:raise ValueError('Nenhum pareamento; revisar códigos antes de concluir equivalência.')
    if pairs.duplicated(['station_id','date']).any():raise ValueError('Duplicata no asset.')
    pairs.to_csv(safe_path('dados/chuva/comparacao_fonte_amostra.csv'),index=False)
    summary=[]
    for flag,frame in pairs.groupby('filled'):
        finite=np.isfinite(frame[['npz_mm','gee_mm']]).all(axis=1)
        delta=frame.loc[finite,'gee_mm']-frame.loc[finite,'npz_mm']
        summary.append({'filled':int(flag),'records':len(frame),'finite_pairs':int(finite.sum()),
            'npz_missing':int(frame.npz_mm.isna().sum()),'equal_within_0_001_mm':int(delta.abs().le(.001).sum()),
            'mean_abs_difference_mm':float(delta.abs().mean()) if len(delta) else None,
            'max_abs_difference_mm':float(delta.abs().max()) if len(delta) else None})
    pd.DataFrame(summary).to_csv(safe_path('resultados/tabelas/chuva_fontes_amostra.csv'),index=False)
    report={'asset':ASSET,'asset_update_time':metadata.get('updateTime'),'npz_sha256':digest(source),
            'script_sha256':digest(__file__),'sample_rule':'10 development stations equally spaced in latitude ordering; January 1991/2010/2020',
            'stations_queried':10,'stations_without_records':empty,'stations_with_records':pairs.station_id.nunique(),
            'records':len(pairs),'duplicate_station_dates':0,'filled_values_used_as_truth':False,
            'limitation':'Sample only; exact IDs, no alias matching. Does not certify national equivalence, QC or independence.'}
    safe_path('resultados/tabelas/chuva_fontes_amostra.json').write_text(json.dumps(report,indent=2),encoding='utf-8')


if __name__=='__main__':main()
