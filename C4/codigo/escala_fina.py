"""Escala fina, etapa 2: variáveis do conjunto curto nos locais da matriz e do painel em três versões, para
validar contra a versão por pixel (V0, a de pontos.py):

    V1 `_bil`  interpolação bilinear das 9 variáveis entre os centros dos pixels de 0,1° (grade estendida e
               preenchida de publicar_curto_gee.py, a mesma que vai para o GEE)
    V2 `_rel`  V1 + correção pela altitude nas temperaturas: T = T_bil + gradiente x (z_local - z_bil) / 1000, com
               z_local do MERIT (90 m), z_bil a altitude média do pixel interpolada e o gradiente estimado no
               próprio Xavier (relevo.py); a amplitude diária não muda
    V3 `cd_arm_csolo_cadfina`  ARM do balanço hídrico com a chuva e a ETo mensais da janela interpoladas
               (bilinear) e a CAD do local (AWC de ~1 km do relatório v1), em vez da CAD média do pixel

Saídas: C4/dados/matriz_c4_fina.parquet, C4/dados/painel_c4_fina.parquet (as colunas novas) e
        codigo/cenarios_c4_fina.json (curto_bil, curto_rel, curto_rel_cad)

Uso: python escala_fina.py
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd
import rasterio
from scipy import ndimage
from scipy.interpolate import RegularGridInterpolator

from agrometeorologiapy.balanco_hidrico import balanco_hidrico_climatologico_grade
from publicar_curto_gee import BANDAS, DX, DY, H, HE, PAD, VARIAVEIS, W, WE, X0E, Y0E, preencher

RAIZ = Path(__file__).resolve().parents[2]
DADOS = RAIZ / 'C4' / 'dados'
TAB = RAIZ / 'C4' / 'resultados' / 'tabelas'
AWC = RAIZ / 'climas' / 'dados_chelsa' / 'awc' / 'AWC_BR_grade_CHELSA.tif'
TEMPERATURAS = ['cd_t_media', 'cd_tmax_media', 'cd_tmin_media', 'cd_t_mes_quente', 'cd_t_mes_frio', 'cd_biotemp']
LAT = Y0E + DY * (np.arange(HE) + 0.5)
LON = X0E + DX * (np.arange(WE) + 0.5)


def interpolador(campo):
    """Bilinear entre centros de pixel; campo (HE, WE) com a latitude decrescente."""
    return RegularGridInterpolator((LAT[::-1], LON), campo[::-1], method='linear', bounds_error=False, fill_value=None)


class Preenchedor:
    """Preenchimento pelo vizinho mais próximo com os índices calculados uma vez (a máscara do Xavier é fixa)."""
    def __init__(self, exemplo):
        g = np.full((HE, WE), np.nan, np.float32)
        g[PAD:PAD + H, PAD:PAD + W] = exemplo
        _, self.idx = ndimage.distance_transform_edt(~np.isfinite(g), return_indices=True)

    def __call__(self, x):
        g = np.full((HE, WE), np.nan, np.float32)
        g[PAD:PAD + H, PAD:PAD + W] = x
        return g[self.idx[0], self.idx[1]]


def cad_local(lon, lat, cad_pixel):
    with rasterio.open(AWC) as r:
        v = np.array([x[0] for x in r.sample(zip(lon, lat), indexes=1)], dtype=float)
    return np.where(np.isfinite(v) & (v > 0), v, cad_pixel)


def versoes(df, z_local):
    """df: longitude, latitude, year. Devolve as colunas novas (mesmo índice)."""
    pts = np.column_stack([df.latitude.to_numpy(), df.longitude.to_numpy()])
    anos = df.year.to_numpy()
    out = {f'{v}_bil': np.full(len(df), np.nan) for v in BANDAS}
    zg = np.load(DADOS / 'altitude_grade.npz')['z']
    z_bil = interpolador(zg)(pts)
    grad = pd.read_csv(TAB / 'gradiente_altitude.csv').set_index('variavel').gradiente_c_por_km
    for ano in np.unique(anos):
        d = np.load(VARIAVEIS / f'{ano}.npz')
        sel = anos == ano
        for v in BANDAS:
            out[f'{v}_bil'][sel] = interpolador(preencher(d[v])[0])(pts[sel])
    for v in BANDAS:
        out[f'{v}_rel'] = out[f'{v}_bil'] + (grad[v] * (z_local - z_bil) / 1000 if v in TEMPERATURAS else 0)

    # V3: balanço hídrico no local com a chuva e a ETo interpoladas e a CAD fina
    mensal = RAIZ / 'C4' / 'dados' / 'xavier_mensal'
    eto_dir = RAIZ / 'C4' / 'dados' / 'eto_rn'
    pre = Preenchedor(np.load(mensal / '2000.npz')['P'][0])
    anos_dados = range(1961, 2026)
    P = np.zeros((len(anos_dados), 12, len(df)), np.float32)
    E = np.zeros_like(P)
    for k, a in enumerate(anos_dados):
        p, e = np.load(mensal / f'{a}.npz')['P'], np.load(eto_dir / f'{a}.npz')['ETo']
        for m in range(12):
            P[k, m] = interpolador(pre(p[m]))(pts)
            E[k, m] = interpolador(pre(e[m]))(pts)
    cad_pixel = interpolador(preencher(np.load(RAIZ / 'climas_tempo' / 'dados' / 'grade.npz')['cad'])[0])(pts)
    cad = cad_local(df.longitude.to_numpy(), df.latitude.to_numpy(), cad_pixel)
    arm = np.full(len(df), np.nan)
    a0 = np.array(list(anos_dados))
    for ano in np.unique(anos):
        sel = anos == ano
        k = (a0 >= ano - 10) & (a0 <= ano - 1)
        bh = balanco_hidrico_climatologico_grade(P[k][:, :, sel].mean(0), E[k][:, :, sel].mean(0), cad[sel])
        arm[sel] = bh['ARM'].mean(0)
    out['cd_arm_csolo_cadfina'] = arm
    out['cad_local'] = cad
    out['z_local'], out['z_bil'] = z_local, z_bil
    return pd.DataFrame(out, index=df.index)


def z_de(df):
    z = pd.read_parquet(DADOS / 'altitude_locais.parquet')
    chave = df.longitude.round(6).astype(str) + '_' + df.latitude.round(6).astype(str)
    zmap = dict(zip(z.longitude.round(6).astype(str) + '_' + z.latitude.round(6).astype(str), z.z_merit))
    return chave.map(zmap).to_numpy(dtype=float)


def main():
    m = pd.read_parquet(DADOS / 'matriz_c4.parquet')
    vm = versoes(m[['longitude', 'latitude', 'year']], z_de(m))
    pd.concat([m, vm], axis=1).to_parquet(DADOS / 'matriz_c4_fina.parquet', index=False)
    print('matriz: diferença média e máxima em relação ao pixel (V0)')
    for v in BANDAS:
        for suf in ('_bil', '_rel'):
            d = vm[v + suf] - m[v]
            print(f'  {v + suf:24s} média {d.mean():+.3f}  |máx| {d.abs().max():.3f}')
    d = vm.cd_arm_csolo_cadfina - m.cd_arm_csolo
    print(f'  cd_arm_csolo_cadfina     média {d.mean():+.3f}  |máx| {d.abs().max():.3f}  r {np.corrcoef(vm.cd_arm_csolo_cadfina, m.cd_arm_csolo)[0, 1]:.3f}')

    p = pd.read_parquet(DADOS / 'painel_c4.parquet')
    vp = versoes(p[['longitude', 'latitude', 'year']], z_de(p))
    pd.concat([p, vp], axis=1).to_parquet(DADOS / 'painel_c4_fina.parquet', index=False)

    base = json.loads(Path(__file__).with_name('cenarios_c4.json').read_text(encoding='utf-8'))['base']
    temp = ['cd_t_media', 'cd_tmax_media', 'cd_tmin_media', 'cd_t_mes_quente', 'cd_t_mes_frio', 'cd_amplitude', 'cd_biotemp']
    cen = {'curto_bil': [f'{v}_bil' for v in temp] + ['cd_cdd_bil', 'cd_arm_csolo_bil'],
           'curto_rel': [f'{v}_rel' for v in temp] + ['cd_cdd_bil', 'cd_arm_csolo_bil'],
           'curto_rel_cad': [f'{v}_rel' for v in temp] + ['cd_cdd_bil', 'cd_arm_csolo_cadfina']}
    Path(__file__).with_name('cenarios_c4_fina.json').write_text(
        json.dumps({'base': base, 'cenarios': cen}, indent=1, ensure_ascii=False), encoding='utf-8')
    print('painel:', len(p), 'linhas; cenários:', {k: len(v) for k, v in cen.items()})


if __name__ == '__main__':
    main()
