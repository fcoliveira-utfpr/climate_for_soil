"""Etapa 2: normais decenais do Xavier e as quatro classificações climáticas, com a agrometeorologiapy 0.3.0.

Uma classificação por década, alinhada à série de predições do MapBiomas (1985-2024): 1985-1994,
1995-2004, 2005-2014 e 2015-2024 (os mesmos períodos da validação temporal V3 do relatório v2). Normal da
década = média de cada mês nos anos disponíveis (T e ETo até 07/2020 no GEE; chuva até 2022): a última década
tem ~5,5 anos de temperatura e 8 de chuva (registrado em n_anos_T, n_anos_P).

Classificações (todas com filtro de moda 3 x 3, o focalMode do script JS original do Holdridge no
relatório v1, aqui estendido a todos os sistemas; a janela tem ~33 km, no CHELSA tinha ~3 km):
    koppen        classificacao_koppen_grade(T, P, lat)                  -> id 1-31 (KOPPEN_CLASSES)
    holdridge     classificacao_holdridge_grade(T, P, lat), ETP original  -> id 1-38 (HOLDRIDGE_ZONAS_EN)
    thornthwaite  classificacao_thornthwaite_grade(P, ETo, lat, CAD do solo) -> umidade (1-9) e subtipo (1-10);
                  código L2 = 100 x umidade + subtipo
    k10           centróides de corelacao/codigo/zonas_clima.py nas 9 variáveis do clima contínuo
                  (T, P, ETo e balanço hídrico com CAD 100, como no relatório v1)
CAD do solo: AWC (mm/m, 1 m de solo) do relatório v1 (climas/dados_chelsa/awc), média em cada pixel de 0,1°.

Saídas (fora do git), em climas_tempo/dados/:
    classes_decadas.npz  koppen, holdridge, thornthwaite, k10 (década, 393, 391), as variáveis contínuas e
                         n_anos_T / n_anos_P
    classes_1991_2020.npz  normal 1991-2020 (conferência com o CHELSA do relatório v1)
    grade.npz            lat, lon, máscara do Brasil, CAD do solo

Uso: python classificar.py
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import rasterio
from rasterio.enums import Resampling
from rasterio.transform import Affine
from rasterio.warp import reproject

from agrometeorologiapy.classificacao_climatica import (classificacao_holdridge_grade, classificacao_koppen_grade,
                                                        classificacao_thornthwaite_grade)

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / 'corelacao' / 'codigo'))
import zonas_clima as zc  # noqa: E402

DADOS = RAIZ / 'climas_tempo' / 'dados'
MENSAL = DADOS / 'xavier_mensal'
AWC = RAIZ / 'climas' / 'dados_chelsa' / 'awc' / 'AWC_BR_grade_CHELSA.tif'
ANOS_DADOS = range(1961, 2023)
DECADAS = [(1985, 1994), (1995, 2004), (2005, 2014), (2015, 2024)]


def carregar():
    T, P, E = [], [], []
    for a in ANOS_DADOS:
        d = np.load(MENSAL / f'{a}.npz')
        T.append(d['T']), P.append(d['P']), E.append(d['ETo'])
    return np.stack(T), np.stack(P), np.stack(E)        # (ano, 12, 393, 391)


def grade():
    g = json.loads((MENSAL / 'grade.json').read_text())
    a = g['affineTransform']
    h, w = g['dimensions']['height'], g['dimensions']['width']
    transf = Affine(a['scaleX'], 0, a['translateX'], 0, a['scaleY'], a['translateY'])
    lon = a['translateX'] + a['scaleX'] * (np.arange(w) + 0.5)
    lat = a['translateY'] + a['scaleY'] * (np.arange(h) + 0.5)
    return transf, h, w, *np.meshgrid(lon, lat)


def cad_solo(transf, h, w):
    with rasterio.open(AWC) as r:
        awc = r.read(1)
        awc = np.where(np.isfinite(awc) & (awc > 0), awc, np.nan).astype(np.float32)
        destino = np.full((h, w), np.nan, np.float32)
        reproject(awc, destino, src_transform=r.transform, src_crs=r.crs, dst_transform=transf,
                  dst_crs='EPSG:4326', resampling=Resampling.average, src_nodata=np.nan, dst_nodata=np.nan)
    return destino


def normal(X, anos_idx):
    """Média por mês nos anos indicados, ignorando NaN; e o mínimo de anos disponíveis entre os meses."""
    sub = X[anos_idx]
    with np.errstate(invalid='ignore'):
        return np.nanmean(sub, axis=0), np.isfinite(sub).sum(axis=0).min(axis=0)


def moda3x3(cls, valido):
    """Filtro de moda 3 x 3 (como o focalMode do GEE): cada pixel recebe a classe mais frequente na janela,
    sem contar pixels sem dado (0); empate -> a menor classe. Depois recorta pelo Brasil."""
    h, w = cls.shape
    pad = np.pad(cls, 1)
    viz = np.stack([pad[i:i + h, j:j + w] for i in range(3) for j in range(3)])
    classes = np.unique(cls[cls > 0])
    contagem = np.stack([(viz == c).sum(0) for c in classes])
    out = classes[contagem.argmax(0)].astype(cls.dtype)
    return np.where(valido & (cls > 0), out, 0).astype(cls.dtype)


def classificar(T, P, E, lat, cad, valido, centroides):
    """As quatro classificações de uma normal (12, H, W)."""
    T, P, E = (np.where(valido, x, np.nan) for x in (T, P, E))
    k = classificacao_koppen_grade(T, P, lat)['id']
    h = classificacao_holdridge_grade(T, P, lat)['id']
    th = classificacao_thornthwaite_grade(P, E, lat, CAD=np.where(np.isfinite(cad), cad, np.nan))
    th_l2 = (th['umidade'].astype(np.uint16) * 100 + th['subtipo']).astype(np.uint16)
    th_l2[th['umidade'] == 0] = 0
    b100 = classificacao_thornthwaite_grade(P, E, lat, CAD=100.0)          # balanço com CAD 100 (k10)
    cont = {
        'clim_t_media': T.mean(0), 'clim_t_mes_frio': T.min(0), 'clim_p_anual': P.sum(0),
        'clim_p_mes_seco': P.min(0),
        'clim_p_sazonalidade': P.std(0) / np.maximum(P.mean(0), 1e-6),
        'clim_etp_anual': E.sum(0), 'clim_def_anual': b100['DEF_anual'], 'clim_exc_anual': b100['EXC_anual'],
        'clim_im': b100['Im'],
    }
    df = pd.DataFrame({c: v.ravel() for c, v in cont.items()})
    ok = df.notna().all(axis=1).to_numpy()
    zona = np.zeros(df.shape[0], np.uint8)
    cent, media, dp = centroides
    zona[ok] = zc.atribuir(df[ok], cent, media, dp)
    brutas = {'koppen': k, 'holdridge': h, 'thornthwaite': th_l2, 'k10': zona.reshape(T.shape[1:])}
    return {s: moda3x3(c, valido) for s, c in brutas.items()}, cont


def main():
    T, P, E = carregar()
    transf, h, w, lon, lat = grade()
    cad = cad_solo(transf, h, w)
    brasil = np.isfinite(P).all(axis=(0, 1))
    np.savez_compressed(DADOS / 'grade.npz', lat=lat, lon=lon, brasil=brasil, cad=cad)
    centroides = zc.carregar(10)
    anos_dados = np.array(list(ANOS_DADOS))
    dec = {s: [] for s in ('koppen', 'holdridge', 'thornthwaite', 'k10')}
    n_T, n_P = [], []
    conts = {}
    for ini, fim in DECADAS:
        idx = np.where((anos_dados >= ini) & (anos_dados <= fim))[0]
        tn, nt = normal(T, idx)
        pn, npr = normal(P, idx)
        cls, cont = classificar(tn, pn, normal(E, idx)[0], lat, cad, brasil, centroides)
        n_T.append(int(nt[brasil].min())), n_P.append(int(npr[brasil].min()))
        for s in dec:
            dec[s].append(cls[s])
        for c, v in cont.items():
            conts.setdefault(c, []).append(v.astype(np.float32))
        print(f'década {ini}-{fim}: anos na normal T {n_T[-1]}, P {n_P[-1]}', flush=True)
    np.savez_compressed(DADOS / 'classes_decadas.npz', decadas=np.array(DECADAS), n_anos_T=n_T, n_anos_P=n_P,
                        **{s: np.stack(v) for s, v in dec.items()}, **{c: np.stack(v) for c, v in conts.items()})

    # normal 1991-2020 (T e ETo até 07/2020): conferência com os mapas do CHELSA do relatório v1
    idx = np.where((anos_dados >= 1991) & (anos_dados <= 2020))[0]
    cls, _ = classificar(normal(T, idx)[0], normal(P, idx)[0], normal(E, idx)[0], lat, cad, brasil, centroides)
    np.savez_compressed(DADOS / 'classes_1991_2020.npz', **cls)
    print('normal 1991-2020 ok', flush=True)


if __name__ == '__main__':
    main()
