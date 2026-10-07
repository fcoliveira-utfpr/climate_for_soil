"""CDD (dias secos consecutivos) decenal a partir da chuva diária do Xavier (BR-DWGD), no padrão das
coleções GT_DECADE_*_CONTI_2026 do GT de clima do MapBiomas Solo (cuja coleção de CDD está vazia).

CDD anual (índice ETCCDI): maior número de dias seguidos, no ano, com chuva diária < 1 mm. Uma estiagem
que começa no ano anterior e termina no ano Y conta em Y (a sequência atravessa a virada do ano, como no
padrão do ETCCDI/climdex), o que importa no norte do país, onde a seca vai de dezembro a março.

CDD decenal do ano Y = média do CDD anual de Y-10 a Y-1 (mesma janela das coleções do GT: propriedades
year, startYear, endYear). A grade pública do BR-DWGD vai até 31/12/2022, então os anos com janela
incompleta (2024: 2014-2022) usam os anos disponíveis e registram n_anos < 10.

Fonte: projects/sat-io/open-datasets/BR-DWGD/PR (Xavier et al. 2022, doi 10.1002/joc.7731), diário,
0,1°, inteiro codificado: mm = b1 * 0,006866665 + 225.

Saídas (assets no GEE):
    projects/fcoliveira/assets/Climas2/CDD_ANUAL_BRDWGD     ImageCollection, banda 'cdd', 1961-2022
    projects/fcoliveira/assets/Climas2/CDD_DECENAL_BRDWGD   ImageCollection, banda 'cdd_10yr_mean', 1971-2024

Uso:
    python cdd_brdwgd.py teste              # confere a decodificação e o CDD em pontos conhecidos (não exporta)
    python cdd_brdwgd.py anual [1961 2022]  # exporta o CDD anual (uma tarefa por ano)
    python cdd_brdwgd.py decenal            # exporta o CDD decenal a partir do anual (depois das tarefas anuais)
"""
import sys
from pathlib import Path

import ee

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / 'corelacao' / 'codigo'))
from gee_utils import conectar  # noqa: E402

PR = 'projects/sat-io/open-datasets/BR-DWGD/PR'
ESCALA, DESLOCAMENTO = 0.006866665, 225.0
LIMIAR_MM = 1.0
PRIMEIRO_ANO, ULTIMO_ANO = 1961, 2022          # cobertura da grade pública
ANOS_DECENAL = (1971, 2024)
PASTA = 'projects/fcoliveira/assets/Climas2'
COL_ANUAL = f'{PASTA}/CDD_ANUAL_BRDWGD'
COL_DECENAL = f'{PASTA}/CDD_DECENAL_BRDWGD'


def chuva_diaria():
    pr = ee.ImageCollection(PR)
    return pr.map(lambda im: im.multiply(ESCALA).add(DESLOCAMENTO).rename('pr')
                  .copyProperties(im, ['system:time_start']))


def _dias(ano):
    return chuva_diaria().filterDate(f'{ano}-01-01', f'{ano + 1}-01-01').sort('system:time_start')


def _secos(ano):
    """Vetor (array 1-D por pixel) com 1 nos dias secos e 0 nos chuvosos, em ordem."""
    arr = _dias(ano).map(lambda im: im.lt(LIMIAR_MM).toInt16()).toArray()   # [dias, 1]
    return arr.arrayProject([0])


def _sequencias(seco):
    """Dias secos seguidos até cada dia (zera no dia chuvoso), sem laço: soma acumulada dos dias secos menos
    o valor dela no último dia chuvoso. Também devolve se já houve dia chuvoso até cada dia."""
    acum = seco.arrayAccum(0, ee.Reducer.sum())
    chuvoso = seco.multiply(-1).add(1)
    no_ultimo_chuvoso = acum.multiply(chuvoso).arrayAccum(0, ee.Reducer.max())
    return acum.subtract(no_ultimo_chuvoso), chuvoso.arrayAccum(0, ee.Reducer.max())


def cdd_ano(ano):
    """CDD do ano: a sequência seca que vem de 31/12 do ano anterior continua contando."""
    seq, ja_choveu = _sequencias(_secos(ano))
    if ano > PRIMEIRO_ANO:
        seq_ant, _ = _sequencias(_secos(ano - 1))
        herdada = seq_ant.arraySlice(0, -1).arrayGet([0])          # sequência seca em 31/12 do ano anterior
        seq = seq.add(ja_choveu.multiply(-1).add(1).multiply(herdada))   # soma só até a 1ª chuva do ano
    ref = ee.Image(_dias(ano).first())
    cdd = seq.arrayReduce(ee.Reducer.max(), [0]).arrayGet([0]).rename('cdd').toInt16()
    return (cdd.updateMask(ref.mask()).setDefaultProjection(ref.projection())
            .set({'year': ano, 'system:time_start': ee.Date.fromYMD(ano, 1, 1).millis(),
                  'limiar_mm': LIMIAR_MM, 'fonte': PR}))


def _garantir_colecao(asset_id):
    try:
        ee.data.getAsset(asset_id)
    except ee.EEException:
        ee.data.createAsset({'type': 'IMAGE_COLLECTION'}, asset_id)


def exportar_anual(ano_ini=PRIMEIRO_ANO, ano_fim=ULTIMO_ANO):
    _garantir_colecao(COL_ANUAL)
    ref = ee.Image(chuva_diaria().first())
    proj = ref.projection().getInfo()
    regiao = ref.geometry()
    for ano in range(ano_ini, ano_fim + 1):
        tarefa = ee.batch.Export.image.toAsset(
            image=cdd_ano(ano), description=f'cdd_anual_{ano}', assetId=f'{COL_ANUAL}/{ano}',
            crs=proj['crs'], crsTransform=proj['transform'], region=regiao, maxPixels=1e9)
        tarefa.start()
        print(f'  tarefa {ano}: {tarefa.id}', flush=True)


def cdd_decenal(ano, anual):
    ini, fim = ano - 10, ano - 1
    janela = anual.filter(ee.Filter.rangeContains('year', ini, fim))
    return (janela.mean().rename('cdd_10yr_mean').toFloat()
            .set({'year': ano, 'startYear': ini, 'endYear': fim, 'n_anos': janela.size(),
                  'system:time_start': ee.Date.fromYMD(ano, 1, 1).millis(), 'fonte': COL_ANUAL}))


def exportar_decenal(ano_ini=ANOS_DECENAL[0], ano_fim=ANOS_DECENAL[1]):
    _garantir_colecao(COL_DECENAL)
    anual = ee.ImageCollection(COL_ANUAL)
    n = anual.size().getInfo()
    if n < ULTIMO_ANO - PRIMEIRO_ANO + 1:
        raise SystemExit(f'O CDD anual tem {n} anos; espere todas as tarefas anuais terminarem.')
    ref = anual.first()
    proj = ref.projection().getInfo()
    for ano in range(ano_ini, ano_fim + 1):
        tarefa = ee.batch.Export.image.toAsset(
            image=cdd_decenal(ano, anual), description=f'cdd_decenal_{ano}', assetId=f'{COL_DECENAL}/{ano}',
            crs=proj['crs'], crsTransform=proj['transform'], region=ref.geometry(), maxPixels=1e9)
        tarefa.start()
        print(f'  tarefa {ano}: {tarefa.id}', flush=True)


def teste():
    """Decodificação e CDD de 2010 em pontos de climas bem diferentes (sem exportar nada)."""
    pontos = {'Petrolina (semiárido)': (-40.50, -9.39), 'Manaus (Amazônia úmida)': (-60.02, -3.10),
              'Cuiabá (savana, seca no inverno)': (-56.10, -15.60), 'Curitiba (sem estação seca)': (-49.27, -25.43),
              'Boa Vista (seca dez-mar)': (-60.67, 2.82)}
    fc = ee.FeatureCollection([ee.Feature(ee.Geometry.Point(xy), {'nome': n}) for n, xy in pontos.items()])
    dia = ee.Image(chuva_diaria().filterDate('2010-01-15', '2010-01-16').first())
    faixa = dia.reduceRegion(ee.Reducer.minMax(), dia.geometry(), 50000, bestEffort=True).getInfo()
    print('chuva de 15/01/2010, mín e máx no Brasil (mm):', faixa)
    for ano in (2010, 2012):
        res = cdd_ano(ano).reduceRegions(fc, ee.Reducer.first(), 11132).getInfo()['features']
        print(f'CDD {ano}:', {f['properties']['nome']: f['properties'].get('first') for f in res})


if __name__ == '__main__':
    conectar(None)
    etapa = sys.argv[1] if len(sys.argv) > 1 else 'teste'
    if etapa == 'teste':
        teste()
    elif etapa == 'anual':
        anos = [int(a) for a in sys.argv[2:4]] or [PRIMEIRO_ANO, ULTIMO_ANO]
        exportar_anual(*anos)
    elif etapa == 'decenal':
        exportar_decenal()
    else:
        raise SystemExit(__doc__)
