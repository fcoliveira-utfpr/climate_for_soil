"""Confere as covariáveis de covariaveis_c3.py contra as matrizes do MapBiomas legíveis por esta conta.

- c03_psd_v2025_11_18 (textura C3): mesmas covariáveis estáticas do módulo do carbono, exceto a textura.
- matriz-collection3_carbon_datac2v2 (carbono, versão anterior do módulo): dinâmicas no ano de cada linha
  (idades de uso, índices com decaimento, água) e Area_Estavel.

Em N linhas sorteadas de cada matriz, extrai a nossa pilha no mesmo ponto (e no mesmo ano, na de carbono) e
mede, por coluna em comum, a fração de linhas com o mesmo valor (diferença ≤ 0,5 depois do arredondamento)
e a correlação. Saída: resultados/tabelas/conferencia_covariaveis.csv.

Uso: python conferir_covariaveis.py [N]
"""
import sys
from pathlib import Path

import ee
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / 'corelacao' / 'codigo'))
from gee_utils import conectar  # noqa: E402

import covariaveis_c3 as c3  # noqa: E402

MATRIZES = 'projects/mapbiomas-workspace/SOLOS/AMOSTRAS/MATRIZES/collection3/'
TEXTURA = MATRIZES + 'c03_psd_v2025_11_18'
CARBONO = MATRIZES + 'matriz-collection3_carbon_datac2v2'
RENOMEAR_CARBONO = {'antropico': 'agropecuaria'}          # nome antigo -> nome da C3
SAIDA = Path(__file__).resolve().parents[1] / 'resultados' / 'tabelas' / 'conferencia_covariaveis.csv'


def _sorteio(asset, n, semente=2026):
    fc = ee.FeatureCollection(asset).randomColumn('sorteio', semente).sort('sorteio').limit(n)
    return fc.map(lambda f: f.set('linha', f.get('system:index')))


def _baixar(fc):
    return pd.DataFrame([f['properties'] for f in fc.getInfo()['features']]).set_index('linha')


def _comparar(ref, nosso, matriz):
    linhas = []
    for col in sorted(set(ref.columns) & set(nosso.columns)):
        a = pd.to_numeric(ref[col], errors='coerce')
        b = pd.to_numeric(nosso[col].reindex(a.index), errors='coerce')
        ok = a.notna() & b.notna()
        if not ok.any():
            continue
        dif = (a[ok] - b[ok]).abs()
        r = np.corrcoef(a[ok], b[ok])[0, 1] if a[ok].std() > 0 and b[ok].std() > 0 else np.nan
        linhas.append({'matriz': matriz, 'covariavel': col, 'n': int(ok.sum()), 'iguais': (dif <= 0.5).mean(),
                       'dif_media': dif.mean(), 'r': r})
    return pd.DataFrame(linhas)


def conferir_textura(n):
    ref = _sorteio(TEXTURA, n)
    nosso = c3.estaticas().round().sampleRegions(collection=ref.select(['linha']), scale=30)
    return _comparar(_baixar(ref), _baixar(nosso), 'c03_psd_v2025_11_18')


def conferir_carbono(n):
    ref = _sorteio(CARBONO, n)
    ref_df = _baixar(ref).rename(columns=RENOMEAR_CARBONO)
    est = c3.estaticas()
    partes = []
    for ano in sorted(ref_df['year'].dropna().astype(int).unique()):
        img = ee.Image.cat([est.select(['Area_Estavel']), c3.dinamicas(int(ano))]).round()
        pts = ref.filter(ee.Filter.eq('year', int(ano))).select(['linha'])
        partes.append(_baixar(img.sampleRegions(collection=pts, scale=30)))
    nosso = pd.concat(partes)
    return _comparar(ref_df, nosso, 'carbon_datac2v2')


if __name__ == '__main__':
    conectar(None)
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 300
    tab = pd.concat([conferir_textura(n), conferir_carbono(n)], ignore_index=True)
    SAIDA.parent.mkdir(parents=True, exist_ok=True)
    tab.to_csv(SAIDA, index=False, float_format='%.4g')
    pd.set_option('display.width', 200, 'display.max_rows', 300)
    print(tab.sort_values('iguais').to_string(index=False))
