"""Treina uma vez e salva como asset os três modelos da simulação de mapas (script JS simulacao_mapas_soc):
treinar 300 árvores profundas a cada tile estoura o limite de tempo do mapa interativo; com o modelo salvo,
o script só faz ee.Classifier.load.

Mesmo treino do script JS: matriz_soc_c3_fabricio_treino com os filtros do script da trainingFinal
(27.425 linhas), smileRandomForest (300 árvores, 24 variáveis por divisão, folha mínima 2, bagFraction
0,632, semente 2021), resposta carbono_gm2_qmap.
    A_oficial_koppen    maxNodes 40, covariáveis da produção (Köppen)
    B_decenal           maxNodes 40, Köppen -> dec_tmean, dec_prec, dec_cdd
    C_decenal_profundo  sem limite de nós, decenal (41,7 MB: só em exportação)
    C_decenal_1000/3000 limite de 1.000 / 3.000 folhas (cabem no mapa interativo; MEC quase igual)

Saída: projects/fcoliveira/assets/SOC_C3_FABRICIO/modelos/rf_<versao>

Uso: python gee_modelos.py [versoes separadas por vírgula]
"""
import sys

import ee

import config as cfg
import covariaveis_c3 as c3
from gee_treino import DESTINO as TREINO
from gee_utils import conectar

PASTA = f'{cfg.PASTA_GEE}/modelos'


def filtros():
    """Condições para descartar (script da trainingFinal, inclusive o 'resingas')."""
    F = ee.Filter
    return [
        F.And(F.eq('PSEUDOROCK_index', 1), F.eq('afloramento', 0)),
        F.And(F.eq('PSEUDOSAND_index', 1), F.eq('areia', 0)),
        F.And(F.eq('PSEUDOROCK_index', 1), F.gt('mb_ndvi_median_decay', 147)),
        F.And(F.eq('PSEUDOROCK_index', 1), F.gt('black_soil_prob', 10)),
        F.And(F.eq('PSEUDOROCK_index', 1), F.gt('argila_000_030cm', 0)),
        F.And(F.eq('PSEUDOSAND_index', 1), F.gt('argila_000_030cm', 0)),
        F.And(F.eq('PSEUDOSAND_index', 1), F.gt('black_soil_prob', 10)),
        F.And(F.eq('PSEUDOSAND_index', 1), F.gt('Wetsols', 10)),
        F.And(F.eq('IFN_index', 1), F.gt('resingas', 0)),
        F.And(F.eq('YEAR_index', -26), F.gt('resingas', 0)),
        F.And(F.gt('black_soil_prob', 10), F.gt('areia', 0)),
        F.And(F.gt('black_soil_prob', 10), F.gt('areia_000_030cm', 70)),
        F.And(F.eq('PSEUDOSAND_index', 0), F.eq('PSEUDOROCK_index', 0), F.lt('mb_evi2_median_decay', 100),
              F.gt('Water_40y_recurrence', 0)),
    ]


ESTATICAS = [b for b in c3.ESTATICAS if b not in c3.KOPPEN]
OFICIAL = c3.INDICES_PONTOS + ESTATICAS + c3.KOPPEN + c3.DINAMICAS
DECENAL = c3.INDICES_PONTOS + ESTATICAS + c3.DINAMICAS + ['dec_tmean', 'dec_prec', 'dec_cdd']
VERSOES = {'A_oficial_koppen': (40, OFICIAL), 'B_decenal': (40, DECENAL), 'C_decenal_profundo': (None, DECENAL),
           # árvores intermediárias: o modelo sem limite (41,7 MB) estoura a memória do mapa interativo
           'C_decenal_1000': (1000, DECENAL), 'C_decenal_3000': (3000, DECENAL)}


def treino():
    fc = ee.FeatureCollection(TREINO)
    for f in filtros():
        fc = fc.filter(f.Not())
    return fc


def main(versoes):
    conectar(None)
    try:
        ee.data.getAsset(PASTA)
    except ee.EEException:
        ee.data.createAsset({'type': 'FOLDER'}, PASTA)
    fc = treino()
    for v in versoes:
        max_nodes, entradas = VERSOES[v]
        par = dict(numberOfTrees=300, variablesPerSplit=24, minLeafPopulation=2, bagFraction=0.632, seed=2021)
        if max_nodes:
            par['maxNodes'] = max_nodes
        clf = ee.Classifier.smileRandomForest(**par).setOutputMode('REGRESSION').train(fc, 'carbono_gm2_qmap', entradas)
        t = ee.batch.Export.classifier.toAsset(classifier=clf, description=f'rf_{v}', assetId=f'{PASTA}/rf_{v}')
        t.start()
        print(f'{v}: {len(entradas)} entradas, maxNodes {max_nodes}; tarefa {t.id}')


if __name__ == '__main__':
    main(sys.argv[1].split(',') if len(sys.argv) > 1 else list(VERSOES)[:3])
