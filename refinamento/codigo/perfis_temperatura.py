"""C10: perfis e saltos entre pixels no piloto; diagnóstico, não validação."""
import json
import numpy as np
import pandas as pd
import rasterio
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from codigo.dados_temperatura import safe_path
from codigo.grade_brasil import digest
from codigo.mapa_piloto import month_weights


def main():
    covpath = safe_path('dados/piloto/covariaveis.tiff')
    temppath = safe_path('dados/piloto/temperatura_media_30m_anual_curitiba_M5_lightgbm_correction.tiff')
    with rasterio.open(covpath) as source:
        cov = source.read(masked=True).astype(float).filled(np.nan)
        transform, crs = source.transform, source.crs
    cov[cov == -9999] = np.nan
    with rasterio.open(temppath) as source:
        if source.transform != transform or source.crs != crs or source.shape != cov.shape[1:]:
            raise ValueError('Perfis exigem grades alinhadas.')
        temperature = source.read(1, masked=True).astype(float).filled(np.nan)*source.scales[0]
    chelsa = np.tensordot(month_weights(), cov[:12], axes=1)
    rows = []
    for axis, orientation in ((0, 'norte_sul'), (1, 'oeste_leste')):
        delta = np.abs(np.diff(temperature, axis=axis))
        coarse_delta = np.abs(np.diff(chelsa, axis=axis))
        valid = np.isfinite(delta) & np.isfinite(coarse_delta)
        for label, mask in (('mudanca_CHELSA', coarse_delta > 1e-6), ('CHELSA_constante', coarse_delta <= 1e-6)):
            values = delta[valid & mask]
            rows.append({'orientation': orientation, 'class': label, 'pairs': len(values),
                         'mean_abs_jump_c': float(values.mean()) if len(values) else None,
                         'p95_abs_jump_c': float(np.quantile(values, .95)) if len(values) else None,
                         'max_abs_jump_c': float(values.max()) if len(values) else None})
    pd.DataFrame(rows).to_csv(safe_path('resultados/tabelas/c10_saltos_curitiba.csv'), index=False)
    fig, axes = plt.subplots(3, 2, figsize=(12, 8))
    for index, fraction in enumerate((.25, .5, .75)):
        row = int(temperature.shape[0]*fraction)
        distance = np.arange(temperature.shape[1])*30/1000
        axes[index, 0].plot(distance, temperature[row], label='Modelo 30 m', lw=1)
        axes[index, 0].plot(distance, chelsa[row], label='CHELSA', lw=1)
        axes[index, 0].set_ylabel('Temperatura anual (°C)')
        axes[index, 0].set_title(f'Transecto oeste–leste, linha {row}')
        axes[index, 0].legend(fontsize=8)
        axes[index, 1].plot(distance, cov[12, row], color='#617d8a', lw=1)
        axes[index, 1].set_ylabel('Altitude DSM (m)')
        axes[index, 1].set_title('Relevo no mesmo transecto')
        for ax in axes[index]:
            ax.set_xlabel('Distância (km)'); ax.grid(alpha=.2)
    fig.suptitle('C10 — perfis do piloto experimental de Curitiba (12 × 12 km)')
    fig.tight_layout(rect=(0, 0, 1, .96))
    fig.savefig(safe_path('resultados/figuras/c10_perfis_curitiba.png'), dpi=160)
    plt.close(fig)
    safe_path('resultados/tabelas/c10_perfis_curitiba.json').write_text(json.dumps({
        'temperature_sha256': digest(temppath), 'covariates_sha256': digest(covpath),
        'script_sha256': digest(__file__), 'transect_row_fractions': [.25,.5,.75],
        'interpretation': 'Descriptive pixel jumps; terrain confounding not controlled; no national seams assessed.',
        'independent_validation': False}, indent=2), encoding='utf-8')


if __name__ == '__main__': main()
