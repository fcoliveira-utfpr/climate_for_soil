"""Figuras das comparações executadas de métodos, escala, satélite e alvo térmico."""
import json
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from codigo.dados_temperatura import safe_path


def comparison(prefix, methods, labels, title, note, output):
    fig,axes=plt.subplots(1,2,figsize=(11,4.9),sharey=True)
    for block,ax in zip((1,2),axes):
        data=pd.read_csv(safe_path(f'resultados/tabelas/{prefix}_{block}graus.csv'))
        means=data.loc[data.scope.eq('global')].groupby('method').rmse.mean()
        bars=ax.bar(labels,[means[m] for m in methods],color=['#617d8a','#147d64','#c59744','#668aa8'][:len(methods)])
        ax.bar_label(bars,fmt='%.3f',fontsize=9,padding=3)
        ax.set_title(f'Blocos de {block}°');ax.set_ylim(0,max(means[m] for m in methods)*1.2)
        ax.grid(axis='y',alpha=.2);ax.set_axisbelow(True)
    axes[0].set_ylabel('RMSE mensal (°C)')
    fig.suptitle(title);fig.text(.5,.015,note,ha='center',fontsize=9)
    fig.tight_layout(rect=(0,.08,1,.95));fig.savefig(safe_path(f'resultados/figuras/{output}.png'),dpi=170);plt.close(fig)


def main():
    comparison('m3_m6_temperatura',['M2_linear','M3_GWR','M5_lightgbm','M6_linear_residual'],
        ['Linear','GWR','LightGBM','Híbrido'],'Temperatura — métodos estatísticos e aprendizado de máquina',
        '102 estações; três repetições; tuning espacial interno; teste reservado preservado.','c3_metodos_ampliados')
    comparison('escalas_temperatura',['M5_lightgbm_30','M5_lightgbm_90','M5_lightgbm_1000'],
        ['30 m','90 m','1.000 m'],'C5 — escala do relevo na correção de CHELSA',
        '96 estações comuns às três escalas; seis excluídas por covariáveis ausentes.','c5_escalas_temperatura')
    comparison('modis_temperatura',['M2_linear_base','M2_linear_modis','M5_lightgbm_base','M5_lightgbm_modis'],
        ['Linear\nbase','Linear\n+ MODIS','LightGBM\nbase','LightGBM\n+ MODIS'],'C6 — contribuição de LST diurna e noturna',
        '42 estações comuns; descritor MODIS de 2001–2020; alvo de 1991–2020; viés de céu limpo.','c6_modis_temperatura')
    data=pd.read_csv(safe_path('resultados/tabelas/c11_definicoes_mensais_2020.csv')).set_index('method')
    fig,axes=plt.subplots(1,2,figsize=(10,4.8))
    for ax,metric,title in zip(axes,['bias','rmse'],['Viés contra média de 24 h','RMSE contra média de 24 h']):
        values=data.loc[['mean_extremes','mean_compensated'],metric]
        bars=ax.bar(['(Tmax + Tmin)/2','Compensada\noperacional'],values,color=['#c59744','#147d64'])
        ax.bar_label(bars,fmt='%.3f',padding=3);ax.set_title(title);ax.set_ylabel('°C');ax.set_ylim(-.2,1.15)
        ax.axhline(0,color='gray',lw=.6);ax.grid(axis='y',alpha=.2);ax.set_axisbelow(True)
    fig.suptitle('C11 — definições térmicas em estações automáticas INMET, 2020')
    fig.text(.5,.015,'4.619 pares estação-mês, 521 estações; mesmos dias completos; não equivale à normal 1991–2020.',ha='center',fontsize=9)
    fig.tight_layout(rect=(0,.08,1,.95));fig.savefig(safe_path('resultados/figuras/c11_definicoes_2020.png'),dpi=170);plt.close(fig)


if __name__=='__main__':main()
