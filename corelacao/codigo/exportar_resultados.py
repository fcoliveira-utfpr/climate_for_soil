"""Consolida os resultados completos em poucas tabelas, sem descartar comparacoes."""
import json
import shutil

import pandas as pd

from preparar_dados import RES, PUBLIC, CLIMAS, FRACOES
from clima_legendas import HLZ_L1_LEGENDA, HLZ_L2_LEGENDA

FIGURAS=['rel_fluxo_metodologico.png','rel_integracao_030.png','rel_amostragem.png',
         'rel_textura_tres_fracoes.png','rel_soc_koppen.png','rel_efeitos_testes.png',
         'rel_dunn_soc_koppen.png','rel_soc_textura_dispersao.png','rel_comparacao_clima.png',
         'rel_modelos_r2.png','rel_dobras_espaciais.png','rel_validacao_espacial.png',
         'rel_importancia_climatica.png']+[f'painel_{level}.png' for level in CLIMAS]


def exportar():
    tables=PUBLIC/'tabelas'; figures=PUBLIC/'figuras'; sources=PUBLIC/'fontes'
    for folder in [tables,figures,sources]: folder.mkdir(parents=True,exist_ok=True)
    tests=pd.read_csv(RES/'testes_completos.csv')
    tests.to_csv(tables/'testes_globais.csv',index=False)
    descriptions=[]; correlations=[]; coverages=[]; pairs=[]
    for tag,variables in [('textura',{x:x for x in FRACOES}),('soc',{'SOC':'soc_g_m2'})]:
        correlations.append(pd.read_csv(RES/f'{tag}_pontobisserial.csv'))
        coverages.append(pd.read_csv(RES/f'{tag}_cobertura.csv'))
        for level in CLIMAS:
            desc=pd.read_csv(RES/f'{tag}_descritiva_{level}.csv')
            for label,variable in variables.items():
                mapping={variable+'_'+s:n for s,n in [('count','n'),('mean','media'),('std','desvio_padrao'),
                                                     ('median','mediana'),('q25','q25'),('q75','q75')]}
                descriptions.append(desc[['classe',*mapping]].rename(columns=mapping)
                                    .assign(variavel=label,nivel=level,
                                            unidade='%' if label in FRACOES else 'g/m2'))
                path=RES/f'{tag}_dunn_{label}_{level}.csv'
                if not path.exists(): continue
                matrix=pd.read_csv(path,index_col=0)
                for i,first in enumerate(matrix.index):
                    for second in matrix.columns[i+1:]:
                        pairs.append({'variavel':label,'nivel':level,
                                      'classe_1':first,'classe_2':second,'p_holm':matrix.loc[first,second]})
    pd.concat(descriptions,ignore_index=True).to_csv(tables/'descritivas.csv',index=False)
    pd.concat(correlations,ignore_index=True).to_csv(tables/'ponto_bisserial.csv',index=False)
    pd.concat(coverages,ignore_index=True).to_csv(tables/'cobertura.csv',index=False)
    pd.DataFrame(pairs).to_csv(tables/'dunn_pares.csv',index=False)
    sp=pd.read_csv(RES/'spearman_soc_textura.csv')
    sp.to_csv(tables/'spearman.csv',index=False)
    for name in ['comparacao_mesmos_pontos.csv','regressao_modelos.csv','regressao_coeficientes.csv',
                 'validacao_modelos.csv','validacao_folds.csv','logistica_validacao.csv',
                 'importancia_climatica.csv','importancia_climatica_folds.csv']:
        shutil.copy2(RES/name,tables/name)
    for name in FIGURAS: shutil.copy2(RES/name,figures/name)

    legenda=pd.DataFrame(
        [{'nivel':'HLZ_L1','codigo':c,'rotulo':n} for c,n in HLZ_L1_LEGENDA.items()]+
        [{'nivel':'HLZ_L2','codigo':c,'rotulo':n} for c,n in HLZ_L2_LEGENDA.items()])
    legenda.to_csv(sources/'legenda_holdridge.csv',index=False)

    preparacao=json.loads((RES/'preparacao.json').read_text(encoding='utf-8'))
    manifest={'assets':preparacao['assets']}
    (sources/'proveniencia.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    summary={'preparacao':preparacao,
             'analise':json.loads((RES/'resumo_analise.json').read_text(encoding='utf-8')),
             'regressao':json.loads((RES/'regressao_amostra.json').read_text(encoding='utf-8'))}
    (sources/'amostras.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    print(f'Entrega consolidada: {len(tests)} testes, {len(pairs)} pares Dunn, {len(list(tables.glob("*.csv")))} CSVs e {len(FIGURAS)} figuras.')


if __name__=='__main__':
    exportar()
