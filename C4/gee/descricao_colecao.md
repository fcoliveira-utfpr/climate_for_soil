**Xavier BR-DWGD v3.2.4 — Conjunto curto de clima decenal (média móvel de 10 anos), 1985-2026, Brasil, 0,1°**

**Resumo**

Nove variáveis climáticas em **média móvel dos 10 anos anteriores** ao ano da imagem (a imagem de 2010 usa
2000-2009), calculadas a partir da grade diária do Xavier BR-DWGD v3.2.4: sete de temperatura, o CDD (dias secos
consecutivos) e o armazenamento de água no solo (ARM) do balanço hídrico de Thornthwaite-Mather com a CAD do
solo. Uma imagem por ano, de 1985 a 2026. Produto gerado pelo GAMBI-TEC (UTFPR, Campus Santa Helena) como
covariável climática do modelo de carbono orgânico do solo (SOC, 0-30 cm) do MapBiomas Solo, em substituição ao
Köppen do IPEF: ganhou do Köppen nas validações espacial, temporal e espaço-temporal, em todas as repetições.

**Especificações**

- Fonte: Xavier BR-DWGD v3.2.4 (Brazilian Daily Weather Gridded Data), `projects/ee-alexandrexavier/assets/BR-DWGD`,
  diário de 1961 a 2025
- Variáveis originais: Tmax, Tmin, chuva, umidade relativa, radiação solar e vento a 2 m (diários)
- Período: janelas de 10 anos de 1975-1984 (imagem de 1985) a 2016-2025 (imagem de 2026); todas completas
- Resolução espacial: 0,1° (~11 km), a grade do BR-DWGD
- Sistema de referência: EPSG:4326 (WGS 84)
- Extensão: 74,9° W a 28,0° W e 6,4° N a 34,9° S (a grade do Xavier estendida para cobrir todo o território,
  ilhas oceânicas incluídas)
- Tipo: float32
- Imagens: 42 (uma por ano, 1985-2026), 11 bandas cada
- NoData: nenhum; **toda a grade tem valor**
- Propriedades: `year` (ano da imagem), `inicio_janela`, `fim_janela`, `system:time_start` (1º de janeiro do ano)

**Bandas**

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

**Processamento**

1. Download do diário v3.2.4 no GEE e agregação mensal por ano (médias de Tmax, Tmin, UR, radiação e vento;
   somas de chuva) e do CDD anual, calculado no GEE (`baixar_xavier.py`). As escalas de cada imagem
   (`BAND_*_MULT`, `BAND_*_ADD`) são lidas das propriedades. A coleção mensal do autor não foi usada (num teste,
   a chuva mensal não bateu com a soma dos dias).
2. ETo de Penman-Monteith (FAO-56) pelo saldo de radiação, com a biblioteca agrometeorologiapy (`eto_rn.py`);
   conferida com a ETo do próprio Xavier: r = 0,998, diferença média de −0,8%.
3. Para cada ano Y de 1985 a 2026, médias mensais da janela Y−10 a Y−1 e cálculo das variáveis
   (`variaveis.py`): temperaturas; biotemperatura de Holdridge (agrometeorologiapy); CDD médio; balanço hídrico
   climatológico de Thornthwaite-Mather (agrometeorologiapy) com a CAD do solo = AWC × 1 m (mapa de AWC do Brasil,
   `projects/fcoliveira/assets/AWC_br`, média no pixel; 100 mm onde não há AWC).
4. Pixels sem dado do Xavier (bordas de fronteira e de litoral, ilhas oceânicas e a ponta oeste do Acre: 1,5% dos
   pixels que tocam o Brasil) e o restante da grade estendida recebem o valor do pixel válido mais próximo
   (`publicar_curto_gee.py`); a distância fica na banda `dist_preenchimento_km`.
5. Envio ao GEE sem upload manual, uma banda por vez (`subir_por_banda.py`), e montagem das 42 imagens.

**Controle de qualidade**

- Conferência asset × cálculo local, todos os anos e bandas: diferenças só de arredondamento (≤ 0,005 °C,
  ≤ 0,05 dia, ≤ 0,05 mm) e nenhum pixel sem valor em toda a grade (`montar_colecao_gee.py conferir`).
- Notebook de conferência (`C4/notebooks/conferir_variaveis_gee.ipynb`): mapa interativo com inspector, série
  temporal por pixel, amostragem a 30 m com bilinear em pontos críticos (Fernando de Noronha, Atol das Rocas,
  São Pedro e São Paulo, Trindade e Martim Vaz, extremos norte, sul, leste e oeste, litoral, fronteiras) e em
  3.000 pontos aleatórios no Brasil, e faixas de valores e saltos entre anos.
- Versões alternativas testadas e descartadas: temperatura corrigida pela altitude (gradientes de −5,0 a −5,8 °C/km
  estimados no próprio Xavier) e CAD do solo em 1 km. Pioraram a validação temporal.

**Validação no modelo de SOC**

Modelo de SOC do MapBiomas Solo, Coleção 3 (matriz de treino reproduzida, 27.425 linhas), com o modelo do mapa
(smileRandomForest do GEE) e com o ranger; validação espacial (V2, blocos de 2°), temporal (V3, uma década fora)
e espaço-temporal (V4); 3 repetições; MEC (Nash-Sutcliffe) nas 9.787 amostras reais de 0-30 cm.

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

Ganhos de MEC sobre o Köppen IPEF, média das 3 repetições. O conjunto curto ganha do Köppen nas 6 combinações em
todas as repetições. A interpolação bilinear melhora o modelo do mapa nos três esquemas (+0,005 a +0,010 sobre o
valor do pixel); no ranger fica empatada no espaço (−0,002) e melhora no tempo.

**Assets relacionados**

- `projects/fcoliveira/assets/Climas2/koppen_xavier_1991_2020`: Köppen-Geiger 1991-2020 do Xavier v3.2.4
- `projects/fcoliveira/assets/Climas2/xavier_normal_1991_2020`: normal 1991-2020 de temperatura e chuva do
  Xavier v3.2.4

**Limitações**

- A resolução é a do Xavier (~11 km): a bilinear suaviza os degraus, mas não cria detalhe. As temperaturas **não
  são corrigidas pela altitude**: em serras e chapadas menores que o pixel, o valor é o da média do pixel (a
  correção foi testada e piorou a validação temporal).
- A CAD do solo é fixa no tempo; só o clima muda de um ano para o outro.
- Nas ilhas oceânicas o valor vem do pixel de terra mais próximo do Xavier (Trindade fica a ~1.100 km da costa);
  use `dist_preenchimento_km` para identificar ou excluir esses pixels.
- O Xavier tem poucas estações na Amazônia e no Centro-Oeste; ali a grade é mais suavizada.
- A queda do SOC no tempo que o modelo prevê com estas variáveis ainda não tem validação independente
  (experimentos de longa duração). As imagens de 2025 e 2026 estão calculadas, mas o painel de covariáveis
  usado na validação ia até 2024.

**Como usar: o módulo `clima_curto` (recomendado)**

O GEE usa o vizinho mais próximo por padrão; sem `.resample('bilinear')` o modelo vê degraus de 11 km. O módulo
abaixo devolve o clima com a bilinear e deve ser usado **no treino e no mapa**, para que o modelo veja os mesmos
valores nos dois.

1. No Code Editor, crie um script num repositório (por exemplo `users/SEU_USUARIO/SEU_REPOSITORIO:clima_curto`) e
   cole o código do módulo (também em github.com/fcoliveira-utfpr/climate_for_soil, `C4/gee/clima_curto.js`).
2. Nos scripts do modelo, carregue com `require` e use as funções `amostrar` (treino), `empilhar` e `climaDoAno`
   (mapa).

**Código do módulo `clima_curto`**

```javascript
/**
 * Módulo: conjunto curto de clima decenal para o modelo de SOC do MapBiomas Solo (Xavier BR-DWGD v3.2.4).
 * Todas as funções devolvem o clima com interpolação BILINEAR, a forma validada.
 * Autor: Fabrício Correia de Oliveira (UTFPR). Código: github.com/fcoliveira-utfpr/climate_for_soil (C4/gee).
 */
var COLECAO = 'projects/fcoliveira/assets/Climas2/xavier_conjunto_curto_decenal';
var BANDAS = ['cd_t_media', 'cd_tmax_media', 'cd_tmin_media', 'cd_t_mes_quente', 'cd_t_mes_frio',
              'cd_amplitude', 'cd_biotemp', 'cd_cdd', 'cd_arm_csolo'];
var ANO_MIN = 1985;
var ANO_MAX = 2026;

exports.BANDAS = BANDAS;
exports.colecao = ee.ImageCollection(COLECAO);

/** As 9 variáveis do ano (1985-2026), com interpolação bilinear. Anos fora da faixa usam o extremo mais próximo. */
exports.climaDoAno = function (ano) {
  var a = ee.Number(ano).max(ANO_MIN).min(ANO_MAX);
  return ee.Image(ee.ImageCollection(COLECAO).filter(ee.Filter.eq('year', a)).first())
    .select(BANDAS)
    .resample('bilinear');
};

/** Acrescenta o clima do ano a uma imagem de covariáveis (para o mapa do ano). */
exports.empilhar = function (covariaveis, ano) {
  return ee.Image(covariaveis).addBands(exports.climaDoAno(ano));
};

/** Clima de cada amostra no ano dela (para o treino). campoAno: propriedade com o ano (padrão 'year'). */
exports.amostrar = function (amostras, campoAno, escala) {
  campoAno = campoAno || 'year';
  escala = escala || 30;
  amostras = ee.FeatureCollection(amostras);
  var anos = amostras.aggregate_array(campoAno).distinct();
  return ee.FeatureCollection(anos.map(function (a) {
    return exports.climaDoAno(a).sampleRegions({
      collection: amostras.filter(ee.Filter.eq(campoAno, a)),
      scale: escala,
      geometries: true
    });
  })).flatten();
};
```

**Google Earth Engine (Code Editor, JavaScript)**

```javascript
// ===== Xavier v3.2.4 | Conjunto curto de clima decenal | 1985-2026 | Brasil 0,1° =====
var clima = require('users/SEU_USUARIO/SEU_REPOSITORIO:clima_curto');

// Treino: o clima de cada amostra no ano dela (propriedade 'year'), com a mesma interpolação do mapa
var amostras = ee.FeatureCollection('...');            // amostras de SOC com a propriedade 'year'
var treino = clima.amostrar(amostras, 'year', 30);     // acrescenta as 9 bandas como propriedades

// Mapa do ano: as demais covariáveis do ano + o clima do mesmo ano
var ano = 2020;
// var pilha = clima.empilhar(covariaveisDoAno, ano);
// var rf = ee.Classifier.smileRandomForest(...).setOutputMode('REGRESSION')
//            .train(treino, 'carbono', clima.BANDAS.concat(outrasBandas));
// var soc = pilha.classify(rf);

// Visualização
var brasil = ee.FeatureCollection('FAO/GAUL/2015/level0').filter(ee.Filter.eq('ADM0_NAME', 'Brazil'));
var paleta = ['#313695', '#4575b4', '#74add1', '#abd9e9', '#ffffbf', '#fdae61', '#f46d43', '#d73027', '#a50026'];
var visT = {min: 14, max: 28, palette: paleta};
var visArm = {min: 0, max: 200, palette: ['#8c510a', '#d8b365', '#f6e8c3', '#c7eae5', '#5ab4ac', '#01665e']};
var c = clima.climaDoAno(ano);
Map.setCenter(-52, -14, 4);
Map.addLayer(c.select('cd_t_media').clip(brasil), visT, 'T média ' + ano + ' (°C)');
Map.addLayer(c.select('cd_arm_csolo').clip(brasil), visArm, 'ARM ' + ano + ' (mm)', false);
Map.addLayer(c.select('cd_cdd').clip(brasil), {min: 10, max: 150, palette: ['#ffffd4', '#fe9929', '#993404']},
             'CDD ' + ano + ' (dias)', false);
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
Map.add(legenda('Temperatura média decenal (°C)', visT, 'bottom-left'));

// Série 1985-2026 num ponto (Santa Helena/PR)
var ponto = ee.Geometry.Point([-54.33, -24.86]);
var serie = clima.colecao.map(function (img) {
  var v = img.select(['cd_t_media', 'cd_arm_csolo']).resample('bilinear')
             .reduceRegion(ee.Reducer.first(), ponto, 30);
  return ee.Feature(null, v).set('ano', img.get('year'));
});
print(ui.Chart.feature.byFeature(serie.sort('ano'), 'ano', ['cd_t_media'])
  .setOptions({title: 'Temperatura média decenal | Santa Helena/PR', hAxis: {title: 'Ano', format: '####'},
               vAxis: {title: '°C'}, colors: ['#d73027'], lineWidth: 2, pointSize: 3, legend: {position: 'none'}}));
```

**Google Colab (Python)**

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

**Citação**

Dados originais: Xavier, A. C.; Scanlon, B. R.; King, C. W.; Alves, A. I. (2022). New improved Brazilian daily
weather gridded data (1961-2020). International Journal of Climatology, 42(16), 8390-8404.
https://doi.org/10.1002/joc.7731 (versão v3.2.4, 1961-2025).

Processamento: Oliveira, F. C. (2026). Conjunto curto de clima decenal do Xavier BR-DWGD v3.2.4 para o modelo de
SOC do MapBiomas Solo. GAMBI-TEC/UTFPR. https://github.com/fcoliveira-utfpr/climate_for_soil (pasta `C4/`).

**Contato**

Prof. Dr. Fabrício Correia de Oliveira — GAMBI-TEC, UTFPR Campus Santa Helena, fcoliveira@utfpr.edu.br

**Licença**

Produto derivado distribuído sob CC BY 4.0; cite também os dados originais do BR-DWGD (Xavier et al., 2022).
