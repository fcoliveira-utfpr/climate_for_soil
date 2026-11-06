# Xavier BR-DWGD v3.2.4 — Zonas de vida de Holdridge, normal climatológica 1991-2020, Brasil, 0,1°

## Resumo

Zonas de vida de Holdridge do Brasil calculadas com a normal mensal de 1991 a 2020 (30 anos completos) de temperatura e chuva da grade diária do Xavier BR-DWGD v3.2.4, com a biblioteca agrometeorologiapy. Três bandas: a classificação com filtro de moda 3 × 3 (recomendada para mapas e modelos), a classificação direta e a distância até o pixel de onde veio a zona (bordas e ilhas preenchidas). Produto gerado pelo GAMBI-TEC (UTFPR, Campus Santa Helena). Entre as classificações climáticas testadas como covariável do modelo de carbono orgânico do solo (SOC, 0-30 cm) do MapBiomas Solo, foi a melhor: a única que ganhou do Köppen do IPEF nos três esquemas de validação e nos dois modelos.

## Especificações

- Fonte: Xavier BR-DWGD v3.2.4 (Brazilian Daily Weather Gridded Data), `projects/ee-alexandrexavier/assets/BR-DWGD`
- Variáveis originais: Tmax, Tmin e chuva diárias
- Período: 1991-01 a 2020-12 (normal climatológica padrão OMM)
- Resolução espacial: 0,1° (~11 km), a grade do BR-DWGD (469 × 413 pixels)
- Sistema de referência: EPSG:4326 (WGS 84)
- Extensão: 74,9° W a 28,0° W e 6,4° N a 34,9° S (a grade do Xavier estendida para cobrir todo o território, ilhas oceânicas incluídas; a mesma da coleção `xavier_conjunto_curto_decenal`)
- Tipo: uint8 (códigos de zona, 1 a 38) e uint16 (distância)
- Bandas: 3 (`holdridge`, `holdridge_sem_filtro`, `dist_preenchimento_km`)
- NoData: nenhum; **toda a grade tem zona**

## Bandas

| Banda | Conteúdo |
|---|---|
| `holdridge` | zona de vida com filtro de moda 3 × 3 (cada pixel recebe a zona mais frequente na janela, como o `focalMode` do GEE); remove pixels isolados nas fronteiras entre zonas |
| `holdridge_sem_filtro` | classificação direta de cada pixel |
| `dist_preenchimento_km` | distância até o pixel do Xavier de onde veio a zona (0 = dado original) |

## Legenda
(códigos de 1 a 38 da agrometeorologiapy; só as zonas presentes no Brasil; área na banda `holdridge`; médias da zona: biotemperatura, chuva anual e razão ETP/P)

| Código | Zona de vida | Nome original | Cor | Área no Brasil | Biotemp. (°C) | Chuva (mm/ano) | ETP/P |
|---|---|---|---|---|---|---|---|
| 22 | Floresta úmida temperada quente | Warm temperate moist forest | `#41ab5d` | 0,9% | 17,0 | 1.697 | 0,60 |
| 23 | Floresta muito úmida temperada quente | Warm temperate wet forest | `#238443` | < 0,1% | 15,8 | 1.943 | 0,48 |
| 27 | Estepe espinhosa subtropical | Subtropical thorn steppe | `#c6dbef` | 2,5% | 23,6 | 570 | 2,48 |
| 28 | Floresta seca subtropical | Subtropical dry forest | `#9ecae1` | 12,3% | 22,8 | 1.091 | 1,28 |
| 29 | Floresta úmida subtropical | Subtropical moist forest | `#6baed6` | 24,5% | 22,0 | 1.565 | 0,84 |
| 30 | Floresta muito úmida subtropical | Subtropical wet forest | `#3182bd` | < 0,1% | 21,7 | 2.719 | 0,47 |
| 35 | Floresta muito seca tropical | Tropical very dry forest | `#fdae6b` | 4,3% | 24,7 | 577 | 2,58 |
| 36 | Floresta seca tropical | Tropical dry forest | `#fd8d3c` | 7,3% | 25,0 | 1.116 | 1,37 |
| 37 | Floresta úmida tropical | Tropical moist forest | `#d94801` | 46,9% | 25,6 | 2.191 | 0,70 |
| 38 | Floresta muito úmida tropical | Tropical wet forest | `#8c2d04` | 1,3% | 26,6 | 3.417 | 0,46 |

## Processamento

1. Normal mensal 1991-2020 a partir do diário v3.2.4 (`baixar_xavier.py`): temperatura média do mês = média dos dias de (Tmax + Tmin)/2; chuva do mês = soma dos dias; média dos 30 anos. É a mesma normal do Köppen `koppen_xavier_1991_2020`.
2. Classificação com `classificacao_holdridge_grade` da agrometeorologiapy (`holdridge_1991_2020.py`):
    - biotemperatura: média das temperaturas mensais limitadas a 0-30 °C, com a correção de latitude t − 3·|lat|/100·(t − 24)² nos meses acima de 24 °C (Holdridge, 1967);
    - ETP de Holdridge = 58,93 × biotemperatura (mm/ano) e razão ETP/P;
    - zona de vida (38 zonas) pela faixa de biotemperatura (região latitudinal), pela chuva anual e pela razão ETP/P (província de umidade), nos hexágonos do diagrama de Holdridge.
3. Filtro de moda 3 × 3 para a banda `holdridge`.
4. Pixels sem dado do Xavier (bordas de fronteira e de litoral, ilhas oceânicas e a ponta oeste do Acre: cerca de 1,5% dos pixels que tocam o Brasil, onde caem 141 das 27.425 amostras de SOC) e o restante da grade estendida recebem a zona do pixel válido mais próximo; a distância fica na banda `dist_preenchimento_km`.
5. Envio ao GEE sem Cloud Storage nem upload manual: cada banda vai como `ee.Array` e a imagem é remontada no GEE pela linha e coluna de cada pixel.

## Controle de qualidade

- Asset × GeoTIFF local: 100% dos pixels iguais nas três bandas; nenhum pixel sem zona em toda a grade.
- A função foi conferida com o Holdridge do relatório técnico v1 (CHELSA, outro código) em 3.000 locais: 98,9% de concordância; as diferenças estão em fronteiras de zona (biotemperatura perto de 18 e 24 °C, ETP/P perto de 0,5, 1 e 2) e vêm do filtro de moda do mapa do v1.
- Banda `holdridge` × `holdridge_sem_filtro`: 97,6% dos pixels iguais.

## Comparação com outras bases

| Comparação | Concordância |
|---|---|
| Xavier v3.2.2 (temperatura até 07/2020), mesma metodologia | 98,0% |
| Holdridge do CHELSA V2.1 1991-2020 (~1 km, agregado a 0,1°) | 82,2% |

## Validação no modelo de SOC

Modelo de SOC do MapBiomas Solo, Coleção 3 (matriz de treino reproduzida, 27.425 linhas), com o modelo do mapa (smileRandomForest do GEE) e com o ranger; validação espacial (V2, blocos de 2°), temporal (V3, uma década fora) e espaço-temporal (V4); 3 repetições; MEC (Nash-Sutcliffe) nas amostras reais de 0-30 cm (relatório técnico v3, Holdridge estático do Xavier v3.2.2 com a mesma metodologia). As zonas entraram como variáveis indicadoras (0/1) hierárquicas: faixa térmica (região latitudinal) e zona de vida.

| MEC (ganho sobre o Köppen IPEF) | V2 | V3 | V4 |
|---|---|---|---|
| Modelo do mapa, Köppen IPEF | 0,179 | 0,124 | 0,111 |
| **Modelo do mapa, Holdridge Xavier** | **0,196 (+0,017)** | **0,138 (+0,014)** | **0,129 (+0,017)** |
| Ranger, Köppen IPEF | 0,240 | 0,172 | 0,152 |
| **Ranger, Holdridge Xavier** | **0,247 (+0,006)** | **0,184 (+0,012)** | **0,158 (+0,006)** |

Foi a melhor classificação: Köppen, Thornthwaite e zonas k10 do mesmo Xavier empataram ou perderam para o Köppen IPEF. Classificar por década não melhorou (Holdridge decenal ≈ estático). As variáveis contínuas do clima decenal (`xavier_conjunto_curto_decenal`) ganham mais (+0,012 a +0,031) e são a recomendação principal; o Holdridge é a opção quando o modelo ou a análise precisam de uma classe.

## Assets relacionados

- `projects/fcoliveira/assets/Climas2/xavier_normal_1991_2020`: a normal 1991-2020 de temperatura e chuva usada aqui (mesma grade e período)
- `projects/fcoliveira/assets/Climas2/koppen_xavier_1991_2020`: Köppen-Geiger 1991-2020 com a mesma normal
- `projects/mapbiomas-solos-workspace/assets/covariates/climate/XAVIER_1985-2026_CLIMA_DECENAL_11KM_2026`: clima decenal (média móvel de 10 anos, 1985-2026) do mesmo Xavier, recomendado como covariável contínua do modelo de SOC

## Limitações

- **O resultado depende da fonte dos dados.** Com o CHELSA (relatório v2), o Holdridge foi a pior classificação no modelo de SOC; a fronteira de 24 °C da correção de latitude e os limites de biotemperatura caem em lugares diferentes conforme a base. A vantagem vale para o Xavier.
- A resolução é a do Xavier (~11 km): zonas de altitude em serras estreitas tendem a ficar subestimadas.
- Nas bordas e nas ilhas oceânicas a zona vem do pixel de terra mais próximo do Xavier (Trindade fica a ~1.100 km da costa); use `dist_preenchimento_km` para identificar esses pixels.
- A ETP é a de Holdridge (função só da biotemperatura), não a de Penman-Monteith.
- O teste no modelo de SOC foi feito com o Xavier v3.2.2 e nas partições do v3; não foi repetido nas partições novas do v6.

## Como usar

A banda `holdridge` tem códigos não contíguos; para usar a paleta, renumere as zonas presentes de 1 a n com `remap`. O asset cobre o retângulo da grade inteiro; recorte pelo limite do Brasil para mapas e áreas. No modelo, use as zonas como variáveis indicadoras (uma coluna 0/1 por zona) ou como fator.

## Google Earth Engine (Code Editor, JavaScript)

```javascript
// ===== Xavier v3.2.4 | Zonas de vida de Holdridge | Normal 1991-2020 | Brasil 0,1° =====
var holdridge = ee.Image('projects/mapbiomas-solos-workspace/assets/covariates/climate/XAVIER_1991-2020_HOLDRIDGE_11KM_2026').select('holdridge');
var ids = [22, 23, 27, 28, 29, 30, 35, 36, 37, 38];
var zonas = ['Floresta úmida temperada quente', 'Floresta muito úmida temperada quente', 'Estepe espinhosa subtropical', 'Floresta seca subtropical', 'Floresta úmida subtropical', 'Floresta muito úmida subtropical', 'Floresta muito seca tropical', 'Floresta seca tropical', 'Floresta úmida tropical', 'Floresta muito úmida tropical'];
var cores = ['#41ab5d', '#238443', '#c6dbef', '#9ecae1', '#6baed6', '#3182bd', '#fdae6b', '#fd8d3c', '#d94801', '#8c2d04'];

// Renumera as zonas presentes (1..n) para usar a paleta na ordem
var vis = holdridge.remap(ids, ee.List.sequence(1, ids.length));
var brasil = ee.FeatureCollection('FAO/GAUL/2015/level0').filter(ee.Filter.eq('ADM0_NAME', 'Brazil'));
Map.setCenter(-52, -14, 4);
Map.addLayer(vis.clip(brasil), {min: 1, max: ids.length, palette: cores}, 'Holdridge Xavier 1991-2020');
Map.addLayer(ee.Image().paint(brasil, 0, 1), {palette: ['000000']}, 'Limite do Brasil');

// Legenda
var legenda = ui.Panel({style: {position: 'bottom-left', padding: '8px 15px'}});
legenda.add(ui.Label('Zonas de vida de Holdridge 1991-2020 (Xavier)', {fontWeight: 'bold', fontSize: '13px'}));
for (var i = 0; i < ids.length; i++) {
  legenda.add(ui.Panel([
    ui.Label('', {backgroundColor: cores[i], padding: '8px', margin: '0 6px 4px 0', border: '1px solid #999'}),
    ui.Label(ids[i] + ' ' + zonas[i], {margin: '0 0 4px 0', fontSize: '12px'})
  ], ui.Panel.Layout.Flow('horizontal')));
}
Map.add(legenda);

// Zona no ponto clicado
Map.style().set('cursor', 'crosshair');
Map.onClick(function (c) {
  holdridge.reduceRegion(ee.Reducer.first(), ee.Geometry.Point([c.lon, c.lat]), 11132).evaluate(function (v) {
    var k = v && v.holdridge;
    print('Lon ' + c.lon.toFixed(3) + ' | Lat ' + c.lat.toFixed(3) + ': ' +
          (k ? k + ' ' + zonas[ids.indexOf(k)] : 'sem dado'));
  });
});

// Área de cada zona no Brasil (km²)
var area = ee.Image.pixelArea().divide(1e6).addBands(holdridge).reduceRegion({
  reducer: ee.Reducer.sum().group(1, 'zona'), geometry: brasil.geometry(), scale: 11132, maxPixels: 1e9});
print('Área por zona (km²):', area);

// Zonas como variáveis indicadoras (0/1) para o modelo: uma banda por zona
var indicadoras = ee.Image.cat(ids.map(function (k) {
  return holdridge.eq(k).unmask(0).rename('holdridge_' + k);
}));
print('Bandas indicadoras:', indicadoras.bandNames());
// var amostrasComZona = indicadoras.sampleRegions({collection: amostras, scale: 30, geometries: true});
```

## Google Colab (Python)

```python
# ===== Xavier v3.2.4 | Zonas de vida de Holdridge | Normal 1991-2020 | Brasil 0,1° =====
!pip install -q geemap

import ee
import geemap
import pandas as pd

ee.Authenticate()
ee.Initialize(project='SEU_PROJETO')

holdridge = ee.Image('projects/mapbiomas-solos-workspace/assets/covariates/climate/XAVIER_1991-2020_HOLDRIDGE_11KM_2026').select('holdridge')
ids = [22, 23, 27, 28, 29, 30, 35, 36, 37, 38]
zonas = ['Floresta úmida temperada quente', 'Floresta muito úmida temperada quente', 'Estepe espinhosa subtropical', 'Floresta seca subtropical', 'Floresta úmida subtropical', 'Floresta muito úmida subtropical', 'Floresta muito seca tropical', 'Floresta seca tropical', 'Floresta úmida tropical', 'Floresta muito úmida tropical']
cores = ['#41ab5d', '#238443', '#c6dbef', '#9ecae1', '#6baed6', '#3182bd', '#fdae6b', '#fd8d3c', '#d94801', '#8c2d04']

brasil = ee.FeatureCollection('FAO/GAUL/2015/level0').filter(ee.Filter.eq('ADM0_NAME', 'Brazil'))

# ---------- Mapa interativo com legenda ----------
vis = holdridge.remap(ids, list(range(1, len(ids) + 1))).clip(brasil)
m = geemap.Map(center=[-14, -52], zoom=4)
m.add_layer(vis, {'min': 1, 'max': len(ids), 'palette': cores}, 'Holdridge Xavier 1991-2020')
m.add_legend(title='Zonas de vida de Holdridge 1991-2020',
             legend_dict={f'{k} {z}': c.lstrip('#') for k, z, c in zip(ids, zonas, cores)})
m
```

```python
# ---------- Área de cada zona no Brasil ----------
r = ee.Image.pixelArea().divide(1e6).addBands(holdridge).reduceRegion(
    reducer=ee.Reducer.sum().group(1, 'zona'), geometry=brasil.geometry(), scale=11132, maxPixels=1e9).getInfo()
area = pd.DataFrame(r['groups']).rename(columns={'sum': 'km2'})
area['nome'] = area['zona'].map(dict(zip(ids, zonas)))
area['%'] = (100 * area.km2 / area.km2.sum()).round(1)
print(area.sort_values('km2', ascending=False).to_string(index=False))
```

## Citação

Dados originais: Xavier, A. C.; Scanlon, B. R.; King, C. W.; Alves, A. I. (2022). New improved Brazilian daily weather gridded data (1961-2020). International Journal of Climatology, 42(16), 8390-8404. https://doi.org/10.1002/joc.7731 (versão v3.2.4, 1961-2025).

Método: Holdridge, L. R. (1967). Life zone ecology. San José: Tropical Science Center.

Processamento: Oliveira, F. C. (2026). Zonas de vida de Holdridge do Brasil 1991-2020 a partir do Xavier BR-DWGD v3.2.4. GAMBI-TEC/UTFPR. https://github.com/fcoliveira-utfpr/climate_for_soil (`C4/codigo/holdridge_1991_2020.py`).

## Contato

Prof. Dr. Fabrício Correia de Oliveira — GAMBI-TEC, UTFPR Campus Santa Helena, fcoliveira@utfpr.edu.br

## Licença

Produto derivado distribuído sob CC BY 4.0; cite também os dados originais do BR-DWGD (Xavier et al., 2022).
