"""Figuras de sintese produzidas exclusivamente a partir das tabelas atuais."""
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from preparar_dados import RES, CLIMAS, carregar_bases
from matplotlib.patches import FancyBboxPatch
from sklearn.model_selection import GroupKFold, KFold
from regressoes_corrigidas import montar, grupos_espaciais
from analise_solo_clima import selecionar, SOC, FRACOES

BLUE='#246cb5'
ORANGE='#cc5a20'
plt.rcParams.update({'font.size':10,'axes.spines.top':False,'axes.spines.right':False,
                     'figure.facecolor':'white','axes.facecolor':'white'})


def save(fig,name):
    fig.tight_layout()
    fig.savefig(RES/name,dpi=180,bbox_inches='tight')
    plt.close(fig)


def barras(ax,x,a,b,labels,legends):
    ax.bar(x-.19,a,.36,label=legends[0],color=BLUE)
    ax.bar(x+.19,b,.36,label=legends[1],color=ORANGE)
    for xpos,series in [(x-.19,a),(x+.19,b)]:
        for pos,value in zip(xpos,series):
            ax.annotate(f'{value:.3f}'.replace('.',','),(pos,value),xytext=(0,4),
                        textcoords='offset points',ha='center',fontsize=8)
    ax.set_xticks(x,labels)
    ax.grid(axis='y',alpha=.2)
    ax.set_axisbelow(True)
    ax.legend(frameon=False,fontsize=9)
    ax.set_ylim(min(0,min(a),min(b))-.01,max(max(a),max(b))*1.32)


def barra_unica(ax,x,a,labels,cor=BLUE):
    ax.bar(x,a,.5,color=cor)
    for pos,value in zip(x,a):
        ax.annotate(f'{value:.3f}'.replace('.',','),(pos,value),xytext=(0,4),
                    textcoords='offset points',ha='center',fontsize=8)
    ax.set_xticks(x,labels)
    ax.grid(axis='y',alpha=.2)
    ax.set_axisbelow(True)
    ax.set_ylim(min(0,min(a))-.01,max(a)*1.22)


def main():
    tests=pd.read_csv(RES/'comparacao_mesmos_pontos.csv')
    tests=tests[tests.comparacao_nivel.eq(2)]
    order=['areia','silte','argila','SOC']
    pivot=tests.pivot(index='variavel_pt',columns='nivel',values='eta2').loc[order]
    counts=tests.groupby('variavel_pt').n.first()
    fig,ax=plt.subplots(figsize=(7.2,4.2))
    barras(ax,np.arange(4),pivot.koppen_l2,pivot.HLZ_L2,
           [v.replace('_',' ')+'\n(n='+f'{counts[v]:,}'.replace(',','.')+')' for v in order],
           ['Köppen L2','Holdridge L2'])
    ax.set_title('Associação nos mesmos locais, por variável')
    ax.set_ylabel('η²H de Kruskal-Wallis (baseado em postos)')
    save(fig,'rel_comparacao_clima.png')

    models=pd.read_csv(RES/'regressao_modelos.csv')
    pivot=models.set_index('modelo').loc[['M1 clima','M2 textura','M3 textura+clima',
                                          'M4 textura+clima+relevo','M5 clima+relevo'],'R2']
    fig,ax=plt.subplots(figsize=(7.6,4.6))
    barra_unica(ax,np.arange(5),pivot.to_numpy(),
               ['Clima','Textura','Textura\n+ clima','Textura + clima\n+ relevo/latitude','Clima\n+ relevo/latitude'])
    ax.set_title('Ajuste associativo sobre log(SOC)')
    ax.set_ylabel('R² no conjunto de ajuste')
    save(fig,'rel_modelos_r2.png')

    cv=pd.read_csv(RES/'validacao_modelos.csv')
    cv=cv[cv.alvo.eq('SOC')].pivot(index='esquema',columns='modelo',values='R2_oof')
    cv=cv.loc[['aleatoria','espacial_1grau','espacial_2graus','espacial_5graus']]
    fig,ax=plt.subplots(figsize=(8.2,4.2))
    barras(ax,np.arange(4),cv.OLS,cv.RandomForest,['Aleatória','Blocos de 1°','Blocos de 2°','Blocos de 5°'],['OLS','Random forest'])
    ax.set_ylabel('R² das predições fora das dobras (OOF)')
    ax.set_title('O desempenho depende da separação espacial')
    save(fig,'rel_validacao_espacial.png')

    desc=pd.read_csv(RES/'soc_descritiva_koppen_l2.csv')
    desc=desc[desc.soc_g_m2_count.ge(30)].sort_values('soc_g_m2_median')
    fig,ax=plt.subplots(figsize=(7.0,4.0))
    x=np.arange(len(desc))
    barra_unica(ax,x,desc.soc_g_m2_median.to_numpy(),
               [f'{c}\n(n={int(n)})' for c,n in zip(desc.classe,desc.soc_g_m2_count)])
    ax.set_ylabel('Estoque mediano de carbono (g/m², 0-30 cm)')
    ax.set_title('Carbono por subclasse de Köppen')
    save(fig,'rel_soc_koppen.png')

    tex,soc,joint=carregar_bases()
    common=set(tex.ponto_id)&set(soc.ponto_id)
    fig,ax=plt.subplots(figsize=(7.3,5.2))
    for df,label,color in [(soc[~soc.ponto_id.isin(common)],'Somente carbono',ORANGE),
                            (tex[~tex.ponto_id.isin(common)],'Somente textura','#799b61'),
                            (joint,'Carbono e textura',BLUE)]:
        ax.scatter(df.longitude,df.latitude,s=3,alpha=.4,color=color,label=f'{label} (n={len(df):,})')
    ax.set_xlabel('Longitude (graus)'); ax.set_ylabel('Latitude (graus)')
    ax.set_title('Distribuição dos locais com cobertura de 0-30 cm')
    ax.legend(markerscale=3,fontsize=8,frameon=False)
    ax.set_aspect('equal',adjustable='box')
    save(fig,'rel_amostragem.png')
    print('Cinco figuras de sintese atualizadas.')
    figuras_didaticas()


def figuras_didaticas():
    """Esquemas explicativos e figuras detalhadas; sem alterar os testes."""
    tex,soc,joint=carregar_bases()
    fig,ax=plt.subplots(figsize=(9,6.3))
    ax.set(xlim=(0,10),ylim=(0,10)); ax.axis('off')
    boxes=[(.25,7.8,4.25,1.5,'TEXTURA\nc03_psd_v2025_11_18\nMedida em laboratório',BLUE),
           (5.5,7.8,4.25,1.5,'CARBONO\nmatriz-collection3_carbon_datac2v2\nEstoque, profund_inf = 30 cm',ORANGE),
           (.25,5.2,4.25,1.7,'Filtrar 0-30 cm, excluir amostras\nartificiais, exigir fechamento ~100%\nUma mediana por local',BLUE),
           (5.5,5.2,4.25,1.7,'Excluir pseudoamostras e\ncoordenadas inválidas\nUma mediana por local',ORANGE),
           (1.35,2.6,7.3,1.6,'Köppen já vem como dummy nas duas matrizes\nHoldridge L1 / L2 extraído à parte (asset com legenda confirmada)\nClasses ausentes e grupos pequenos tratados explicitamente','#35685d'),
           (.25,.1,4.25,1.5,'CLIMA × SOLO\nTestes entre grupos, Dunn,\nponto-bisserial e gráficos',BLUE),
           (5.5,.1,4.25,1.5,'SOLO × SOLO\nMesmo perfil + mesmo local\nSpearman e regressões',ORANGE)]
    for x,y,w,h,label,color in boxes:
        ax.add_patch(FancyBboxPatch((x,y),w,h,boxstyle='round,pad=0.1',fc=color,ec='none',alpha=.11))
        ax.text(x+w/2,y+h/2,label,ha='center',va='center',fontsize=10.5,color='#163447',linespacing=1.55)
    for start,end in [((2.4,7.7),(2.4,7.0)),((7.6,7.7),(7.6,7.0)),((2.4,5.1),(3.5,4.3)),
                      ((7.6,5.1),(6.5,4.3)),((3.5,2.5),(2.4,1.75)),((6.5,2.5),(7.6,1.75))]:
        ax.annotate('',xy=end,xytext=start,arrowprops={'arrowstyle':'->','color':'#607a8a','lw':1.8})
    save(fig,'rel_fluxo_metodologico.png')

    fig,axes=plt.subplots(1,2,figsize=(8.7,5.5),gridspec_kw={'width_ratios':[.9,1.6]})
    ax=axes[0]
    for depth,label,color in [(10,'Registro 1\n35 cm',BLUE),(25,'Registro 2\n25 cm',ORANGE)]:
        ax.scatter([.5],[depth],s=400,color=color,alpha=.75,edgecolors='white',linewidth=2,zorder=3)
        ax.text(.5,depth,label,ha='center',va='center',fontsize=9.5,color='white',zorder=4)
    ax.axhspan(30,40,color='#e4e7ea',hatch='///',ec='#aaaaaa',zorder=1)
    ax.text(.5,35,'Fora da\ncamada-alvo',ha='center',va='center',fontsize=10,zorder=2)
    ax.set(xlim=(-.1,1.1),ylim=(40,0),xticks=[],yticks=[0,10,20,30,40],ylabel='Profundidade do registro (cm)')
    ax.set_title('Exemplo didático',fontsize=12)
    ax=axes[1]; ax.axis('off')
    lines=[('1  Filtrar por profundidade','Cada registro é um ponto no espaço em uma\nprofundidade. Só entram registros com\nprofundidade ≤ 30 cm (o de 35 cm sai).'),
           ('2  Uma mediana por local','Mais de um registro no mesmo local e\ncamada-alvo: mediana de cada fração,\nnão soma ponderada por espessura.'),
           ('3  Excluir amostras artificiais','Sinalizadas como cópia/pseudoamostra\nno identificador da fonte.'),
           ('4  Exigir fechamento','Areia + silte + argila = 100% (±1 ponto).\nA mediana coluna a coluna pode não fechar\nse os registros do local divergem muito.')]
    for y,(title,body) in zip([.95,.71,.43,.19],lines):
        ax.text(0,y,title,fontsize=12,weight='bold',color=BLUE,va='top')
        ax.text(0,y-.06,body,fontsize=10.5,va='top',linespacing=1.4)
    save(fig,'rel_integracao_030.png')

    fig,axes=plt.subplots(3,1,figsize=(8.8,8.2),sharex=True,sharey=True)
    order=sorted(selecionar(tex,'areia','koppen_l2').classe.unique())
    for ax,v,color in zip(axes,FRACOES,[BLUE,'#547851',ORANGE]):
        sub=selecionar(tex,v,'koppen_l2')
        groups=[sub.loc[sub.classe.eq(c),'valor'] for c in order]
        bp=ax.boxplot(groups,patch_artist=True,showfliers=False,medianprops={'color':'#142936','lw':1.8})
        for patch in bp['boxes']: patch.set(facecolor=color,alpha=.45)
        ax.set(ylim=(0,100),ylabel=v.capitalize()+' (%)',yticks=[0,25,50,75,100])
        ax.grid(axis='y',alpha=.2)
    axes[-1].set_xticks(np.arange(1,len(order)+1),[c+f'\n(n={len(g)})' for c,g in zip(order,groups)],fontsize=10)
    fig.suptitle('Três frações, mesmas classes de Köppen L2 e mesmos locais',fontsize=12)
    save(fig,'rel_textura_tres_fracoes.png')

    tests=pd.read_csv(RES/'testes_completos.csv')
    variables=[*FRACOES,'SOC']; levels=['koppen_l1','koppen_l2','koppen_l3','HLZ_L1','HLZ_L2']
    matrix=tests.pivot(index='variavel_pt',columns='nivel',values='eta2').loc[variables,levels]
    fig,ax=plt.subplots(figsize=(8.4,3.7))
    im=ax.imshow(matrix,vmin=0,vmax=.25,cmap='Blues',aspect='auto')
    ax.set_xticks(range(5),['Köppen L1','Köppen L2','Köppen L3','Holdridge L1','Holdridge L2'],fontsize=10)
    ax.set_yticks(range(4),['Areia','Silte','Argila','SOC'])
    for i in range(4):
        for j in range(5):
            value=matrix.iloc[i,j]
            ax.text(j,i,f'{value:.3f}'.replace('.',','),ha='center',va='center',fontsize=12,color='white' if value>.15 else '#12374c')
    ax.set_title('Tamanho da associação: os 20 testes sobre perfis',pad=15)
    fig.colorbar(im,ax=ax,label='η²H (baseado em postos)',shrink=.8)
    save(fig,'rel_efeitos_testes.png')

    dunn=pd.read_csv(RES/'soc_dunn_SOC_koppen_l2.csv',index_col=0)
    fig,ax=plt.subplots(figsize=(7.2,6.3))
    from matplotlib.colors import ListedColormap, BoundaryNorm
    data=np.where(dunn.to_numpy()<.001,2,np.where(dunn.to_numpy()<.05,1,0)).astype(float)
    np.fill_diagonal(data,np.nan)
    palette=ListedColormap(['#e5e9ed','#9cc1df','#246cb5'])
    ax.imshow(np.ma.masked_invalid(data),cmap=palette,norm=BoundaryNorm([-.5,.5,1.5,2.5],3))
    ax.set_xticks(range(len(dunn)),dunn.columns); ax.set_yticks(range(len(dunn)),dunn.index)
    for i in range(len(dunn)):
        for j in range(len(dunn)):
            if i==j: label='-'
            else:
                p=dunn.iloc[i,j]
                label='<0,001' if p<.001 else f'{p:.3f}'.replace('.',',')
            ax.text(j,i,label,ha='center',va='center',fontsize=10,color='white' if data[i,j]==2 else '#203544')
    ax.set_title('Dunn-Holm: SOC × Köppen L2\np ajustado em cada comparação entre duas classes',pad=16,fontsize=12)
    save(fig,'rel_dunn_soc_koppen.png')

    correlations=pd.read_csv(RES/'spearman_soc_textura.csv').query('soc == @SOC').set_index('textura')
    fig,axes=plt.subplots(3,1,figsize=(8.5,8.0),sharex=True,sharey=True)
    for ax,v,color in zip(axes,FRACOES,[BLUE,'#547851',ORANGE]):
        ax.scatter(joint[v],joint[SOC],s=5,alpha=.13,color=color,rasterized=True,edgecolors='none')
        ax.set_yscale('log')
        ax.set(xlim=(0,100),ylabel='SOC (g/m²)')
        ax.set_yticks([100,1000,10000,100000],['100','1.000','10.000','100.000'])
        ax.grid(axis='y',alpha=.2)
        ax.text(.98,.95,v.capitalize()+f" | ρ = {correlations.loc[v,'rho']:.3f}".replace('.',','),
                ha='right',va='top',transform=ax.transAxes,fontsize=11,weight='bold',color=color)
    axes[-1].set_xlabel('Fração do solo (%) - mediana por local em 0-30 cm')
    fig.suptitle(f'Cada ponto é um local pareado (n = {len(joint):,})'.replace(',','.'),fontsize=12)
    save(fig,'rel_soc_textura_dispersao.png')

    base=montar(); base=base[base[SOC]>0].reset_index(drop=True)
    groups=grupos_espaciais(base,2)
    fig,axes=plt.subplots(1,2,figsize=(8.8,5.0),sharex=True,sharey=True)
    colors=['#246cb5','#d96933','#688b54','#9467bd','#8a6950']
    splitters=[('Divisão aleatória',KFold(5,shuffle=True,random_state=42).split(base)),
               ('Blocos de 2°',GroupKFold(5).split(base,groups=groups))]
    for ax,(title,splits) in zip(axes,splitters):
        for fold,(_,test) in enumerate(splits):
            points=base.iloc[test]
            ax.scatter(points.longitude,points.latitude,s=3,alpha=.65,color=colors[fold],label=f'Dobra {fold+1}',edgecolors='none')
        ax.set_title(title,fontsize=12)
        ax.set_xlabel('Longitude'); ax.set_aspect('equal',adjustable='box')
    axes[0].set_ylabel('Latitude')
    handles,labels=axes[0].get_legend_handles_labels()
    fig.legend(handles,labels,loc='lower center',ncol=5,frameon=False,markerscale=3,fontsize=10,bbox_to_anchor=(.5,-.04))
    save(fig,'rel_dobras_espaciais.png')
    # Cinco paineis preservam os boxplots de todas as respostas/niveis pedidos,
    # sem publicar 25 arquivos separados. N e p estao nas tabelas completas.
    for level in CLIMAS:
        variables=[(tex,v,v.capitalize(),'%',color) for v,color in zip(FRACOES,[BLUE,'#547851',ORANGE])]
        variables += [(soc,'soc_g_m2','SOC','t/ha',BLUE)]
        classes=sorted(set().union(*(set(selecionar(frame,v,level).classe) for frame,v,*_ in variables)))
        fig,axes=plt.subplots(1,4,figsize=(11.8,max(3.8,len(classes)*.34+1.8)),sharey=True)
        for ax,(frame,v,label,unit,color) in zip(axes,variables):
            selected=selecionar(frame,v,level)
            positions=[]; values=[]
            for position,climate_class in enumerate(classes):
                group=selected.loc[selected.classe.eq(climate_class),'valor']
                if len(group):
                    positions.append(position)
                    values.append(group.to_numpy()/(100 if unit=='t/ha' else 1))
            boxes=ax.boxplot(values,positions=positions,vert=False,patch_artist=True,showfliers=False,
                             medianprops={'color':'#102736','lw':1.4})
            for patch in boxes['boxes']: patch.set(fc=color,alpha=.42)
            ax.set_title(label,fontsize=12,pad=12)
            ax.set_xlabel(unit,fontsize=11); ax.grid(axis='x',alpha=.16)
            if unit=='%': ax.set_xlim(0,100); ax.set_xticks([0,50,100])
            else: ax.set_xscale('symlog',linthresh=10); ax.set_xticks([0,10,100,1000],['0','10','100','1.000']); ax.tick_params(axis='x',labelrotation=35)
        import textwrap
        axes[0].set_yticks(range(len(classes)),['\n'.join(textwrap.wrap(c.replace('_',' '),29)) for c in classes],fontsize=10)
        axes[0].invert_yaxis()
        label=level.replace('koppen_l','Köppen L').replace('HLZ_L','Holdridge L')
        fig.suptitle(label+' | perfis de 0-30 cm',fontsize=14,y=1.015)
        fig.text(.53,-.035,'Grupos com n ≥ 30 por resposta. Estoques: escala simétrica-log (trecho linear até 10 t/ha).\n'
                 'Extremos não desenhados; mantidos nos testes. Caixa ausente: grupo não elegível para a resposta. '
                 'N por grupo em descritivas.csv.',ha='center',fontsize=10)
        save(fig,f'painel_{level}.png')
    print('Sete figuras detalhadas e didaticas atualizadas.')


if __name__=='__main__':
    main()
