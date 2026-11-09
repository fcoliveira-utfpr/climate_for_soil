"""Consolida somente execuções concluídas e verifica pareamento das comparações."""
import json
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from codigo.dados_temperatura import safe_path
from codigo.grade_brasil import digest
from codigo.modelos import paired_intervals
from codigo.modelos_chuva import summary


def read_run(suffix):
    path = safe_path(f'dados/chuva/predicoes_{suffix}.csv')
    meta = json.loads(path.with_suffix('.json').read_text(encoding='utf-8'))
    if meta['output_sha256'] != digest(path) or meta['holdout_scored']:
        raise ValueError('Execução sem integridade ou com teste reservado consumido.')
    return pd.read_csv(path, dtype={'station_id': str}), meta


def main():
    audits = {}
    for block in (1, 2):
        base, first = read_run(f'M2_{block}graus_30m_base')
        frames = [base]
        runs = ['M2']
        for method in ('M4', 'M5', 'M6'):
            suffix = f'{method}_{block}graus_30m_base'
            if not safe_path(f'dados/chuva/predicoes_{suffix}.json').exists():
                continue
            frame, meta = read_run(suffix)
            if meta['hashes'] != first['hashes']:
                raise ValueError('Comparações usam dados de versões diferentes.')
            frames.append(frame.loc[frame.method.str.startswith(method)])
            runs.append(method)
        combined = pd.concat(frames, ignore_index=True)
        metrics = summary(combined)
        metrics.to_csv(safe_path(f'resultados/tabelas/chuva_metodos_{block}graus.csv'), index=False)
        for reference in ('M0_chelsa', 'M0_chirps'):
            differences = paired_intervals(combined.rename(columns={'precipitation_mm': 'temperature_c'}), reference_method=reference)
            differences.rename(columns={'delta_rmse_c': 'delta_rmse_mm'}).to_csv(
                safe_path(f'resultados/tabelas/chuva_metodos_diferencas_{reference}_{block}graus.csv'), index=False)
        audits[str(block)] = {'methods_executed': runs, 'development_stations': first['development_stations'],
                             'reserved_stations': first['reserved_after_covariates'], 'hashes': first['hashes']}
        fig, ax = plt.subplots(figsize=(10, 5))
        means = metrics.loc[metrics.scope.eq('monthly')].groupby('method').rmse.mean().sort_values()
        bars = ax.barh(means.index, means, color='#147d64')
        ax.bar_label(bars, fmt='%.2f', padding=3)
        ax.set_xlim(0, means.max()*1.18)
        ax.set_xlabel('RMSE mensal (mm); média de três repetições')
        ax.set_title(f'Chuva 1991–2020 — validação espacial em blocos de {block}°')
        ax.invert_yaxis()
        fig.text(.5, .01, '1.878 estações de desenvolvimento; independência das grades ainda não comprovada.', ha='center', fontsize=9)
        fig.tight_layout(rect=(0, .04, 1, 1))
        fig.savefig(safe_path(f'resultados/figuras/chuva_metodos_{block}graus.png'), dpi=160)
        plt.close(fig)
        variants = []
        for scale, satellite in ((30, False), (90, False), (1000, False), (30, True)):
            suffix = f'M5_{block}graus_{scale}m_{"satelite" if satellite else "base"}'
            if not safe_path(f'dados/chuva/predicoes_{suffix}.json').exists():
                continue
            frame, meta = read_run(suffix)
            if meta['hashes'] != first['hashes']:
                raise ValueError('Covariáveis de versões diferentes.')
            selected = frame.loc[frame.method.eq('M5_correction')].copy()
            selected['method'] = f'M5_{scale}m_{"CHIRPS" if satellite else "base"}'
            variants.append(selected)
        if variants:
            combined = pd.concat(variants, ignore_index=True)
            summary(combined).to_csv(safe_path(f'resultados/tabelas/chuva_covariaveis_{block}graus.csv'), index=False)
            differences = paired_intervals(combined.rename(columns={'precipitation_mm': 'temperature_c'}), reference_method='M5_30m_base')
            differences.rename(columns={'delta_rmse_c': 'delta_rmse_mm'}).to_csv(
                safe_path(f'resultados/tabelas/chuva_covariaveis_diferencas_{block}graus.csv'), index=False)
            audits[str(block)]['variants_executed'] = list(combined.method.unique())
            # O CHIRPS é também uma referência: adicionar a covariável não basta
            # para demonstrar ganho sobre a própria grade usada como preditor.
            reference = base.loc[base.method.eq('M0_chirps')]
            paired = pd.concat([combined, reference], ignore_index=True)
            differences = paired_intervals(paired.rename(columns={'precipitation_mm': 'temperature_c'}), reference_method='M0_chirps')
            differences.rename(columns={'delta_rmse_c': 'delta_rmse_mm'}).to_csv(
                safe_path(f'resultados/tabelas/chuva_covariaveis_vs_chirps_{block}graus.csv'), index=False)
    safe_path('resultados/tabelas/chuva_comparacoes.json').write_text(json.dumps(audits, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
