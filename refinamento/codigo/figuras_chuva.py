"""Figuras das comparações pareadas de covariáveis, sazonalidade e densidade."""
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from codigo.dados_temperatura import safe_path


def main():
    specifications=[
        ('chuva_covariaveis',['M5_30m_base','M5_90m_base','M5_1000m_base','M5_30m_CHIRPS'],
         ['30 m','90 m','1.000 m','30 m + CHIRPS'],'C5/C6 — relevo e CHIRPS na modelagem da chuva','chuva_c5_c6'),
        ('chuva_c7_c8',['M5_harmonics_100pct','M5_none_100pct','M5_categorical_100pct','M5_per_month_100pct'],
         ['Harmônicos','Sem sazonalidade','Mês categórico','Por mês'],'C7 — estratégias sazonais para chuva','chuva_c7'),
        ('chuva_c7_c8',[f'M5_harmonics_{f:03d}pct' for f in (25,50,75,100)],
         ['25%','50%','75%','100%'],'C8 — fração de estações somente no treino de chuva','chuva_c8')]
    for prefix,methods,labels,title,name in specifications:
        fig,axes=plt.subplots(1,2,figsize=(12,5),sharey=True)
        for block,ax in zip((1,2),axes):
            data=pd.read_csv(safe_path(f'resultados/tabelas/{prefix}_{block}graus.csv'))
            means=data.loc[data.scope.eq('monthly')].groupby('method').rmse.mean()
            bars=ax.bar(labels,[means[m] for m in methods],color=['#617d8a','#147d64','#c59744','#668aa8'])
            ax.bar_label(bars,fmt='%.2f',padding=3,fontsize=9)
            ax.set_title(f'Blocos de {block}°');ax.set_ylim(0,max(means[m] for m in methods)*1.2)
            ax.tick_params(axis='x',labelsize=9);ax.grid(axis='y',alpha=.2);ax.set_axisbelow(True)
        axes[0].set_ylabel('RMSE mensal (mm)')
        fig.suptitle(title)
        fig.text(.5,.015,'LightGBM corrigindo CHELSA; 1.878 estações comuns; teste reservado preservado.',ha='center',fontsize=9)
        fig.tight_layout(rect=(0,.06,1,.94));fig.savefig(safe_path(f'resultados/figuras/{name}.png'),dpi=160);plt.close(fig)


if __name__=='__main__':main()
