"""C11: extremos, 24 horas e compensada operacional em automáticas INMET 2020.

Dia UTC contém os registros 01:00 até 00:00 seguinte (24:00), com extremos
da hora anterior. Exige 24 registros válidos de todas as três séries. A fórmula
compensada é aplicada às automáticas; não reproduz os horários de leitura de
termômetros convencionais. Não altera a normal 1991–2020.
"""
import io
import json
import unicodedata
import zipfile
import numpy as np
import pandas as pd
from codigo.metricas import metricas
from codigo.dados_temperatura import safe_path
from codigo.grade_brasil import digest

URL='https://portal.inmet.gov.br/uploads/dadoshistoricos/2020.zip'


def daily_means(frame):
    frame=frame.copy().sort_index()
    if not isinstance(frame.index,pd.DatetimeIndex) or frame.index.has_duplicates:
        raise ValueError('Datas devem ser timestamps únicos.')
    if (frame.index.minute!=0).any() or (frame.index.second!=0).any():raise ValueError('Observações devem ser horárias.')
    valid=np.isfinite(frame[['air','maximum','minimum']]).all(axis=1)
    valid&=frame[['air','maximum','minimum']].gt(-30).all(axis=1)&frame[['air','maximum','minimum']].lt(50).all(axis=1)
    valid&=frame.minimum.le(frame.maximum)
    frame['valid']=valid
    frame['date']=(frame.index-pd.Timedelta(hours=1)).normalize()
    frame['hour']=frame.index.hour
    rows=[]
    for date,group in frame.groupby('date'):
        if len(group)!=24 or group.hour.nunique()!=24 or not group.valid.all():continue
        maximum,minimum=group.maximum.max(),group.minimum.min()
        t12=group.loc[group.hour.eq(12),'air'].iloc[0]
        t24=group.loc[group.hour.eq(0),'air'].iloc[0]
        rows.append({'date':date,'mean_24h':group.air.mean(),'mean_extremes':(maximum+minimum)/2,
                     'mean_compensated':(maximum+minimum+t12+2*t24)/5})
    result=pd.DataFrame(rows,columns=['date','mean_24h','mean_extremes','mean_compensated'])
    result['date']=pd.to_datetime(result.date)
    return result


def read_station(content):
    text=content.decode('latin1');lines=text.splitlines()
    metadata={line.split(';')[0].strip(':'):line.split(';')[1] for line in lines[:8]}
    frame=pd.read_csv(io.StringIO(text),sep=';',skiprows=8,decimal=',',na_values=['-9999','-9999.0','-9999,0'])
    def norm(s):return ''.join(c for c in unicodedata.normalize('NFKD',s.upper()) if not unicodedata.combining(c))
    columns={norm(c):c for c in frame}
    def column(prefix):return next(v for k,v in columns.items() if k.startswith(prefix))
    times=pd.to_datetime(frame.iloc[:,0],format='%Y/%m/%d')+pd.to_timedelta(frame.iloc[:,1].str.extract(r'(\d{2})\d{2}')[0].astype(int),unit='h')
    values=pd.DataFrame({name:pd.to_numeric(frame[column(prefix)],errors='coerce').to_numpy() for name,prefix in
                        [('air','TEMPERATURA DO AR'),('maximum','TEMPERATURA MAXIMA NA HORA'),('minimum','TEMPERATURA MINIMA NA HORA')]},index=pd.DatetimeIndex(times))
    return metadata,values


def main():
    import requests
    path=safe_path('dados/brutos/inmet_2020.zip')
    if not path.exists():
        partial=path.with_suffix('.part')
        with requests.get(URL,stream=True,timeout=(15,120)) as response:
            response.raise_for_status()
            with partial.open('wb') as handle:
                for chunk in response.iter_content(1024*1024):handle.write(chunk)
        partial.replace(path)
    days=[];stations=[]
    with zipfile.ZipFile(path) as archive:
        files=sorted(n for n in archive.namelist() if n.lower().endswith('.csv'))
        for index,name in enumerate(files):
            metadata,frame=read_station(archive.read(name))
            daily=daily_means(frame)
            daily=daily.loc[daily.date.dt.year.eq(2020)].copy()
            station=metadata['CODIGO (WMO)']
            daily['station_id'],daily['uf'],daily['region']=station,metadata['UF'],metadata['REGIAO']
            days.append(daily)
            stations.append({'station_id':station,'uf':metadata['UF'],'region':metadata['REGIAO'],
                             'latitude':float(metadata['LATITUDE'].replace(',','.')),
                             'longitude':float(metadata['LONGITUDE'].replace(',','.')),
                             'valid_paired_days':len(daily),'source_rows':len(frame)})
            if (index+1)%100==0:print(f'C11: {index+1}/{len(files)} estações',flush=True)
    daily=pd.concat(days,ignore_index=True)
    private=safe_path('dados/inmet');private.mkdir(parents=True,exist_ok=True)
    daily.to_csv(private/'c11_dias_2020.csv',index=False)
    pd.DataFrame(stations).to_csv(private/'c11_estacoes_2020.csv',index=False)
    daily['month']=daily.date.dt.month
    rows=[]
    for scope,grouping in [('global',None),('region','region'),('month','month')]:
        subsets=[('all',daily)] if grouping is None else daily.groupby(grouping)
        for group,frame in subsets:
            if frame.station_id.nunique()<5:continue
            for method in ('mean_extremes','mean_compensated'):
                rows.append({'scope':scope,'group':group,'method':method,'n_stations':frame.station_id.nunique(),
                             **metricas(frame.mean_24h,frame[method])})
    pd.DataFrame(rows).to_csv(safe_path('resultados/tabelas/c11_definicoes_2020.csv'),index=False)
    monthly=daily.groupby(['station_id','uf','region','month']).agg(n_days=('date','size'),
        mean_24h=('mean_24h','mean'),mean_extremes=('mean_extremes','mean'),mean_compensated=('mean_compensated','mean')).reset_index()
    monthly['required_days']=[int(np.ceil(pd.Period(f'2020-{m:02d}').days_in_month*.8)) for m in monthly.month]
    eligible=monthly.loc[monthly.n_days.ge(monthly.required_days)]
    eligible.to_csv(private/'c11_meses_2020.csv',index=False)
    pd.DataFrame([{'method':method,'n_station_months':len(eligible),'n_stations':eligible.station_id.nunique(),
                   **metricas(eligible.mean_24h,eligible[method])} for method in ('mean_extremes','mean_compensated')]).to_csv(
                       safe_path('resultados/tabelas/c11_definicoes_mensais_2020.csv'),index=False)
    report={'source':URL,'source_sha256':digest(path),'script_sha256':digest(__file__),'files':len(files),
            'stations_with_paired_days':int(daily.station_id.nunique()),'paired_days':len(daily),
            'eligible_station_months':len(eligible),'minimum_month_coverage':.8,
            'daily_window':'01:00 to next 00:00 UTC, all 24 records for instantaneous air and hourly extrema',
            'compensated_formula':'(Tmax + Tmin + T12 + 2*T24)/5',
            'limitation':'one year of automatic stations; operational compensated proxy, not reproduction of conventional thermometer windows or 1991-2020 normal',
            'source_method':'https://portal.inmet.gov.br/uploads/normais/NORMAISCLIMATOLOGICAS.pdf'}
    safe_path('resultados/tabelas/c11_definicoes_2020.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report,indent=2))


if __name__=='__main__':main()
