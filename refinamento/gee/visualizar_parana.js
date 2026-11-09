// ===== Refinamento a 30 m | Paraná inteiro | Temperatura e chuva, normal 1991-2020 | Visualizador =====
// PRÉVIA EXPERIMENTAL (ver refinamento/mapa.md). Cada pixel sai de um modelo aplicado às covariáveis do pixel:
// LightGBM corrigindo o CHELSA (temperatura) e um LightGBM por mês corrigindo o CHELSA (chuva), sem interpolar estações.
//
// Dois assets int16 de 39 bandas, gerados por refinamento/codigo/pacote_gee_parana.py. O upload nomeia b1..b39:
//   b1-b13   média: temperatura em °C × 100 | chuva em mm (meses 01-12 e anual)
//   b14-b26  meia-largura do intervalo de 90% calibrado (mesma unidade da média)
//   b27-b39  1 = pixel fora da área de aplicabilidade do modelo
var PASTA = 'projects/mystic-hull-480913-h5/assets/refinamento_30m/';
var PERIODOS = ['01', '02', '03', '04', '05', '06', '07', '08', '09', '10', '11', '12', 'anual'];
var ROTULOS = ['Janeiro', 'Fevereiro', 'Março', 'Abril', 'Maio', 'Junho', 'Julho', 'Agosto',
               'Setembro', 'Outubro', 'Novembro', 'Dezembro', 'Anual'];
var NOMES = [];
['media', 'inc90', 'aoa'].forEach(function (k) { PERIODOS.forEach(function (p) { NOMES.push(k + '_' + p); }); });

function carregar(asset, escala) {
  var img = ee.Image(PASTA + asset).rename(NOMES);
  var valores = img.select('media_.*', 'inc90_.*').multiply(escala);
  return valores.addBands(img.select('aoa_.*'));
}
var VARIAVEIS = {
  'Temperatura média (°C)': {img: carregar('parana_temperatura_30m', 0.01), unidade: '°C',
    faixa: {media: [12, 28], anual: [16.5, 24.5], inc90: [0, 2]},
    paleta: ['#313695', '#4575b4', '#74add1', '#abd9e9', '#ffffbf', '#fdae61', '#f46d43', '#d73027', '#a50026']},
  'Chuva (mm)': {img: carregar('parana_chuva_30m', 1), unidade: 'mm',
    faixa: {media: [40, 330], anual: [1250, 2350], inc90: [0, 180]},
    paleta: ['#f7fbff', '#deebf7', '#c6dbef', '#9ecae1', '#6baed6', '#4292c6', '#2171b5', '#08519c', '#08306b']}
};
var CAMADAS = ['Média', 'Incerteza (meia-largura do intervalo de 90%)', 'Fora da área de aplicabilidade'];
var estado = {variavel: 'Temperatura média (°C)', camada: CAMADAS[0], periodo: 'anual'};

function visualizacao() {
  var v = VARIAVEIS[estado.variavel], p = estado.periodo;
  if (estado.camada === CAMADAS[0]) {
    var f = p === 'anual' ? v.faixa.anual : v.faixa.media;
    return {banda: 'media_' + p, vis: {min: f[0], max: f[1], palette: v.paleta}, flag: false};
  }
  if (estado.camada === CAMADAS[1]) {
    var g = p === 'anual' && v.unidade === 'mm' ? [0, 400] : v.faixa.inc90;
    return {banda: 'inc90_' + p, vis: {min: g[0], max: g[1], palette: ['#fff5eb', '#fdae6b', '#e6550d', '#7f2704']}, flag: false};
  }
  return {banda: 'aoa_' + p, vis: {min: 0, max: 1, palette: ['#d7301f']}, flag: true};
}

var painelLegenda = ui.Panel({style: {position: 'bottom-left', padding: '8px 15px'}});
function legenda(titulo, vis, flag) {
  painelLegenda.clear();
  painelLegenda.add(ui.Label(titulo, {fontWeight: 'bold', fontSize: '13px'}));
  if (flag) {
    painelLegenda.add(ui.Label('vermelho: covariáveis diferentes das estações de treino', {fontSize: '12px'}));
    return;
  }
  painelLegenda.add(ui.Thumbnail({
    image: ee.Image.pixelLonLat().select(0).multiply((vis.max - vis.min) / 100).add(vis.min).visualize(vis),
    params: {bbox: [0, 0, 100, 10], dimensions: '200x12'}, style: {stretch: 'horizontal', margin: '0 8px', maxHeight: '20px'}}));
  painelLegenda.add(ui.Panel([ui.Label(String(vis.min), {margin: '4px 8px'}),
    ui.Label(String((vis.min + vis.max) / 2), {margin: '4px 8px', textAlign: 'center', stretch: 'horizontal'}),
    ui.Label(String(vis.max), {margin: '4px 8px'})], ui.Panel.Layout.flow('horizontal')));
}

var demCol = ee.ImageCollection('COPERNICUS/DEM/GLO30').select('DEM');
var relevo = ee.Terrain.hillshade(demCol.mosaic().setDefaultProjection(demCol.first().projection()));

function desenhar() {
  var c = visualizacao(), v = VARIAVEIS[estado.variavel];
  var camada = v.img.select(c.banda);
  if (c.flag) camada = camada.selfMask();
  var titulo = estado.variavel + ' | ' + estado.camada + ' | ' + ROTULOS[PERIODOS.indexOf(estado.periodo)];
  Map.layers().reset();
  Map.addLayer(relevo, {min: 0, max: 255}, 'Relevo sombreado', false);
  Map.addLayer(camada, c.vis, titulo);
  legenda(titulo, c.vis, c.flag);
}

var painelPonto = ui.Panel();
var painel = ui.Panel({widgets: [
  ui.Label('Refinamento a 30 m | Paraná', {fontWeight: 'bold', fontSize: '15px'}),
  ui.Label('Prévia experimental, normal 1991-2020, pixel de 30 m (UTM 22S). Validação no teste reservado e ' +
           'limitações em refinamento/mapa.md.', {fontSize: '12px'}),
  ui.Label('Variável'), ui.Select({items: Object.keys(VARIAVEIS), value: estado.variavel,
    onChange: function (x) { estado.variavel = x; desenhar(); }, style: {stretch: 'horizontal'}}),
  ui.Label('Camada'), ui.Select({items: CAMADAS, value: estado.camada,
    onChange: function (x) { estado.camada = x; desenhar(); }, style: {stretch: 'horizontal'}}),
  ui.Label('Período'), ui.Select({items: PERIODOS.map(function (p, i) { return {label: ROTULOS[i], value: p}; }),
    value: estado.periodo, onChange: function (x) { estado.periodo = x; desenhar(); }, style: {stretch: 'horizontal'}}),
  ui.Label('Clique no mapa para ver os 12 meses no ponto.', {fontSize: '12px'}), painelPonto,
  ui.Label('Produced using Copernicus WorldDEM-30 © DLR e.V. 2010-2014 and © Airbus Defence and Space GmbH ' +
           '2014-2018 provided under COPERNICUS by the European Union and ESA; all rights reserved.',
           {fontSize: '10px', color: '#666666'})
], style: {width: '340px', padding: '8px'}});
ui.root.insert(0, painel);
Map.add(painelLegenda);

Map.style().set('cursor', 'crosshair');
Map.onClick(function (coords) {
  var v = VARIAVEIS[estado.variavel], ponto = ee.Geometry.Point([coords.lon, coords.lat]);
  painelPonto.clear();
  painelPonto.add(ui.Label('Consultando...'));
  v.img.reduceRegion({reducer: ee.Reducer.first(), geometry: ponto, scale: 30}).evaluate(function (x) {
    painelPonto.clear();
    if (!x || x.media_anual === null || x.media_anual === undefined) { painelPonto.add(ui.Label('Fora do Paraná.')); return; }
    var linhas = [['Mês', 'Valor', 'Mínimo do intervalo', 'Máximo do intervalo']];
    for (var i = 0; i < 12; i++) {
      var m = x['media_' + PERIODOS[i]], h = x['inc90_' + PERIODOS[i]];
      linhas.push([ROTULOS[i].slice(0, 3), m, m - h, m + h]);
    }
    painelPonto.add(ui.Label('Anual: ' + x.media_anual.toFixed(v.unidade === 'mm' ? 0 : 2) + ' ' + v.unidade +
      ' ± ' + x.inc90_anual.toFixed(v.unidade === 'mm' ? 0 : 2) + (x.aoa_anual === 1 ? ' | fora da área de aplicabilidade' : ''),
      {fontSize: '12px'}));
    painelPonto.add(ui.Chart(linhas, 'LineChart', {title: estado.variavel + ' no ponto (faixa de 90%)', legend: {position: 'none'},
      series: {1: {lineDashStyle: [4, 4], color: '#999999'}, 2: {lineDashStyle: [4, 4], color: '#999999'}},
      colors: [v.unidade === 'mm' ? '#2171b5' : '#b4441a'], pointSize: 3}));
  });
});

Map.setCenter(-51.5, -24.6, 7);
desenhar();
