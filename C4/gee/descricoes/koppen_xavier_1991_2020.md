# Xavier BR-DWGD v3.2.4 — Köppen-Geiger, normal climatológica 1991-2020, Brasil, 0,1°

## Resumo

Classificação climática de Köppen-Geiger do Brasil calculada com a normal mensal de 1991 a 2020 (30 anos completos) de temperatura e chuva da grade diária do Xavier BR-DWGD v3.2.4, com a biblioteca agrometeorologiapy. Duas bandas: a classificação com filtro de moda 3 × 3 (recomendada para mapas) e a classificação direta. Produto gerado pelo GAMBI-TEC (UTFPR, Campus Santa Helena) como base climática atualizada (normal padrão da OMM) para estudos de solo e de clima, em alternativa ao Köppen de Alvares et al. (2013), feito com a normal 1950-1990.

## Especificações

- Fonte: Xavier BR-DWGD v3.2.4 (Brazilian Daily Weather Gridded Data), `projects/ee-alexandrexavier/assets/BR-DWGD`
- Variáveis originais: Tmax, Tmin e chuva diárias
- Período: 1991-01 a 2020-12 (normal climatológica padrão OMM)
- Resolução espacial: 0,1° (~11 km), grade nativa do BR-DWGD (391 × 393 pixels)
- Sistema de referência: EPSG:4326 (WGS 84)
- Extensão: 73,9° W a 34,8° W e 5,4° N a 33,9° S
- Tipo: uint8 (códigos de classe)
- Bandas: 2 (`koppen`, `koppen_sem_filtro`)
- NoData: mascarado (fora da área com dado do Xavier)

## Bandas

| Banda | Conteúdo |
|---|---|
| `koppen` | classe de Köppen-Geiger com filtro de moda 3 × 3 (cada pixel recebe a classe mais frequente na janela, como o `focalMode` do GEE); remove pixels isolados nas fronteiras entre classes |
| `koppen_sem_filtro` | classificação direta de cada pixel |

## Legenda
(códigos de 1 a 31 da agrometeorologiapy; só as classes presentes no Brasil; área na banda `koppen`)

| Código | Classe | Significado | Cor | Área no Brasil |
|---|---|---|---|---|
| 1 | Af | tropical úmido, sem estação seca | `#0000FF` | 18.9% |
| 2 | Am | tropical de monção | `#0078FF` | 17.8% |
| 3 | As | tropical com verão seco | `#46A0FF` | 1.6% |
| 4 | Aw | tropical com inverno seco (savana) | `#96C8FF` | 46.3% |
| 5 | BSh | semiárido quente | `#F5A623` | 7.4% |
| 7 | BWh | desértico quente | `#FF0000` | 0.1% |
| 9 | Cfa | subtropical úmido, verão quente | `#C8FF50` | 5.8% |
| 10 | Cfb | temperado úmido, verão ameno | `#64FF50` | 0.9% |
| 15 | Cwa | subtropical com inverno seco, verão quente | `#C8FFC8` | 1.1% |
| 16 | Cwb | subtropical de altitude, inverno seco, verão ameno | `#96FF96` | 0.1% |

## Processamento

1. Normal mensal 1991-2020 a partir do diário v3.2.4 (`baixar_xavier.py`): temperatura média do mês = média dos dias de (Tmax + Tmin)/2; chuva do mês = soma dos dias; média dos 30 anos. As escalas de cada imagem (`BAND_*_MULT`, `BAND_*_ADD`) são lidas das propriedades.
2. Classificação com `classificacao_koppen_grade` da agrometeorologiapy (`koppen_1991_2020.py`), pelos critérios de Alvares et al. (2013), com a sazonalidade f/s/w dos grupos C e D de Kottek et al. (2006):
    - grupo A: mês mais frio ≥ 18 °C; Af com mês mais seco ≥ 60 mm; Am quando o mês mais seco ≥ 100 − chuva anual/25; senão As (seca no verão) ou Aw (seca no inverno);
    - grupo B: chuva anual < 10 × (2T + 28, 2T + 14 ou 2T, conforme ≥ 70% da chuva no verão, distribuída ou ≥ 70% no inverno); BW abaixo da metade do limiar; h/k pela temperatura anual de 18 °C;
    - grupo C: mês mais frio entre −3 e 18 °C; letras a/b/c pelo mês mais quente (22 °C) e pelo número de meses acima de 10 °C; verão = outubro a março no hemisfério sul.
3. Filtro de moda 3 × 3 para a banda `koppen`.
4. Envio ao GEE sem Cloud Storage nem upload manual (`subir_koppen_gee.py`): cada banda vai como `ee.Array` e a imagem é remontada no GEE pela linha e coluna de cada pixel.

## Controle de qualidade

- Asset × GeoTIFF local: 100% dos pixels iguais nas duas bandas.
- A função de classificação foi validada com 100% de concordância contra o Köppen do CHELSA calculado com outro código (relatório técnico v1).
- Banda `koppen` × `koppen_sem_filtro`: 98,5% dos pixels iguais.

## Comparação com outras bases

| Comparação | Concordância |
|---|---|
| Xavier v3.2.2 (temperatura até 07/2020), mesma metodologia | 97,6% |
| Köppen do CHELSA V2.1 1991-2020 (~1 km, agregado a 0,1°) | 87,8% |
| Moro et al. (2026), Köppen 1991-2020 do Brasil (doi:10.17632/yttctnzrfn.1) | 97,4% |

A menor concordância com o CHELSA reflete a diferença entre as bases (resolução, estações e método de interpolação). Com o Moro et al., há uma diferença de método: lá o As é testado dentro do ramo do Am.

## Assets relacionados

- `projects/fcoliveira/assets/Climas2/xavier_normal_1991_2020`: a normal 1991-2020 de temperatura e chuva usada aqui (mesma grade e período)
- `projects/fcoliveira/assets/Climas2/xavier_conjunto_curto_decenal`: clima decenal (média móvel de 10 anos, 1985-2026) do mesmo Xavier, recomendado como covariável do modelo de SOC

## Limitações

- A resolução é a do Xavier (~11 km): classes de altitude (Cwb, Cfb) em serras estreitas tendem a ficar subestimadas.
- Pixels sem dado do Xavier (bordas de fronteira e de litoral, ilhas oceânicas e a ponta oeste do Acre, cerca de 1,5% dos pixels que tocam o Brasil) ficam sem classe.
- O Xavier tem poucas estações na Amazônia e no Centro-Oeste; ali as fronteiras Af/Am/Aw dependem da interpolação.
- A normal 1991-2020 é mais quente que a usada por Alvares et al. (2013): as fronteiras térmicas (A/C, a/b) se deslocam em relação a esse mapa.
- Como covariável de modelos de SOC, uma classe de 30 anos não acompanha a mudança do clima; na validação do projeto, o clima contínuo decenal foi melhor que as classes.

## Como usar

A banda `koppen` tem códigos não contíguos (1, 2, 3, 4, 5, 7, 9, ...); para usar a paleta, renumere as classes presentes de 1 a n com `remap`.

## Google Earth Engine (Code Editor, JavaScript)

```javascript
// ===== Xavier v3.2.4 | Köppen-Geiger | Normal 1991-2020 | Brasil 0,1° =====
var koppen = ee.Image('projects/fcoliveira/assets/Climas2/koppen_xavier_1991_2020').select('koppen');
var ids = [1, 2, 3, 4, 5, 7, 9, 10, 15, 16];
var classes = ['Af', 'Am', 'As', 'Aw', 'BSh', 'BWh', 'Cfa', 'Cfb', 'Cwa', 'Cwb'];
var cores = ['#0000FF', '#0078FF', '#46A0FF', '#96C8FF', '#F5A623', '#FF0000', '#C8FF50', '#64FF50', '#C8FFC8', '#96FF96'];

// Renumera as classes presentes (1..n) para usar a paleta na ordem
var vis = koppen.remap(ids, ee.List.sequence(1, ids.length));
var brasil = ee.FeatureCollection('FAO/GAUL/2015/level0').filter(ee.Filter.eq('ADM0_NAME', 'Brazil'));
Map.setCenter(-52, -14, 4);
Map.addLayer(vis, {min: 1, max: ids.length, palette: cores}, 'Köppen Xavier 1991-2020');
Map.addLayer(ee.Image().paint(brasil, 0, 1), {palette: ['000000']}, 'Limite do Brasil');

// Legenda
var legenda = ui.Panel({style: {position: 'bottom-left', padding: '8px 15px'}});
legenda.add(ui.Label('Köppen-Geiger 1991-2020 (Xavier)', {fontWeight: 'bold', fontSize: '13px'}));
for (var i = 0; i < ids.length; i++) {
  legenda.add(ui.Panel([
    ui.Label('', {backgroundColor: cores[i], padding: '8px', margin: '0 6px 4px 0'}),
    ui.Label(classes[i], {margin: '0 0 4px 0'})
  ], ui.Panel.Layout.Flow('horizontal')));
}
Map.add(legenda);

// Classe num ponto (Santa Helena/PR)
var ponto = ee.Geometry.Point([-54.33, -24.86]);
var cod = koppen.reduceRegion(ee.Reducer.first(), ponto, 11132).get('koppen');
print('Classe em Santa Helena/PR:', ee.List(classes).get(ee.List(ids).indexOf(cod)));

// Área de cada classe (km²)
var area = ee.Image.pixelArea().divide(1e6).addBands(koppen).reduceRegion({
  reducer: ee.Reducer.sum().group(1, 'classe'), geometry: koppen.geometry(), scale: 11132, maxPixels: 1e9});
print('Área por classe (km²):', area);

// Classe de cada amostra (por exemplo, para estratificar)
// var amostras = ee.FeatureCollection('...');
// var comClasse = koppen.sampleRegions({collection: amostras, scale: 30, geometries: true});
```

## Google Colab (Python)

```python
# ===== Xavier v3.2.4 | Köppen-Geiger | Normal 1991-2020 | Brasil 0,1° =====
!pip install -q geemap

import ee
import geemap
import pandas as pd

ee.Authenticate()
ee.Initialize(project='SEU_PROJETO')

koppen = ee.Image('projects/fcoliveira/assets/Climas2/koppen_xavier_1991_2020').select('koppen')
ids = [1, 2, 3, 4, 5, 7, 9, 10, 15, 16]
classes = ['Af', 'Am', 'As', 'Aw', 'BSh', 'BWh', 'Cfa', 'Cfb', 'Cwa', 'Cwb']
cores = ['#0000FF', '#0078FF', '#46A0FF', '#96C8FF', '#F5A623', '#FF0000', '#C8FF50', '#64FF50', '#C8FFC8', '#96FF96']

# ---------- Mapa interativo com legenda ----------
vis = koppen.remap(ids, list(range(1, len(ids) + 1)))
m = geemap.Map(center=[-14, -52], zoom=4)
m.add_layer(vis, {'min': 1, 'max': len(ids), 'palette': cores}, 'Köppen Xavier 1991-2020')
m.add_legend(title='Köppen-Geiger 1991-2020', legend_dict=dict(zip(classes, [c.lstrip('#') for c in cores])))
m
```

```python
# ---------- Área de cada classe ----------
r = ee.Image.pixelArea().divide(1e6).addBands(koppen).reduceRegion(
    reducer=ee.Reducer.sum().group(1, 'classe'), geometry=koppen.geometry(), scale=11132, maxPixels=1e9).getInfo()
area = pd.DataFrame(r['groups']).rename(columns={'sum': 'km2'})
area['classe'] = area['classe'].map(dict(zip(ids, classes)))
area['%'] = (100 * area.km2 / area.km2.sum()).round(1)
print(area.sort_values('km2', ascending=False).to_string(index=False))
```

## Citação

Dados originais: Xavier, A. C.; Scanlon, B. R.; King, C. W.; Alves, A. I. (2022). New improved Brazilian daily weather gridded data (1961-2020). International Journal of Climatology, 42(16), 8390-8404. https://doi.org/10.1002/joc.7731 (versão v3.2.4, 1961-2025).

Método: Alvares, C. A.; Stape, J. L.; Sentelhas, P. C.; Gonçalves, J. L. M.; Sparovek, G. (2013). Köppen's climate classification map for Brazil. Meteorologische Zeitschrift, 22(6), 711-728. https://doi.org/10.1127/0941-2948/2013/0507 Kottek, M.; Grieser, J.; Beck, C.; Rudolf, B.; Rubel, F. (2006). World map of the Köppen-Geiger climate classification updated. Meteorologische Zeitschrift, 15(3), 259-263. https://doi.org/10.1127/0941-2948/2006/0130

Processamento: Oliveira, F. C. (2026). Köppen-Geiger do Brasil 1991-2020 a partir do Xavier BR-DWGD v3.2.4. GAMBI-TEC/UTFPR. https://github.com/fcoliveira-utfpr/climate_for_soil (`C4/codigo/koppen_1991_2020.py`).

## Contato

Prof. Dr. Fabrício Correia de Oliveira — GAMBI-TEC, UTFPR Campus Santa Helena, fcoliveira@utfpr.edu.br

## Licença

Produto derivado distribuído sob CC BY 4.0; cite também os dados originais do BR-DWGD (Xavier et al., 2022).
