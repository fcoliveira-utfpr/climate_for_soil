"""Sobe o Köppen do Xavier v3.2.4 (normal 1991-2020, koppen_1991_2020.py) para o GEE como asset, sem Cloud
Storage: o raster é pequeno (391 x 393), então cada banda vai como ee.Array e a imagem é remontada no GEE
indexando o array pela linha e coluna de cada pixel da grade do Xavier; depois é exportada como asset com a
descrição e os metadados nas propriedades. Ao final, confere pixel a pixel o asset contra o GeoTIFF.

A normal 1991-2020 de temperatura e chuva (subprodutos do Köppen; 26 bandas em ponto flutuante, grande demais
para ir como array) é calculada no próprio GEE, a partir do mesmo asset diário v3.2.4 e com o mesmo método do
download (média mensal de (Tmax + Tmin)/2 e soma mensal da chuva, média dos 30 anos), e conferida contra
xavier_normal_1991_2020.tif.

Uso: python subir_koppen_gee.py exportar          # Köppen
     python subir_koppen_gee.py conferir
     python subir_koppen_gee.py descricao         # atualiza a descrição do Köppen já publicado
     python subir_koppen_gee.py normal            # exporta a normal de temperatura e chuva
     python subir_koppen_gee.py conferir_normal
     python subir_koppen_gee.py descricao_normal  # atualiza a descrição da normal já publicada
"""
import sys
from pathlib import Path

import ee
import numpy as np
import pandas as pd
import rasterio

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / 'corelacao' / 'codigo'))
from gee_utils import conectar  # noqa: E402
from baixar_xavier import diario  # noqa: E402

PASTA = RAIZ / 'C4' / 'resultados' / 'koppen_xavier_1991_2020'
TIF = PASTA / 'koppen_xavier_1991_2020.tif'
ASSET = 'projects/fcoliveira/assets/Climas2/koppen_xavier_1991_2020'
ASSET_NORMAL = 'projects/fcoliveira/assets/Climas2/xavier_normal_1991_2020'
TIF_NORMAL = PASTA / 'xavier_normal_1991_2020.tif'
X0, DX, Y0, DY = -73.89999847412109, 0.1, 5.399999902564652, -0.09999999586416751
H, W = 393, 391
GRADE = {'dimensions': {'width': W, 'height': H},
         'affineTransform': {'scaleX': DX, 'shearX': 0, 'translateX': X0, 'shearY': 0, 'scaleY': DY, 'translateY': Y0},
         'crsCode': 'EPSG:4326'}


SIGNIFICADO = {
    'Af': 'tropical úmido, sem estação seca', 'Am': 'tropical de monção', 'As': 'tropical com verão seco',
    'Aw': 'tropical com inverno seco (savana)', 'BSh': 'semiárido quente', 'BSk': 'semiárido frio',
    'BWh': 'desértico quente', 'BWk': 'desértico frio', 'Cfa': 'subtropical úmido, verão quente',
    'Cfb': 'temperado úmido, verão ameno', 'Csa': 'subtropical com verão seco e quente',
    'Csb': 'subtropical com verão seco e ameno', 'Cwa': 'subtropical com inverno seco, verão quente',
    'Cwb': 'subtropical de altitude, inverno seco, verão ameno'}


def descricao(leg):
    tabela = '\n'.join(f'| {r.id} | {r.classe} | {SIGNIFICADO.get(r.classe, "")} | `{r.cor}` | {r.area_pct:.1f}% |'
                        for r in leg.itertuples())
    ids = ', '.join(str(i) for i in leg.id)
    cores = ', '.join(f"'{c}'" for c in leg.cor)
    classes = ', '.join(f"'{c}'" for c in leg.classe)
    return f"""**Xavier BR-DWGD v3.2.4 — Köppen-Geiger, normal climatológica 1991-2020, Brasil, 0,1°**

**Resumo**

Classificação climática de Köppen-Geiger do Brasil calculada com a normal mensal de 1991 a 2020 (30 anos
completos) de temperatura e chuva da grade diária do Xavier BR-DWGD v3.2.4, com a biblioteca agrometeorologiapy.
Duas bandas: a classificação com filtro de moda 3 × 3 (recomendada para mapas) e a classificação direta. Produto
gerado pelo GAMBI-TEC (UTFPR, Campus Santa Helena) como base climática atualizada (normal padrão da OMM) para
estudos de solo e de clima, em alternativa ao Köppen de Alvares et al. (2013), feito com a normal 1950-1990.

**Especificações**

- Fonte: Xavier BR-DWGD v3.2.4 (Brazilian Daily Weather Gridded Data), `projects/ee-alexandrexavier/assets/BR-DWGD`
- Variáveis originais: Tmax, Tmin e chuva diárias
- Período: 1991-01 a 2020-12 (normal climatológica padrão OMM)
- Resolução espacial: 0,1° (~11 km), grade nativa do BR-DWGD (391 × 393 pixels)
- Sistema de referência: EPSG:4326 (WGS 84)
- Extensão: 73,9° W a 34,8° W e 5,4° N a 33,9° S
- Tipo: uint8 (códigos de classe)
- Bandas: 2 (`koppen`, `koppen_sem_filtro`)
- NoData: mascarado (fora da área com dado do Xavier)

**Bandas**

| Banda | Conteúdo |
|---|---|
| `koppen` | classe de Köppen-Geiger com filtro de moda 3 × 3 (cada pixel recebe a classe mais frequente na janela, como o `focalMode` do GEE); remove pixels isolados nas fronteiras entre classes |
| `koppen_sem_filtro` | classificação direta de cada pixel |

**Legenda** (códigos de 1 a 31 da agrometeorologiapy; só as classes presentes no Brasil; área na banda `koppen`)

| Código | Classe | Significado | Cor | Área no Brasil |
|---|---|---|---|---|
{tabela}

**Processamento**

1. Normal mensal 1991-2020 a partir do diário v3.2.4 (`baixar_xavier.py`): temperatura média do mês = média dos
   dias de (Tmax + Tmin)/2; chuva do mês = soma dos dias; média dos 30 anos. As escalas de cada imagem
   (`BAND_*_MULT`, `BAND_*_ADD`) são lidas das propriedades.
2. Classificação com `classificacao_koppen_grade` da agrometeorologiapy (`koppen_1991_2020.py`), pelos critérios
   de Alvares et al. (2013), com a sazonalidade f/s/w dos grupos C e D de Kottek et al. (2006):
   - grupo A: mês mais frio ≥ 18 °C; Af com mês mais seco ≥ 60 mm; Am quando o mês mais seco ≥ 100 − chuva
     anual/25; senão As (seca no verão) ou Aw (seca no inverno);
   - grupo B: chuva anual < 10 × (2T + 28, 2T + 14 ou 2T, conforme ≥ 70% da chuva no verão, distribuída ou
     ≥ 70% no inverno); BW abaixo da metade do limiar; h/k pela temperatura anual de 18 °C;
   - grupo C: mês mais frio entre −3 e 18 °C; letras a/b/c pelo mês mais quente (22 °C) e pelo número de meses
     acima de 10 °C; verão = outubro a março no hemisfério sul.
3. Filtro de moda 3 × 3 para a banda `koppen`.
4. Envio ao GEE sem Cloud Storage nem upload manual (`subir_koppen_gee.py`): cada banda vai como `ee.Array` e a
   imagem é remontada no GEE pela linha e coluna de cada pixel.

**Controle de qualidade**

- Asset × GeoTIFF local: 100% dos pixels iguais nas duas bandas.
- A função de classificação foi validada com 100% de concordância contra o Köppen do CHELSA calculado com outro
  código (relatório técnico v1).
- Banda `koppen` × `koppen_sem_filtro`: 98,5% dos pixels iguais.

**Comparação com outras bases**

| Comparação | Concordância |
|---|---|
| Xavier v3.2.2 (temperatura até 07/2020), mesma metodologia | 97,6% |
| Köppen do CHELSA V2.1 1991-2020 (~1 km, agregado a 0,1°) | 87,8% |
| Moro et al. (2026), Köppen 1991-2020 do Brasil (doi:10.17632/yttctnzrfn.1) | 97,4% |

A menor concordância com o CHELSA reflete a diferença entre as bases (resolução, estações e método de
interpolação). Com o Moro et al., há uma diferença de método: lá o As é testado dentro do ramo do Am.

**Assets relacionados**

- `{ASSET_NORMAL}`: a normal 1991-2020 de temperatura e chuva usada aqui (mesma grade e período)
- `projects/fcoliveira/assets/Climas2/xavier_conjunto_curto_decenal`: clima decenal (média móvel de 10 anos,
  1985-2026) do mesmo Xavier, recomendado como covariável do modelo de SOC

**Limitações**

- A resolução é a do Xavier (~11 km): classes de altitude (Cwb, Cfb) em serras estreitas tendem a ficar subestimadas.
- Pixels sem dado do Xavier (bordas de fronteira e de litoral, ilhas oceânicas e a ponta oeste do Acre, cerca de
  1,5% dos pixels que tocam o Brasil) ficam sem classe.
- O Xavier tem poucas estações na Amazônia e no Centro-Oeste; ali as fronteiras Af/Am/Aw dependem da interpolação.
- A normal 1991-2020 é mais quente que a usada por Alvares et al. (2013): as fronteiras térmicas (A/C, a/b) se
  deslocam em relação a esse mapa.
- Como covariável de modelos de SOC, uma classe de 30 anos não acompanha a mudança do clima; na validação do
  projeto, o clima contínuo decenal foi melhor que as classes.

**Como usar**

A banda `koppen` tem códigos não contíguos (1, 2, 3, 4, 5, 7, 9, ...); para usar a paleta, renumere as classes
presentes de 1 a n com `remap`.

**Google Earth Engine (Code Editor, JavaScript)**

```javascript
// ===== Xavier v3.2.4 | Köppen-Geiger | Normal 1991-2020 | Brasil 0,1° =====
var koppen = ee.Image('{ASSET}').select('koppen');
var ids = [{ids}];
var classes = [{classes}];
var cores = [{cores}];

// Renumera as classes presentes (1..n) para usar a paleta na ordem
var vis = koppen.remap(ids, ee.List.sequence(1, ids.length));
var brasil = ee.FeatureCollection('FAO/GAUL/2015/level0').filter(ee.Filter.eq('ADM0_NAME', 'Brazil'));
Map.setCenter(-52, -14, 4);
Map.addLayer(vis, {{min: 1, max: ids.length, palette: cores}}, 'Köppen Xavier 1991-2020');
Map.addLayer(ee.Image().paint(brasil, 0, 1), {{palette: ['000000']}}, 'Limite do Brasil');

// Legenda
var legenda = ui.Panel({{style: {{position: 'bottom-left', padding: '8px 15px'}}}});
legenda.add(ui.Label('Köppen-Geiger 1991-2020 (Xavier)', {{fontWeight: 'bold', fontSize: '13px'}}));
for (var i = 0; i < ids.length; i++) {{
  legenda.add(ui.Panel([
    ui.Label('', {{backgroundColor: cores[i], padding: '8px', margin: '0 6px 4px 0'}}),
    ui.Label(classes[i], {{margin: '0 0 4px 0'}})
  ], ui.Panel.Layout.Flow('horizontal')));
}}
Map.add(legenda);

// Classe num ponto (Santa Helena/PR)
var ponto = ee.Geometry.Point([-54.33, -24.86]);
var cod = koppen.reduceRegion(ee.Reducer.first(), ponto, 11132).get('koppen');
print('Classe em Santa Helena/PR:', ee.List(classes).get(ee.List(ids).indexOf(cod)));

// Área de cada classe (km²)
var area = ee.Image.pixelArea().divide(1e6).addBands(koppen).reduceRegion({{
  reducer: ee.Reducer.sum().group(1, 'classe'), geometry: koppen.geometry(), scale: 11132, maxPixels: 1e9}});
print('Área por classe (km²):', area);

// Classe de cada amostra (por exemplo, para estratificar)
// var amostras = ee.FeatureCollection('...');
// var comClasse = koppen.sampleRegions({{collection: amostras, scale: 30, geometries: true}});
```

**Google Colab (Python)**

```python
# ===== Xavier v3.2.4 | Köppen-Geiger | Normal 1991-2020 | Brasil 0,1° =====
!pip install -q geemap

import ee
import geemap
import pandas as pd

ee.Authenticate()
ee.Initialize(project='SEU_PROJETO')

koppen = ee.Image('{ASSET}').select('koppen')
ids = [{ids}]
classes = [{classes}]
cores = [{cores}]

# ---------- Mapa interativo com legenda ----------
vis = koppen.remap(ids, list(range(1, len(ids) + 1)))
m = geemap.Map(center=[-14, -52], zoom=4)
m.add_layer(vis, {{'min': 1, 'max': len(ids), 'palette': cores}}, 'Köppen Xavier 1991-2020')
m.add_legend(title='Köppen-Geiger 1991-2020', legend_dict=dict(zip(classes, [c.lstrip('#') for c in cores])))
m
```

```python
# ---------- Área de cada classe ----------
r = ee.Image.pixelArea().divide(1e6).addBands(koppen).reduceRegion(
    reducer=ee.Reducer.sum().group(1, 'classe'), geometry=koppen.geometry(), scale=11132, maxPixels=1e9).getInfo()
area = pd.DataFrame(r['groups']).rename(columns={{'sum': 'km2'}})
area['classe'] = area['classe'].map(dict(zip(ids, classes)))
area['%'] = (100 * area.km2 / area.km2.sum()).round(1)
print(area.sort_values('km2', ascending=False).to_string(index=False))
```

**Citação**

Dados originais: Xavier, A. C.; Scanlon, B. R.; King, C. W.; Alves, A. I. (2022). New improved Brazilian daily
weather gridded data (1961-2020). International Journal of Climatology, 42(16), 8390-8404.
https://doi.org/10.1002/joc.7731 (versão v3.2.4, 1961-2025).

Método: Alvares, C. A.; Stape, J. L.; Sentelhas, P. C.; Gonçalves, J. L. M.; Sparovek, G. (2013). Köppen's climate
classification map for Brazil. Meteorologische Zeitschrift, 22(6), 711-728. https://doi.org/10.1127/0941-2948/2013/0507
Kottek, M.; Grieser, J.; Beck, C.; Rudolf, B.; Rubel, F. (2006). World map of the Köppen-Geiger climate
classification updated. Meteorologische Zeitschrift, 15(3), 259-263. https://doi.org/10.1127/0941-2948/2006/0130

Processamento: Oliveira, F. C. (2026). Köppen-Geiger do Brasil 1991-2020 a partir do Xavier BR-DWGD v3.2.4.
GAMBI-TEC/UTFPR. https://github.com/fcoliveira-utfpr/climate_for_soil (`C4/codigo/koppen_1991_2020.py`).

**Contato**

Prof. Dr. Fabrício Correia de Oliveira — GAMBI-TEC, UTFPR Campus Santa Helena, fcoliveira@utfpr.edu.br

**Licença**

Produto derivado distribuído sob CC BY 4.0; cite também os dados originais do BR-DWGD (Xavier et al., 2022)."""


def imagem():
    with rasterio.open(TIF) as r:
        bandas = r.read()
    lonlat = ee.Image.pixelLonLat()
    col = lonlat.select('longitude').subtract(X0).divide(DX).floor().clamp(0, W - 1).toInt()
    lin = lonlat.select('latitude').subtract(Y0).divide(DY).floor().clamp(0, H - 1).toInt()
    pos = ee.Image.cat(lin, col)
    out = []
    for b, nome in zip(bandas, ('koppen', 'koppen_sem_filtro')):
        arr = ee.Image(ee.Array(b.astype(int).tolist()))
        out.append(arr.arrayGet(pos).toUint8().rename(nome))
    img = ee.Image.cat(out)
    return img.updateMask(img.select('koppen').gt(0))


def exportar():
    leg = pd.read_csv(PASTA / 'legenda.csv')
    props = {'description': descricao(leg), 'fonte': 'Xavier et al. (2022) BR-DWGD v3.2.4',
             'periodo': '1991-2020', 'metodo': 'agrometeorologiapy classificacao_koppen_grade; banda koppen com moda 3x3',
             'classes': '; '.join(f'{r.id}={r.classe}' for r in leg.itertuples()),
             'paleta': ','.join(leg.cor), 'autor': 'Fabricio Correia de Oliveira (UTFPR)',
             'codigo': 'github.com/fcoliveira-utfpr/climate_for_soil C4/codigo/koppen_1991_2020.py',
             'system:time_start': ee.Date('1991-01-01').millis(), 'system:time_end': ee.Date('2021-01-01').millis()}
    img = imagem().set(props)
    regiao = ee.Geometry.Rectangle([X0, Y0 + H * DY, X0 + W * DX, Y0], 'EPSG:4326', False)
    tarefa = ee.batch.Export.image.toAsset(image=img, description='koppen_xavier_1991_2020', assetId=ASSET,
                                           crs='EPSG:4326', crsTransform=[DX, 0, X0, 0, DY, Y0], region=regiao,
                                           maxPixels=1e9)
    tarefa.start()
    print('tarefa:', tarefa.id)


def conferir():
    arr = ee.data.computePixels({'expression': ee.Image(ASSET).unmask(0), 'fileFormat': 'NUMPY_NDARRAY', 'grid': GRADE})
    with rasterio.open(TIF) as r:
        local = r.read()
    for i, nome in enumerate(('koppen', 'koppen_sem_filtro')):
        gee = np.asarray(arr[nome]).astype(int)
        print(f'{nome}: pixels iguais {100 * (gee == local[i]).mean():.3f}% de {gee.size}')
    print(ee.data.getAsset(ASSET)['properties'].keys())


def atualizar_descricao():
    leg = pd.read_csv(PASTA / 'legenda.csv')
    ee.data.setAssetProperties(ASSET, {'description': descricao(leg)})
    print(ee.data.getAsset(ASSET)['properties']['description'][:400])


DESCRICAO_NORMAL = """**Xavier BR-DWGD v3.2.4 — Normal climatológica mensal de temperatura média e chuva, 1991-2020, Brasil, 0,1°**

**Resumo**

Normal climatológica mensal (1991-2020) da temperatura média do ar e da chuva, calculada a partir da grade
diária do Xavier BR-DWGD v3.2.4. Cada banda mensal é a média de um mês ao longo dos 30 anos; há também a
temperatura média anual e a chuva anual. Produto gerado pelo GAMBI-TEC (UTFPR, Campus Santa Helena); é a entrada
do Köppen-Geiger `projects/fcoliveira/assets/Climas2/koppen_xavier_1991_2020` e serve de base para outras
classificações climáticas e para covariáveis contínuas.

**Especificações**

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

**Bandas**

| Banda | Conteúdo | Unidade | Faixa no Brasil |
|---|---|---|---|
| `T_01` a `T_12` | temperatura média de janeiro a dezembro | °C | 9,0 (julho, serras do Sul) a 31,2 (outubro, Norte) |
| `P_01` a `P_12` | chuva de janeiro a dezembro | mm/mês | 0 (agosto e setembro, semiárido) a 612 (abril) |
| `T_anual` | temperatura média anual (média das 12 bandas) | °C | 12,8 a 28,9 |
| `P_anual` | chuva anual (soma das 12 bandas) | mm/ano | 370 a 3.801 |

**Processamento**

1. Leitura do diário v3.2.4 no próprio GEE, aplicando as escalas de cada imagem (`BAND_*_MULT`, `BAND_*_ADD`).
2. Para cada mês de cada ano de 1991 a 2020: temperatura média = média dos dias de (Tmax + Tmin)/2; chuva = soma
   dos dias.
3. Média de cada mês ao longo dos 30 anos; `T_anual` = média das 12 temperaturas; `P_anual` = soma das 12 chuvas
   (`subir_koppen_gee.py`, função `normal_gee`).
4. Exportação como asset de 26 bandas na grade nativa do Xavier.

**Controle de qualidade**

- Conferência banda a banda com a mesma normal calculada localmente, a partir de um download independente do
  mesmo diário (`subprodutos_koppen.py`): idêntica nas 24 bandas mensais (diferença máxima de 0,0002 mm na chuva).
- A coleção mensal publicada pelo autor (`BR-DWGD_Monthly`) não foi usada: num teste em Brasília (01/2010), a
  chuva mensal dela (171 mm) não bateu com a soma dos dias (114 mm).

**Assets relacionados (mesma grade e período)**

- `projects/fcoliveira/assets/Climas2/koppen_xavier_1991_2020`: Köppen-Geiger 1991-2020 calculado com esta normal
- `projects/fcoliveira/assets/Climas2/xavier_conjunto_curto_decenal`: clima decenal (média móvel de 10 anos,
  1985-2026) do mesmo Xavier, recomendado como covariável do modelo de SOC

**Usos**

- Classificação climática de Köppen-Geiger (critérios de Alvares et al., 2013, com a sazonalidade de Kottek et
  al., 2006), incluindo o limiar de 18 °C do mês mais frio (grupo A) e o limiar de aridez do grupo B
- Zonas de vida de Holdridge, balanço hídrico climatológico e classificação de Thornthwaite (com uma ETo)
- Covariáveis contínuas (temperatura anual, do mês mais frio e do mês mais quente, chuva anual e do mês mais seco)

**Limitações**

- A resolução é a do Xavier (~11 km): em serras menores que o pixel, a temperatura é a média do pixel e não é
  corrigida pela altitude.
- Pixels sem dado do Xavier (bordas de fronteira e de litoral, ilhas oceânicas e a ponta oeste do Acre, cerca de
  1,5% dos pixels que tocam o Brasil) ficam mascarados.
- O Xavier tem poucas estações na Amazônia e no Centro-Oeste; ali a grade é mais suavizada.
- A normal 1991-2020 é mais quente que as usadas nas classificações clássicas do Brasil (por exemplo, Alvares et
  al., 2013); fronteiras térmicas se deslocam em relação a esses mapas.

**Como usar**

As bandas já vêm nomeadas por mês. Faixas de visualização sugeridas para o Brasil: 14 a 28 °C (temperatura
anual), 8 a 30 °C (mensal), 400 a 3.000 mm (chuva anual) e 0 a 400 mm (chuva mensal).

**Google Earth Engine (Code Editor, JavaScript)**

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

**Google Colab (Python)**

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

**Citação**

Dados originais: Xavier, A. C.; Scanlon, B. R.; King, C. W.; Alves, A. I. (2022). New improved Brazilian daily
weather gridded data (1961-2020). International Journal of Climatology, 42(16), 8390-8404.
https://doi.org/10.1002/joc.7731 (versão v3.2.4, 1961-2025).

Processamento: Oliveira, F. C. (2026). Normal climatológica 1991-2020 de temperatura e chuva do Xavier BR-DWGD
v3.2.4. GAMBI-TEC/UTFPR. https://github.com/fcoliveira-utfpr/climate_for_soil (`C4/codigo/subir_koppen_gee.py`).

**Contato**

Prof. Dr. Fabrício Correia de Oliveira — GAMBI-TEC, UTFPR Campus Santa Helena, fcoliveira@utfpr.edu.br

**Licença**

Produto derivado distribuído sob CC BY 4.0; cite também os dados originais do BR-DWGD (Xavier et al., 2022)."""


def atualizar_descricao_normal():
    ee.data.setAssetProperties(ASSET_NORMAL, {'description': DESCRICAO_NORMAL})
    print('descrição da normal:', len(ee.data.getAsset(ASSET_NORMAL)['properties']['description']), 'caracteres')


def normal_gee():
    col = diario().filterDate('1991-01-01', '2021-01-01')

    def ano(a):
        a = ee.Number(a)
        bandas = []
        for m in range(1, 13):
            ini = ee.Date.fromYMD(a, m, 1)
            mes = col.filterDate(ini, ini.advance(1, 'month'))
            t = mes.select('Tmax').mean().add(mes.select('Tmin').mean()).divide(2).rename(f'T_{m:02d}')
            p = mes.select('P').sum().rename(f'P_{m:02d}')
            bandas += [t, p]
        return ee.Image.cat(bandas)
    media = ee.ImageCollection(ee.List.sequence(1991, 2020).map(ano)).mean()
    t = media.select([f'T_{m:02d}' for m in range(1, 13)])
    p = media.select([f'P_{m:02d}' for m in range(1, 13)])
    mascara = ee.Image(col.first()).select('P').mask()
    img = ee.Image.cat(t, p, t.reduce(ee.Reducer.mean()).rename('T_anual'),
                       p.reduce(ee.Reducer.sum()).rename('P_anual')).toFloat()
    return img.updateMask(mascara)


def exportar_normal():
    props = {'description': DESCRICAO_NORMAL, 'fonte': 'Xavier et al. (2022) BR-DWGD v3.2.4', 'periodo': '1991-2020',
             'unidades': 'T_*: graus C; P_*: mm/mes; P_anual: mm/ano', 'autor': 'Fabricio Correia de Oliveira (UTFPR)',
             'system:time_start': ee.Date('1991-01-01').millis(), 'system:time_end': ee.Date('2021-01-01').millis()}
    regiao = ee.Geometry.Rectangle([X0, Y0 + H * DY, X0 + W * DX, Y0], 'EPSG:4326', False)
    tarefa = ee.batch.Export.image.toAsset(image=normal_gee().set(props), description='xavier_normal_1991_2020',
                                           assetId=ASSET_NORMAL, crs='EPSG:4326', crsTransform=[DX, 0, X0, 0, DY, Y0],
                                           region=regiao, maxPixels=1e9)
    tarefa.start()
    print('tarefa:', tarefa.id)


def conferir_normal(asset=True):
    img = ee.Image(ASSET_NORMAL) if asset else normal_gee()
    with rasterio.open(TIF_NORMAL) as r:
        local = {d: r.read(i) for i, d in enumerate(r.descriptions, 1)}
    for grupo in (['T_01', 'T_07', 'P_01', 'P_07'] if not asset else list(local)):
        arr = ee.data.computePixels({'expression': img.select([grupo]), 'fileFormat': 'NUMPY_NDARRAY', 'grid': GRADE})
        g = np.asarray(arr[grupo], dtype=float)
        g = np.where(np.ma.getmaskarray(np.ma.masked_invalid(np.ma.masked_array(g))), np.nan, g)
        ok = np.isfinite(g) & np.isfinite(local[grupo])
        d = g[ok] - local[grupo][ok]
        print(f'{grupo}: pixels {ok.sum()}, dif. média {d.mean():+.4f}, dif. máx. abs. {np.abs(d).max():.4f}')


if __name__ == '__main__':
    conectar(None)
    {'exportar': exportar, 'conferir': conferir, 'descricao': atualizar_descricao, 'normal': exportar_normal,
     'conferir_normal': conferir_normal, 'descricao_normal': atualizar_descricao_normal}[sys.argv[1] if len(sys.argv) > 1 else 'exportar']()
