"""Verificacao numerica cruzada dos dados, CSVs e notebook."""
import hashlib
import argparse
import importlib.metadata
import json
import platform
import re
import unittest
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import nbformat
import numpy as np
import pandas as pd
from nbclient import NotebookClient
from scipy import stats
from statsmodels.stats.multitest import multipletests

import test_metodologia
from preparar_dados import ROOT, DADOS, RES, PUBLIC, FRACOES, carregar_bases, coordenadas_validas
from analise_solo_clima import kruskal_por_nivel, ponto_bisserial, dunn_por_nivel, SOC
from regressoes_corrigidas import montar, dummies_clima, ajustar, TEXTURA_REG


def hash_entrega(path):
    """Hashes portaveis: Git pode converter CRLF/LF em arquivos textuais."""
    raw=path.read_bytes()
    if path.suffix.lower() in {'.py','.md','.csv','.json','.txt','.ipynb'} or path.name in {'.gitignore','.gitattributes'}:
        raw=raw.replace(b'\r\n',b'\n')
    return hashlib.sha256(raw).hexdigest()


def arquivos_entrega():
    roots=['README.md','solo_clima_consolidado.ipynb','requirements.txt','.gitignore','.gitattributes']
    files=[ROOT/name for name in roots]
    files+=list((ROOT/'codigo').glob('*.py'))+list((ROOT/'docs').glob('*.md'))
    files+=[p for p in PUBLIC.rglob('*') if p.is_file() and p.name!='verificacao.json']
    return sorted(files)


def verificar_entrega(checar_hashes=True):
    """Nao depende de .local/dados nem do Earth Engine."""
    checks=PUBLIC/'fontes'/'verificacao.json'
    if checar_hashes:
        prior=json.loads(checks.read_text(encoding='utf-8'))
        current={p.relative_to(ROOT).as_posix() for p in arquivos_entrega()}
        assert current==set(prior['sha256']), 'Lista de arquivos da entrega mudou; refaca a verificacao completa'
        for name,digest in prior['sha256'].items():
            assert hash_entrega(ROOT/name)==digest, 'Arquivo alterado: '+name
    nb=nbformat.read(ROOT/'solo_clima_consolidado.ipynb',as_version=4)
    nbformat.validate(nb)
    code=[c for c in nb.cells if c.cell_type=='code']
    assert all(c.execution_count is not None for c in code)
    assert not any(o.output_type=='error' for c in code for o in c.outputs)
    referenced={m for c in nb.cells if c.cell_type=='code' for m in re.findall(r'"(resultados/[^"]+)"',c.source)}
    for path in referenced:
        assert (ROOT/path).exists(), 'Figura/arquivo referenciado no notebook nao existe: '+path
    tests=pd.read_csv(PUBLIC/'tabelas/testes_globais.csv')
    assert len(tests)==20
    np.testing.assert_allclose(tests.p_holm_omnibus,multipletests(tests.p,method='holm')[1],rtol=1e-10,atol=1e-300)
    pairs=pd.read_csv(PUBLIC/'tabelas/dunn_pares.csv')
    expected_pairs=int((tests.n_classes*(tests.n_classes-1)/2).sum())
    assert len(pairs)==expected_pairs
    assert not pairs[['variavel','nivel','classe_1','classe_2']].duplicated().any()
    assert pairs.p_holm.between(0,1).all()
    for path in [ROOT/'README.md',ROOT/'docs/reproducao.md',PUBLIC/'README.md']:
        for link in re.findall(r'\]\(([^)]+)\)',path.read_text(encoding='utf-8')):
            if not link.startswith(('https://','http://','#')):
                assert (path.parent/link).exists(), 'Link local quebrado: '+link
    # Executa em uma copia minima: impossivel depender dos dados/cache privados por engano.
    qa=ROOT/'.local'/'qa'; qa.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='entrega_',dir=qa) as folder:
        target=Path(folder).resolve()
        assert target.is_relative_to(qa.resolve())
        shutil.copytree(PUBLIC,target/'resultados')
        NotebookClient(nb,timeout=180,kernel_name='python3',resources={'metadata':{'path':str(target)}}).execute()
    return len(code)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--entrega',action='store_true',help='Confere somente os arquivos publicados, sem caches de dados nem GEE')
    args=parser.parse_args()
    if args.entrega:
        n_code=verificar_entrega()
        print(f'Entrega integra: {n_code} celulas executadas sem dados locais ou GEE.')
        return
    suite=unittest.defaultTestLoader.loadTestsFromModule(test_metodologia)
    tested=unittest.TextTestRunner(verbosity=1).run(suite)
    assert tested.wasSuccessful(), 'Falha nos testes de metodologia'
    tex,soc,joint=carregar_bases()
    for frame in [tex,soc,joint]:
        assert not frame.ponto_id.duplicated().any()
        assert coordenadas_validas(frame).all()
    assert (tex[FRACOES].sum(axis=1)-100).abs().le(1).all(), 'Fechamento das fracoes fora da tolerancia'
    assert (joint[FRACOES].sum(axis=1)-100).abs().le(1).all()
    preparacao=json.loads((RES/'preparacao.json').read_text(encoding='utf-8'))
    assert preparacao['n_textura']==len(tex) and preparacao['n_carbono']==len(soc) and preparacao['n_pareados']==len(joint)
    tests=pd.read_csv(RES/'testes_completos.csv')
    assert len(tests)==20 and not tests[['variavel_pt','nivel']].duplicated().any()
    pbs={tag:pd.read_csv(RES/f'{tag}_pontobisserial.csv') for tag in ['textura','soc']}
    np.testing.assert_allclose(tests.p_holm_omnibus,multipletests(tests.p,method='holm')[1],rtol=1e-10,atol=1e-300)
    for row in tests.itertuples():
        tag='textura' if row.variavel_pt in FRACOES else 'soc'
        frame=tex if tag=='textura' else soc
        calculated=kruskal_por_nivel(frame,row.variavel,row.nivel)
        for key in ['n','n_classes','H','p','eta2','epsilon2','F_anova','p_anova','F_welch','p_welch']:
            np.testing.assert_allclose(getattr(row,key),calculated[key],rtol=1e-10,atol=1e-300,equal_nan=True)
        actual=pbs[tag].query('variavel_pt == @row.variavel_pt and nivel == @row.nivel').set_index('classe').sort_index()
        calculated_pb=ponto_bisserial(frame,row.variavel,row.nivel).set_index('classe').sort_index()
        assert actual.index.equals(calculated_pb.index)
        for key in ['n_total','n_classe','r_pb','p','p_holm']:
            np.testing.assert_allclose(actual[key],calculated_pb[key],rtol=1e-10,atol=1e-300)
        assert actual.n_total.eq(row.n).all()
        saved=pd.read_csv(RES/f'{tag}_dunn_{row.variavel_pt}_{row.nivel}.csv',index_col=0)
        calculated_dunn=dunn_por_nivel(frame,row.variavel,row.nivel)
        assert saved.index.equals(calculated_dunn.index) and saved.columns.equals(calculated_dunn.columns)
        np.testing.assert_allclose(saved,calculated_dunn,rtol=1e-10,atol=1e-300)
    corr=pd.read_csv(RES/'spearman_soc_textura.csv')
    for row in corr.itertuples():
        rho,p=stats.spearmanr(joint[row.soc],joint[row.textura])
        np.testing.assert_allclose([row.rho,row.p],[rho,p],rtol=1e-10,atol=1e-300)
        assert row.n==len(joint)
    comparable=pd.read_csv(RES/'comparacao_mesmos_pontos.csv')
    assert comparable.groupby(['variavel_pt','comparacao_nivel']).n.nunique().eq(1).all()
    models=pd.read_csv(RES/'regressao_modelos.csv')
    assert models.groupby('alvo').n.nunique().eq(1).all()
    model_base=montar()
    base=model_base[model_base[SOC]>0].reset_index(drop=True)
    y=np.log(base[SOC]); dummy,reference=dummies_clima(base)
    texture=base[TEXTURA_REG]; relief=base[['elevation','latitude']]
    matrices={'M1 clima':dummy,'M2 textura':texture,
              'M3 textura+clima':pd.concat([texture,dummy],axis=1),
              'M4 textura+clima+relevo':pd.concat([texture,dummy,relief],axis=1),
              'M5 clima+relevo':pd.concat([dummy,relief],axis=1)}
    for name,X in matrices.items():
        expected,_=ajustar(y,X,name)
        stored=models.query('alvo == "SOC" and modelo == @name').iloc[0]
        assert stored.referencia_clima==reference
        for key in ['n','k','R2','R2_aj','AIC']:
            np.testing.assert_allclose(stored[key],expected[key],rtol=1e-10,atol=1e-12)
    folds=pd.read_csv(RES/'validacao_folds.csv')
    cv=pd.read_csv(RES/'validacao_modelos.csv')
    for row in cv.itertuples():
        group=folds.query('alvo == @row.alvo and esquema == @row.esquema and modelo == @row.modelo')
        assert len(group)==5 and group.n_teste.sum()==row.n
        assert (group.n_teste+group.n_treino).eq(row.n).all()
    exported=pd.read_csv(PUBLIC/'tabelas/testes_globais.csv')
    pd.testing.assert_frame_equal(exported,tests,check_exact=False,rtol=1e-10,atol=1e-300)
    from exportar_resultados import exportar
    # A exportacao deterministica deve manter o conteudo publicado, sem perder pares/classes.
    before={p:hashlib.sha256(p.read_bytes()).hexdigest() for p in (PUBLIC/'tabelas').glob('*.csv')}
    exportar()
    assert all(hashlib.sha256(p.read_bytes()).hexdigest()==digest for p,digest in before.items())
    n_code=verificar_entrega(checar_hashes=False)
    packages=['earthengine-api','pandas','numpy','scipy','statsmodels','scikit-posthocs',
              'scikit-learn','matplotlib','pyarrow','pillow','nbformat','nbclient','ipykernel']
    environment={'python':platform.python_version(),'sistema':platform.platform(),
                 'pacotes':{p:importlib.metadata.version(p) for p in packages}}
    (PUBLIC/'fontes/ambiente.json').write_text(json.dumps(environment,ensure_ascii=False,indent=2),encoding='utf-8')
    artifacts=arquivos_entrega()
    pares_dunn=int((tests.n_classes*(tests.n_classes-1)/2).sum())
    report={'verificado_em':datetime.now(timezone.utc).isoformat(),'status':'aprovado',
            'testes_unitarios':tested.testsRun,'testes_globais_recalculados':len(tests),
            'n_textura':len(tex),'n_soc':len(soc),'n_pareados':len(joint),
            'celulas_executadas_sem_dados_locais':n_code,'pares_dunn_preservados':pares_dunn,
            'pendencia':"Legenda oficial de zone38_id do vetor holdridge_38BR_1km (professor) nao confirmada; HLZ_L1/L2 vem de outro asset (holdridge_lifezones_chelsa-v2026), ver docs/assets.md.",
            'algoritmo_hash':'SHA-256; texto normalizado de CRLF para LF, binarios sem alteracao',
            'sha256':{p.relative_to(ROOT).as_posix():hash_entrega(p) for p in artifacts}}
    (PUBLIC/'fontes/verificacao.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(f'Verificacao aprovada: {tested.testsRun} testes unitarios, {len(tests)} testes globais/Dunn/ponto-bisserial recalculados; '
          f'{n_code} celulas do notebook executadas sem dados locais.')


if __name__=='__main__':
    main()
