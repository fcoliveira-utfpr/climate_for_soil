"""Sobe o conjunto curto para o GEE sem Cloud Storage e sem upload manual, uma banda por vez.

O pedido de exportação com as 10 bandas de um ano como ee.Array passa do limite do GEE, mas com uma banda (~1,2 MB)
funciona. Então:
    1. `bandas`: cada variável de cada ano (e a distância de preenchimento e a altitude, que não mudam com o ano)
       vira um asset temporário em Climas2/tmp_curto/<variável>_<ano>, com os mesmos valores do GeoTIFF de
       gerar_geotiff_gee.py (grade estendida, preenchida, Brasil + 2 pixels; inteiro escalado no envio).
    2. `juntar`: no GEE, sem array, as bandas de cada ano viram uma imagem da coleção final
       (publicar_curto_gee.COLECAO), com as propriedades year, inicio_janela e fim_janela.
    3. `limpar`: apaga a pasta temporária (depois de montar_colecao_gee.py conferir).

Uso: python subir_por_banda.py bandas | juntar | limpar
"""
import sys
import time
from pathlib import Path

import ee
import numpy as np

from publicar_curto_gee import (ANOS, BANDAS, COLECAO, DX, DY, HE, VARIAVEIS, WE, X0E, Y0E, alvo, preencher)

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / 'corelacao' / 'codigo'))
from gee_utils import conectar  # noqa: E402

TMP = 'projects/fcoliveira/assets/Climas2/tmp_curto'
Z = RAIZ / 'C4' / 'dados' / 'altitude_grade.npz'
SEM = -99999
REGIAO = None


def _posicao():
    lonlat = ee.Image.pixelLonLat()
    col = lonlat.select('longitude').subtract(X0E).divide(DX).floor().clamp(0, WE - 1).toInt()
    lin = lonlat.select('latitude').subtract(Y0E).divide(DY).floor().clamp(0, HE - 1).toInt()
    return ee.Image.cat(lin, col)


def _banda(valores, escala, nome):
    a = alvo()
    arr = ee.Image(ee.Array(np.where(a, np.round(valores * escala), SEM).astype(int).tolist())).arrayGet(_posicao())
    return arr.updateMask(arr.neq(SEM)).divide(escala).toFloat().rename(nome)


def _existe(asset):
    for tentativa in range(20):
        try:
            ee.data.getAsset(asset)
            return True
        except ee.EEException:
            return False
        except Exception as e:          # erro de rede (SSL): espera e tenta de novo
            if tentativa == 19:
                raise
            print('  nova tentativa (consulta):', asset.split('/')[-1], str(e)[:60], flush=True)
            time.sleep(30)


def _exportar(img, nome):
    """Inicia a tarefa; a rede às vezes devolve erro de SSL por alguns minutos, então tenta até 20 vezes."""
    regiao = ee.Geometry.Rectangle([X0E, Y0E + HE * DY, X0E + WE * DX, Y0E], 'EPSG:4326', False)
    for tentativa in range(20):
        try:
            t = ee.batch.Export.image.toAsset(image=img, description=f'tmp_{nome}', assetId=f'{TMP}/{nome}',
                                              crs='EPSG:4326', crsTransform=[DX, 0, X0E, 0, DY, Y0E], region=regiao,
                                              maxPixels=1e9, pyramidingPolicy={'.default': 'mean'})
            t.start()
            return t.id
        except Exception as e:
            if tentativa == 19:
                raise
            print('  nova tentativa:', nome, str(e)[:80], flush=True)
            time.sleep(30)


def bandas():
    if not _existe(TMP):
        ee.data.createAsset({'type': 'FOLDER'}, TMP)
    em_andamento = {t['description'] for t in ee.data.getTaskList() if t['state'] in ('READY', 'RUNNING')}
    feitos = 0
    v, km = None, None
    for ano in ANOS:
        d = np.load(VARIAVEIS / f'{ano}.npz')
        for b, esc in BANDAS.items():
            nome = f'{b}_{ano}'
            if _existe(f'{TMP}/{nome}') or f'tmp_{nome}' in em_andamento:
                continue
            v, km = preencher(d[b])
            _exportar(_banda(v, esc, b), nome)
            feitos += 1
        print(ano, 'tarefas iniciadas até aqui:', feitos, flush=True)
    if km is None:
        km = preencher(np.load(VARIAVEIS / '2000.npz')['cd_t_media'])[1]
    for nome, x, esc in [('dist_preenchimento_km', km, 1), ('z_pixel_m', np.load(Z)['z'], 1)]:
        if not _existe(f'{TMP}/{nome}') and f'tmp_{nome}' not in em_andamento:
            _exportar(_banda(x, esc, nome), nome)
            feitos += 1
    print('total de tarefas iniciadas:', feitos)


def juntar():
    faltam = [f'{b}_{a}' for a in ANOS for b in BANDAS if not _existe(f'{TMP}/{b}_{a}')]
    assert not faltam, f'{len(faltam)} bandas ainda não existem, por exemplo {faltam[:3]}'
    if not _existe(COLECAO):
        ee.data.createAsset({'type': 'IMAGE_COLLECTION'}, COLECAO)
    regiao = ee.Geometry.Rectangle([X0E, Y0E + HE * DY, X0E + WE * DX, Y0E], 'EPSG:4326', False)
    fixas = [ee.Image(f'{TMP}/dist_preenchimento_km'), ee.Image(f'{TMP}/z_pixel_m')]
    for ano in ANOS:
        if _existe(f'{COLECAO}/{ano}'):
            continue
        img = ee.Image.cat([ee.Image(f'{TMP}/{b}_{ano}') for b in BANDAS] + fixas).set({
            'year': ano, 'inicio_janela': ano - 10, 'fim_janela': ano - 1,
            'system:time_start': ee.Date.fromYMD(ano, 1, 1).millis(), 'fonte': 'Xavier et al. (2022) BR-DWGD v3.2.4'})
        t = ee.batch.Export.image.toAsset(image=img, description=f'curto_decenal_{ano}', assetId=f'{COLECAO}/{ano}',
                                          crs='EPSG:4326', crsTransform=[DX, 0, X0E, 0, DY, Y0E], region=regiao,
                                          maxPixels=1e9, pyramidingPolicy={'.default': 'mean'})
        t.start()
        print(ano, t.id, flush=True)


def limpar():
    filhos = ee.data.listAssets({'parent': TMP}).get('assets', [])
    for f in filhos:
        ee.data.deleteAsset(f['id'])
    ee.data.deleteAsset(TMP)
    print('apagados:', len(filhos), 'assets temporários e a pasta', TMP)


if __name__ == '__main__':
    conectar(None)
    {'bandas': bandas, 'juntar': juntar, 'limpar': limpar}[sys.argv[1]]()
