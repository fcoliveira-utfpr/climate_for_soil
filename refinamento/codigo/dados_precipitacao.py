"""Normais de chuva observada 1991–2020; mês exige todos os dias válidos.

Usa pr.npz cedido pelo autor. Não mistura os preenchimentos do asset GEE com
observações. Normal anual é soma das 12 normais mensais, não média diária.
"""
from __future__ import annotations
import calendar
import json
import numpy as np
import pandas as pd

from codigo.dados_temperatura import load_observations, safe_path
from codigo.grade_brasil import digest


def monthly_totals(values, dates):
    dates = pd.DatetimeIndex(dates)
    values = np.asarray(values, dtype=float)
    if values.ndim != 2 or values.shape[0] != len(dates) or dates.empty:
        raise ValueError('Valores e calendário incompatíveis.')
    if not dates.equals(pd.date_range(dates.min(), dates.max(), freq='D')):
        raise ValueError('Calendário deve ser diário, ordenado e sem duplicatas ou lacunas.')
    periods = dates.to_period('M')
    months = periods.unique()
    totals, counts = [], []
    for period in months:
        subset = values[periods == period]
        valid = np.isfinite(subset) & (subset >= 0) & (subset < 450)
        n = valid.sum(axis=0)
        total = np.where(valid, subset, 0).sum(axis=0)
        expected = calendar.monthrange(period.year, period.month)[1]
        total[n != expected] = np.nan
        totals.append(total)
        counts.append(n)
    return months, np.stack(totals), np.stack(counts)


def normals(months, totals, minimum_years=24):
    if not 1 <= minimum_years <= 30:
        raise ValueError('Cobertura deve ficar entre 1 e 30 anos.')
    if np.isinf(totals).any() or np.any(totals[np.isfinite(totals)] < 0):
        raise ValueError('Totais mensais inválidos.')
    result = np.full((13, totals.shape[1]), np.nan)
    years = np.zeros_like(result, dtype=int)
    for month in range(1, 13):
        rows = totals[months.month == month]
        count = np.isfinite(rows).sum(axis=0)
        years[month] = count
        means = np.divide(np.nansum(rows, axis=0), count,
                          out=np.full(totals.shape[1], np.nan), where=count > 0)
        result[month] = np.where(count >= minimum_years, means, np.nan)
    complete = np.isfinite(result[1:]).all(axis=0)
    result[0, complete] = result[1:, complete].sum(axis=0)
    years[0] = years[1:].min(axis=0)
    return result, years


def main():
    source = safe_path('dados/brutos/pr.npz')
    provenance = json.loads(safe_path('dados/brutos/pr.fonte.json').read_text(encoding='utf-8'))
    if provenance['sha256'] != digest(source):
        raise ValueError('Fonte de precipitação não confere com o download.')
    observed = load_observations(source)
    selected = observed.dates.year >= 1991
    selected &= observed.dates.year <= 2020
    dates, values = observed.dates[selected], observed.data[selected]
    months, totals, counts = monthly_totals(values, dates)
    if len(months) != 360 or str(months[0]) != '1991-01' or str(months[-1]) != '2020-12':
        raise ValueError('Período observado diferente de 1991–2020.')
    table, sensitivity = [], []
    for minimum in (21, 24, 27):
        normal, years = normals(months, totals, minimum)
        sensitivity.append({'minimum_years':minimum,'coverage_fraction':minimum/30,
                            'stations_12_months':int(np.isfinite(normal[0]).sum()),
                            'eligible_station_months':int(np.isfinite(normal[1:]).sum())})
        if minimum == 24:
            for month in range(13):
                table.append(observed.stations.assign(month=month,precipitation_mm=normal[month],
                                                      n_years=years[month],coverage=years[month]/30))
    normal_path = safe_path('dados/processados/normais_precipitacao.csv')
    pd.concat(table, ignore_index=True).to_csv(normal_path,index=False,float_format='%.10g')
    monthly_path = safe_path('dados/processados/precipitacao_mensal.csv')
    # Gravar por mês evita materializar milhões de registros como objetos Python.
    for i, period in enumerate(months):
        frame = pd.DataFrame({'station_id':observed.stations.station_id,'year':period.year,
                              'month':period.month,'precipitation_mm':totals[i], 'n_valid_days':counts[i]})
        frame.to_csv(monthly_path,index=False,mode='w' if i==0 else 'a',header=i==0,float_format='%.10g')
    pd.DataFrame(sensitivity).to_csv(safe_path('resultados/tabelas/chuva_sensibilidade_cobertura.csv'),index=False)
    duplicates = observed.stations.duplicated(['latitude','longitude'],keep=False)
    qc = {'source_stations':len(observed.stations),'source_days':len(observed.dates),
          'selected_days':len(dates),'station_months_expected':int(totals.size),
          'station_months_complete':int(np.isfinite(totals).sum()),
          'invalid_finite_daily_values':int((np.isfinite(values)&((values<0)|(values>=450))).sum()),
          'nonfinite_daily_values':int((~np.isfinite(values)).sum()),
          'stations_duplicate_coordinates_flag':int(duplicates.sum())}
    pd.DataFrame([qc]).to_csv(safe_path('resultados/tabelas/chuva_controle_qualidade.csv'),index=False)
    manifest = {**provenance,**qc,'script_sha256':digest(__file__),
                'output_sha256':digest(normal_path),'monthly_output_sha256':digest(monthly_path),
                'period':'1991-2020','monthly_units':'mm/month','annual_units':'mm/year',
                'monthly_rule':'all calendar days finite and 0 <= pr < 450 mm/day',
                'annual_rule':'sum of 12 eligible monthly normals; month=0',
                'minimum_years':24,'filled_values_added':False,'sensitivity':sensitivity,
                'status':'initial_QC_not_validated_rainfall_product',
                'pending':['station homogeneity and relocation','independence from grids',
                           'comparison with GEE pr asset','covariates and models','national maps']}
    normal_path.with_suffix('.manifesto.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    print(json.dumps({**qc,'sensitivity':sensitivity},indent=2))


if __name__=='__main__':
    main()
