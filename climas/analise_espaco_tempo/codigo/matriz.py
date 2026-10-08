"""Etapa 2: matriz de treino do SOC C3 reconstruída (matriz_soc_c3_fabricio).

Como em carbon/1_data_matrix: para cada ano dos pontos, a pilha de covariaveis_c3.pilha(ano) é amostrada
(sampleRegions, 30 m) nos pontos daquele ano; tudo vai para um asset numa única exportação. Depois, os
filtros da matriz em duas versões:
- 'js': o script que gerou a c03_soc_v2025_trainingFinal (referencia/soc_trainingFinal_c3_2025_11_26.js),
  com 'resingas' (no GEE, os dois filtros de restinga removem todo o IFN e todo o YEAR_index -26) e
  black_soil_prob > 10 no filtro de areia;
- 'r': soildata/26_soc_filter_matrix.R (restingas e black_soil_prob > 50).
Fica a versão JS, que reproduz exatamente a trainingFinal; a versão R reproduz as contagens anotadas no R 26.

Uso:
    python matriz.py exportar     # dispara a tarefa no GEE
    python matriz.py baixar       # baixa o asset para climas/dados_espaco_tempo/ (parquet)
    python matriz.py filtrar      # aplica os filtros, grava a matriz e resultados/tabelas/filtros_matriz.csv
"""
import sys

import ee
import pandas as pd

import config as cfg
import covariaveis_c3 as c3
from gee_utils import conectar
from preparar_dados import baixar_featurecollection

# (nome, condição para DESCARTAR) na ordem do script; `v` é a versão ('js' ou 'r').
FILTROS = [
    ('rocha fora de afloramento', lambda d, v: (d.PSEUDOROCK_index == 1) & (d.afloramento == 0)),
    ('areia fora de areia', lambda d, v: (d.PSEUDOSAND_index == 1) & (d.areia == 0)),
    ('rocha com NDVI > 147', lambda d, v: (d.PSEUDOROCK_index == 1) & (d.mb_ndvi_median_decay > 147)),
    ('rocha com solo escuro > 10', lambda d, v: (d.PSEUDOROCK_index == 1) & (d.black_soil_prob > 10)),
    ('rocha com argila > 0', lambda d, v: (d.PSEUDOROCK_index == 1) & (d.argila_000_030cm > 0)),
    ('areia com argila > 0', lambda d, v: (d.PSEUDOSAND_index == 1) & (d.argila_000_030cm > 0)),
    ('areia com solo escuro > 10', lambda d, v: (d.PSEUDOSAND_index == 1) & (d.black_soil_prob > 10)),
    ('areia com Wetsols > 10', lambda d, v: (d.PSEUDOSAND_index == 1) & (d.Wetsols > 10)),
    # JS: ee.Filter.gt('resingas', 0) compara uma propriedade que não existe e dá nulo; o .not() de
    # and(IFN == 1, nulo) também é falso, então saem TODAS as linhas do IFN e todas as de YEAR_index -26
    # (não só as de restinga). É o que reproduz a trainingFinal (27.425 linhas, 14.704 ids, 13.108 grupos).
    ('IFN em restinga', lambda d, v: (d.IFN_index == 1) & ((d.restingas > 0) | (v == 'js'))),
    ('YEAR_index -26 em restinga', lambda d, v: (d.YEAR_index == -26) & ((d.restingas > 0) | (v == 'js'))),
    ('solo escuro > 10 em areia (uso)', lambda d, v: (d.black_soil_prob > 10) & (d.areia > 0)),
    ('solo escuro em textura arenosa (> 70)',
     lambda d, v: (d.black_soil_prob > (10 if v == 'js' else 50)) & (d.areia_000_030cm > 70)),
    ('água: EVI2 < 100 e recorrência > 0',
     lambda d, v: (d.PSEUDOSAND_index == 0) & (d.PSEUDOROCK_index == 0) & (d.mb_evi2_median_decay < 100)
     & (d.Water_40y_recurrence > 0)),
]


def exportar():
    try:
        ee.data.getAsset(cfg.PASTA_GEE)
    except ee.EEException:
        ee.data.createAsset({'type': 'FOLDER'}, cfg.PASTA_GEE)
    pontos = ee.FeatureCollection(cfg.ASSET_PONTOS)
    anos = sorted(int(a) for a in pontos.aggregate_array('ano').distinct().getInfo())
    est = c3.estaticas()
    partes = [c3.pilha(ano, est).sampleRegions(collection=pontos.filter(ee.Filter.eq('ano', ano)),
                                               properties=cfg.PROPS_PONTOS, scale=30, geometries=True)
              for ano in anos]
    tarefa = ee.batch.Export.table.toAsset(collection=ee.FeatureCollection(partes).flatten(),
                                           description='matriz_soc_c3_fabricio_bruta',
                                           assetId=cfg.MATRIZ_BRUTA_GEE)
    tarefa.start()
    print(f'{len(anos)} anos ({anos[0]}-{anos[-1]}); tarefa {tarefa.id}')


def baixar():
    df = baixar_featurecollection(cfg.MATRIZ_BRUTA_GEE)
    cfg.DADOS.mkdir(parents=True, exist_ok=True)
    df.to_parquet(cfg.MATRIZ_BRUTA, index=False)
    print(f'{len(df)} linhas x {df.shape[1]} colunas -> {cfg.MATRIZ_BRUTA}')


def aplicar_filtros(df, versao):
    linhas, d = [], df
    for nome, cond in FILTROS:
        fora = cond(d, versao)
        linhas.append({'versao': versao, 'filtro': nome, 'removidas': int(fora.sum()), 'restam': int((~fora).sum())})
        d = d[~fora]
    return d, pd.DataFrame(linhas)


def grupos(d):
    return d['id'].str.replace(r'^trep(10|20)-', '', regex=True).nunique()


def filtrar():
    bruta = pd.read_parquet(cfg.MATRIZ_BRUTA)
    print(f'matriz bruta: {len(bruta)} linhas (pontos no asset: 35.235)')
    tabs, saidas = [], {}
    for versao in ('js', 'r'):
        saidas[versao], tab = aplicar_filtros(bruta, versao)
        tabs.append(tab)
    tab = pd.concat(tabs, ignore_index=True)
    cfg.TABELAS.mkdir(parents=True, exist_ok=True)
    tab.to_csv(cfg.TABELAS / 'filtros_matriz.csv', index=False)
    print(tab.to_string(index=False))
    ref = cfg.TRAINING_FINAL
    for v, d in saidas.items():
        print(f'{v}: {len(d)} linhas, {d.id.nunique()} ids, {grupos(d)} grupos '
              f'(trainingFinal: {ref["linhas"]}, {ref["ids"]}, {ref["grupos"]})')
    saidas['js'].to_parquet(cfg.MATRIZ, index=False)
    print(f'matriz (versão JS) -> {cfg.MATRIZ}')


if __name__ == '__main__':
    conectar(None)
    etapa = sys.argv[1] if len(sys.argv) > 1 else ''
    {'exportar': exportar, 'baixar': baixar, 'filtrar': filtrar}.get(etapa, lambda: print(__doc__))()
