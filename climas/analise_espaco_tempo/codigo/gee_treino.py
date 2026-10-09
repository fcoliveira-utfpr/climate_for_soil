"""Matriz de treino no GEE para a simulação dos mapas (script JS simulacao_mapas_soc no repositório
users/fcoliveira/mapbiomas): a matriz bruta reconstruída (matriz_soc_c3_fabricio_bruta, 35.235 linhas, as
covariáveis da C3 no ano de cada linha) mais o clima decenal do ano de cada linha:
    dec_tmean (GT_DECADE_TMEAN_CONTI_2026), dec_prec (GT_DECADE_PRECIPITATION_CONTI_2026),
    dec_cdd (projects/fcoliveira/assets/Climas2/CDD_DECENAL_BRDWGD).
As grades decenais são de 0,1° e não cobrem parte do litoral; os vazios são preenchidos com a média dos
pixels vizinhos (janela de 7 × 7 células, ~0,7°), a mesma regra do script de mapas. Os filtros da matriz
(JS da trainingFinal) são aplicados no próprio script de mapas, como na produção.

Saída: projects/fcoliveira/assets/SOC_C3_FABRICIO/matriz_soc_c3_fabricio_treino

Uso: python gee_treino.py
"""
import ee

import config as cfg
from gee_utils import conectar

COV = 'projects/mapbiomas-workspace/SOLOS/COVARIAVEIS/'
DECENAIS = [('dec_tmean', COV + 'GT_DECADE_TMEAN_CONTI_2026', 'tmean_10yr_mean'),
            ('dec_prec', COV + 'GT_DECADE_PRECIPITATION_CONTI_2026', 'prec_10yr_mean'),
            ('dec_cdd', 'projects/fcoliveira/assets/Climas2/CDD_DECENAL_BRDWGD', 'cdd_10yr_mean')]
DESTINO = f'{cfg.PASTA_GEE}/matriz_soc_c3_fabricio_treino'


def preencher(img):
    """Vazios (litoral) = média dos vizinhos numa janela de 7 x 7 células da própria grade."""
    proj = img.projection()
    viz = img.focalMean(3, 'square', 'pixels').reproject(proj)
    return img.unmask(viz)


def decenal(ano):
    bandas = [preencher(ee.Image(ee.ImageCollection(col).filter(ee.Filter.eq('year', ano)).first()).select([b], [n]))
              for n, col, b in DECENAIS]
    return ee.Image.cat(bandas)


def main():
    conectar(None)
    bruta = ee.FeatureCollection(cfg.MATRIZ_BRUTA_GEE)
    anos = sorted(int(a) for a in bruta.aggregate_array('year').distinct().getInfo())
    partes = [decenal(a).reduceRegions(bruta.filter(ee.Filter.eq('year', a)), ee.Reducer.first(), 11132)
              for a in anos]
    treino = ee.FeatureCollection(partes).flatten()
    t = ee.batch.Export.table.toAsset(collection=treino, description='matriz_soc_c3_fabricio_treino',
                                      assetId=DESTINO)
    t.start()
    print(f'{len(anos)} anos; tarefa {t.id} -> {DESTINO}')


if __name__ == '__main__':
    main()
