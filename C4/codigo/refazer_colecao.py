"""Refaz a coleção do conjunto curto no GEE, substituindo a atual (grade estendida inteira preenchida).

Etapas, cada uma repetida até dar certo (a rede desta máquina cai com erro de SSL de tempos em tempos):
    1. apaga os assets temporários antigos (Climas2/tmp_curto)
    2. sobe as 380 bandas (subir_por_banda.bandas) e espera as tarefas
    3. apaga as 42 imagens atuais da coleção
    4. junta as bandas por ano (subir_por_banda.juntar) e espera as tarefas
    5. grava a descrição, confere a coleção contra os .npz locais e apaga os temporários

Uso: python refazer_colecao.py            # do zero
     python refazer_colecao.py retomar    # mantém as bandas temporárias já enviadas
"""
import sys
import time

import ee

import montar_colecao_gee as mc
import subir_por_banda as sb
from publicar_curto_gee import COLECAO
from subir_por_banda import conectar


def insistir(func, *a, rotulo=''):
    for tentativa in range(240):         # a rede já ficou mais de 1 h fora
        try:
            return func(*a)
        except AssertionError:
            raise
        except Exception as e:
            print(f'  [{rotulo}] erro, nova tentativa em 60 s:', str(e)[:100], flush=True)
            time.sleep(60)
            try:
                conectar(None)
            except Exception:
                pass
    raise RuntimeError(f'{rotulo}: desisti depois de 240 tentativas')


def esperar(prefixo):
    while True:
        ts = insistir(ee.data.getTaskList, rotulo='lista de tarefas')
        ts = [t for t in ts if t.get('description', '').startswith(prefixo)]
        pend = [t for t in ts if t['state'] in ('READY', 'RUNNING')]
        if not pend:
            falhas = [t['description'] for t in ts if t['state'] == 'FAILED']
            print(f'{prefixo}: concluídas; falhas recentes: {falhas[:5]}', flush=True)
            return
        print(f'{prefixo}: {len(pend)} pendentes', flush=True)
        time.sleep(60)


def apagar_filhos(pasta):
    filhos = insistir(lambda: ee.data.listAssets({'parent': pasta}).get('assets', []), rotulo='listar')
    for f in filhos:
        insistir(ee.data.deleteAsset, f['id'], rotulo='apagar')
    print('apagados:', len(filhos), 'assets de', pasta, flush=True)


def main():
    conectar(None)
    if 'retomar' not in sys.argv and insistir(sb._existe, sb.TMP, rotulo='existe'):
        apagar_filhos(sb.TMP)
    # o envio pode cair no meio: repete até todas as bandas existirem
    while True:
        insistir(sb.bandas, rotulo='bandas')
        esperar('tmp_')
        n = len(insistir(lambda: ee.data.listAssets({'parent': sb.TMP}).get('assets', []), rotulo='contar'))
        print('bandas no GEE:', n, flush=True)
        if n >= 380:
            break
    apagar_filhos(COLECAO)
    while True:
        insistir(sb.juntar, rotulo='juntar')
        esperar('curto_decenal_')
        n = insistir(lambda: ee.ImageCollection(COLECAO).size().getInfo(), rotulo='contar coleção')
        print('imagens na coleção:', n, flush=True)
        if n >= 42:
            break
    insistir(mc.descricao, rotulo='descrição')
    insistir(mc.conferir, rotulo='conferir')
    insistir(sb.limpar, rotulo='limpar')
    print('FIM: coleção refeita e conferida', flush=True)


if __name__ == '__main__':
    main()
