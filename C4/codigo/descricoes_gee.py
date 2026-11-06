"""Descrições dos assets do C4 no formato que o GEE mostra bem (o mesmo do CHELSA_1991-2020_TMED_1KM_2026):
Markdown com título `#`, seções `##` e cada parágrafo ou item de lista numa linha só (o GEE respeita as quebras de
linha, então o texto quebrado a cada ~115 caracteres aparecia picado).

As descrições são escritas nos scripts (montar_colecao_gee.DESCRICAO, subir_koppen_gee.descricao e DESCRICAO_NORMAL,
holdridge_1991_2020.texto); aqui elas são convertidas e:
    arquivos  gravadas em C4/gee/descricoes/<asset>.md
    gravar    gravadas na propriedade description de cada asset (Climas2 e as cópias em covariates/climate)
    copiar    copia o Holdridge e a coleção decenal para projects/mapbiomas-solos-workspace/assets/covariates/climate

Uso: python descricoes_gee.py arquivos | gravar | copiar
"""
import re
import sys
from pathlib import Path

import pandas as pd

SAIDA = Path(__file__).resolve().parents[1] / 'gee' / 'descricoes'
CLIMAS2 = 'projects/fcoliveira/assets/Climas2'
WORKSPACE = 'projects/mapbiomas-solos-workspace/assets/covariates/climate'
COPIAS = {f'{CLIMAS2}/holdridge_xavier_1991_2020': f'{WORKSPACE}/XAVIER_1991-2020_HOLDRIDGE_11KM_2026',
          f'{CLIMAS2}/xavier_conjunto_curto_decenal': f'{WORKSPACE}/XAVIER_1985-2026_CLIMA_DECENAL_11KM_2026'}


def formatar(md):
    """Markdown dos scripts -> formato do GEE: títulos # e ##, parágrafos e itens de lista numa linha só."""
    linhas, out, codigo = md.split('\n'), [], False
    for ln in linhas:
        if ln.startswith('```'):
            codigo = not codigo
            out.append(ln)
            continue
        if codigo:
            out.append(ln)
            continue
        m = re.fullmatch(r'\*\*(.+?)\*\*(.*)', ln.strip())
        if m and not out:                                   # primeira linha: título
            out.append(f'# {m.group(1)}{m.group(2)}')
            continue
        if m and not m.group(2).strip():                    # linha só com negrito: seção
            nivel = '###' if re.match(r'\d+\.', m.group(1)) else '##'
            out.append(f'{nivel} {m.group(1)}')
            continue
        if m and m.group(2).lstrip().startswith('('):       # "**Legenda** (explicação)": seção + texto
            out += [f'## {m.group(1)}', m.group(2).strip()]
            continue
        # continuação de parágrafo ou de item de lista: junta à linha anterior
        continua = (ln.strip() and out and out[-1].strip() and not out[-1].startswith(('#', '|', '```'))
                    and not ln.lstrip().startswith(('- ', '|', '#')) and not re.match(r'\s*\d+\. ', ln))
        if continua:
            out[-1] = out[-1].rstrip() + ' ' + ln.strip()
        else:
            out.append(ln.rstrip())
    texto = '\n'.join(out)
    return re.sub(r'\n{3,}', '\n\n', texto).strip() + '\n'


def textos():
    """{asset em Climas2: descrição no formato do GEE}. Importados aqui por causa do sys.path dos scripts."""
    import montar_colecao_gee as mc
    import subir_koppen_gee as sk
    import holdridge_1991_2020 as hd
    return {
        mc.COLECAO: formatar(mc.DESCRICAO),
        sk.ASSET: formatar(sk.descricao(pd.read_csv(sk.PASTA / 'legenda.csv'))),
        sk.ASSET_NORMAL: formatar(sk.DESCRICAO_NORMAL),
        hd.ASSET: formatar(hd.texto(pd.read_csv(hd.SAIDA / 'legenda.csv'), pd.read_csv(hd.SAIDA / 'conferencia.csv'))),
    }


def para_copia(md):
    """Na descrição da cópia em covariates/climate, os caminhos dos dois assets copiados apontam para a cópia."""
    for origem, destino in COPIAS.items():
        md = md.replace(origem, destino)
    return md


def arquivos():
    SAIDA.mkdir(parents=True, exist_ok=True)
    for asset, md in textos().items():
        nome = asset.split('/')[-1]
        (SAIDA / f'{nome}.md').write_text(md, encoding='utf-8')
        if asset in COPIAS:
            (SAIDA / f'{COPIAS[asset].split("/")[-1]}.md').write_text(para_copia(md), encoding='utf-8')
    for f in sorted(SAIDA.glob('*.md')):
        print(f.name, len(f.read_text(encoding='utf-8')), 'caracteres')


def _conectar():
    import ee
    from subir_por_banda import conectar
    conectar(None)
    return ee


def gravar():
    ee = _conectar()
    for asset, md in textos().items():
        alvos = [(asset, md)] + ([(COPIAS[asset], para_copia(md))] if asset in COPIAS else [])
        for a, texto in alvos:
            try:
                ee.data.setAssetProperties(a, {'description': texto})
                print(a.split('/')[-1], len(texto), 'caracteres')
            except ee.EEException as e:
                print(a.split('/')[-1], 'não gravada:', str(e)[:100])


def copiar():
    ee = _conectar()
    for origem, destino in COPIAS.items():
        tipo = ee.data.getAsset(origem)['type']
        if tipo == 'IMAGE':
            ee.data.copyAsset(origem, destino, allowOverwrite=True)
            print('copiado:', destino)
            continue
        # coleção: cria a coleção de destino e copia cada imagem
        try:
            ee.data.getAsset(destino)
        except ee.EEException:
            ee.data.createAsset({'type': 'IMAGE_COLLECTION'}, destino)
        filhos = ee.data.listAssets({'parent': origem}).get('assets', [])
        for f in filhos:
            ee.data.copyAsset(f['id'], f'{destino}/{f["id"].split("/")[-1]}', allowOverwrite=True)
        print('copiado:', destino, len(filhos), 'imagens')


if __name__ == '__main__':
    {'arquivos': arquivos, 'gravar': gravar, 'copiar': copiar}[sys.argv[1]]()
