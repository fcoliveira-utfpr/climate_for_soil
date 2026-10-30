"""Publica no GEE as 9 variáveis do conjunto curto (Xavier v3.2.4, média móvel de 10 anos) para 1985-2026, como
uma ImageCollection com uma imagem por ano, para uso no modelo de SOC do MapBiomas.

Cobertura das bordas: a máscara do Xavier deixa sem dado 1,5% dos pixels de 0,1° que tocam o Brasil (faixas de
fronteira e litoral, ilhas oceânicas e a ponta oeste do Acre, fora do retângulo da grade). A grade é estendida em
1° a norte, sul e oeste e até 28° W a leste (Fernando de Noronha, Trindade e Martim Vaz), e cada pixel sem dado
recebe o valor do pixel válido mais próximo, no mesmo ano. A banda `dist_preenchimento_km` diz a distância até o
pixel de origem (0 = dado do Xavier). Os valores cobrem o Brasil (limite LSIB, ilhas incluídas) mais 2 pixels
(~22 km) além da fronteira e do litoral; fora disso a imagem é mascarada (o limite do pedido ao GEE é de 10 MB).

Envio sem Cloud Storage: cada banda vai como ee.Array em inteiro escalado (temperaturas x 100, CDD e ARM x 10) e
é remontada no GEE pela linha e coluna de cada pixel; o asset fica em float32, nas unidades originais
(precisão de 0,01 °C, 0,1 dia e 0,1 mm).

Uso: python publicar_curto_gee.py exportar [ano_ini ano_fim]
     python publicar_curto_gee.py conferir          # compara o asset com os .npz locais em todos os anos
     python publicar_curto_gee.py descricao         # (re)grava a descrição da coleção
"""
import sys
from pathlib import Path

import ee
import numpy as np
from scipy import ndimage

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / 'corelacao' / 'codigo'))
from gee_utils import conectar  # noqa: E402

VARIAVEIS = RAIZ / 'C4' / 'dados' / 'variaveis'
COBERTURA = RAIZ / 'C4' / 'dados' / 'cobertura_brasil.npz'   # máscara do Brasil na grade estendida
COLECAO = 'projects/fcoliveira/assets/Climas2/xavier_conjunto_curto_decenal'
ANOS = range(1985, 2027)
BANDAS = {  # banda: escala inteira usada no envio
    'cd_t_media': 100, 'cd_tmax_media': 100, 'cd_tmin_media': 100, 'cd_t_mes_quente': 100, 'cd_t_mes_frio': 100,
    'cd_amplitude': 100, 'cd_biotemp': 100, 'cd_cdd': 10, 'cd_arm_csolo': 10}
X0, DX, Y0, DY = -73.89999847412109, 0.1, 5.399999902564652, -0.09999999586416751
H, W = 393, 391
PAD, LESTE = 10, 68                    # 1° a norte, sul e oeste; a leste até ~28° W
X0E, Y0E = X0 - PAD * DX, Y0 - PAD * DY
HE, WE = H + 2 * PAD, W + PAD + LESTE
GRADE = {'dimensions': {'width': WE, 'height': HE},
         'affineTransform': {'scaleX': DX, 'shearX': 0, 'translateX': X0E, 'shearY': 0, 'scaleY': DY, 'translateY': Y0E},
         'crsCode': 'EPSG:4326'}

DESCRICAO = """**Conjunto curto de clima decenal para o modelo de SOC (Xavier BR-DWGD v3.2.4), 1985-2026**

Nove variáveis climáticas em **média móvel dos 10 anos anteriores** ao ano da imagem (a imagem de 2010 usa
2000-2009), recomendadas para substituir o Köppen IPEF no modelo de carbono orgânico do solo do MapBiomas Solo
(relatórios técnicos v6 e v7: ganham do Köppen nas validações espacial, temporal e espaço-temporal, nos dois
modelos testados e em todas as repetições).

- **Dados:** Xavier, A. C.; Scanlon, B. R.; King, C. W.; Alves, A. I. (2022), International Journal of
  Climatology 42(16), 8390-8404 (doi:10.1002/joc.7731); versão v3.2.4 (`projects/ee-alexandrexavier/assets/BR-DWGD`,
  1961-2025). Todas as janelas de 1985 a 2026 têm 10 anos completos.
- **Grade:** 0,1° (EPSG:4326), a do BR-DWGD estendida em 1° para cobrir todo o território (ilhas incluídas).
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
| `dist_preenchimento_km` | distância até o pixel do Xavier de onde veio o valor (0 = dado original; > 0 = borda, ilha ou fora da máscara, preenchida pelo vizinho válido mais próximo) | km |

- **Precisão:** 0,01 °C nas temperaturas e 0,1 dia / 0,1 mm no CDD e no ARM (envio em inteiro escalado).
- **Propriedades:** `year` (ano da imagem), `inicio_janela` e `fim_janela`.
- **Código:** GitHub fcoliveira-utfpr/climate_for_soil, `C4/codigo/` (`baixar_xavier.py`, `eto_rn.py`,
  `variaveis.py`, `publicar_curto_gee.py`) e o notebook de conferência `C4/notebooks/conferir_variaveis_gee.ipynb`.
- **Autor:** Fabrício Correia de Oliveira (UTFPR), outubro de 2026.

**Exemplo de uso no Code Editor:**

```javascript
var curto = ee.ImageCollection('projects/fcoliveira/assets/Climas2/xavier_conjunto_curto_decenal');
var ano = 2020;
var img = curto.filter(ee.Filter.eq('year', ano)).first();
Map.setCenter(-52, -14, 4);
Map.addLayer(img.select('cd_t_media'), {min: 16, max: 28, palette: ['#313695', '#74add1', '#ffffbf', '#f46d43', '#a50026']}, 'T média ' + ano);
Map.addLayer(img.select('cd_arm_csolo'), {min: 0, max: 200, palette: ['#8c510a', '#f6e8c3', '#5ab4ac', '#01665e']}, 'ARM ' + ano, false);
Map.addLayer(img.select('dist_preenchimento_km').selfMask(), {min: 0, max: 50, palette: ['#fee0d2', '#de2d26']}, 'bordas preenchidas', false);

// no modelo de SOC: as 9 variáveis do ano de cada amostra/mapa, reamostradas (bilinear) para a grade de 30 m
var clima = img.select('cd_.*').resample('bilinear');
print(clima.bandNames());
```"""


def alvo():
    """Pixels que recebem valor: Brasil (LSIB) ou dado do Xavier, dilatados em 2 pixels."""
    c = np.load(COBERTURA)
    assert c['br'].shape == (HE, WE)
    return ndimage.binary_dilation(c['br'] | c['xavier'], iterations=2)


def preencher(x):
    """Grade estendida (HE, WE) com o vizinho válido mais próximo e a distância (km) até ele."""
    g = np.full((HE, WE), np.nan, np.float32)
    g[PAD:PAD + H, PAD:PAD + W] = x
    falta = ~np.isfinite(g)
    dist, (li, co) = ndimage.distance_transform_edt(falta, return_indices=True)
    lat = Y0E + DY * (np.arange(HE) + 0.5)
    km = dist * 11.1 * np.sqrt((1 + np.cos(np.deg2rad(lat))[:, None] ** 2) / 2)   # pixel de 0,1° ~ 11,1 km
    return g[li, co], km.astype(np.float32)


def imagem(ano):
    d = np.load(VARIAVEIS / f'{ano}.npz')
    lonlat = ee.Image.pixelLonLat()
    col = lonlat.select('longitude').subtract(X0E).divide(DX).floor().clamp(0, WE - 1).toInt()
    lin = lonlat.select('latitude').subtract(Y0E).divide(DY).floor().clamp(0, HE - 1).toInt()
    pos = ee.Image.cat(lin, col)
    a = alvo()
    bandas, km = [], None
    for b, esc in BANDAS.items():
        v, km = preencher(d[b])
        arr = ee.Image(ee.Array(np.where(a, np.round(v * esc), 0).astype(int).tolist()))
        bandas.append(arr.arrayGet(pos).divide(esc).toFloat().rename(b))
    kmi = ee.Image(ee.Array(np.where(a, np.round(km), 0).astype(int).tolist())).arrayGet(pos).toFloat()
    mascara = ee.Image(ee.Array(a.astype(int).tolist())).arrayGet(pos)
    return ee.Image.cat(bandas + [kmi.rename('dist_preenchimento_km')]).updateMask(mascara).set({'year': ano, 'inicio_janela': ano - 10, 'fim_janela': ano - 1,
                                              'system:time_start': ee.Date.fromYMD(ano, 1, 1).millis(),
                                              'fonte': 'Xavier et al. (2022) BR-DWGD v3.2.4'})


def garantir_colecao():
    try:
        ee.data.getAsset(COLECAO)
    except ee.EEException:
        ee.data.createAsset({'type': 'IMAGE_COLLECTION'}, COLECAO)


def exportar(ini=ANOS[0], fim=ANOS[-1]):
    garantir_colecao()
    regiao = ee.Geometry.Rectangle([X0E, Y0E + HE * DY, X0E + WE * DX, Y0E], 'EPSG:4326', False)
    for ano in range(ini, fim + 1):
        t = ee.batch.Export.image.toAsset(image=imagem(ano), description=f'curto_decenal_{ano}',
                                          assetId=f'{COLECAO}/{ano}', crs='EPSG:4326',
                                          crsTransform=[DX, 0, X0E, 0, DY, Y0E], region=regiao, maxPixels=1e9)
        t.start()
        print(ano, t.id, flush=True)


def conferir():
    col = ee.ImageCollection(COLECAO)
    print('imagens na coleção:', col.size().getInfo())
    pior = {}
    for ano in ANOS:
        img = col.filter(ee.Filter.eq('year', ano)).first()
        arr = ee.data.computePixels({'expression': img, 'fileFormat': 'NUMPY_NDARRAY', 'grid': GRADE})
        d = np.load(VARIAVEIS / f'{ano}.npz')
        a = alvo()
        for b, esc in BANDAS.items():
            v, _ = preencher(d[b])
            g = np.ma.filled(np.ma.masked_array(arr[b]).astype(float), np.nan)
            assert np.isfinite(g[a]).all(), (ano, b, 'pixel do Brasil sem valor')
            pior[b] = max(pior.get(b, 0), float(np.abs(g[a] - v[a]).max()))
        print(ano, 'ok', flush=True)
    print('maior diferença absoluta asset x local (todas as imagens):', {b: round(x, 4) for b, x in pior.items()})


def descricao():
    garantir_colecao()
    ee.data.setAssetProperties(COLECAO, {'description': DESCRICAO})
    print('descrição:', len(ee.data.getAsset(COLECAO)['properties']['description']), 'caracteres')


if __name__ == '__main__':
    conectar(None)
    etapa = sys.argv[1] if len(sys.argv) > 1 else 'exportar'
    if etapa == 'exportar':
        exportar(*[int(a) for a in sys.argv[2:4]])
    elif etapa == 'conferir':
        conferir()
    elif etapa == 'descricao':
        descricao()
