"""Etapas 1 e 2: testes sobre medidas harmonizadas em 0-30 cm (fontes publicas C3)."""
import json
import textwrap

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import scikit_posthocs as sp
from scipy import stats
from statsmodels.stats.multitest import multipletests

from preparar_dados import CLIMAS, FRACOES, RES, carregar_bases

SAIDA = str(RES)
SOC = 'soc_g_m2'  # estoque com correcao de vies por quantile mapping (ver preparar_dados.preparar_carbono)
TEXTURA = {v:v for v in FRACOES}
N_MINIMO = 30
NIVEIS = {n:n+'_' for n in CLIMAS}
NIVEIS_PT = {'koppen_l1':'Köppen L1', 'koppen_l2':'Köppen L2', 'koppen_l3':'Köppen L3',
             'HLZ_L1':'Holdridge L1 (rótulos do asset)', 'HLZ_L2':'Holdridge L2 (rótulos do asset)'}
plt.rcParams.update({'font.size':9,'axes.spines.top':False,'axes.spines.right':False})


def carregar():
    return carregar_bases()[1]


def rotular(df, nivel):
    if nivel in df.columns:
        return df[nivel].astype('string'), [c for c in df if c.startswith(nivel+'_')]
    cols = [c for c in df if c.startswith(NIVEIS[nivel])]
    if not cols:
        return pd.Series(pd.NA,index=df.index,dtype='string'), []
    block = df[cols]
    valid = block.notna().all(axis=1) & block.isin([0,1]).all(axis=1) & block.sum(axis=1).eq(1)
    labels = pd.Series(pd.NA,index=df.index,dtype='string')
    labels.loc[valid] = block.loc[valid].idxmax(axis=1).str.removeprefix(NIVEIS[nivel])
    return labels, cols


def classes_validas(rotulos, n_min=N_MINIMO):
    n = rotulos.value_counts()
    return n[n>=n_min].index.tolist(), n[n<n_min].to_dict()


def selecionar(df, variavel, nivel):
    labels,_ = rotular(df,nivel)
    numeric = pd.to_numeric(df[variavel],errors='coerce')
    mask = labels.notna() & np.isfinite(numeric)
    valid,_ = classes_validas(labels[mask])
    mask &= labels.isin(valid)
    return pd.DataFrame({'valor':numeric[mask], 'classe':labels[mask]})


def eta2_kruskal(H,n,k):
    return max(0,(H-k+1)/(n-k)) if n>k else np.nan, H/(n-1) if n>1 else np.nan


def kruskal_por_nivel(df,variavel,nivel):
    sub = selecionar(df,variavel,nivel)
    groups = [g.valor.to_numpy() for _,g in sub.groupby('classe')]
    if len(groups)<2 or sub.valor.nunique()<2:
        return None
    H,p = stats.kruskal(*groups)
    F,pa = stats.f_oneway(*groups)
    if all(np.var(g,ddof=1)>0 for g in groups):
        fw,pw = stats.f_oneway(*groups,equal_var=False)
    else:
        fw,pw = np.nan,np.nan
    eta,eps = eta2_kruskal(H,len(sub),len(groups))
    return {'variavel':variavel,'nivel':nivel,'n':len(sub),'n_classes':len(groups),
            'H':H,'p':p,'eta2':eta,'epsilon2':eps,'F_anova':F,'p_anova':pa,
            'F_welch':fw,'p_welch':pw}


def dunn_por_nivel(df,variavel,nivel):
    sub = selecionar(df,variavel,nivel)
    if sub.classe.nunique()<2:
        return None
    return sp.posthoc_dunn(sub,val_col='valor',group_col='classe',p_adjust='holm')


def ponto_bisserial(df,variavel,nivel):
    sub = selecionar(df,variavel,nivel)
    if sub.classe.nunique()<2 or sub.valor.nunique()<2:
        return None
    dummies = pd.get_dummies(sub.classe,dtype=int)
    rows = []
    for label in dummies:
        r,p = stats.pointbiserialr(dummies[label],sub.valor)
        rows.append({'classe':nivel+'_'+label,'n_classe':int(dummies[label].sum()),
                     'n_total':len(sub),'r_pb':r,'p':p})
    out = pd.DataFrame(rows)
    out['p_holm'] = multipletests(out.p,method='holm')[1]
    return out.sort_values('r_pb',key=abs,ascending=False)


def descritiva(df,variaveis,nivel):
    labels,_ = rotular(df,nivel)
    data = df[variaveis].copy()
    data['classe'] = labels
    table = data.groupby('classe')[variaveis].agg(['count','mean','std','median',
                                                  lambda x:x.quantile(.25), lambda x:x.quantile(.75)])
    table.columns = [f'{v}_{s}'.replace('<lambda_0>','q25').replace('<lambda_1>','q75') for v,s in table.columns]
    return table.sort_index()


def boxplot(df,variavel,nivel,titulo,arquivo,ylabel=None):
    sub = selecionar(df,variavel,nivel)
    order = sub.groupby('classe').valor.median().sort_values().index
    if len(order)<2:
        return
    data = [sub.loc[sub.classe==c,'valor'].values for c in order]
    fig,ax = plt.subplots(figsize=(max(7,len(order)*.62),5.2))
    bp=ax.boxplot(data,patch_artist=True,showfliers=False,medianprops={'color':'#aa3322','linewidth':1.5})
    for box in bp['boxes']:
        box.set(facecolor='#cfe2f3',edgecolor='#4a6fa5')
    labels=['\n'.join(textwrap.wrap(c.replace('_',' '),20))+f'\n(n={len(g)})' for c,g in zip(order,data)]
    ax.set_xticks(range(1,len(order)+1),labels,rotation=45,ha='right',fontsize=8)
    ax.set_title(titulo,fontsize=11)
    ax.set_ylabel(ylabel or variavel)
    ax.grid(axis='y',alpha=.25)
    fig.tight_layout()
    fig.savefig(RES/arquivo,dpi=160,bbox_inches='tight')
    plt.close(fig)


def heatmap_spearman(mat,titulo,arquivo):
    fig,ax=plt.subplots(figsize=(6,5))
    im=ax.imshow(mat,cmap='RdBu_r',vmin=-1,vmax=1)
    ax.set_xticks(range(len(mat)),mat.columns,rotation=35,ha='right')
    ax.set_yticks(range(len(mat)),mat.index)
    for i in range(len(mat)):
        for j in range(len(mat)):
            v=mat.iloc[i,j]
            ax.text(j,i,f'{v:.2f}',ha='center',va='center',color='white' if abs(v)>.55 else 'black')
    ax.set_title(titulo)
    fig.colorbar(im,ax=ax,label='ρ de Spearman')
    fig.tight_layout()
    fig.savefig(RES/arquivo,dpi=160,bbox_inches='tight')
    plt.close(fig)


def etapa(df,variables,tag):
    kw,pb,coverage=[],[],[]
    for level in NIVEIS:
        descritiva(df,list(variables.values()),level).to_csv(RES/f'{tag}_descritiva_{level}.csv')
        labels,_=rotular(df,level)
        for name,variable in variables.items():
            sub=selecionar(df,variable,level)
            coverage.append({'variavel':name,'nivel':level,'n_base':len(df),'n_sem_classe':int(labels.isna().sum()),
                             'n_teste':len(sub),'n_classes_teste':sub.classe.nunique()})
            row=kruskal_por_nivel(df,variable,level)
            if row is None:
                continue
            row['variavel_pt']=name
            kw.append(row)
            dunn_por_nivel(df,variable,level).to_csv(RES/f'{tag}_dunn_{name}_{level}.csv')
            corr=ponto_bisserial(df,variable,level)
            if corr is not None:
                pb.append(corr.assign(variavel_pt=name,nivel=level))
            unit=f'{name.capitalize()} (%, média 0-30 cm)' if name in FRACOES else f'{name} (g/m², 0-30 cm)'
            boxplot(df,variable,level,unit+' por '+NIVEIS_PT[level],f'{tag}_box_{name}_{level}.png',unit)
    out=pd.DataFrame(kw)
    out.to_csv(RES/f'{tag}_kruskal.csv',index=False)
    if pb:
        pd.concat(pb,ignore_index=True).to_csv(RES/f'{tag}_pontobisserial.csv',index=False)
    pd.DataFrame(coverage).to_csv(RES/f'{tag}_cobertura.csv',index=False)
    return out


def spearman_soc_textura(joint):
    rows=[]
    for variable in FRACOES:
        sub=joint[[SOC,variable]].dropna()
        rho,p=stats.spearmanr(sub[SOC],sub[variable])
        rows.append({'par':'SOC x '+variable,'soc':SOC,'textura':variable,'rho':rho,'p':p,'n':len(sub)})
    out=pd.DataFrame(rows)
    out['p_holm']=multipletests(out.p,method='holm')[1]
    out.to_csv(RES/'spearman_soc_textura.csv',index=False)
    matrix=joint[[SOC,*FRACOES]].corr(method='spearman')
    matrix.index=matrix.columns=['SOC',*FRACOES]
    matrix.to_csv(RES/'spearman_matriz.csv')
    heatmap_spearman(matrix,'Mesmo perfil: carbono e textura (0-30 cm)','rel_spearman.png')
    return out


def main():
    RES.mkdir(exist_ok=True)
    tex,soc,joint=carregar_bases()
    kt=etapa(tex,TEXTURA,'textura')
    ks=etapa(soc,{'SOC':SOC},'soc')
    all_tests=pd.concat([kt,ks],ignore_index=True)
    all_tests['p_holm_omnibus']=multipletests(all_tests.p,method='holm')[1]
    all_tests.to_csv(RES/'testes_completos.csv',index=False)
    all_tests.to_csv(RES/'anova_complementar.csv',index=False)
    spearman_soc_textura(joint)
    comparisons=[]
    for df,variables in [(tex,TEXTURA),(soc,{'SOC':SOC})]:
        for name,var in variables.items():
            for depth in (1,2):
                a,b=f'koppen_l{depth}',f'HLZ_L{depth}'
                sub=df.copy()
                while True:
                    ia=selecionar(sub,var,a).index
                    ib=selecionar(sub,var,b).index
                    new=sub.loc[sub.index.intersection(ia).intersection(ib)]
                    if len(new)==len(sub):
                        break
                    sub=new
                for level in [a,b]:
                    row=kruskal_por_nivel(sub,var,level)
                    if row:
                        comparisons.append({**row,'variavel_pt':name,'comparacao_nivel':depth})
    pd.DataFrame(comparisons).to_csv(RES/'comparacao_mesmos_pontos.csv',index=False)
    summary={'n_textura':len(tex),'n_carbono':len(soc),'n_pareados':len(joint),
             'n_testes':len(all_tests),'n_p_holm_menor_005':int((all_tests.p_holm_omnibus<.05).sum()),
             'textura_fechamento_max_erro':float((tex[FRACOES].sum(axis=1)-100).abs().max())}
    (RES/'resumo_analise.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(summary,indent=2))


if __name__=='__main__':
    main()
