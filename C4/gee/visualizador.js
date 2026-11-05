// ===== Xavier v3.2.4 | Conjunto curto de clima decenal | 1985-2026 | Visualizador =====
var COLECAO = 'projects/fcoliveira/assets/Climas2/xavier_conjunto_curto_decenal';
var col = ee.ImageCollection(COLECAO);
var ANO_MIN = 1985, ANO_MAX = 2026;

// Inspeção da coleção
print('Nº de imagens:', col.size());
print('Anos disponíveis:', col.aggregate_array('year').sort());
print('Primeira imagem:', col.first());

// Brasil (FAO GAUL 2015, com as ilhas oceânicas)
var brasil = ee.FeatureCollection('FAO/GAUL/2015/level0').filter(ee.Filter.eq('ADM0_NAME', 'Brazil'));
var limite = ee.Image().paint(brasil, 0, 1);

// Paletas
var PAL_T = ['#313695', '#4575b4', '#74add1', '#abd9e9', '#ffffbf', '#fdae61', '#f46d43', '#d73027', '#a50026'];
var PAL_AMP = ['#f7fcf5', '#c7e9c0', '#74c476', '#238b45', '#00441b'];
var PAL_CDD = ['#ffffd4', '#fe9929', '#993404'];
var PAL_ARM = ['#8c510a', '#d8b365', '#f6e8c3', '#c7eae5', '#5ab4ac', '#01665e'];

// Variáveis e faixas de visualização (ajuste min/max conforme as estatísticas impressas no console)
var VARS = {
  'Temperatura média (°C)':             {banda: 'cd_t_media',      vis: {min: 14, max: 28, palette: PAL_T}},
  'Temperatura máxima média (°C)':      {banda: 'cd_tmax_media',   vis: {min: 20, max: 34, palette: PAL_T}},
  'Temperatura mínima média (°C)':      {banda: 'cd_tmin_media',   vis: {min: 8,  max: 24, palette: PAL_T}},
  'T do mês mais quente (°C)':          {banda: 'cd_t_mes_quente', vis: {min: 18, max: 32, palette: PAL_T}},
  'T do mês mais frio (°C)':            {banda: 'cd_t_mes_frio',   vis: {min: 8,  max: 28, palette: PAL_T}},
  'Amplitude térmica diária (°C)':      {banda: 'cd_amplitude',    vis: {min: 6,  max: 16, palette: PAL_AMP}},
  'Biotemperatura (°C)':                {banda: 'cd_biotemp',      vis: {min: 12, max: 28, palette: PAL_T}},
  'Dias secos consecutivos (dias)':     {banda: 'cd_cdd',          vis: {min: 10, max: 150, palette: PAL_CDD}},
  'Armazenamento de água no solo (mm)': {banda: 'cd_arm_csolo',    vis: {min: 0,  max: 200, palette: PAL_ARM}}
};
var NOMES = Object.keys(VARS);
var BANDAS = NOMES.map(function (n) { return VARS[n].banda; });

// Estado
var estado = {ano: 2020, nome: NOMES[0]};

function imagemDoAno(ano) {
  return ee.Image(col.filter(ee.Filter.eq('year', ano)).first())
    .select(BANDAS).resample('bilinear').clip(brasil);
}

// Legenda
var painelLegenda = ui.Panel({style: {position: 'bottom-left', padding: '8px 15px'}});
function atualizarLegenda(titulo, vis) {
  painelLegenda.clear();
  var barra = ui.Thumbnail({
    image: ee.Image.pixelLonLat().select(0).multiply((vis.max - vis.min) / 100).add(vis.min).visualize(vis),
    params: {bbox: [0, 0, 100, 10], dimensions: '200x12'},
    style: {stretch: 'horizontal', margin: '0 8px', maxHeight: '20px'}
  });
  var rotulos = ui.Panel([
    ui.Label(String(vis.min), {margin: '4px 8px'}),
    ui.Label(String((vis.min + vis.max) / 2), {margin: '4px 8px', textAlign: 'center', stretch: 'horizontal'}),
    ui.Label(String(vis.max), {margin: '4px 8px'})
  ], ui.Panel.Layout.flow('horizontal'));
  painelLegenda.add(ui.Label(titulo, {fontWeight: 'bold', fontSize: '13px'}));
  painelLegenda.add(barra);
  painelLegenda.add(rotulos);
}

// Desenho do mapa
function desenhar() {
  var v = VARS[estado.nome];
  var img = imagemDoAno(estado.ano).select(v.banda);
  Map.layers().reset();
  Map.addLayer(img, v.vis, estado.nome + ' | ' + estado.ano);
  Map.addLayer(limite, {palette: ['000000']}, 'Limite do Brasil');
  atualizarLegenda(estado.nome + ' | ' + estado.ano, v.vis);

  // Estatísticas no Brasil (percentis 2 e 98) para conferir as faixas de visualização
  img.reduceRegion({
    reducer: ee.Reducer.percentile([2, 98]).combine(ee.Reducer.mean(), '', true),
    geometry: brasil.geometry(), scale: 11132, maxPixels: 1e9, bestEffort: true
  }).evaluate(function (s) { print(estado.nome + ' ' + estado.ano + ' (P2, P98, média):', s); });
}

// Controles
var seletor = ui.Select({
  items: NOMES, value: estado.nome,
  onChange: function (n) { estado.nome = n; desenhar(); },
  style: {stretch: 'horizontal'}
});
var slider = ui.Slider({
  min: ANO_MIN, max: ANO_MAX, value: estado.ano, step: 1,
  onChange: function (a) { estado.ano = a; desenhar(); },
  style: {stretch: 'horizontal'}
});
var painelInfo = ui.Label('Clique no mapa para ver as 9 variáveis no ponto.', {fontSize: '12px', whiteSpace: 'pre'});

var painel = ui.Panel({
  widgets: [
    ui.Label('Clima decenal | Xavier v3.2.4', {fontWeight: 'bold', fontSize: '15px'}),
    ui.Label('Variável'), seletor,
    ui.Label('Ano'), slider,
    painelInfo
  ],
  style: {width: '320px', padding: '8px'}
});
ui.root.insert(0, painel);
Map.add(painelLegenda);

// Valores no ponto clicado
Map.style().set('cursor', 'crosshair');
Map.onClick(function (coords) {
  var pt = ee.Geometry.Point([coords.lon, coords.lat]);
  painelInfo.setValue('Consultando...');
  imagemDoAno(estado.ano).reduceRegion(ee.Reducer.first(), pt, 30).evaluate(function (v) {
    if (!v) { painelInfo.setValue('Sem dados no ponto.'); return; }
    var txt = 'Lon ' + coords.lon.toFixed(3) + ' | Lat ' + coords.lat.toFixed(3) + ' | ' + estado.ano + '\n';
    NOMES.forEach(function (n) {
      var x = v[VARS[n].banda];
      txt += n + ': ' + (x === null ? '—' : x.toFixed(2)) + '\n';
    });
    painelInfo.setValue(txt);
  });
});

Map.setCenter(-52, -14, 4);
desenhar();
