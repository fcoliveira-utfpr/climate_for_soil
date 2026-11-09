"""Figuras agregadas das comparações C7/C8 e do inventário nacional."""
import json
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection
from pyproj import Transformer
from codigo.dados_temperatura import safe_path
from codigo.grade_brasil import boundary


def main():
    tables = {}
    for block in (1,2):
        data = pd.read_csv(safe_path(f'resultados/tabelas/c7_c8_metricas_{block}graus.csv'))
        tables[block] = data[data.scope.eq('global')].groupby('method').rmse.mean()
    fig, axes = plt.subplots(1,2,figsize=(11,4.8),sharey=True)
    strategies = ['harmonics','none','categorical','per_month']
    labels = ['Harmônicos','Sem termo\nsazonal','Mês\ncategórico','Modelo\npor mês']
    for block, ax in zip((1,2),axes):
        for offset, method, color, label in [(-.18,'M2_linear','#617d8a','Linear'),(.18,'M5_lightgbm','#147d64','LightGBM')]:
            values = [tables[block][f'{method}_{s}_100pct'] for s in strategies]
            bars = ax.bar(np.arange(4)+offset,values,.34,label=label,color=color)
            ax.bar_label(bars,fmt='%.3f',fontsize=8,padding=3)
        ax.set(xticks=range(4),xticklabels=labels,title=f'Blocos de {block}°',ylim=(0,.72))
        ax.grid(axis='y',alpha=.2)
    axes[0].set_ylabel('RMSE mensal (°C)')
    axes[0].legend(loc='upper left', ncol=2, fontsize=9)
    fig.suptitle('C7 — Estratégias de sazonalidade na correção de CHELSA')
    fig.text(.5,.015,'102 estações de desenvolvimento; média de 3 repetições; teste reservado não avaliado.',ha='center',fontsize=9)
    fig.tight_layout(rect=(0,.06,1,.95))
    fig.savefig(safe_path('resultados/figuras/c7_sazonalidade.png'),dpi=170)
    plt.close(fig)
    fig, axes = plt.subplots(1,2,figsize=(10,4.6),sharey=True)
    for block, ax in zip((1,2),axes):
        for method,color,label in [('M2_linear','#617d8a','Linear'),('M5_lightgbm','#147d64','LightGBM')]:
            xs = [25,50,75,100]
            ys = [tables[block][f'{method}_harmonics_{x:03d}pct'] for x in xs]
            ax.plot(xs,ys,'o-',label=label,color=color)
        ax.set(title=f'Blocos de {block}°',xlabel='Estações mantidas no treino (%)',xticks=xs)
        ax.grid(alpha=.2)
    axes[0].set_ylabel('RMSE mensal (°C)')
    axes[1].legend()
    fig.suptitle('C8 — Efeito da densidade de estações')
    fig.text(.5,.015,'Avaliação fixa; subamostragem somente no treino; harmônicos e tuning espacial interno.',ha='center',fontsize=9)
    fig.tight_layout(rect=(0,.06,1,.95))
    fig.savefig(safe_path('resultados/figuras/c8_densidade.png'),dpi=170)
    plt.close(fig)
    inventory = json.loads(safe_path('dados/brasil/grade.json').read_text(encoding='utf-8'))
    lines = []
    for tile in inventory['tiles']:
        _,_,left,_,_,top = tile['transform']
        right,bottom = left+tile['width']*30,top-tile['height']*30
        converter = Transformer.from_crs(tile['crs'],'EPSG:4326',always_xy=True)
        lon,lat = converter.transform([left,right,right,left,left],[top,top,bottom,bottom,top])
        lines.append(np.column_stack([lon,lat]))
    fig,ax = plt.subplots(figsize=(8,8))
    ax.add_collection(LineCollection(lines,colors='#87a5b6',linewidths=.35))
    country = boundary()
    polygons = list(country.geoms) if hasattr(country,'geoms') else [country]
    for polygon in polygons:
        x,y = polygon.exterior.xy
        ax.plot(x,y,color='#173d45',linewidth=.6)
    ax.autoscale()
    ax.set_aspect('equal')
    ax.set(xlabel='Longitude',ylabel='Latitude',title=f'Brasil — {len(lines)} tiles planejados de 30 m')
    ax.grid(alpha=.15)
    fig.text(.5,.015,'Inventário de processamento: esta figura não representa mapas climáticos concluídos.\nLimites: API de malhas do IBGE; tiles de 4096 × 4096 pixels, separados por zona UTM.',ha='center',fontsize=8)
    fig.tight_layout(rect=(0,.06,1,1))
    fig.savefig(safe_path('resultados/figuras/brasil_grade_planejada.png'),dpi=170)
    plt.close(fig)


if __name__=='__main__':
    main()
