"""Subprodutos do Köppen do Xavier v3.2.4 (normal 1991-2020): níveis da classe, critérios da classificação e
a normal mensal, em GeoTIFF (mesma grade de koppen_1991_2020.py).

Os critérios repetem as fórmulas de classificacao_koppen_grade da agrometeorologiapy (Alvares et al. 2013, com a
sazonalidade f/s/w de Kottek et al. 2006; verão = out-mar no hemisfério sul):
    t_anual, t_mes_frio, t_mes_quente (°C); meses_t10 (meses com T > 10 °C)
    p_anual, p_mes_seco (mm); frac_p_verao (fração da chuva no semestre de verão)
    limiar_aridez (cm): 2T + 14; 2T se >= 70% da chuva no inverno; 2T + 28 se >= 70% no verão
    razao_aridez = p_anual / (10 * limiar_aridez): < 1 -> grupo B; < 0,5 -> deserto (BW)
    limiar_am (mm) = 100 - p_anual / 25; margem_am = p_mes_seco - limiar_am (>= 0 -> Am, se p_mes_seco < 60)
Os níveis vêm da classe com moda 3 x 3 (banda koppen):
    grupo     1 A, 2 B, 3 C, 4 D, 5 E
    subgrupo  1 Af, 2 Am, 3 As, 4 Aw, 5 BS, 6 BW, 7 Cf, 8 Cs, 9 Cw, 10 Df, 11 Ds, 12 Dw, 13 ET, 14 EF

Saídas (em C4/resultados/koppen_xavier_1991_2020/):
    koppen_xavier_1991_2020_niveis.tif      uint8, bandas grupo e subgrupo (0 = sem dado)
    koppen_xavier_1991_2020_criterios.tif   float32, 11 bandas (NaN = sem dado)
    xavier_normal_1991_2020.tif             float32, 24 bandas: T_01..T_12 (°C) e P_01..P_12 (mm/mês)
    subprodutos.csv                         banda, arquivo, descrição, unidade, mínimo, média e máximo no Brasil
    criterios_koppen.png                    prévia dos critérios

Uso: python subprodutos_koppen.py      (depois de koppen_1991_2020.py)
"""
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import rasterio

from agrometeorologiapy.classificacao_climatica import classificacao_koppen_grade
from koppen_1991_2020 import ANOS, H, MENSAL, SAIDA, TRANSF, W

VERAO_SUL, INVERNO_SUL = [9, 10, 11, 0, 1, 2], [3, 4, 5, 6, 7, 8]
GRUPO = {**dict.fromkeys(range(1, 5), 1), **dict.fromkeys(range(5, 9), 2), **dict.fromkeys(range(9, 18), 3),
         **dict.fromkeys(range(18, 30), 4), 30: 5, 31: 5}
SUBGRUPO = {1: 1, 2: 2, 3: 3, 4: 4, 5: 5, 6: 5, 7: 6, 8: 6, **dict.fromkeys(range(9, 12), 7),
            **dict.fromkeys(range(12, 15), 8), **dict.fromkeys(range(15, 18), 9), **dict.fromkeys(range(18, 22), 10),
            **dict.fromkeys(range(22, 26), 11), **dict.fromkeys(range(26, 30), 12), 30: 13, 31: 14}
CRITERIOS = {
    't_anual': ('temperatura média anual', '°C'), 't_mes_frio': ('temperatura do mês mais frio', '°C'),
    't_mes_quente': ('temperatura do mês mais quente', '°C'), 'meses_t10': ('meses com T > 10 °C', 'meses'),
    'p_anual': ('chuva anual', 'mm'), 'p_mes_seco': ('chuva do mês mais seco', 'mm'),
    'frac_p_verao': ('fração da chuva no semestre de verão (out-mar no sul)', 'fração'),
    'limiar_aridez': ('limiar de aridez do grupo B (2T + 0, 14 ou 28)', 'cm'),
    'razao_aridez': ('chuva anual / (10 x limiar de aridez): < 1 = B; < 0,5 = BW', 'adimensional'),
    'limiar_am': ('limiar Am/Aw: 100 - chuva anual / 25', 'mm'),
    'margem_am': ('chuva do mês mais seco - limiar Am/Aw (>= 0 -> Am quando < 60 mm)', 'mm'),
}


def normais():
    T, P = [], []
    for a in ANOS:
        d = np.load(MENSAL / f'{a}.npz')
        T.append((d['Tmax'] + d['Tmin']) / 2)
        P.append(d['P'])
    return np.stack(T).mean(0), np.stack(P).mean(0)


def criterios(T, P, lat):
    norte = lat > 0
    tann, rann = T.mean(0), P.sum(0)
    p_verao = np.where(norte, P[INVERNO_SUL].sum(0), P[VERAO_SUL].sum(0))
    p_inverno = rann - p_verao
    with np.errstate(divide='ignore', invalid='ignore'):
        fv, fi = p_verao / rann, p_inverno / rann
    lim = np.where(fv >= 0.7, 2 * tann + 28, np.where(fi >= 0.7, 2 * tann, 2 * tann + 14))
    lim_am = 100 - rann / 25
    return {'t_anual': tann, 't_mes_frio': T.min(0), 't_mes_quente': T.max(0), 'meses_t10': (T > 10).sum(0).astype(float),
            'p_anual': rann, 'p_mes_seco': P.min(0), 'frac_p_verao': fv, 'limiar_aridez': lim,
            'razao_aridez': rann / (10 * lim), 'limiar_am': lim_am, 'margem_am': P.min(0) - lim_am}


def gravar(nome, bandas, dtype, nodata):
    perfil = {'driver': 'GTiff', 'height': H, 'width': W, 'count': len(bandas), 'dtype': dtype, 'crs': 'EPSG:4326',
              'transform': TRANSF, 'nodata': nodata, 'compress': 'deflate'}
    with rasterio.open(SAIDA / nome, 'w', **perfil) as r:
        for i, (b, x) in enumerate(bandas.items(), 1):
            r.write(x.astype(dtype), i)
            r.set_band_description(i, b)
        r.update_tags(fonte='Xavier et al. (2022) BR-DWGD v3.2.4, normal 1991-2020')


def main():
    T, P = normais()
    lat = np.repeat((TRANSF.f + TRANSF.e * (np.arange(H) + 0.5))[:, None], W, axis=1)
    brasil = np.isfinite(T).all(0) & np.isfinite(P).all(0)
    with rasterio.open(SAIDA / 'koppen_xavier_1991_2020.tif') as r:
        koppen, bruto = r.read(1), r.read(2)
    # conferência: a classe recalculada aqui é a da banda sem filtro
    assert (classificacao_koppen_grade(np.where(brasil, T, np.nan), np.where(brasil, P, np.nan), lat)['id'] == bruto).all()

    niveis = {'grupo': np.vectorize(lambda c: GRUPO.get(int(c), 0))(koppen),
              'subgrupo': np.vectorize(lambda c: SUBGRUPO.get(int(c), 0))(koppen)}
    gravar('koppen_xavier_1991_2020_niveis.tif', niveis, 'uint8', 0)
    with np.errstate(invalid='ignore', divide='ignore'):
        crit = {k: np.where(brasil, v, np.nan) for k, v in criterios(T, P, lat).items()}
    # conferência: grupo B pelos critérios = classes B sem filtro
    assert ((crit['razao_aridez'] < 1) == np.isin(bruto, [5, 6, 7, 8]))[brasil].all()
    gravar('koppen_xavier_1991_2020_criterios.tif', crit, 'float32', np.nan)
    normal = {**{f'T_{m:02d}': np.where(brasil, T[m - 1], np.nan) for m in range(1, 13)},
              **{f'P_{m:02d}': np.where(brasil, P[m - 1], np.nan) for m in range(1, 13)}}
    gravar('xavier_normal_1991_2020.tif', normal, 'float32', np.nan)

    linhas = []
    for arq, bandas, desc in [('koppen_xavier_1991_2020_niveis.tif', niveis,
                               {'grupo': ('grupo: 1 A, 2 B, 3 C, 4 D, 5 E', 'classe'),
                                'subgrupo': ('subgrupo: 1 Af, 2 Am, 3 As, 4 Aw, 5 BS, 6 BW, 7 Cf, 8 Cs, 9 Cw', 'classe')}),
                              ('koppen_xavier_1991_2020_criterios.tif', crit, CRITERIOS),
                              ('xavier_normal_1991_2020.tif', normal,
                               {b: (f"{'temperatura média' if b[0] == 'T' else 'chuva'} do mês {b[2:]}",
                                    '°C' if b[0] == 'T' else 'mm/mês') for b in normal})]:
        for b, x in bandas.items():
            v = x[brasil].astype(float)
            linhas.append({'arquivo': arq, 'banda': b, 'descricao': desc[b][0], 'unidade': desc[b][1],
                           'min': v.min(), 'media': v.mean(), 'max': v.max()})
    tab = pd.DataFrame(linhas)
    tab.to_csv(SAIDA / 'subprodutos.csv', index=False, float_format='%.3f')

    fig, axs = plt.subplots(3, 4, figsize=(16, 12))
    ext = (TRANSF.c, TRANSF.c + W * TRANSF.a, TRANSF.f + H * TRANSF.e, TRANSF.f)
    for ax, (b, x) in zip(axs.flat, crit.items()):
        cmap = 'RdBu' if b in ('razao_aridez', 'margem_am') else 'viridis'
        im = ax.imshow(x, extent=ext, cmap=cmap, interpolation='nearest',
                       **({'vmin': 0, 'vmax': 2} if b == 'razao_aridez' else
                          {'vmin': -60, 'vmax': 60} if b == 'margem_am' else {}))
        ax.set_title(f'{b} ({CRITERIOS[b][1]})', fontsize=10)
        ax.set_xticks([]), ax.set_yticks([])
        fig.colorbar(im, ax=ax, shrink=0.75)
    axs.flat[-1].axis('off')
    fig.suptitle('Critérios do Köppen, Xavier v3.2.4, normal 1991-2020', fontsize=13)
    fig.tight_layout()
    fig.savefig(SAIDA / 'criterios_koppen.png', dpi=120)
    plt.close(fig)
    print(tab.round(2).to_string(index=False))


if __name__ == '__main__':
    main()
