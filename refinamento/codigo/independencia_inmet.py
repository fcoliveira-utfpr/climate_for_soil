"""C14: triagem de procedência, sem confundir código diferente com independência."""
import json
import zipfile
import numpy as np
import pandas as pd
from sklearn.neighbors import BallTree
from codigo.dados_temperatura import safe_path,_load_legacy_ids
from codigo.grade_brasil import digest


def main():
    hourly=safe_path('dados/brutos/inmet_2020.zip')
    stations=[]
    with zipfile.ZipFile(hourly) as archive:
        for name in archive.namelist():
            if not name.lower().endswith('.csv'):continue
            with archive.open(name) as handle:lines=handle.read(4096).decode('latin1').splitlines()[:8]
            meta={line.split(';')[0].strip(':'):line.split(';')[1] for line in lines}
            stations.append({'station_id':meta['CODIGO (WMO)'],'latitude':float(meta['LATITUDE'].replace(',','.')),
                             'longitude':float(meta['LONGITUDE'].replace(',','.'))})
    stations=pd.DataFrame(stations)
    if stations.station_id.duplicated().any():raise ValueError('Códigos INMET duplicados.')
    author=[];hashes={}
    for name in ('Tmax','Tmin'):
        path=safe_path(f'dados/brutos/{name}.npz');hashes[name]=digest(path)
        with np.load(path,allow_pickle=False) as archive:
            try:ids=archive['ID'].astype(str)
            except ValueError:ids=_load_legacy_ids(path)
            coords=archive['lat_lon_alt'][:,:2]
        author.append(pd.DataFrame({'station_id':ids,'latitude':coords[:,0],'longitude':coords[:,1]}))
    author=pd.concat(author,ignore_index=True).drop_duplicates()
    tree=BallTree(np.deg2rad(author[['latitude','longitude']]),metric='haversine')
    distances,_=tree.query(np.deg2rad(stations[['latitude','longitude']]),k=1)
    stations['nearest_author_km']=distances[:,0]*6371.0088
    stations['id_in_author']=stations.station_id.isin(author.station_id)
    stations['candidate_only']=~stations.id_in_author&stations.nearest_author_km.gt(5)
    private=safe_path('dados/inmet');private.mkdir(parents=True,exist_ok=True)
    stations.to_csv(private/'c14_candidatas_2020.csv',index=False)
    report={'hourly_sha256':digest(hourly),'author_sources_sha256':hashes,'script_sha256':digest(__file__),
            'inmet_stations':len(stations),'matching_author_id':int(stations.id_in_author.sum()),
            'within_5km_author_station':int(stations.nearest_author_km.le(5).sum()),
            'candidate_without_id_or_5km_match':int(stations.candidate_only.sum()),
            'proven_independent_stations':0,'independent_test_completed':False,
            'reason':'Absence from supplied Tmax/Tmin is only a candidate screen; needs historical versions, aliases, relocations and grid-specific provenance. 2020 alone is not a 1991-2020 normal.'}
    safe_path('resultados/tabelas/c14_triagem_inmet_2020.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report,indent=2))


if __name__=='__main__':main()
