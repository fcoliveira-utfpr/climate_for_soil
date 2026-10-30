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


def codigo_exemplo(leg):
    ids = ', '.join(str(i) for i in leg.id)
    cores = ', '.join(f"'{c}'" for c in leg.cor)
    nomes = ', '.join(f"'{c} - {SIGNIFICADO.get(c, c)}'" for c in leg.classe)
    return f"""var koppen = ee.Image('{ASSET}').select('koppen');
var ids = [{ids}];
var cores = [{cores}];
var nomes = [{nomes}];

// renumera as classes presentes (1..n) para usar a paleta na ordem
var vis = koppen.remap(ids, ee.List.sequence(1, ids.length));
Map.setCenter(-52, -14, 4);
Map.addLayer(vis, {{min: 1, max: ids.length, palette: cores}}, 'Köppen Xavier 1991-2020');

// legenda
var legenda = ui.Panel({{style: {{position: 'bottom-left', padding: '8px'}}}});
legenda.add(ui.Label('Köppen-Geiger 1991-2020 (Xavier)', {{fontWeight: 'bold'}}));
for (var i = 0; i < ids.length; i++) {{
  legenda.add(ui.Panel([
    ui.Label('', {{backgroundColor: cores[i], padding: '8px', margin: '0 6px 4px 0'}}),
    ui.Label(nomes[i], {{margin: '0 0 4px 0'}})
  ], ui.Panel.Layout.Flow('horizontal')));
}}
Map.add(legenda);

// área de cada classe (km²) no Brasil
var area = ee.Image.pixelArea().divide(1e6).addBands(koppen).reduceRegion({{
  reducer: ee.Reducer.sum().group(1, 'classe'), geometry: koppen.geometry(), scale: 11132, maxPixels: 1e9}});
print('área por classe (km²)', area);"""


def descricao(leg):
    tabela = '\n'.join(f'| {r.id} | {r.classe} | {SIGNIFICADO.get(r.classe, "")} | `{r.cor}` | {r.area_pct:.1f}% |'
                        for r in leg.itertuples())
    return f"""**Köppen-Geiger do Brasil, normal climatológica 1991-2020, a partir do Xavier (BR-DWGD v3.2.4)**

Classificação climática de Köppen-Geiger na grade nativa do BR-DWGD (0,1°, 391 x 393 pixels, EPSG:4326),
calculada com a normal mensal de 1991 a 2020 (30 anos completos).

- **Dados:** Xavier, A. C.; Scanlon, B. R.; King, C. W.; Alves, A. I. (2022). New improved Brazilian daily
  weather gridded data (1961-2020). International Journal of Climatology, 42(16), 8390-8404
  (doi:10.1002/joc.7731). Versão v3.2.4 (abril de 2026, `projects/ee-alexandrexavier/assets/BR-DWGD`).
  Temperatura média mensal = média de (Tmax + Tmin)/2 diários; chuva mensal = soma dos dias.
- **Método:** `classificacao_koppen_grade` da biblioteca agrometeorologiapy (F. C. de Oliveira, UTFPR), pela
  metodologia de Alvares et al. (2013), com a sazonalidade f/s/w dos grupos C e D de Kottek et al. (2006); verão =
  out-mar no hemisfério sul. Validada com 100% de concordância contra o Köppen do CHELSA calculado com outro
  código (relatório v1).
- **Bandas:** `koppen` (com filtro de moda 3 x 3, o mesmo do `focalMode`) e `koppen_sem_filtro`
  (classificação direta). Concordância entre elas: 98,5% dos pixels. Valor 0 = sem dado (fora do Brasil).
- **Conferência:** 87,8% de concordância com o Köppen do CHELSA V2.1 1991-2020 e 97,6% com o do Xavier v3.2.2.
- **Normal de temperatura e chuva usada (subprodutos):** `{ASSET_NORMAL}`.
- **Código:** GitHub fcoliveira-utfpr/climate_for_soil, `C4/codigo/koppen_1991_2020.py`.
- **Autor:** Fabrício Correia de Oliveira (UTFPR), outubro de 2026.

**Legenda** (banda `koppen`; códigos de 1 a 31 da agrometeorologiapy; só as classes presentes no Brasil):

| Código | Classe | Significado | Cor | Área no Brasil |
|---|---|---|---|---|
{tabela}

**Exemplo de uso no Code Editor** (mapa, legenda e área de cada classe):

```javascript
{codigo_exemplo(leg)}
```"""


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


DESCRICAO_NORMAL = """**Normal climatológica 1991-2020 de temperatura e chuva do Brasil, Xavier (BR-DWGD v3.2.4)**

Médias mensais de 1991 a 2020 na grade nativa do BR-DWGD (0,1°, 391 x 393 pixels, EPSG:4326). São os dados de
entrada do Köppen-Geiger `projects/fcoliveira/assets/Climas2/koppen_xavier_1991_2020`.

- **Dados:** Xavier, A. C.; Scanlon, B. R.; King, C. W.; Alves, A. I. (2022). New improved Brazilian daily
  weather gridded data (1961-2020). International Journal of Climatology, 42(16), 8390-8404
  (doi:10.1002/joc.7731). Versão v3.2.4 (abril de 2026, `projects/ee-alexandrexavier/assets/BR-DWGD`), com as
  escalas de cada banda (BAND_*_MULT e BAND_*_ADD).
- **Bandas:**
  - `T_01` a `T_12`: temperatura média do mês (°C) = média dos dias de (Tmax + Tmin)/2, média dos 30 anos;
  - `P_01` a `P_12`: chuva do mês (mm/mês) = soma dos dias, média dos 30 anos;
  - `T_anual`: média das 12 temperaturas mensais (°C);
  - `P_anual`: soma das 12 chuvas mensais (mm/ano).
- **Conferência:** idêntica à normal calculada localmente a partir do mesmo diário (diferença máxima de
  0,0002 mm na chuva).
- **Código:** GitHub fcoliveira-utfpr/climate_for_soil, `C4/codigo/subir_koppen_gee.py` (cálculo no GEE) e
  `C4/codigo/subprodutos_koppen.py` (o mesmo cálculo local, usado na conferência).
- **Autor:** Fabrício Correia de Oliveira (UTFPR), outubro de 2026.

**Legenda das bandas**

| Banda | Conteúdo | Unidade | Faixa no Brasil |
|---|---|---|---|
| `T_01` a `T_12` | temperatura média de janeiro a dezembro | °C | 9 (jul, serras do Sul) a 31 (out, Norte) |
| `P_01` a `P_12` | chuva de janeiro a dezembro | mm/mês | 0 (ago-set, semiárido) a 612 (abr) |
| `T_anual` | temperatura média anual | °C | 12,8 a 28,9 |
| `P_anual` | chuva anual | mm/ano | 370 a 3.801 |

**Exemplo de uso no Code Editor** (mapas anuais com legenda e série mensal num ponto):

```javascript
var normal = ee.Image('projects/fcoliveira/assets/Climas2/xavier_normal_1991_2020');
Map.setCenter(-52, -14, 4);
var visT = {bands: ['T_anual'], min: 14, max: 28, palette: ['#313695', '#74add1', '#ffffbf', '#f46d43', '#a50026']};
var visP = {bands: ['P_anual'], min: 400, max: 3000, palette: ['#8c510a', '#f6e8c3', '#c7eae5', '#5ab4ac', '#01665e']};
Map.addLayer(normal, visT, 'Temperatura média anual (°C)');
Map.addLayer(normal, visP, 'Chuva anual (mm)', false);

// legenda (barra de cores) da camada de temperatura
function barra(titulo, vis) {
  var painel = ui.Panel({style: {position: 'bottom-left', padding: '8px'}});
  painel.add(ui.Label(titulo, {fontWeight: 'bold'}));
  painel.add(ui.Thumbnail({image: ee.Image.pixelLonLat().select(0),
    params: {bbox: [0, 0, 1, 0.1], dimensions: '200x12', format: 'png', min: 0, max: 1, palette: vis.palette}}));
  painel.add(ui.Panel([ui.Label(vis.min), ui.Label(vis.max, {margin: '0 0 0 150px'})],
    ui.Panel.Layout.Flow('horizontal')));
  return painel;
}
Map.add(barra('Temperatura média anual (°C)', visT));

// série mensal de um ponto (Brasília)
var ponto = ee.Geometry.Point([-47.9, -15.8]);
var v = normal.reduceRegion(ee.Reducer.first(), ponto, 11132);
var meses = ['01', '02', '03', '04', '05', '06', '07', '08', '09', '10', '11', '12'];
print('Temperatura mensal (°C)', meses.map(function (m) { return v.get('T_' + m); }));
print('Chuva mensal (mm)', meses.map(function (m) { return v.get('P_' + m); }));
```"""


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
