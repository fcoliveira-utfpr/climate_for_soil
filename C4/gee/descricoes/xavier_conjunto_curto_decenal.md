# Xavier BR-DWGD v3.2.4 — Conjunto curto de clima decenal (média móvel de 10 anos), 1985-2026, Brasil, 0,1°

## Resumo

Nove variáveis climáticas em **média móvel dos 10 anos anteriores** ao ano da imagem (a imagem de 2010 usa 2000-2009), calculadas a partir da grade diária do Xavier BR-DWGD v3.2.4: sete de temperatura, o CDD (dias secos consecutivos) e o armazenamento de água no solo (ARM) do balanço hídrico de Thornthwaite-Mather com a CAD do solo. Uma imagem por ano, de 1985 a 2026. Produto gerado pelo GAMBI-TEC (UTFPR, Campus Santa Helena) como covariável climática do modelo de carbono orgânico do solo (SOC, 0-30 cm) do MapBiomas Solo, em substituição ao Köppen do IPEF: ganhou do Köppen nas validações espacial, temporal e espaço-temporal, em todas as repetições.

## Especificações

- Fonte: Xavier BR-DWGD v3.2.4 (Brazilian Daily Weather Gridded Data), `projects/ee-alexandrexavier/assets/BR-DWGD`, diário de 1961 a 2025
- Variáveis originais: Tmax, Tmin, chuva, umidade relativa, radiação solar e vento a 2 m (diários)
- Período: janelas de 10 anos de 1975-1984 (imagem de 1985) a 2016-2025 (imagem de 2026); todas completas
- Resolução espacial: 0,1° (~11 km), a grade do BR-DWGD
- Sistema de referência: EPSG:4326 (WGS 84)
- Extensão: 74,9° W a 28,0° W e 6,4° N a 34,9° S (a grade do Xavier estendida para cobrir todo o território, ilhas oceânicas incluídas)
- Tipo: float32
- Imagens: 42 (uma por ano, 1985-2026), 11 bandas cada
- NoData: nenhum; **toda a grade tem valor**
- Propriedades: `year` (ano da imagem), `inicio_janela`, `fim_janela`, `system:time_start` (1º de janeiro do ano)

## Bandas

| Banda | Variável | Unidade |
|---|---|---|
| `cd_t_media` | temperatura média: média de (Tmax + Tmin)/2 | °C |
| `cd_tmax_media` | temperatura máxima média | °C |
| `cd_tmin_media` | temperatura mínima média | °C |
| `cd_t_mes_quente` | temperatura média do mês mais quente | °C |
| `cd_t_mes_frio` | temperatura média do mês mais frio | °C |
| `cd_amplitude` | amplitude térmica diária média (Tmax - Tmin) | °C |
| `cd_biotemp` | biotemperatura de Holdridge | °C |
| `cd_cdd` | CDD: maior sequência anual de dias com chuva < 1 mm (ETCCDI), média dos 10 anos | dias |
| `cd_arm_csolo` | armazenamento médio de água no solo (média dos 12 meses) do balanço hídrico de Thornthwaite-Mather com a CAD do solo | mm |
| `dist_preenchimento_km` | distância até o pixel do Xavier de onde veio o valor (0 = dado original) | km |
| `z_pixel_m` | altitude média do pixel (MERIT DEM); auxiliar, não é covariável | m |

## Processamento

1. Download do diário v3.2.4 no GEE e agregação mensal por ano (médias de Tmax, Tmin, UR, radiação e vento; somas de chuva) e do CDD anual, calculado no GEE (`baixar_xavier.py`). As escalas de cada imagem (`BAND_*_MULT`, `BAND_*_ADD`) são lidas das propriedades. A coleção mensal do autor não foi usada (num teste, a chuva mensal não bateu com a soma dos dias).
2. ETo de Penman-Monteith (FAO-56) pelo saldo de radiação, com a biblioteca agrometeorologiapy (`eto_rn.py`); conferida com a ETo do próprio Xavier: r = 0,998, diferença média de −0,8%.
3. Para cada ano Y de 1985 a 2026, médias mensais da janela Y−10 a Y−1 e cálculo das variáveis (`variaveis.py`): temperaturas; biotemperatura de Holdridge (agrometeorologiapy); CDD médio; balanço hídrico climatológico de Thornthwaite-Mather (agrometeorologiapy) com a CAD do solo = AWC × 1 m (mapa de AWC do Brasil, `projects/fcoliveira/assets/AWC_br`, média no pixel; 100 mm onde não há AWC).
4. Pixels sem dado do Xavier (bordas de fronteira e de litoral, ilhas oceânicas e a ponta oeste do Acre: 1,5% dos pixels que tocam o Brasil) e o restante da grade estendida recebem o valor do pixel válido mais próximo (`publicar_curto_gee.py`); a distância fica na banda `dist_preenchimento_km`.
5. Envio ao GEE sem upload manual, uma banda por vez (`subir_por_banda.py`), e montagem das 42 imagens.

## Controle de qualidade

- Conferência asset × cálculo local, todos os anos e bandas: diferenças só de arredondamento (≤ 0,005 °C, ≤ 0,05 dia, ≤ 0,05 mm) e nenhum pixel sem valor em toda a grade (`montar_colecao_gee.py conferir`).
- Notebook de conferência (`C4/notebooks/conferir_variaveis_gee.ipynb`): mapa interativo com inspector, série temporal por pixel, amostragem a 30 m com bilinear em pontos críticos (Fernando de Noronha, Atol das Rocas, São Pedro e São Paulo, Trindade e Martim Vaz, extremos norte, sul, leste e oeste, litoral, fronteiras) e em 3.000 pontos aleatórios no Brasil, e faixas de valores e saltos entre anos.
- Versões alternativas testadas e descartadas: temperatura corrigida pela altitude (gradientes de −5,0 a −5,8 °C/km estimados no próprio Xavier) e CAD do solo em 1 km. Pioraram a validação temporal.

## Validação no modelo de SOC

Modelo de SOC do MapBiomas Solo, Coleção 3 (matriz de treino reproduzida, 27.425 linhas), com o modelo do mapa (smileRandomForest do GEE) e com o ranger; validação espacial (V2, blocos de 2°), temporal (V3, uma década fora) e espaço-temporal (V4); 3 repetições; MEC (Nash-Sutcliffe) nas 9.787 amostras reais de 0-30 cm.

| Modelo do mapa (GEE) | V2 | V3 | V4 |
|---|---|---|---|
| Köppen IPEF (atual), MEC | 0,181 | 0,123 | 0,114 |
| Conjunto curto, valor do pixel | +0,012 | +0,015 | +0,022 |
| **Conjunto curto, bilinear** | **+0,017** | **+0,021** | **+0,031** |

| Ranger | V2 | V3 | V4 |
|---|---|---|---|
| Köppen IPEF (atual), MEC | 0,229 | 0,176 | 0,161 |
| Conjunto curto, valor do pixel | +0,014 | +0,019 | +0,020 |
| **Conjunto curto, bilinear** | **+0,012** | **+0,024** | **+0,023** |

Ganhos de MEC sobre o Köppen IPEF, média das 3 repetições. O conjunto curto ganha do Köppen nas 6 combinações em todas as repetições. A interpolação bilinear melhora o modelo do mapa nos três esquemas (+0,005 a +0,010 sobre o valor do pixel); no ranger fica empatada no espaço (−0,002) e melhora no tempo.

## Assets relacionados

- `projects/fcoliveira/assets/Climas2/koppen_xavier_1991_2020`: Köppen-Geiger 1991-2020 do Xavier v3.2.4
- `projects/fcoliveira/assets/Climas2/xavier_normal_1991_2020`: normal 1991-2020 de temperatura e chuva do Xavier v3.2.4

## Limitações

- A resolução é a do Xavier (~11 km): a bilinear suaviza os degraus, mas não cria detalhe. As temperaturas **não são corrigidas pela altitude**: em serras e chapadas menores que o pixel, o valor é o da média do pixel (a correção foi testada e piorou a validação temporal).
- A CAD do solo é fixa no tempo; só o clima muda de um ano para o outro.
- Nas ilhas oceânicas o valor vem do pixel de terra mais próximo do Xavier (Trindade fica a ~1.100 km da costa); use `dist_preenchimento_km` para identificar ou excluir esses pixels.
- O Xavier tem poucas estações na Amazônia e no Centro-Oeste; ali a grade é mais suavizada.
- A queda do SOC no tempo que o modelo prevê com estas variáveis ainda não tem validação independente (experimentos de longa duração). As imagens de 2025 e 2026 estão calculadas, mas o painel de covariáveis usado na validação ia até 2024.

## Como usar

Amostre sempre com **interpolação bilinear** (`.resample('bilinear')`), no treino e no mapa: o GEE usa o vizinho mais próximo por padrão, e sem a bilinear o modelo vê degraus de 11 km. Os códigos abaixo são completos: cole num script novo do Code Editor e clique em Run.

### 1. Visualizador (Code Editor, JavaScript)

Seletor de variável e de ano, legenda, estatísticas no console e valores das 9 variáveis no ponto clicado.

```javascript
// ===== Xavier v3.2.4 | Conjunto curto de clima decenal | 1985-2026 | Visualizador =====
var COLECAO = 'projects/fcoliveira/assets/Climas2/xavier_conjunto_curto_decenal';
var col = ee.ImageCollection(COLECAO);
var ANO_MIN = 1985, ANO_MAX = 2026;

// Inspeção da coleção
print('Nº de imagens:', col.size());
print('Anos disponíveis:', col.aggregate_array('year').sort());
print('Primeira imagem:', col.first());

// Brasil (FAO GAUL 2015, com as ilhas oceânicas)
var brasil = ee.FeatureCollection('FAO/GAUL/2015/level0').filter(ee.Filter.eq('ADM0_NAME', 'Brazil'));
var limite = ee.Image().paint(brasil, 0, 1);

// Paletas
var PAL_T = ['#313695', '#4575b4', '#74add1', '#abd9e9', '#ffffbf', '#fdae61', '#f46d43', '#d73027', '#a50026'];
var PAL_AMP = ['#f7fcf5', '#c7e9c0', '#74c476', '#238b45', '#00441b'];
var PAL_CDD = ['#ffffd4', '#fe9929', '#993404'];
var PAL_ARM = ['#8c510a', '#d8b365', '#f6e8c3', '#c7eae5', '#5ab4ac', '#01665e'];

// Variáveis e faixas de visualização (ajuste min/max conforme as estatísticas impressas no console)
var VARS = {
  'Temperatura média (°C)':             {banda: 'cd_t_media',      vis: {min: 14, max: 28, palette: PAL_T}},
  'Temperatura máxima média (°C)':      {banda: 'cd_tmax_media',   vis: {min: 20, max: 34, palette: PAL_T}},
  'Temperatura mínima média (°C)':      {banda: 'cd_tmin_media',   vis: {min: 8,  max: 24, palette: PAL_T}},
  'T do mês mais quente (°C)':          {banda: 'cd_t_mes_quente', vis: {min: 18, max: 32, palette: PAL_T}},
  'T do mês mais frio (°C)':            {banda: 'cd_t_mes_frio',   vis: {min: 8,  max: 28, palette: PAL_T}},
  'Amplitude térmica diária (°C)':      {banda: 'cd_amplitude',    vis: {min: 6,  max: 16, palette: PAL_AMP}},
  'Biotemperatura (°C)':                {banda: 'cd_biotemp',      vis: {min: 12, max: 28, palette: PAL_T}},
  'Dias secos consecutivos (dias)':     {banda: 'cd_cdd',          vis: {min: 10, max: 150, palette: PAL_CDD}},
  'Armazenamento de água no solo (mm)': {banda: 'cd_arm_csolo',    vis: {min: 0,  max: 200, palette: PAL_ARM}}
};
var NOMES = Object.keys(VARS);
var BANDAS = NOMES.map(function (n) { return VARS[n].banda; });

// Estado
var estado = {ano: 2020, nome: NOMES[0]};

function imagemDoAno(ano) {
  return ee.Image(col.filter(ee.Filter.eq('year', ano)).first())
    .select(BANDAS).resample('bilinear').clip(brasil);
}

// Legenda
var painelLegenda = ui.Panel({style: {position: 'bottom-left', padding: '8px 15px'}});
function atualizarLegenda(titulo, vis) {
  painelLegenda.clear();
  var barra = ui.Thumbnail({
    image: ee.Image.pixelLonLat().select(0).multiply((vis.max - vis.min) / 100).add(vis.min).visualize(vis),
    params: {bbox: [0, 0, 100, 10], dimensions: '200x12'},
    style: {stretch: 'horizontal', margin: '0 8px', maxHeight: '20px'}
  });
  var rotulos = ui.Panel([
    ui.Label(String(vis.min), {margin: '4px 8px'}),
    ui.Label(String((vis.min + vis.max) / 2), {margin: '4px 8px', textAlign: 'center', stretch: 'horizontal'}),
    ui.Label(String(vis.max), {margin: '4px 8px'})
  ], ui.Panel.Layout.flow('horizontal'));
  painelLegenda.add(ui.Label(titulo, {fontWeight: 'bold', fontSize: '13px'}));
  painelLegenda.add(barra);
  painelLegenda.add(rotulos);
}

// Desenho do mapa
function desenhar() {
  var v = VARS[estado.nome];
  var img = imagemDoAno(estado.ano).select(v.banda);
  Map.layers().reset();
  Map.addLayer(img, v.vis, estado.nome + ' | ' + estado.ano);
  Map.addLayer(limite, {palette: ['000000']}, 'Limite do Brasil');
  atualizarLegenda(estado.nome + ' | ' + estado.ano, v.vis);

  // Estatísticas no Brasil (percentis 2 e 98) para conferir as faixas de visualização
  img.reduceRegion({
    reducer: ee.Reducer.percentile([2, 98]).combine(ee.Reducer.mean(), '', true),
    geometry: brasil.geometry(), scale: 11132, maxPixels: 1e9, bestEffort: true
  }).evaluate(function (s) { print(estado.nome + ' ' + estado.ano + ' (P2, P98, média):', s); });
}

// Controles
var seletor = ui.Select({
  items: NOMES, value: estado.nome,
  onChange: function (n) { estado.nome = n; desenhar(); },
  style: {stretch: 'horizontal'}
});
var slider = ui.Slider({
  min: ANO_MIN, max: ANO_MAX, value: estado.ano, step: 1,
  onChange: function (a) { estado.ano = a; desenhar(); },
  style: {stretch: 'horizontal'}
});
var painelInfo = ui.Label('Clique no mapa para ver as 9 variáveis no ponto.', {fontSize: '12px', whiteSpace: 'pre'});

var painel = ui.Panel({
  widgets: [
    ui.Label('Clima decenal | Xavier v3.2.4', {fontWeight: 'bold', fontSize: '15px'}),
    ui.Label('Variável'), seletor,
    ui.Label('Ano'), slider,
    painelInfo
  ],
  style: {width: '320px', padding: '8px'}
});
ui.root.insert(0, painel);
Map.add(painelLegenda);

// Valores no ponto clicado
Map.style().set('cursor', 'crosshair');
Map.onClick(function (coords) {
  var pt = ee.Geometry.Point([coords.lon, coords.lat]);
  painelInfo.setValue('Consultando...');
  imagemDoAno(estado.ano).reduceRegion(ee.Reducer.first(), pt, 30).evaluate(function (v) {
    if (!v) { painelInfo.setValue('Sem dados no ponto.'); return; }
    var txt = 'Lon ' + coords.lon.toFixed(3) + ' | Lat ' + coords.lat.toFixed(3) + ' | ' + estado.ano + '\n';
    NOMES.forEach(function (n) {
      var x = v[VARS[n].banda];
      txt += n + ': ' + (x === null ? '—' : x.toFixed(2)) + '\n';
    });
    painelInfo.setValue(txt);
  });
});

Map.setCenter(-52, -14, 4);
desenhar();
```

### 2. No modelo de SOC (Code Editor, JavaScript)

O clima de cada amostra no ano dela (treino) e o clima de um ano empilhado nas demais covariáveis (mapa), com a mesma bilinear nos dois. Troque as amostras de teste pelas amostras de SOC (com a propriedade `year`).

```javascript
// ===== Xavier v3.2.4 | Conjunto curto de clima decenal | Uso no modelo de SOC =====
var COLECAO = 'projects/fcoliveira/assets/Climas2/xavier_conjunto_curto_decenal';
var BANDAS = ['cd_t_media', 'cd_tmax_media', 'cd_tmin_media', 'cd_t_mes_quente', 'cd_t_mes_frio',
              'cd_amplitude', 'cd_biotemp', 'cd_cdd', 'cd_arm_csolo'];

// As 9 variáveis do ano (1985-2026), com interpolação bilinear; anos fora da faixa usam o extremo mais próximo
function climaDoAno(ano) {
  var a = ee.Number(ano).max(1985).min(2026);
  return ee.Image(ee.ImageCollection(COLECAO).filter(ee.Filter.eq('year', a)).first())
    .select(BANDAS).resample('bilinear');
}

// Clima de cada amostra no ano dela (campoAno: propriedade com o ano)
function amostrar(amostras, campoAno, escala) {
  amostras = ee.FeatureCollection(amostras);
  var anos = amostras.aggregate_array(campoAno).distinct();
  return ee.FeatureCollection(anos.map(function (a) {
    return climaDoAno(a).sampleRegions({
      collection: amostras.filter(ee.Filter.eq(campoAno, a)), scale: escala, geometries: true
    });
  })).flatten();
}

// ---------- Treino: amostras de teste (troque pelas amostras de SOC) ----------
var amostras = ee.FeatureCollection([
  ee.Feature(ee.Geometry.Point([-47.90, -15.80]), {local: 'Brasília', year: 1990, carbono: 40}),
  ee.Feature(ee.Geometry.Point([-47.90, -15.80]), {local: 'Brasília', year: 2020, carbono: 38}),
  ee.Feature(ee.Geometry.Point([-60.02, -3.10]),  {local: 'Manaus', year: 2005, carbono: 55}),
  ee.Feature(ee.Geometry.Point([-54.33, -24.86]), {local: 'Santa Helena', year: 2015, carbono: 45})
]);
var treino = amostrar(amostras, 'year', 30);
print('Amostras com as 9 variáveis do ano de cada uma:', treino);

// ---------- Mapa do ano: demais covariáveis + clima do mesmo ano ----------
var ano = 2020;
var clima = climaDoAno(ano);
// var pilha = covariaveisDoAno.addBands(clima);
// var rf = ee.Classifier.smileRandomForest(...).setOutputMode('REGRESSION')
//            .train(treino, 'carbono', BANDAS.concat(outrasBandas));
// var soc = pilha.classify(rf);

Map.setCenter(-52, -14, 4);
Map.addLayer(clima.select('cd_t_media'), {min: 14, max: 28,
  palette: ['#313695', '#74add1', '#ffffbf', '#f46d43', '#a50026']}, 'T média ' + ano + ' (bilinear)');
Map.addLayer(treino, {color: '000000'}, 'Amostras');
```

As mesmas funções, como módulo para `require`, estão em github.com/fcoliveira-utfpr/climate_for_soil, `C4/gee/clima_curto.js`.

### 3. Google Colab (Python)

```python
# ===== Xavier v3.2.4 | Conjunto curto de clima decenal | 1985-2026 | Brasil 0,1° =====
!pip install -q geemap

import ee
import geemap
import matplotlib.pyplot as plt
import pandas as pd

ee.Authenticate()
ee.Initialize(project='SEU_PROJETO')

COLECAO = 'projects/fcoliveira/assets/Climas2/xavier_conjunto_curto_decenal'
BANDAS = ['cd_t_media', 'cd_tmax_media', 'cd_tmin_media', 'cd_t_mes_quente', 'cd_t_mes_frio',
          'cd_amplitude', 'cd_biotemp', 'cd_cdd', 'cd_arm_csolo']
col = ee.ImageCollection(COLECAO)

def clima_do_ano(ano):
    """As 9 variáveis do ano com interpolação bilinear (a forma validada)."""
    a = ee.Number(ano).max(1985).min(2026)
    return ee.Image(col.filter(ee.Filter.eq('year', a)).first()).select(BANDAS).resample('bilinear')

def amostrar(amostras, campo_ano='year', escala=30):
    """Clima de cada amostra no ano dela (para o treino)."""
    anos = amostras.aggregate_array(campo_ano).distinct()
    return ee.FeatureCollection(anos.map(lambda a: clima_do_ano(a).sampleRegions(
        collection=amostras.filter(ee.Filter.eq(campo_ano, a)), scale=escala, geometries=True))).flatten()

# ---------- Mapa interativo ----------
brasil = ee.FeatureCollection('FAO/GAUL/2015/level0').filter(ee.Filter.eq('ADM0_NAME', 'Brazil'))
paleta = ['#313695', '#4575b4', '#74add1', '#abd9e9', '#ffffbf', '#fdae61', '#f46d43', '#d73027', '#a50026']
vis_t = {'min': 14, 'max': 28, 'palette': paleta}
c = clima_do_ano(2020)
m = geemap.Map(center=[-14, -52], zoom=4)
m.add_layer(c.select('cd_t_media').clip(brasil), vis_t, 'T média 2020 (°C)')
m.add_layer(c.select('cd_arm_csolo').clip(brasil), {'min': 0, 'max': 200, 'palette': ['#8c510a', '#f6e8c3', '#01665e']},
            'ARM 2020 (mm)', False)
m.add_layer(ee.Image().paint(brasil, 0, 1), {'palette': ['black']}, 'Limite do Brasil')
m.add_colorbar(vis_t, label='Temperatura média decenal (°C)', layer_name='T média 2020 (°C)')
m
```

```python
# ---------- Amostras com anos diferentes e série num ponto ----------
amostras = ee.FeatureCollection([
    ee.Feature(ee.Geometry.Point([-47.90, -15.80]), {'local': 'Brasília', 'year': 1990}),
    ee.Feature(ee.Geometry.Point([-47.90, -15.80]), {'local': 'Brasília', 'year': 2020}),
    ee.Feature(ee.Geometry.Point([-60.02, -3.10]), {'local': 'Manaus', 'year': 2005}),
])
tab = pd.DataFrame([f['properties'] for f in amostrar(amostras).getInfo()['features']])
print(tab[['local', 'year'] + BANDAS].round(2))

ponto = ee.Geometry.Point([-54.33, -24.86])  # Santa Helena/PR
fc = col.map(lambda img: ee.Feature(None, img.select(BANDAS).resample('bilinear')
                                    .reduceRegion(ee.Reducer.first(), ponto, 30)).set('ano', img.get('year')))
df = pd.DataFrame([f['properties'] for f in fc.getInfo()['features']]).sort_values('ano')
fig, ax = plt.subplots(1, 2, figsize=(12, 3.5))
ax[0].plot(df.ano, df.cd_t_media, color='#d73027', lw=2); ax[0].set(title='Temperatura média decenal (°C)', xlabel='ano')
ax[1].plot(df.ano, df.cd_arm_csolo, color='#01665e', lw=2); ax[1].set(title='ARM decenal (mm)', xlabel='ano')
fig.suptitle('Santa Helena/PR, média dos 10 anos anteriores'); plt.tight_layout(); plt.show()
```

## Citação

Dados originais: Xavier, A. C.; Scanlon, B. R.; King, C. W.; Alves, A. I. (2022). New improved Brazilian daily weather gridded data (1961-2020). International Journal of Climatology, 42(16), 8390-8404. https://doi.org/10.1002/joc.7731 (versão v3.2.4, 1961-2025).

Processamento: Oliveira, F. C. (2026). Conjunto curto de clima decenal do Xavier BR-DWGD v3.2.4 para o modelo de SOC do MapBiomas Solo. GAMBI-TEC/UTFPR. https://github.com/fcoliveira-utfpr/climate_for_soil (pasta `C4/`).

## Contato

Prof. Dr. Fabrício Correia de Oliveira — GAMBI-TEC, UTFPR Campus Santa Helena, fcoliveira@utfpr.edu.br

## Licença

Produto derivado distribuído sob CC BY 4.0; cite também os dados originais do BR-DWGD (Xavier et al., 2022).
