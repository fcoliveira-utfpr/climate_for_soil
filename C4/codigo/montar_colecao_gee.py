"""Monta no GEE a coleção anual do conjunto curto a partir do GeoTIFF de gerar_geotiff_gee.py, depois que ele foi
subido manualmente (Code Editor: Assets > NEW > Image Upload > GeoTIFF). O upload chama as bandas de b1 a b380, na
ordem de resultados/gee/bandas.csv; aqui cada ano vira uma imagem com os nomes das variáveis.

Uso: python montar_colecao_gee.py exportar <asset do GeoTIFF>
     python montar_colecao_gee.py conferir             # asset x .npz locais, todos os anos e bandas
     python montar_colecao_gee.py descricao
"""
import sys
from pathlib import Path

import ee
import numpy as np
import pandas as pd

from publicar_curto_gee import ANOS, BANDAS, COLECAO, DX, DY, GRADE, HE, VARIAVEIS, WE, X0E, Y0E, alvo, preencher

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / 'corelacao' / 'codigo'))
from gee_utils import conectar  # noqa: E402

BANDAS_CSV = RAIZ / 'C4' / 'resultados' / 'gee' / 'bandas.csv'

DESCRICAO = """**Conjunto curto de clima decenal para o modelo de SOC do MapBiomas Solo (Xavier BR-DWGD v3.2.4), 1985-2026**

Nove variáveis climáticas em **média móvel dos 10 anos anteriores** ao ano da imagem (a imagem de 2010 usa
2000-2009). Recomendadas para substituir o Köppen IPEF no modelo de carbono orgânico do solo: ganham do Köppen nas
validações espacial (V2), temporal (V3) e espaço-temporal (V4), com o modelo validado (ranger) e com o modelo do
mapa, em todas as repetições, também em partições de validação independentes (relatórios técnicos v6 e v7).

**Como usar no modelo: amostrar com interpolação bilinear** (`.resample('bilinear')`), no treino e no mapa.
Na validação, a bilinear foi melhor que o valor do pixel (até +0,010 de MEC) e que as versões com correção da
temperatura pela altitude ou com a CAD do solo em 1 km, que pioraram no tempo. Sem a bilinear, o mapa de 30 m
herda degraus de 11 km.

- **Dados:** Xavier, A. C.; Scanlon, B. R.; King, C. W.; Alves, A. I. (2022), International Journal of
  Climatology 42(16), 8390-8404 (doi:10.1002/joc.7731); versão v3.2.4 (`projects/ee-alexandrexavier/assets/BR-DWGD`,
  1961-2025). Todas as janelas de 1985 a 2026 têm 10 anos completos.
- **Grade:** 0,1° (EPSG:4326), a do BR-DWGD estendida para cobrir todo o território. Os pixels sem dado do Xavier
  (bordas de fronteira e litoral, ilhas oceânicas e a ponta oeste do Acre: 1,5% dos pixels que tocam o Brasil)
  recebem o valor do pixel válido mais próximo (banda `dist_preenchimento_km`). Valores no Brasil + ~22 km;
  fora disso, mascarado.
- **Bandas (float32):**

| Banda | Variável | Unidade |
|---|---|---|
| `cd_t_media` | temperatura média: média de (Tmax + Tmin)/2 | °C |
| `cd_tmax_media` | temperatura máxima média | °C |
| `cd_tmin_media` | temperatura mínima média | °C |
| `cd_t_mes_quente` | temperatura média do mês mais quente | °C |
| `cd_t_mes_frio` | temperatura média do mês mais frio | °C |
| `cd_amplitude` | amplitude térmica diária média (Tmax - Tmin) | °C |
| `cd_biotemp` | biotemperatura de Holdridge (agrometeorologiapy) | °C |
| `cd_cdd` | CDD: maior sequência anual de dias com chuva < 1 mm (ETCCDI), média | dias |
| `cd_arm_csolo` | armazenamento médio de água do balanço hídrico de Thornthwaite-Mather (ETo de Penman-Monteith pelo saldo de radiação, agrometeorologiapy), com a CAD do solo | mm |
| `dist_preenchimento_km` | distância até o pixel do Xavier de onde veio o valor (0 = dado original) | km |
| `z_pixel_m` | altitude média do pixel (MERIT DEM); auxiliar | m |

- **Propriedades:** `year` (ano da imagem), `inicio_janela`, `fim_janela`.
- **Código:** GitHub fcoliveira-utfpr/climate_for_soil, `C4/codigo/`; notebook de conferência
  `C4/notebooks/conferir_variaveis_gee.ipynb`.
- **Autor:** Fabrício Correia de Oliveira (UTFPR), outubro de 2026.

**Exemplo de uso no Code Editor** (as 9 variáveis do ano do mapa, prontas para empilhar com as covariáveis):

```javascript
var curto = ee.ImageCollection('projects/fcoliveira/assets/Climas2/xavier_conjunto_curto_decenal');
var VARIAVEIS = ['cd_t_media', 'cd_tmax_media', 'cd_tmin_media', 'cd_t_mes_quente', 'cd_t_mes_frio',
                 'cd_amplitude', 'cd_biotemp', 'cd_cdd', 'cd_arm_csolo'];

function climaDoAno(ano) {
  return curto.filter(ee.Filter.eq('year', ano)).first().select(VARIAVEIS).resample('bilinear');
}

var clima2020 = climaDoAno(2020);
Map.setCenter(-52, -14, 4);
Map.addLayer(clima2020.select('cd_t_media'), {min: 16, max: 28,
  palette: ['#313695', '#74add1', '#ffffbf', '#f46d43', '#a50026']}, 'T média 2020 (bilinear)');
Map.addLayer(clima2020.select('cd_arm_csolo'), {min: 0, max: 200,
  palette: ['#8c510a', '#f6e8c3', '#5ab4ac', '#01665e']}, 'ARM 2020', false);

// nas amostras: o clima do ano de cada ponto, com a mesma interpolação do mapa
// var amostras = ee.FeatureCollection('...');  // com a propriedade 'year'
// var comClima = amostras.map(function (f) {
//   var v = climaDoAno(ee.Number(f.get('year'))).reduceRegion(ee.Reducer.first(), f.geometry(), 30);
//   return f.set(v);
// });
```"""


def nomes():
    return pd.read_csv(BANDAS_CSV).nome.tolist()


def imagem(fonte, ano):
    lista = nomes()
    idx = [lista.index(f'{b}_{ano}') + 1 for b in BANDAS] + [lista.index('dist_preenchimento_km') + 1,
                                                              lista.index('z_pixel_m') + 1]
    img = ee.Image(fonte).select([f'b{i}' for i in idx], list(BANDAS) + ['dist_preenchimento_km', 'z_pixel_m'])
    return img.toFloat().set({'year': ano, 'inicio_janela': ano - 10, 'fim_janela': ano - 1,
                              'system:time_start': ee.Date.fromYMD(ano, 1, 1).millis(),
                              'fonte': 'Xavier et al. (2022) BR-DWGD v3.2.4'})


def exportar(fonte):
    b = ee.Image(fonte).bandNames().size().getInfo()
    assert b == len(nomes()), f'o asset tem {b} bandas; esperado {len(nomes())}'
    try:
        ee.data.getAsset(COLECAO)
    except ee.EEException:
        ee.data.createAsset({'type': 'IMAGE_COLLECTION'}, COLECAO)
    regiao = ee.Geometry.Rectangle([X0E, Y0E + HE * DY, X0E + WE * DX, Y0E], 'EPSG:4326', False)
    for ano in ANOS:
        t = ee.batch.Export.image.toAsset(image=imagem(fonte, ano), description=f'curto_decenal_{ano}',
                                          assetId=f'{COLECAO}/{ano}', crs='EPSG:4326',
                                          crsTransform=[DX, 0, X0E, 0, DY, Y0E], region=regiao, maxPixels=1e9,
                                          pyramidingPolicy={'.default': 'mean'})
        t.start()
        print(ano, t.id, flush=True)


def conferir():
    col = ee.ImageCollection(COLECAO)
    print('imagens na coleção:', col.size().getInfo())
    a, pior = alvo(), {}
    for ano in ANOS:
        img = col.filter(ee.Filter.eq('year', ano)).first().select(list(BANDAS))
        arr = ee.data.computePixels({'expression': img, 'fileFormat': 'NUMPY_NDARRAY', 'grid': GRADE})
        d = np.load(VARIAVEIS / f'{ano}.npz')
        for b in BANDAS:
            v, _ = preencher(d[b])
            g = np.ma.filled(np.ma.masked_array(arr[b]).astype(float), np.nan)
            assert np.isfinite(g[a]).all(), (ano, b, 'pixel do Brasil sem valor')
            pior[b] = max(pior.get(b, 0), float(np.abs(g[a] - v[a]).max()))
        print(ano, 'ok', flush=True)
    print('maior diferença absoluta asset x local:', {b: round(x, 5) for b, x in pior.items()})


def descricao():
    ee.data.setAssetProperties(COLECAO, {'description': DESCRICAO})
    print('descrição:', len(ee.data.getAsset(COLECAO)['properties']['description']), 'caracteres')


if __name__ == '__main__':
    conectar(None)
    etapa = sys.argv[1] if len(sys.argv) > 1 else ''
    if etapa == 'exportar':
        exportar(sys.argv[2])
    elif etapa == 'conferir':
        conferir()
    elif etapa == 'descricao':
        descricao()
    else:
        raise SystemExit(__doc__)
