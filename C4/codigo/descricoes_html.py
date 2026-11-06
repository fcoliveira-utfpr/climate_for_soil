"""Descrições dos assets do C4 em HTML: o GEE mostra a descrição como HTML, e o Markdown aparecia cru.

Converte as três descrições (coleção do conjunto curto, Köppen 1991-2020 e normal 1991-2020) de Markdown para HTML
e:
    paginas  grava C4/gee/descricoes/<asset>.html, para abrir no navegador, selecionar tudo e colar no editor de
             descrição do GEE (Code Editor > Assets > asset > editar descrição)
    gravar   grava o HTML direto na propriedade description de cada asset

Uso: python descricoes_html.py paginas | gravar
"""
import sys
from pathlib import Path

import markdown
import pandas as pd

SAIDA = Path(__file__).resolve().parents[1] / 'gee' / 'descricoes'
ESTILO = """<style>
body {font-family: Arial, sans-serif; font-size: 14px; max-width: 980px; margin: 24px auto; padding: 0 16px;
      color: #222; background: #fff; line-height: 1.45}
table {border-collapse: collapse; margin: 8px 0} th, td {border: 1px solid #bbb; padding: 4px 8px; text-align: left}
pre {background: #f4f4f4; padding: 10px; overflow-x: auto; font-size: 12px} code {font-family: Consolas, monospace}
</style>"""


def textos():
    # importados aqui: assim o ESTILO pode ser usado por scripts que põem climas_tempo/codigo no sys.path
    import montar_colecao_gee as mc
    import subir_koppen_gee as sk
    return {
        mc.COLECAO: mc.DESCRICAO,
        sk.ASSET: sk.descricao(pd.read_csv(sk.PASTA / 'legenda.csv')),
        sk.ASSET_NORMAL: sk.DESCRICAO_NORMAL,
    }


def html(md):
    return markdown.markdown(md, extensions=['tables', 'fenced_code', 'sane_lists'])


def paginas():
    SAIDA.mkdir(parents=True, exist_ok=True)
    for asset, md in textos().items():
        nome = asset.split('/')[-1]
        (SAIDA / f'{nome}.html').write_text(
            f'<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><title>{nome}</title>{ESTILO}</head>'
            f'<body>\n{html(md)}\n</body></html>', encoding='utf-8')
        print('página:', SAIDA / f'{nome}.html')


def gravar():
    import ee
    from subir_por_banda import conectar
    conectar(None)
    for asset, md in textos().items():
        ee.data.setAssetProperties(asset, {'description': html(md)})
        print(asset.split('/')[-1], len(ee.data.getAsset(asset)['properties']['description']), 'caracteres')


if __name__ == '__main__':
    {'paginas': paginas, 'gravar': gravar}[sys.argv[1]]()
