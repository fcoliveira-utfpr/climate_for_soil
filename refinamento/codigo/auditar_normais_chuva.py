"""Confere integridade e agregação das normais reais, sem divulgar estações."""
import json
import numpy as np
import pandas as pd
from codigo.dados_temperatura import safe_path
from codigo.grade_brasil import digest


def main():
    path = safe_path('dados/processados/normais_precipitacao.csv')
    manifest = json.loads(path.with_suffix('.manifesto.json').read_text(encoding='utf-8'))
    if digest(path) != manifest['output_sha256']:
        raise ValueError('Hash das normais diverge do manifesto.')
    frame = pd.read_csv(path, dtype={'station_id':str})
    if frame.duplicated(['station_id','month']).any():
        raise ValueError('Normais duplicadas.')
    if not frame.groupby('station_id').month.apply(lambda x:set(x)==set(range(13))).all():
        raise ValueError('Cada estação deve ter 12 registros mensais e um anual.')
    annual = frame.loc[frame.month.eq(0)].set_index('station_id')
    monthly = frame.loc[frame.month.ne(0)].pivot(index='station_id',columns='month',values='precipitation_mm')
    eligible = annual.precipitation_mm.notna()
    expected = monthly.sum(axis=1, min_count=12).reindex(annual.index)
    if not eligible.equals(expected.notna()):
        raise ValueError('Elegibilidade anual diverge dos meses.')
    error = (annual.loc[eligible,'precipitation_mm']-expected[eligible]).abs().max()
    if not np.isfinite(error) or error >= 1e-5:
        raise ValueError('Agregação anual diverge da soma mensal.')
    if not frame.precipitation_mm.dropna().ge(0).all():
        raise ValueError('Normal negativa.')
    if not frame.loc[frame.precipitation_mm.notna(),'n_years'].ge(24).all():
        raise ValueError('Normal aceita com menos de 24 anos.')
    report = {'normal_sha256':digest(path), 'script_sha256':digest(__file__),
              'stations_annual_eligible':int(eligible.sum()),
              'maximum_annual_sum_rounding_error_mm':float(error),
              'eligible_duplicate_coordinate_flags':int(annual.loc[eligible].duplicated(['latitude','longitude'],keep=False).sum()),
              'eligible_missing_elevation':int(annual.loc[eligible].elevation_m.isna().sum()),
              'monthly_normals_nonnegative':True, 'source_comparison_with_gee_completed':False,
              'homogeneity_completed':False}
    safe_path('resultados/tabelas/chuva_auditoria_normais.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report,indent=2))


if __name__=='__main__':
    main()
