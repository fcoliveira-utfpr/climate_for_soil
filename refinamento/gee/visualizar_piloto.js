// ===== Refinamento a 30 m | Piloto de Curitiba (12 x 12 km) | Normal 1991-2020 | Visualizador =====
// PRÉVIA EXPERIMENTAL, ainda não validada (ver refinamento/mapa.md).
//
// Asset de 39 bandas gerado por refinamento/codigo/pacote_gee_piloto.py
// (arquivo dados/gee/piloto_curitiba_30m_39bandas.tif, enviado pelo Code Editor: Assets > NEW > GeoTIFF).
// O upload nomeia as bandas b1..b39; este script dá os nomes:
//   temp_01 ... temp_12, temp_anual   temperatura média do ar, (Tmax + Tmin)/2, em °C
//   disp_01 ... disp_12, disp_anual   desvio padrão entre 5 modelos, em °C (não é intervalo de previsão)
//   fora_01 ... fora_12, fora_anual   1 = alguma covariável fora da faixa do treino
//
// Asset no projeto GEE do Vitor (compartilhado para leitura). Se o upload for para outro caminho, troque abaixo.
var ASSET = 'projects/mystic-hull-480913-h5/assets/refinamento_30m/piloto_curitiba_30m';

var PERIODOS = ['01', '02', '03', '04', '05', '06', '07', '08', '09', '10', '11', '12', 'anual'];
var ROTULOS = ['Janeiro', 'Fevereiro', 'Março', 'Abril', 'Maio', 'Junho', 'Julho', 'Agosto',
               'Setembro', 'Outubro', 'Novembro', 'Dezembro', 'Anual'];
var BANDAS = [];
['temp', 'disp', 'fora'].forEach(function (prefixo) {
  PERIODOS.forEach(function (p) { BANDAS.push(prefixo + '_' + p); });
});
var img = ee.Image(ASSET).rename(BANDAS);
print('Piloto de Curitiba (39 bandas):', img);

// Mínimo e máximo de cada período no recorte, arredondados, para realçar o detalhe espacial.
// Com "mesma escala", todos os meses usam 13 a 23 °C e a diferença entre as estações aparece.
var FAIXA_T = {
  '01': [21.3, 22.4], '02': [21.4, 22.5], '03': [20.5, 21.6], '04': [18.5, 19.8],
  '05': [15.4, 16.7], '06': [14.2, 15.6], '07': [13.8, 15.1], '08': [14.9, 16.1],
  '09': [16.0, 17.2], '10': [17.8, 18.9], '11': [19.0, 20.2], '12': [20.7, 21.8],
  'anual': [17.8, 19.0]
};
var FAIXA_COMUM = [13, 23];

// Paletas
var PAL_T = ['#313695', '#4575b4', '#74add1', '#abd9e9', '#ffffbf', '#fdae61', '#f46d43', '#d73027', '#a50026'];
var PAL_D = ['#440154', '#3b528b', '#21918c', '#5ec962', '#fde725'];
var COR_FORA = '#d7301f';

var CAMADAS = ['Temperatura média (°C)', 'Dispersão entre modelos (°C)', 'Fora da faixa do treino'];

// Estado
var estado = {camada: CAMADAS[0], periodo: 'anual', escalaComum: false};

// Contexto: relevo sombreado (Copernicus GLO-30) e contorno do recorte
var demCol = ee.ImageCollection('COPERNICUS/DEM/GLO30').select('DEM');
var dem = demCol.mosaic().setDefaultProjection(demCol.first().projection());
var relevo = ee.Terrain.hillshade(dem);
var contorno = ee.Image().paint(ee.FeatureCollection([ee.Feature(img.geometry())]), 0, 2);

function rotuloPeriodo(p) { return ROTULOS[PERIODOS.indexOf(p)]; }

function camadaAtual() {
  var p = estado.periodo;
  if (estado.camada === CAMADAS[0]) {
    var f = estado.escalaComum ? FAIXA_COMUM : FAIXA_T[p];
    return {imagem: img.select('temp_' + p), vis: {min: f[0], max: f[1], palette: PAL_T}, flag: false};
  }
  if (estado.camada === CAMADAS[1]) {
    return {imagem: img.select('disp_' + p), vis: {min: 0, max: 0.35, palette: PAL_D}, flag: false};
  }
  return {imagem: img.select('fora_' + p).selfMask(), vis: {min: 0, max: 1, palette: [COR_FORA]}, flag: true};
}

// Legenda
var painelLegenda = ui.Panel({style: {position: 'bottom-left', padding: '8px 15px'}});
function numero(x) { return String(Number(x.toFixed(2))); }
function atualizarLegenda(titulo, vis, flag) {
  painelLegenda.clear();
  painelLegenda.add(ui.Label(titulo, {fontWeight: 'bold', fontSize: '13px'}));
  if (flag) {
    painelLegenda.add(ui.Panel([
      ui.Label('', {backgroundColor: COR_FORA, padding: '8px', margin: '2px 8px 0 0'}),
      ui.Label('covariável fora da faixa do treino (0,4% dos pixels)', {margin: '2px 0 0 0'})
    ], ui.Panel.Layout.flow('horizontal')));
    return;
  }
  var barra = ui.Thumbnail({
    image: ee.Image.pixelLonLat().select(0).multiply((vis.max - vis.min) / 100).add(vis.min).visualize(vis),
    params: {bbox: [0, 0, 100, 10], dimensions: '200x12'},
    style: {stretch: 'horizontal', margin: '0 8px', maxHeight: '20px'}
  });
  var rotulos = ui.Panel([
    ui.Label(numero(vis.min), {margin: '4px 8px'}),
    ui.Label(numero((vis.min + vis.max) / 2), {margin: '4px 8px', textAlign: 'center', stretch: 'horizontal'}),
    ui.Label(numero(vis.max), {margin: '4px 8px'})
  ], ui.Panel.Layout.flow('horizontal'));
  painelLegenda.add(barra);
  painelLegenda.add(rotulos);
}

// Desenho do mapa
function desenhar() {
  var c = camadaAtual();
  var titulo = estado.camada + ' | ' + rotuloPeriodo(estado.periodo);
  Map.layers().reset();
  Map.addLayer(relevo, {min: 0, max: 255}, 'Relevo sombreado (Copernicus GLO-30)', false);
  Map.addLayer(c.imagem, c.vis, titulo);
  Map.addLayer(contorno, {palette: ['000000']}, 'Recorte do piloto (12 x 12 km)');
  atualizarLegenda(titulo, c.vis, c.flag);
}

// Controles
var seletorCamada = ui.Select({
  items: CAMADAS, value: estado.camada,
  onChange: function (v) { estado.camada = v; desenhar(); },
  style: {stretch: 'horizontal'}
});
var seletorPeriodo = ui.Select({
  items: PERIODOS.map(function (p, i) { return {label: ROTULOS[i], value: p}; }),
  value: estado.periodo,
  onChange: function (v) { estado.periodo = v; desenhar(); },
  style: {stretch: 'horizontal'}
});
var escalaComum = ui.Checkbox({
  label: 'Mesma escala em todos os meses (13 a 23 °C)', value: estado.escalaComum,
  onChange: function (v) { estado.escalaComum = v; desenhar(); }
});
var painelPonto = ui.Panel();

var painel = ui.Panel({
  widgets: [
    ui.Label('Refinamento a 30 m | piloto de Curitiba', {fontWeight: 'bold', fontSize: '15px'}),
    ui.Label('Prévia experimental, ainda não validada. Temperatura média 1991-2020 estimada pelo LightGBM ' +
             'corrigindo o CHELSA, pixel de 30 m (UTM 22S), recorte de 12 x 12 km. A textura fina ainda ' +
             'não foi aprovada (comparação C10).', {fontSize: '12px'}),
    ui.Label('Camada'), seletorCamada,
    ui.Label('Período'), seletorPeriodo,
    escalaComum,
    ui.Label('Clique no mapa para ver o ciclo anual no ponto.', {fontSize: '12px'}),
    painelPonto,
    ui.Label('Produced using Copernicus WorldDEM-30 © DLR e.V. 2010-2014 and © Airbus Defence and Space GmbH ' +
             '2014-2018 provided under COPERNICUS by the European Union and ESA; all rights reserved.',
             {fontSize: '10px', color: '#666666'})
  ],
  style: {width: '340px', padding: '8px'}
});
ui.root.insert(0, painel);
Map.add(painelLegenda);

// Valores no ponto clicado: ciclo dos 12 meses, anual, dispersão e flag
Map.style().set('cursor', 'crosshair');
Map.onClick(function (coords) {
  var ponto = ee.Geometry.Point([coords.lon, coords.lat]);
  painelPonto.clear();
  painelPonto.add(ui.Label('Consultando...'));
  img.reduceRegion({reducer: ee.Reducer.first(), geometry: ponto, scale: 30}).evaluate(function (v) {
    painelPonto.clear();
    if (!v || v.temp_anual === null || v.temp_anual === undefined) {
      painelPonto.add(ui.Label('Fora do recorte do piloto.'));
      return;
    }
    var linhas = [['Mês', 'Temperatura (°C)']];
    for (var i = 0; i < 12; i++) {
      linhas.push([ROTULOS[i].slice(0, 3), v['temp_' + PERIODOS[i]]]);
    }
    painelPonto.add(ui.Label('Lon ' + coords.lon.toFixed(4) + ' | Lat ' + coords.lat.toFixed(4), {fontSize: '12px'}));
    painelPonto.add(ui.Label('Anual: ' + v.temp_anual.toFixed(2) + ' °C | dispersão: ' + v.disp_anual.toFixed(2) + ' °C' +
                             (v.fora_anual === 1 ? ' | fora da faixa do treino' : ''), {fontSize: '12px'}));
    painelPonto.add(ui.Chart(linhas, 'LineChart', {
      title: 'Ciclo anual no ponto (°C)', legend: {position: 'none'},
      vAxis: {title: '°C'}, pointSize: 4, lineWidth: 2, colors: ['#b4441a']
    }));
  });
});

Map.centerObject(img, 13);
desenhar();
