# Xavier BR-DWGD v3.2.4 — Normal climatológica mensal de temperatura média e chuva, 1991-2020, Brasil, 0,1°

## Resumo

Normal climatológica mensal (1991-2020) da temperatura média do ar e da chuva, calculada a partir da grade diária do Xavier BR-DWGD v3.2.4. Cada banda mensal é a média de um mês ao longo dos 30 anos; há também a temperatura média anual e a chuva anual. Produto gerado pelo GAMBI-TEC (UTFPR, Campus Santa Helena); é a entrada do Köppen-Geiger `projects/fcoliveira/assets/Climas2/koppen_xavier_1991_2020` e serve de base para outras classificações climáticas e para covariáveis contínuas.

## Especificações

- Fonte: Xavier BR-DWGD v3.2.4 (Brazilian Daily Weather Gridded Data), `projects/ee-alexandrexavier/assets/BR-DWGD`
- Variáveis originais: Tmax, Tmin e chuva diárias
- Período: 1991-01 a 2020-12 (normal climatológica padrão OMM; 30 anos completos de todas as variáveis)
- Resolução espacial: 0,1° (~11 km), grade nativa do BR-DWGD (391 × 393 pixels)
- Sistema de referência: EPSG:4326 (WGS 84)
- Extensão: 73,9° W a 34,8° W e 5,4° N a 33,9° S
- Unidades: °C (temperatura), mm/mês (chuva mensal), mm/ano (chuva anual)
- Tipo: float32
- Bandas: 26 (12 de temperatura, 12 de chuva, 2 anuais)
- NoData: mascarado (fora da área com dado do Xavier)

## Bandas

| Banda | Conteúdo | Unidade | Faixa no Brasil |
|---|---|---|---|
| `T_01` a `T_12` | temperatura média de janeiro a dezembro | °C | 9,0 (julho, serras do Sul) a 31,2 (outubro, Norte) |
| `P_01` a `P_12` | chuva de janeiro a dezembro | mm/mês | 0 (agosto e setembro, semiárido) a 612 (abril) |
| `T_anual` | temperatura média anual (média das 12 bandas) | °C | 12,8 a 28,9 |
| `P_anual` | chuva anual (soma das 12 bandas) | mm/ano | 370 a 3.801 |

## Processamento

1. Leitura do diário v3.2.4 no próprio GEE, aplicando as escalas de cada imagem (`BAND_*_MULT`, `BAND_*_ADD`).
2. Para cada mês de cada ano de 1991 a 2020: temperatura média = média dos dias de (Tmax + Tmin)/2; chuva = soma dos dias.
3. Média de cada mês ao longo dos 30 anos; `T_anual` = média das 12 temperaturas; `P_anual` = soma das 12 chuvas (`subir_koppen_gee.py`, função `normal_gee`).
4. Exportação como asset de 26 bandas na grade nativa do Xavier.

## Controle de qualidade

- Conferência banda a banda com a mesma normal calculada localmente, a partir de um download independente do mesmo diário (`subprodutos_koppen.py`): idêntica nas 24 bandas mensais (diferença máxima de 0,0002 mm na chuva).
- A coleção mensal publicada pelo autor (`BR-DWGD_Monthly`) não foi usada: num teste em Brasília (01/2010), a chuva mensal dela (171 mm) não bateu com a soma dos dias (114 mm).

## Assets relacionados (mesma grade e período)

- `projects/fcoliveira/assets/Climas2/koppen_xavier_1991_2020`: Köppen-Geiger 1991-2020 calculado com esta normal
- `projects/fcoliveira/assets/Climas2/xavier_conjunto_curto_decenal`: clima decenal (média móvel de 10 anos, 1985-2026) do mesmo Xavier, recomendado como covariável do modelo de SOC

## Usos

- Classificação climática de Köppen-Geiger (critérios de Alvares et al., 2013, com a sazonalidade de Kottek et al., 2006), incluindo o limiar de 18 °C do mês mais frio (grupo A) e o limiar de aridez do grupo B
- Zonas de vida de Holdridge, balanço hídrico climatológico e classificação de Thornthwaite (com uma ETo)
- Covariáveis contínuas (temperatura anual, do mês mais frio e do mês mais quente, chuva anual e do mês mais seco)

## Limitações

- A resolução é a do Xavier (~11 km): em serras menores que o pixel, a temperatura é a média do pixel e não é corrigida pela altitude.
- Pixels sem dado do Xavier (bordas de fronteira e de litoral, ilhas oceânicas e a ponta oeste do Acre, cerca de 1,5% dos pixels que tocam o Brasil) ficam mascarados.
- O Xavier tem poucas estações na Amazônia e no Centro-Oeste; ali a grade é mais suavizada.
- A normal 1991-2020 é mais quente que as usadas nas classificações clássicas do Brasil (por exemplo, Alvares et al., 2013); fronteiras térmicas se deslocam em relação a esses mapas.

## Como usar

As bandas já vêm nomeadas por mês. Faixas de visualização sugeridas para o Brasil: 14 a 28 °C (temperatura anual), 8 a 30 °C (mensal), 400 a 3.000 mm (chuva anual) e 0 a 400 mm (chuva mensal).

## Google Earth Engine (Code Editor, JavaScript)

```javascript
// ===== Xavier v3.2.4 | Temperatura e chuva | Normal 1991-2020 | Brasil 0,1° =====
var normal = ee.Image('projects/fcoliveira/assets/Climas2/xavier_normal_1991_2020');
var meses = ['01', '02', '03', '04', '05', '06', '07', '08', '09', '10', '11', '12'];
var nomes = ['jan', 'fev', 'mar', 'abr', 'mai', 'jun', 'jul', 'ago', 'set', 'out', 'nov', 'dez'];
var temp = normal.select('T_[0-9].*');
var chuva = normal.select('P_[0-9].*');

// Temperatura do mês mais frio e do mais quente; chuva do mês mais seco
var tFrio = temp.reduce(ee.Reducer.min()).rename('t_mes_frio');
var tQuente = temp.reduce(ee.Reducer.max()).rename('t_mes_quente');
var pSeco = chuva.reduce(ee.Reducer.min()).rename('p_mes_seco');
var grupoA = tFrio.gte(18).selfMask();   // critério do grupo A de Köppen

var brasil = ee.FeatureCollection('FAO/GAUL/2015/level0').filter(ee.Filter.eq('ADM0_NAME', 'Brazil'));
var paletaT = ['#313695', '#4575b4', '#74add1', '#abd9e9', '#ffffbf', '#fdae61', '#f46d43', '#d73027', '#a50026'];
var paletaP = ['#8c510a', '#d8b365', '#f6e8c3', '#c7eae5', '#5ab4ac', '#01665e'];
var visT = {min: 14, max: 28, palette: paletaT};
var visP = {min: 400, max: 3000, palette: paletaP};

Map.setCenter(-52, -14, 4);
Map.addLayer(normal.select('T_anual'), visT, 'Temperatura média anual (°C)');
Map.addLayer(normal.select('P_anual'), visP, 'Chuva anual (mm)', false);
Map.addLayer(tFrio, {min: 8, max: 28, palette: paletaT}, 'Temperatura do mês mais frio (°C)', false);
Map.addLayer(pSeco, {min: 0, max: 150, palette: paletaP}, 'Chuva do mês mais seco (mm)', false);
Map.addLayer(grupoA, {palette: ['#1b7837'], opacity: 0.5}, 'Mês mais frio ≥ 18 °C (Köppen A)', false);
Map.addLayer(ee.Image().paint(brasil, 0, 1), {palette: ['000000']}, 'Limite do Brasil');

// Legenda (barra de cores contínua)
function legenda(titulo, vis, posicao) {
  var barra = ui.Thumbnail({
    image: ee.Image.pixelLonLat().select(0).multiply((vis.max - vis.min) / 100).add(vis.min).visualize(vis),
    params: {bbox: [0, 0, 100, 10], dimensions: '200x12'},
    style: {stretch: 'horizontal', margin: '0 8px', maxHeight: '20px'}
  });
  var rotulos = ui.Panel([ui.Label(String(vis.min), {margin: '4px 8px'}),
    ui.Label(String((vis.min + vis.max) / 2), {margin: '4px 8px', textAlign: 'center', stretch: 'horizontal'}),
    ui.Label(String(vis.max), {margin: '4px 8px'})], ui.Panel.Layout.flow('horizontal'));
  return ui.Panel({widgets: [ui.Label(titulo, {fontWeight: 'bold', fontSize: '13px'}), barra, rotulos],
                   style: {position: posicao, padding: '8px 15px'}});
}
Map.add(legenda('Temperatura média anual (°C)', visT, 'bottom-left'));
Map.add(legenda('Chuva anual (mm)', visP, 'bottom-right'));

// Climograma num ponto (Santa Helena/PR)
var ponto = ee.Geometry.Point([-54.33, -24.86]);
var v = normal.reduceRegion(ee.Reducer.first(), ponto, 11132);
var tabela = ee.FeatureCollection(ee.List.sequence(0, 11).map(function (i) {
  i = ee.Number(i).int();
  var m = ee.String(ee.List(meses).get(i));
  return ee.Feature(null, {mes: ee.List(nomes).get(i), chuva: v.get(ee.String('P_').cat(m)),
                           temperatura: v.get(ee.String('T_').cat(m))});
}));
print(ui.Chart.feature.byFeature(tabela, 'mes', ['chuva', 'temperatura'])
  .setSeriesNames(['Chuva (mm)', 'Temperatura (°C)'])
  .setOptions({title: 'Normal 1991-2020 | Santa Helena/PR',
               series: {0: {type: 'bars', targetAxisIndex: 0, color: '#2a78d6'},
                        1: {type: 'line', targetAxisIndex: 1, color: '#d73027', lineWidth: 2, pointSize: 4}},
               vAxes: {0: {title: 'Chuva (mm)'}, 1: {title: 'Temperatura (°C)'}}}));
print('Temperatura anual (°C) e chuva anual (mm):', v.get('T_anual'), v.get('P_anual'));
```

## Google Colab (Python)

```python
# ===== Xavier v3.2.4 | Temperatura e chuva | Normal 1991-2020 | Brasil 0,1° =====
!pip install -q geemap

import ee
import geemap
import matplotlib.pyplot as plt

ee.Authenticate()
ee.Initialize(project='SEU_PROJETO')

normal = ee.Image('projects/fcoliveira/assets/Climas2/xavier_normal_1991_2020')
meses = [f'{m:02d}' for m in range(1, 13)]
nomes = ['jan', 'fev', 'mar', 'abr', 'mai', 'jun', 'jul', 'ago', 'set', 'out', 'nov', 'dez']

# ---------- Mapa interativo ----------
paleta_t = ['#313695', '#4575b4', '#74add1', '#abd9e9', '#ffffbf', '#fdae61', '#f46d43', '#d73027', '#a50026']
paleta_p = ['#8c510a', '#d8b365', '#f6e8c3', '#c7eae5', '#5ab4ac', '#01665e']
vis_t = {'min': 14, 'max': 28, 'palette': paleta_t}
vis_p = {'min': 400, 'max': 3000, 'palette': paleta_p}
m = geemap.Map(center=[-14, -52], zoom=4)
m.add_layer(normal.select('T_anual'), vis_t, 'Temperatura média anual (°C)')
m.add_layer(normal.select('P_anual'), vis_p, 'Chuva anual (mm)', False)
m.add_colorbar(vis_t, label='Temperatura média anual (°C)', layer_name='Temperatura média anual (°C)')
m.add_colorbar(vis_p, label='Chuva anual (mm)', layer_name='Chuva anual (mm)')
m
```

```python
# ---------- Climograma num ponto ----------
ponto = ee.Geometry.Point([-54.33, -24.86])  # Santa Helena/PR
v = normal.reduceRegion(ee.Reducer.first(), ponto, 11132).getInfo()
t = [v[f'T_{m}'] for m in meses]
p = [v[f'P_{m}'] for m in meses]

fig, ax = plt.subplots(figsize=(9, 4))
ax.bar(nomes, p, color='#2a78d6', label='Chuva (mm)')
ax.set_ylabel('Chuva (mm/mês)')
ax2 = ax.twinx()
ax2.plot(nomes, t, color='#d73027', marker='o', lw=2, label='Temperatura (°C)')
ax2.set_ylabel('Temperatura (°C)')
ax.set_title(f"Normal 1991-2020 | Santa Helena/PR | {v['T_anual']:.1f} °C, {v['P_anual']:.0f} mm/ano")
fig.legend(loc='upper right', fontsize=8)
plt.tight_layout()
plt.show()
```

## Citação

Dados originais: Xavier, A. C.; Scanlon, B. R.; King, C. W.; Alves, A. I. (2022). New improved Brazilian daily weather gridded data (1961-2020). International Journal of Climatology, 42(16), 8390-8404. https://doi.org/10.1002/joc.7731 (versão v3.2.4, 1961-2025).

Processamento: Oliveira, F. C. (2026). Normal climatológica 1991-2020 de temperatura e chuva do Xavier BR-DWGD v3.2.4. GAMBI-TEC/UTFPR. https://github.com/fcoliveira-utfpr/climate_for_soil (`C4/codigo/subir_koppen_gee.py`).

## Contato

Prof. Dr. Fabrício Correia de Oliveira — GAMBI-TEC, UTFPR Campus Santa Helena, fcoliveira@utfpr.edu.br

## Licença

Produto derivado distribuído sob CC BY 4.0; cite também os dados originais do BR-DWGD (Xavier et al., 2022).
