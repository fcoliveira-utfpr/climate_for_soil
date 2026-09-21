"""Refaz resultados e entregaveis com os dados em cache, sem consultas externas."""
import subprocess
import sys
from preparar_dados import ROOT, DADOS


def main():
    required=['textura.parquet','soc.parquet','joint.parquet']
    missing=[x for x in required if not (DADOS/x).exists()]
    if missing:
        raise FileNotFoundError('Caches ausentes: '+', '.join(missing)+'. Rode antes python codigo/preparar_dados.py '
                                '(exige conta com acesso liberado ao GEE; ver docs/assets.md).')
    steps=['analise_solo_clima.py','regressoes_corrigidas.py','graficos_relatorio.py',
           'importancia_climatica.py','exportar_resultados.py','verificar_resultados.py']
    for script in steps:
        print('\nExecutando '+script,flush=True)
        subprocess.run([sys.executable,'-X','utf8',str(ROOT/'codigo'/script)],cwd=ROOT,check=True)
    print('Analises recalculadas e verificadas. O notebook e a entrega editorial desta execucao; nao e sobrescrito por este comando.')


if __name__=='__main__':
    main()
