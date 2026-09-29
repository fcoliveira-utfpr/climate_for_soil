/*
 * climate_for_soil — mapas principais no Google Earth Engine
 * https://github.com/fcoliveira-utfpr/climate_for_soil
 *
 * Como usar: cole este código no Code Editor do GEE (code.earthengine.google.com) e clique em "Run".
 * Um painel à esquerda permite escolher o mapa e, para os produtos de solo, o cenário de clima.
 *
 *
 * Conteúdo:
 *  - Clima CHELSA V2.1, normal 1991-2020 (~1 km): temperatura média, precipitação e ETP anuais.
 *  - Classificações a partir do CHELSA: Köppen-Geiger, Holdridge (duas ETPs), Thornthwaite
 *    (classe de umidade, CAD 100 mm) e zonas climáticas homogêneas k10 (k-means).
 *  - Produtos da reprodução dos modelos do MapBiomas Solo C3 (0-30 cm, grade de ~5 km, versão fiel):
 *    SOC (t/ha, com correção de Duan), areia, silte e argila (%), em 9 cenários de clima, e a
 *    diferença de SOC em relação ao Köppen IPEF (o clima usado hoje pelo MapBiomas).
 */

var BASE = 'projects/fcoliveira/assets/CHELSA/';

// ------------------------------------------------------------------------------------------------
// Cenários de clima dos produtos de solo
// ------------------------------------------------------------------------------------------------
var CENARIOS = [
  {label: 'Clima contínuo (12 variáveis) — recomendado', value: 'clima_continuo'},
  {label: 'Köppen IPEF (referência, usado hoje)', value: 'koppen_ipef'},
  {label: 'Zonas climáticas k10', value: 'zonas_k10'},
  {label: 'Sem clima', value: 'sem_clima'},
  {label: 'Köppen CHELSA', value: 'koppen_chelsa'},
  {label: 'Holdridge (ETP Penman-Monteith)', value: 'holdridge_etpm'},
  {label: 'Holdridge (ETP de Holdridge)', value: 'holdridge_eth'},
  {label: 'Thornthwaite (CAD 100 mm)', value: 'th_cad100'},
  {label: 'Thornthwaite (CAD do solo)', value: 'th_cadsolo'}
];

function soc(cenario) { return ee.Image(BASE + 'soc_0_30cm_' + cenario).select(0); }
function textura(cenario, banda) { return ee.Image(BASE + 'textura_0_30cm_' + cenario).select(banda); }

// ------------------------------------------------------------------------------------------------
// Legendas das classificações (só as classes que ocorrem no Brasil)
// ------------------------------------------------------------------------------------------------
// Köppen-Geiger: código 1-31 (Alvares et al. 2013; sazonalidade dos climas C por Kottek et al. 2006)
var KOPPEN_PALETA = [
  '#0000FF', '#0078FF', '#46A0FF', '#96C8FF', '#F5A623', '#FFDA8C', '#FF0000', '#FF9696',
  '#C8FF50', '#64FF50', '#32C800', '#FFFF00', '#C8C800', '#969600', '#C8FFC8', '#96FF96',
  '#64C864', '#B4A0FA', '#8C78F0', '#6450E6', '#3C2CB4', '#E0C8FF', '#C8A0FF', '#B478FF',
  '#9650FF', '#D2D2FF', '#AAAAFF', '#8282FF', '#5A5AFF', '#B4B4B4', '#696969'];
var KOPPEN_CLASSES = [[1, 'Af'], [2, 'Am'], [3, 'As'], [4, 'Aw'], [5, 'BSh'], [7, 'BWh'],
                      [9, 'Cfa'], [10, 'Cfb'], [15, 'Cwa'], [16, 'Cwb']];

// Holdridge: 38 zonas de vida, numeração de Jungkunst et al. (2021) / Leemans (1990)
var HOLDRIDGE_CORES = {
  21: '#dadaeb', 22: '#9e9ac8', 23: '#54278f',
  26: '#fff7bc', 27: '#fec44f', 28: '#addd8e', 29: '#31a354', 30: '#006837',
  34: '#a63603', 35: '#fd8d3c', 36: '#c7e9b4', 37: '#41b6c4', 38: '#225ea8'};
var HOLDRIDGE_CLASSES = [
  [21, 'Warm temperate dry forest'], [22, 'Warm temperate moist forest'], [23, 'Warm temperate wet forest'],
  [26, 'Subtropical desert bush'], [27, 'Subtropical thorn steppe'], [28, 'Subtropical dry forest'],
  [29, 'Subtropical moist forest'], [30, 'Subtropical wet forest'],
  [34, 'Tropical thorn steppe'], [35, 'Tropical very dry forest'], [36, 'Tropical dry forest'],
  [37, 'Tropical moist forest'], [38, 'Tropical wet forest']];
var HOLDRIDGE_PALETA = [];
for (var z = 1; z <= 38; z++) { HOLDRIDGE_PALETA.push(HOLDRIDGE_CORES[z] || '#d9d9d9'); }

// Thornthwaite (1948): classe de umidade pelo índice Im (Aparecido et al. 2016)
var TH_PALETA = ['#4575b4', '#abd9e9', '#a6d96a', '#fee08b', '#fec44f', '#fe9929', '#ec7014',
                 '#cc4c02', '#8c2d04'];
var TH_CLASSES = [[1, 'A — superúmido'], [2, 'B4 — úmido'], [3, 'B3 — úmido'], [4, 'B2 — úmido'],
                  [5, 'B1 — úmido'], [6, 'C2 — subúmido úmido'], [7, 'C1 — subúmido seco'],
                  [8, 'D — semiárido'], [9, 'E — árido']];

// Zonas climáticas homogêneas k10 (centro de cada zona: temperatura média e chuva anual)
var K10_PALETA = ['#f46d43', '#a50026', '#66bd63', '#a6d96a', '#1a9850', '#fee08b', '#fdae61',
                  '#abd9e9', '#74add1', '#313695'];
var K10_CLASSES = [
  [1, '1 — tropical quente, seca longa (26,8 °C; 1.500 mm)'],
  [2, '2 — semiárido quente (26,5 °C; 720 mm)'],
  [3, '3 — Amazônia úmida (26,0 °C; 2.300 mm)'],
  [4, '4 — Amazônia, seca moderada (25,8 °C; 1.970 mm)'],
  [5, '5 — Amazônia superúmida (25,6 °C; 2.860 mm)'],
  [6, '6 — tropical sazonal (24,2 °C; 1.370 mm)'],
  [7, '7 — semiárido mais ameno (24,2 °C; 990 mm)'],
  [8, '8 — tropical de altitude (21,2 °C; 1.440 mm)'],
  [9, '9 — subtropical sem estação seca (19,9 °C; 1.590 mm)'],
  [10, '10 — subtropical superúmido (18,4 °C; 1.960 mm)']];

function classes(lista, paleta) {
  return lista.map(function (c) { return [paleta[c[0] - 1], c[1]]; });
}

// ------------------------------------------------------------------------------------------------
// Mapas disponíveis
// ------------------------------------------------------------------------------------------------
var DIVERGENTE = ['#2166ac', '#67a9cf', '#d1e5f0', '#f7f7f7', '#fddbc7', '#ef8a62', '#b2182b'];

var MAPAS = {
  'Clima — Temperatura média anual (°C)': {
    imagem: function () { return ee.Image(BASE + 'chelsa_brasil_tas_normal_1991_2020').reduce(ee.Reducer.mean()); },
    vis: {min: 12, max: 28, palette: ['#313695', '#74add1', '#e0f3f8', '#fee090', '#f46d43', '#a50026']},
    unidade: '°C',
    texto: 'CHELSA V2.1, normal 1991-2020, ~1 km. Média das 12 temperaturas mensais.'},
  'Clima — Precipitação anual (mm)': {
    imagem: function () { return ee.Image(BASE + 'chelsa_brasil_pr_normal_1991_2020').reduce(ee.Reducer.sum()); },
    vis: {min: 400, max: 3200, palette: ['#fff7ec', '#fdd49e', '#a6d96a', '#41b6c4', '#225ea8', '#081d58']},
    unidade: 'mm',
    texto: 'CHELSA V2.1, normal 1991-2020, ~1 km. Soma das 12 precipitações mensais.'},
  'Clima — ETP anual, Penman-Monteith (mm)': {
    imagem: function () { return ee.Image(BASE + 'chelsa_brasil_pet_normal_1991_2020').reduce(ee.Reducer.sum()); },
    vis: {min: 1000, max: 2100, palette: ['#ffffcc', '#fed976', '#fd8d3c', '#e31a1c', '#800026']},
    unidade: 'mm',
    texto: 'CHELSA V2.1, normal 1991-2020, ~1 km. Evapotranspiração potencial anual (Penman-Monteith).'},
  'Classificação — Köppen-Geiger': {
    imagem: function () { return ee.Image(BASE + 'Koppen_CHELSA_BR_1991_2020').select(0).selfMask(); },
    vis: {min: 1, max: 31, palette: KOPPEN_PALETA},
    classes: classes(KOPPEN_CLASSES, KOPPEN_PALETA),
    texto: 'Köppen-Geiger a partir do CHELSA 1991-2020 (critérios de Alvares et al. 2013).'},
  'Classificação — Holdridge (ETP de Holdridge)': {
    imagem: function () { return ee.Image(BASE + 'Holdridge_CHELSA_BR_1991_2020_ETH').select(0).selfMask(); },
    vis: {min: 1, max: 38, palette: HOLDRIDGE_PALETA},
    classes: classes(HOLDRIDGE_CLASSES, HOLDRIDGE_PALETA),
    texto: 'Zonas de vida de Holdridge; razão ETP/P com ETP = 58,93 × biotemperatura (definição original).'},
  'Classificação — Holdridge (ETP Penman-Monteith)': {
    imagem: function () { return ee.Image(BASE + 'Holdridge_CHELSA_BR_1991_2020_ETPM').select(0).selfMask(); },
    vis: {min: 1, max: 38, palette: HOLDRIDGE_PALETA},
    classes: classes(HOLDRIDGE_CLASSES, HOLDRIDGE_PALETA),
    texto: 'Zonas de vida de Holdridge; razão ETP/P com a ETP de Penman-Monteith do CHELSA.'},
  'Classificação — Thornthwaite, umidade (CAD 100 mm)': {
    imagem: function () { return ee.Image(BASE + 'Thornthwaite_CHELSA_BR_1991_2020_CAD100').select(0).selfMask(); },
    vis: {min: 1, max: 9, palette: TH_PALETA},
    classes: classes(TH_CLASSES, TH_PALETA),
    texto: 'Thornthwaite (1948) com balanço hídrico de Thornthwaite & Mather (CAD 100 mm, ETP Penman-Monteith).'},
  'Classificação — Zonas climáticas homogêneas k10': {
    imagem: function () { return ee.Image(BASE + 'zonas_climaticas_k10').select(0).selfMask(); },
    vis: {min: 1, max: 10, palette: K10_PALETA},
    classes: classes(K10_CLASSES, K10_PALETA),
    texto: 'k-means sobre 9 variáveis do CHELSA e do balanço hídrico, ajustado nos pixels do Brasil. ' +
           'Melhor classificação isolada para SOC e textura.'},
  'Solo — SOC 0-30 cm (t/ha)': {
    cenario: true,
    imagem: function (c) { return soc(c); },
    vis: {min: 20, max: 90, palette: ['#ffffd4', '#fed98e', '#fe9929', '#d95f0e', '#993404', '#662506']},
    unidade: 't/ha',
    texto: 'Estoque de carbono orgânico do solo, 0-30 cm. Reprodução do modelo do MapBiomas Solo C3 ' +
           '(random forest), grade de ~5 km, com correção de Duan do viés do log.'},
  'Solo — Diferença de SOC em relação ao Köppen IPEF (t/ha)': {
    cenario: true,
    imagem: function (c) { return soc(c).subtract(soc('koppen_ipef')); },
    vis: {min: -20, max: 20, palette: DIVERGENTE},
    unidade: 't/ha',
    texto: 'SOC do cenário escolhido menos o SOC com o Köppen IPEF. Vermelho: mais carbono que com o Köppen; ' +
           'azul: menos.'},
  'Solo — Areia 0-30 cm (%)': {
    cenario: true,
    imagem: function (c) { return textura(c, 0); },
    vis: {min: 0, max: 90, palette: ['#f7fcf5', '#fee391', '#fec44f', '#ec7014', '#993404']},
    unidade: '%',
    texto: 'Areia de 0-30 cm. Reprodução do modelo de textura do MapBiomas Solo C3 (GBM), grade de ~5 km.'},
  'Solo — Silte 0-30 cm (%)': {
    cenario: true,
    imagem: function (c) { return textura(c, 1); },
    vis: {min: 0, max: 60, palette: ['#f7fcfd', '#ccece6', '#66c2a4', '#238b45', '#00441b']},
    unidade: '%',
    texto: 'Silte de 0-30 cm. Reprodução do modelo de textura do MapBiomas Solo C3 (GBM), grade de ~5 km.'},
  'Solo — Argila 0-30 cm (%)': {
    cenario: true,
    imagem: function (c) { return textura(c, 2); },
    vis: {min: 0, max: 70, palette: ['#fff5eb', '#fdd0a2', '#fd8d3c', '#d94801', '#7f2704']},
    unidade: '%',
    texto: 'Argila de 0-30 cm. Reprodução do modelo de textura do MapBiomas Solo C3 (GBM), grade de ~5 km.'}
};

// ------------------------------------------------------------------------------------------------
// Interface
// ------------------------------------------------------------------------------------------------
var ufs = ee.FeatureCollection('FAO/GAUL/2015/level1').filter(ee.Filter.eq('ADM0_NAME', 'Brazil'));
var contorno = ui.Map.Layer(ee.Image().byte().paint({featureCollection: ufs, color: 1, width: 1}),
                            {palette: ['#333333']}, 'Estados');

var painel = ui.Panel({style: {width: '360px', padding: '8px'}});
painel.add(ui.Label('Clima como base para estimar carbono e textura do solo',
                    {fontWeight: 'bold', fontSize: '16px'}));
painel.add(ui.Label('Mapas do projeto climate_for_soil (UTFPR). Escolha o mapa e, para os produtos de solo, ' +
                    'o cenário de clima usado no modelo.', {fontSize: '12px', color: '#555'}));

var selMapa = ui.Select({items: Object.keys(MAPAS), value: 'Solo — SOC 0-30 cm (t/ha)',
                         style: {stretch: 'horizontal'}});
var selCenario = ui.Select({items: CENARIOS, value: 'clima_continuo', style: {stretch: 'horizontal'}});
var rotuloCenario = ui.Label('Cenário de clima', {fontWeight: 'bold', margin: '8px 8px 0 8px'});
var texto = ui.Label('', {fontSize: '12px', whiteSpace: 'pre-wrap'});
var legenda = ui.Panel();

painel.add(ui.Label('Mapa', {fontWeight: 'bold', margin: '8px 8px 0 8px'}));
painel.add(selMapa);
painel.add(rotuloCenario);
painel.add(selCenario);
painel.add(texto);
painel.add(legenda);
painel.add(ui.Label('Código, métodos e relatório técnico no GitHub', {fontSize: '12px'},
                    'https://github.com/fcoliveira-utfpr/climate_for_soil'));

function legendaContinua(vis, unidade) {
  var barra = ui.Thumbnail({
    image: ee.Image.pixelLonLat().select(0),
    params: {bbox: [0, 0, 1, 0.1], dimensions: '300x12', format: 'png', min: 0, max: 1, palette: vis.palette},
    style: {stretch: 'horizontal', margin: '4px 8px', maxHeight: '20px'}});
  var meio = (vis.min + vis.max) / 2;
  var valores = ui.Panel([
    ui.Label(String(vis.min), {margin: '0 8px'}),
    ui.Label(String(meio), {margin: '0 8px', textAlign: 'center', stretch: 'horizontal'}),
    ui.Label(String(vis.max) + ' ' + unidade, {margin: '0 8px'})
  ], ui.Panel.Layout.flow('horizontal'));
  return [barra, valores];
}

function legendaClasses(lista) {
  return lista.map(function (c) {
    return ui.Panel([
      ui.Label('', {backgroundColor: c[0], padding: '8px', margin: '2px 6px 2px 8px', border: '1px solid #999'}),
      ui.Label(c[1], {margin: '2px 0', fontSize: '12px'})
    ], ui.Panel.Layout.flow('horizontal'));
  });
}

function atualizar() {
  var nome = selMapa.getValue();
  var def = MAPAS[nome];
  var comCenario = def.cenario === true;
  rotuloCenario.style().set('shown', comCenario);
  selCenario.style().set('shown', comCenario);
  var cenario = selCenario.getValue();
  var titulo = comCenario ? nome + ' — ' + cenario : nome;
  Map.layers().reset([ui.Map.Layer(def.imagem(cenario), def.vis, titulo), contorno]);
  texto.setValue(def.texto);
  legenda.clear();
  var itens = def.classes ? legendaClasses(def.classes) : legendaContinua(def.vis, def.unidade);
  itens.forEach(function (w) { legenda.add(w); });
}

selMapa.onChange(atualizar);
selCenario.onChange(atualizar);

ui.root.insert(0, painel);
Map.setCenter(-54, -15, 4);
Map.setOptions('TERRAIN');
atualizar();
