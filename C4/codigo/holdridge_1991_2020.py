"""Zonas de vida de Holdridge do Xavier v3.2.4 com a normal 1991-2020, como o Köppen de koppen_1991_2020.py.

É a classificação que foi melhor no relatório v3 (Holdridge do Xavier, estático): ganhou do Köppen IPEF nos três
esquemas de validação e nos dois modelos. Mesma normal do Köppen (temperatura média mensal = média de
(Tmax + Tmin)/2 diários; chuva mensal = soma; 1991-2020), classificacao_holdridge_grade da agrometeorologiapy com
a ETP original de Holdridge (58,93 x biotemperatura) e filtro de moda 3 x 3, como no v3. Como na coleção do
conjunto curto (publicar_curto_gee.py), o asset fica na grade do Xavier estendida (74,9° W a 28,0° W, 6,4° N a
34,9° S) e toda ela tem zona: os pixels sem dado recebem a zona do pixel válido mais próximo (banda
dist_preenchimento_km), para cobrir bordas, faixa de buffer e ilhas oceânicas.

Etapas:
    gerar      GeoTIFF (grade estendida, preenchida), legenda, conferência e prévia em
               C4/resultados/holdridge_xavier_1991_2020/
    exportar   sobe para o GEE sem Cloud Storage (cada banda como ee.Array, como o Köppen), substituindo o asset
    conferir   asset x GeoTIFF, pixel a pixel
    descricao  descrição em Markdown (C4/gee/descricoes/holdridge_xavier_1991_2020.md); para gravar no GEE e na
               cópia em covariates/climate, use descricoes_gee.py gravar

Uso: python holdridge_1991_2020.py gerar | exportar | conferir | descricao
"""
import sys
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import rasterio
from matplotlib.colors import ListedColormap
from rasterio.transform import Affine
from rasterio.enums import Resampling
from rasterio.warp import reproject
from scipy import ndimage

from agrometeorologiapy.classificacao_climatica import (HOLDRIDGE_ZONAS, HOLDRIDGE_ZONAS_EN,
                                                       classificacao_holdridge_grade)

from koppen_1991_2020 import TRANSF, H, W, normal

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / 'climas_tempo' / 'codigo'))
from classificar import moda3x3  # noqa: E402
from mapas import PAL_HOLDRIDGE  # noqa: E402

SAIDA = RAIZ / 'C4' / 'resultados' / 'holdridge_xavier_1991_2020'
TIF = SAIDA / 'holdridge_xavier_1991_2020.tif'
CHELSA = RAIZ / 'climas' / 'dados_chelsa' / 'holdridge' / 'Holdridge_CHELSA_BR_1991_2020_ETH.tif'
CAP3 = RAIZ / 'climas_tempo' / 'dados' / 'classes_1991_2020.npz'
ASSET = 'projects/fcoliveira/assets/Climas2/holdridge_xavier_1991_2020'
BANDAS = ('holdridge', 'holdridge_sem_filtro', 'dist_preenchimento_km')
DESCRICOES = RAIZ / 'C4' / 'gee' / 'descricoes'
# grade do BR-DWGD no GEE (as mesmas de subir_koppen_gee.py, que não dá para importar aqui: climas_tempo/codigo,
# no início do sys.path, tem outro baixar_xavier.py)
X0, DX, Y0, DY = -73.89999847412109, 0.1, 5.399999902564652, -0.09999999586416751
# grade estendida, a mesma da coleção do conjunto curto (publicar_curto_gee.py)
PAD, LESTE = 10, 68
X0E, Y0E = X0 - PAD * DX, Y0 - PAD * DY
HE, WE = H + 2 * PAD, W + PAD + LESTE
GRADE = {'dimensions': {'width': WE, 'height': HE},
         'affineTransform': {'scaleX': DX, 'shearX': 0, 'translateX': X0E, 'shearY': 0, 'scaleY': DY,
                             'translateY': Y0E},
         'crsCode': 'EPSG:4326'}


def preencher(cls):
    """Classes (0 = sem dado) na grade estendida, com a zona do pixel válido mais próximo, e a distância (km)."""
    g = np.zeros((HE, WE), np.uint8)
    g[PAD:PAD + H, PAD:PAD + W] = cls
    dist, (li, co) = ndimage.distance_transform_edt(g == 0, return_indices=True)
    lat = Y0E + DY * (np.arange(HE) + 0.5)
    km = dist * 11.1 * np.sqrt((1 + np.cos(np.deg2rad(lat))[:, None] ** 2) / 2)   # pixel de 0,1° ~ 11,1 km
    return g[li, co], km


def concordancia(a, b):
    ok = (a > 0) & (b > 0)
    return 100 * (a[ok] == b[ok]).mean(), int(ok.sum())


def gerar():
    SAIDA.mkdir(parents=True, exist_ok=True)
    T, P = normal()
    lat = TRANSF.f + TRANSF.e * (np.arange(H) + 0.5)
    lat = np.repeat(lat[:, None], W, axis=1)
    brasil = np.isfinite(T).all(0) & np.isfinite(P).all(0)
    h = classificacao_holdridge_grade(np.where(brasil, T, np.nan), np.where(brasil, P, np.nan), lat)
    bruto = np.where(brasil, h['id'], 0).astype(np.uint8)
    filtrado = moda3x3(bruto, brasil).astype(np.uint8)

    f_ext, km = preencher(filtrado)
    b_ext, _ = preencher(bruto)
    perfil = {'driver': 'GTiff', 'height': HE, 'width': WE, 'count': 3, 'dtype': 'uint16', 'crs': 'EPSG:4326',
              'transform': Affine(DX, 0, X0E, 0, DY, Y0E), 'compress': 'deflate'}
    with rasterio.open(TIF, 'w', **perfil) as r:
        r.write(f_ext.astype(np.uint16), 1)
        r.write(b_ext.astype(np.uint16), 2)
        r.write(np.round(km).astype(np.uint16), 3)
        for i, b in enumerate(BANDAS, 1):
            r.set_band_description(i, b)
        r.update_tags(fonte='Xavier et al. (2022) BR-DWGD v3.2.4, normal 1991-2020',
                      metodo='agrometeorologiapy classificacao_holdridge_grade, ETP de Holdridge; banda 1 com moda 3x3',
                      classes='; '.join(f'{k}={v}' for k, v in HOLDRIDGE_ZONAS_EN.items()))

    # legenda (área ponderada pelo cosseno da latitude) e faixas das variáveis da classificação por zona
    peso = np.cos(np.deg2rad(lat)) * brasil
    bio, razao = h['biotemperatura'], h['razao_ETP']
    linhas = []
    for k in [int(x) for x in np.unique(filtrado[filtrado > 0])]:
        m = filtrado == k
        linhas.append({'id': k, 'zona': HOLDRIDGE_ZONAS[k], 'zona_en': HOLDRIDGE_ZONAS_EN[k], 'cor': PAL_HOLDRIDGE[k - 1],
                       'area_pct': 100 * peso[m].sum() / peso.sum(), 'pixels': int(m.sum()),
                       'biotemp_media': float(np.nanmean(bio[m])), 'p_anual_media': float(np.nanmean(h['P_anual'][m])),
                       'razao_etp_media': float(np.nanmean(razao[m]))})
    leg = pd.DataFrame(linhas)
    leg.to_csv(SAIDA / 'legenda.csv', index=False, float_format='%.2f')

    # conferências: Holdridge do capítulo 3 (Xavier v3.2.2, mesma metodologia) e do CHELSA 1991-2020 (v1)
    conf = []
    if CAP3.exists():
        c, n = concordancia(filtrado, np.load(CAP3)['holdridge'])
        conf.append({'comparacao': 'Xavier v3.2.4 x Xavier v3.2.2 do capítulo 3', 'concordancia_pct': c, 'pixels': n})
    with rasterio.open(CHELSA) as r:
        ch = np.zeros((H, W), np.uint8)
        reproject(r.read(1), ch, src_transform=r.transform, src_crs=r.crs, dst_transform=TRANSF, dst_crs='EPSG:4326',
                  resampling=Resampling.mode, src_nodata=r.nodata or 0, dst_nodata=0)
    c, n = concordancia(filtrado, ch)
    conf.append({'comparacao': 'Xavier v3.2.4 x CHELSA 1991-2020 (v1)', 'concordancia_pct': c, 'pixels': n})
    c, n = concordancia(filtrado, bruto)
    conf.append({'comparacao': 'com moda 3x3 x sem filtro', 'concordancia_pct': c, 'pixels': n})
    pd.DataFrame(conf).to_csv(SAIDA / 'conferencia.csv', index=False, float_format='%.2f')

    # prévia
    ids = leg.id.tolist()
    vis = np.full(filtrado.shape, np.nan)
    for i, k in enumerate(ids):
        vis[filtrado == k] = i
    fig, ax = plt.subplots(figsize=(8, 8))
    ax.imshow(vis, cmap=ListedColormap(leg.cor.tolist()), vmin=-0.5, vmax=len(ids) - 0.5, interpolation='nearest',
              extent=[TRANSF.c, TRANSF.c + W * TRANSF.a, TRANSF.f + H * TRANSF.e, TRANSF.f])
    ax.legend(handles=[mpatches.Patch(facecolor=r.cor, edgecolor='#666', label=f'{r.id} {r.zona} ({r.area_pct:.1f}%)')
                       for r in leg.itertuples()], loc='lower left', fontsize=8, framealpha=.9)
    ax.set_title('Zonas de vida de Holdridge, Xavier v3.2.4, normal 1991-2020')
    ax.set_xlabel('longitude'); ax.set_ylabel('latitude')
    fig.tight_layout()
    fig.savefig(SAIDA / 'holdridge_xavier_1991_2020.png', dpi=150)
    print(leg.to_string(index=False))
    print(pd.DataFrame(conf).to_string(index=False))


def _gee():
    import ee
    sys.path.insert(0, str(RAIZ / 'corelacao' / 'codigo'))
    from gee_utils import conectar
    conectar(None)
    return ee


def exportar():
    ee = _gee()
    with rasterio.open(TIF) as r:
        bandas = r.read()
    lonlat = ee.Image.pixelLonLat()
    col = lonlat.select('longitude').subtract(X0E).divide(DX).floor().clamp(0, WE - 1).toInt()
    lin = lonlat.select('latitude').subtract(Y0E).divide(DY).floor().clamp(0, HE - 1).toInt()
    pos = ee.Image.cat(lin, col)
    img = ee.Image.cat([ee.Image(ee.Array(b.astype(int).tolist())).arrayGet(pos).rename(n)
                        for b, n in zip(bandas, BANDAS)])
    img = img.select(list(BANDAS[:2])).toUint8().addBands(img.select(BANDAS[2]).toUint16())
    leg = pd.read_csv(SAIDA / 'legenda.csv')
    img = img.set({'fonte': 'Xavier et al. (2022) BR-DWGD v3.2.4', 'periodo': '1991-2020',
                   'metodo': 'agrometeorologiapy classificacao_holdridge_grade (ETP de Holdridge); banda holdridge com moda 3x3',
                   'classes': '; '.join(f'{r.id}={r.zona_en}' for r in leg.itertuples()),
                   'paleta': ','.join(leg.cor), 'autor': 'Fabricio Correia de Oliveira (UTFPR)',
                   'codigo': 'github.com/fcoliveira-utfpr/climate_for_soil C4/codigo/holdridge_1991_2020.py',
                   'system:time_start': ee.Date('1991-01-01').millis(), 'system:time_end': ee.Date('2021-01-01').millis()})
    try:                         # substitui o asset anterior (mesmo caminho e nome)
        ee.data.deleteAsset(ASSET)
        print('asset anterior apagado')
    except ee.EEException:
        pass
    regiao = ee.Geometry.Rectangle([X0E, Y0E + HE * DY, X0E + WE * DX, Y0E], 'EPSG:4326', False)
    t = ee.batch.Export.image.toAsset(image=img, description='holdridge_xavier_1991_2020', assetId=ASSET,
                                      crs='EPSG:4326', crsTransform=[DX, 0, X0E, 0, DY, Y0E], region=regiao,
                                      maxPixels=1e9)
    t.start()
    print('tarefa:', t.id)


def conferir():
    ee = _gee()
    arr = ee.data.computePixels({'expression': ee.Image(ASSET).unmask(0), 'fileFormat': 'NUMPY_NDARRAY', 'grid': GRADE})
    with rasterio.open(TIF) as r:
        local = r.read()
    for i, nome in enumerate(BANDAS):
        g = np.asarray(arr[nome]).astype(int)
        print(f'{nome}: pixels iguais {100 * (g == local[i]).mean():.3f}% de {g.size}')


def descricao():
    from descricoes_gee import formatar      # Markdown no formato que o GEE mostra (descricoes_gee.py)
    md = formatar(texto(pd.read_csv(SAIDA / 'legenda.csv'), pd.read_csv(SAIDA / 'conferencia.csv')))
    DESCRICOES.mkdir(parents=True, exist_ok=True)
    (DESCRICOES / 'holdridge_xavier_1991_2020.md').write_text(md, encoding='utf-8')
    print('descrição:', DESCRICOES / 'holdridge_xavier_1991_2020.md', len(md), 'caracteres')


def texto(leg, conf):
    pct = dict(zip(conf.comparacao, conf.concordancia_pct))
    def br(x, casas):    # número no formato brasileiro: 1.697 / 17,0
        return f'{x:,.{casas}f}'.replace(',', '_').replace('.', ',').replace('_', '.')

    tabela = '\n'.join(f'| {r.id} | {r.zona} | {r.zona_en} | `{r.cor}` | '
                       f'{br(r.area_pct, 1) + "%" if r.area_pct >= 0.05 else "< 0,1%"} | {br(r.biotemp_media, 1)} | '
                       f'{br(r.p_anual_media, 0)} | {br(r.razao_etp_media, 2)} |' for r in leg.itertuples())
    ids = ', '.join(str(i) for i in leg.id)
    cores = ', '.join(f"'{c}'" for c in leg.cor)
    nomes = ', '.join(f"'{z}'" for z in leg.zona)
    return f"""**Xavier BR-DWGD v3.2.4 — Zonas de vida de Holdridge, normal climatológica 1991-2020, Brasil, 0,1°**

**Resumo**

Zonas de vida de Holdridge do Brasil calculadas com a normal mensal de 1991 a 2020 (30 anos completos) de
temperatura e chuva da grade diária do Xavier BR-DWGD v3.2.4, com a biblioteca agrometeorologiapy. Três bandas: a
classificação com filtro de moda 3 × 3 (recomendada para mapas e modelos), a classificação direta e a distância
até o pixel de onde veio a zona (bordas e ilhas preenchidas). Produto
gerado pelo GAMBI-TEC (UTFPR, Campus Santa Helena). Entre as classificações climáticas testadas como covariável do
modelo de carbono orgânico do solo (SOC, 0-30 cm) do MapBiomas Solo, foi a melhor: a única que ganhou do Köppen
do IPEF nos três esquemas de validação e nos dois modelos.

**Especificações**

- Fonte: Xavier BR-DWGD v3.2.4 (Brazilian Daily Weather Gridded Data), `projects/ee-alexandrexavier/assets/BR-DWGD`
- Variáveis originais: Tmax, Tmin e chuva diárias
- Período: 1991-01 a 2020-12 (normal climatológica padrão OMM)
- Resolução espacial: 0,1° (~11 km), a grade do BR-DWGD (469 × 413 pixels)
- Sistema de referência: EPSG:4326 (WGS 84)
- Extensão: 74,9° W a 28,0° W e 6,4° N a 34,9° S (a grade do Xavier estendida para cobrir todo o território,
  ilhas oceânicas incluídas; a mesma da coleção `xavier_conjunto_curto_decenal`)
- Tipo: uint8 (códigos de zona, 1 a 38) e uint16 (distância)
- Bandas: 3 (`holdridge`, `holdridge_sem_filtro`, `dist_preenchimento_km`)
- NoData: nenhum; **toda a grade tem zona**

**Bandas**

| Banda | Conteúdo |
|---|---|
| `holdridge` | zona de vida com filtro de moda 3 × 3 (cada pixel recebe a zona mais frequente na janela, como o `focalMode` do GEE); remove pixels isolados nas fronteiras entre zonas |
| `holdridge_sem_filtro` | classificação direta de cada pixel |
| `dist_preenchimento_km` | distância até o pixel do Xavier de onde veio a zona (0 = dado original) |

**Legenda** (códigos de 1 a 38 da agrometeorologiapy; só as zonas presentes no Brasil; área na banda `holdridge`;
médias da zona: biotemperatura, chuva anual e razão ETP/P)

| Código | Zona de vida | Nome original | Cor | Área no Brasil | Biotemp. (°C) | Chuva (mm/ano) | ETP/P |
|---|---|---|---|---|---|---|---|
{tabela}

**Processamento**

1. Normal mensal 1991-2020 a partir do diário v3.2.4 (`baixar_xavier.py`): temperatura média do mês = média dos
   dias de (Tmax + Tmin)/2; chuva do mês = soma dos dias; média dos 30 anos. É a mesma normal do Köppen
   `koppen_xavier_1991_2020`.
2. Classificação com `classificacao_holdridge_grade` da agrometeorologiapy (`holdridge_1991_2020.py`):
    - biotemperatura: média das temperaturas mensais limitadas a 0-30 °C, com a correção de latitude
      t − 3·|lat|/100·(t − 24)² nos meses acima de 24 °C (Holdridge, 1967);
    - ETP de Holdridge = 58,93 × biotemperatura (mm/ano) e razão ETP/P;
    - zona de vida (38 zonas) pela faixa de biotemperatura (região latitudinal), pela chuva anual e pela razão
      ETP/P (província de umidade), nos hexágonos do diagrama de Holdridge.
3. Filtro de moda 3 × 3 para a banda `holdridge`.
4. Pixels sem dado do Xavier (bordas de fronteira e de litoral, ilhas oceânicas e a ponta oeste do Acre: cerca de
   1,5% dos pixels que tocam o Brasil, onde caem 141 das 27.425 amostras de SOC) e o restante da grade estendida
   recebem a zona do pixel válido mais próximo; a distância fica na banda `dist_preenchimento_km`.
5. Envio ao GEE sem Cloud Storage nem upload manual: cada banda vai como `ee.Array` e a imagem é remontada no
   GEE pela linha e coluna de cada pixel.

**Controle de qualidade**

- Asset × GeoTIFF local: 100% dos pixels iguais nas três bandas; nenhum pixel sem zona em toda a grade.
- A função foi conferida com o Holdridge do relatório técnico v1 (CHELSA, outro código) em 3.000 locais: 98,9%
  de concordância; as diferenças estão em fronteiras de zona (biotemperatura perto de 18 e 24 °C, ETP/P perto de
  0,5, 1 e 2) e vêm do filtro de moda do mapa do v1.
- Banda `holdridge` × `holdridge_sem_filtro`: {br(pct['com moda 3x3 x sem filtro'], 1)}% dos pixels iguais.

**Comparação com outras bases**

| Comparação | Concordância |
|---|---|
| Xavier v3.2.2 (temperatura até 07/2020), mesma metodologia | {br(pct['Xavier v3.2.4 x Xavier v3.2.2 do capítulo 3'], 1)}% |
| Holdridge do CHELSA V2.1 1991-2020 (~1 km, agregado a 0,1°) | {br(pct['Xavier v3.2.4 x CHELSA 1991-2020 (v1)'], 1)}% |

**Validação no modelo de SOC**

Modelo de SOC do MapBiomas Solo, Coleção 3 (matriz de treino reproduzida, 27.425 linhas), com o modelo do mapa
(smileRandomForest do GEE) e com o ranger; validação espacial (V2, blocos de 2°), temporal (V3, uma década fora)
e espaço-temporal (V4); 3 repetições; MEC (Nash-Sutcliffe) nas amostras reais de 0-30 cm (relatório técnico v3,
Holdridge estático do Xavier v3.2.2 com a mesma metodologia). As zonas entraram como variáveis indicadoras
(0/1) hierárquicas: faixa térmica (região latitudinal) e zona de vida.

| MEC (ganho sobre o Köppen IPEF) | V2 | V3 | V4 |
|---|---|---|---|
| Modelo do mapa, Köppen IPEF | 0,179 | 0,124 | 0,111 |
| **Modelo do mapa, Holdridge Xavier** | **0,196 (+0,017)** | **0,138 (+0,014)** | **0,129 (+0,017)** |
| Ranger, Köppen IPEF | 0,240 | 0,172 | 0,152 |
| **Ranger, Holdridge Xavier** | **0,247 (+0,006)** | **0,184 (+0,012)** | **0,158 (+0,006)** |

Foi a melhor classificação: Köppen, Thornthwaite e zonas k10 do mesmo Xavier empataram ou perderam para o Köppen
IPEF. Classificar por década não melhorou (Holdridge decenal ≈ estático). As variáveis contínuas do clima decenal
(`xavier_conjunto_curto_decenal`) ganham mais (+0,012 a +0,031) e são a recomendação principal; o Holdridge é a
opção quando o modelo ou a análise precisam de uma classe.

**Assets relacionados**

- `projects/fcoliveira/assets/Climas2/xavier_normal_1991_2020`: a normal 1991-2020 de temperatura e chuva usada
  aqui (mesma grade e período)
- `projects/fcoliveira/assets/Climas2/koppen_xavier_1991_2020`: Köppen-Geiger 1991-2020 com a mesma normal
- `projects/fcoliveira/assets/Climas2/xavier_conjunto_curto_decenal`: clima decenal (média móvel de 10 anos,
  1985-2026) do mesmo Xavier, recomendado como covariável contínua do modelo de SOC

**Limitações**

- **O resultado depende da fonte dos dados.** Com o CHELSA (relatório v2), o Holdridge foi a pior classificação no
  modelo de SOC; a fronteira de 24 °C da correção de latitude e os limites de biotemperatura caem em lugares
  diferentes conforme a base. A vantagem vale para o Xavier.
- A resolução é a do Xavier (~11 km): zonas de altitude em serras estreitas tendem a ficar subestimadas.
- Nas bordas e nas ilhas oceânicas a zona vem do pixel de terra mais próximo do Xavier (Trindade fica a ~1.100 km
  da costa); use `dist_preenchimento_km` para identificar esses pixels.
- A ETP é a de Holdridge (função só da biotemperatura), não a de Penman-Monteith.
- O teste no modelo de SOC foi feito com o Xavier v3.2.2 e nas partições do v3; não foi repetido nas partições
  novas do v6.

**Como usar**

A banda `holdridge` tem códigos não contíguos; para usar a paleta, renumere as zonas presentes de 1 a n com
`remap`. O asset cobre o retângulo da grade inteiro; recorte pelo limite do Brasil para mapas e áreas. No modelo, use as zonas como variáveis indicadoras (uma coluna 0/1 por zona) ou como fator.

**Google Earth Engine (Code Editor, JavaScript)**

```javascript
// ===== Xavier v3.2.4 | Zonas de vida de Holdridge | Normal 1991-2020 | Brasil 0,1° =====
var holdridge = ee.Image('{ASSET}').select('holdridge');
var ids = [{ids}];
var zonas = [{nomes}];
var cores = [{cores}];

// Renumera as zonas presentes (1..n) para usar a paleta na ordem
var vis = holdridge.remap(ids, ee.List.sequence(1, ids.length));
var brasil = ee.FeatureCollection('FAO/GAUL/2015/level0').filter(ee.Filter.eq('ADM0_NAME', 'Brazil'));
Map.setCenter(-52, -14, 4);
Map.addLayer(vis.clip(brasil), {{min: 1, max: ids.length, palette: cores}}, 'Holdridge Xavier 1991-2020');
Map.addLayer(ee.Image().paint(brasil, 0, 1), {{palette: ['000000']}}, 'Limite do Brasil');

// Legenda
var legenda = ui.Panel({{style: {{position: 'bottom-left', padding: '8px 15px'}}}});
legenda.add(ui.Label('Zonas de vida de Holdridge 1991-2020 (Xavier)', {{fontWeight: 'bold', fontSize: '13px'}}));
for (var i = 0; i < ids.length; i++) {{
  legenda.add(ui.Panel([
    ui.Label('', {{backgroundColor: cores[i], padding: '8px', margin: '0 6px 4px 0', border: '1px solid #999'}}),
    ui.Label(ids[i] + ' ' + zonas[i], {{margin: '0 0 4px 0', fontSize: '12px'}})
  ], ui.Panel.Layout.Flow('horizontal')));
}}
Map.add(legenda);

// Zona no ponto clicado
Map.style().set('cursor', 'crosshair');
Map.onClick(function (c) {{
  holdridge.reduceRegion(ee.Reducer.first(), ee.Geometry.Point([c.lon, c.lat]), 11132).evaluate(function (v) {{
    var k = v && v.holdridge;
    print('Lon ' + c.lon.toFixed(3) + ' | Lat ' + c.lat.toFixed(3) + ': ' +
          (k ? k + ' ' + zonas[ids.indexOf(k)] : 'sem dado'));
  }});
}});

// Área de cada zona no Brasil (km²)
var area = ee.Image.pixelArea().divide(1e6).addBands(holdridge).reduceRegion({{
  reducer: ee.Reducer.sum().group(1, 'zona'), geometry: brasil.geometry(), scale: 11132, maxPixels: 1e9}});
print('Área por zona (km²):', area);

// Zonas como variáveis indicadoras (0/1) para o modelo: uma banda por zona
var indicadoras = ee.Image.cat(ids.map(function (k) {{
  return holdridge.eq(k).unmask(0).rename('holdridge_' + k);
}}));
print('Bandas indicadoras:', indicadoras.bandNames());
// var amostrasComZona = indicadoras.sampleRegions({{collection: amostras, scale: 30, geometries: true}});
```

**Google Colab (Python)**

```python
# ===== Xavier v3.2.4 | Zonas de vida de Holdridge | Normal 1991-2020 | Brasil 0,1° =====
!pip install -q geemap

import ee
import geemap
import pandas as pd

ee.Authenticate()
ee.Initialize(project='SEU_PROJETO')

holdridge = ee.Image('{ASSET}').select('holdridge')
ids = [{ids}]
zonas = [{nomes}]
cores = [{cores}]

brasil = ee.FeatureCollection('FAO/GAUL/2015/level0').filter(ee.Filter.eq('ADM0_NAME', 'Brazil'))

# ---------- Mapa interativo com legenda ----------
vis = holdridge.remap(ids, list(range(1, len(ids) + 1))).clip(brasil)
m = geemap.Map(center=[-14, -52], zoom=4)
m.add_layer(vis, {{'min': 1, 'max': len(ids), 'palette': cores}}, 'Holdridge Xavier 1991-2020')
m.add_legend(title='Zonas de vida de Holdridge 1991-2020',
             legend_dict={{f'{{k}} {{z}}': c.lstrip('#') for k, z, c in zip(ids, zonas, cores)}})
m
```

```python
# ---------- Área de cada zona no Brasil ----------
r = ee.Image.pixelArea().divide(1e6).addBands(holdridge).reduceRegion(
    reducer=ee.Reducer.sum().group(1, 'zona'), geometry=brasil.geometry(), scale=11132, maxPixels=1e9).getInfo()
area = pd.DataFrame(r['groups']).rename(columns={{'sum': 'km2'}})
area['nome'] = area['zona'].map(dict(zip(ids, zonas)))
area['%'] = (100 * area.km2 / area.km2.sum()).round(1)
print(area.sort_values('km2', ascending=False).to_string(index=False))
```

**Citação**

Dados originais: Xavier, A. C.; Scanlon, B. R.; King, C. W.; Alves, A. I. (2022). New improved Brazilian daily
weather gridded data (1961-2020). International Journal of Climatology, 42(16), 8390-8404.
https://doi.org/10.1002/joc.7731 (versão v3.2.4, 1961-2025).

Método: Holdridge, L. R. (1967). Life zone ecology. San José: Tropical Science Center.

Processamento: Oliveira, F. C. (2026). Zonas de vida de Holdridge do Brasil 1991-2020 a partir do Xavier
BR-DWGD v3.2.4. GAMBI-TEC/UTFPR. https://github.com/fcoliveira-utfpr/climate_for_soil
(`C4/codigo/holdridge_1991_2020.py`).

**Contato**

Prof. Dr. Fabrício Correia de Oliveira — GAMBI-TEC, UTFPR Campus Santa Helena, fcoliveira@utfpr.edu.br

**Licença**

Produto derivado distribuído sob CC BY 4.0; cite também os dados originais do BR-DWGD (Xavier et al., 2022)."""


if __name__ == '__main__':
    {'gerar': gerar, 'exportar': exportar, 'conferir': conferir, 'descricao': descricao}[sys.argv[1]]()
