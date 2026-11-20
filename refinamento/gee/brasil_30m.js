// ===== Refinamento a 30 m | Brasil inteiro, calculado no GEE | Temperatura e chuva, normal 1991-2020 =====
// O mesmo modelo congelado do Paraná (validado no teste reservado), rodando dentro do GEE:
//   temperatura = CHELSA + LightGBM(relevo, posição, mês, CHELSA)
//   chuva do mês = exp(LightGBM do mês + log1p(CHELSA)) × smearing − 1
// Cada pixel sai do modelo aplicado às covariáveis do próprio pixel; nenhuma estação é interpolada.
// Gerado por refinamento/codigo/modelo_gee.py (não edite as constantes à mão).
//
// Uso em outros scripts:  var r = require('users/vitorkenor/refinamento_30m:brasil_30m');
//                         var t = r.temperatura;   // bandas media_01..media_12, media_anual, inc90_01..inc90_anual (°C)
//                         var p = r.chuva;         // idem, em mm
// Ao ver no mapa com pouco zoom, a declividade é calculada na escala da tela; para valores exatos de 30 m,
// use reduceRegion/Export com scale: 30.

var C = {
  "pasta": "projects/mystic-hull-480913-h5/assets/refinamento_30m/modelos",
  "temp_features": [
    "latitude",
    "longitude",
    "month_sin",
    "month_cos",
    "latitude_sin",
    "latitude_cos",
    "dem_elevation_m",
    "chelsa_c",
    "slope_deg"
  ],
  "chuva_features": [
    "latitude",
    "longitude",
    "elevation_30",
    "slope_30",
    "chelsa_mm"
  ],
  "temp_k90": 6.132272811942698,
  "temp_q90_anual": 0.7450836461586725,
  "chuva_k90": 10.587913827467903,
  "chuva_q90_anual": 253.80482021297257,
  "chuva_smearing": {
    "01": [
      1.0054533246853248,
      1.007218699002086,
      1.0053714602706827,
      1.0058110311568143,
      1.0054154003791067,
      1.0071314468504862
    ],
    "02": [
      1.0079028389369524,
      1.0077831839829956,
      1.0058659341208953,
      1.0063876845695583,
      1.0058768773180198,
      1.0077382424710803
    ],
    "03": [
      1.0075139716422794,
      1.0074482702296206,
      1.0052200690772075,
      1.0063341142833186,
      1.0076123717333723,
      1.0077005786041362
    ],
    "04": [
      1.00980053183101,
      1.009216973009317,
      1.0098022604109567,
      1.0083874348928552,
      1.0068670498768397,
      1.009680349727306
    ],
    "05": [
      1.008295397680069,
      1.010163415681482,
      1.0112713242300275,
      1.0068656876153557,
      1.0112227433093008,
      1.0114405706821195
    ],
    "06": [
      1.014849320599346,
      1.018982287379838,
      1.0144405367661538,
      1.0125455735587774,
      1.0191733539123433,
      1.0207633827091374
    ],
    "07": [
      1.025802414576953,
      1.0175838467078475,
      1.018749197550296,
      1.0214103633665472,
      1.025234523445983,
      1.0263952324047967
    ],
    "08": [
      1.024588219929467,
      1.0233829511410586,
      1.0255731350600719,
      1.0191287429261127,
      1.022838012499224,
      1.0308247788625107
    ],
    "09": [
      1.0265807598798231,
      1.0191915212958964,
      1.0188141039872205,
      1.013819758251361,
      1.0185123025590168,
      1.0171759617453042
    ],
    "10": [
      1.0159788782940298,
      1.0208574205313279,
      1.0147978911780353,
      1.0195432644706623,
      1.016573170444124,
      1.0144414989484534
    ],
    "11": [
      1.012612645999426,
      1.0121295664545364,
      1.012917692256069,
      1.0095531801168807,
      1.0185030133765518,
      1.0174628930927425
    ],
    "12": [
      1.0114399059139654,
      1.0075652263091825,
      1.0081469629463842,
      1.0094397433716067,
      1.0085212863481083,
      1.0109175326078232
    ]
  },
  "pesos_mes": [
    0.08486950173389304,
    0.07738638437671108,
    0.08486950173389304,
    0.0821317758715094,
    0.08486950173389304,
    0.0821317758715094,
    0.08486950173389304,
    0.08486950173389304,
    0.0821317758715094,
    0.08486950173389304,
    0.0821317758715094,
    0.08486950173389304
  ]
};

var MESES = ['01', '02', '03', '04', '05', '06', '07', '08', '09', '10', '11', '12'];
var ROTULOS = ['Janeiro', 'Fevereiro', 'Março', 'Abril', 'Maio', 'Junho', 'Julho', 'Agosto',
               'Setembro', 'Outubro', 'Novembro', 'Dezembro', 'Anual'];

function modelo(nome) {
  var tabela = nome.indexOf('temp') === 0 ? 'arvores_temp' : 'arvores_chuva_' + nome.split('_')[1];
  var arvores = ee.FeatureCollection(C.pasta + '/' + tabela).filter(ee.Filter.eq('modelo', nome)).aggregate_array('arvore');
  return ee.Classifier.decisionTreeEnsemble(arvores).setOutputMode('REGRESSION');
}

// ---- covariáveis (as mesmas do treino) ----
var demCol = ee.ImageCollection('COPERNICUS/DEM/GLO30_2024_1').select('DEM');
var dem = demCol.mosaic().setDefaultProjection(demCol.first().projection()).resample('bilinear');
var declividade = ee.Terrain.slope(dem);
var lonlat = ee.Image.pixelLonLat();
var tas = ee.Image('projects/fcoliveira/assets/CHELSA/chelsa_brasil_tas_normal_1991_2020').resample('bilinear');
var pr = ee.Image('projects/fcoliveira/assets/CHELSA/chelsa_brasil_pr_normal_1991_2020').resample('bilinear');
var mascara = tas.select('b1').mask();

function desvio(lista) {  // desvio padrão amostral (ddof = 1) entre os 5 membros
  return ee.ImageCollection(lista).reduce(ee.Reducer.stdDev()).multiply(Math.sqrt(5 / 4));
}

// ---- temperatura ----
function temperaturaMes(i) {
  var m = i + 1, ang = 2 * Math.PI * (m - 1) / 12, s = Math.sin(ang), c = Math.cos(ang);
  var lat = lonlat.select('latitude'), chelsa = tas.select('b' + m);
  var bandas = {
    latitude: lat, longitude: lonlat.select('longitude'),
    month_sin: ee.Image.constant(s), month_cos: ee.Image.constant(c),
    latitude_sin: lat.multiply(s), latitude_cos: lat.multiply(c),
    dem_elevation_m: dem, slope_deg: declividade, chelsa_c: chelsa
  };
  var x = ee.Image.cat(C.temp_features.map(function (f) { return bandas[f].rename(f); })).updateMask(mascara);
  var prev = x.classify(modelo('temp_principal'), 'p').add(chelsa);
  var membros = [0, 1, 2, 3, 4].map(function (k) { return x.classify(modelo('temp_membro' + k), 'p').add(chelsa); });
  return {media: prev, inc90: desvio(membros).multiply(C.temp_k90)};
}

// ---- chuva ----
function chuvaMes(i) {
  var mm = MESES[i], sm = C.chuva_smearing[mm];
  var logc = pr.select('b' + (i + 1)).add(1).log();
  var bandas = {latitude: lonlat.select('latitude'), longitude: lonlat.select('longitude'),
                elevation_30: dem, slope_30: declividade, chelsa_mm: logc};
  var x = ee.Image.cat(C.chuva_features.map(function (f) { return bandas[f].rename(f); })).updateMask(mascara);
  function aplica(nome, smear) {
    return x.classify(modelo(nome), 'p').add(logc).exp().multiply(smear).subtract(1).max(0);
  }
  var prev = aplica('chuva_' + mm + '_principal', sm[0]);
  var membros = [0, 1, 2, 3, 4].map(function (k) { return aplica('chuva_' + mm + '_membro' + k, sm[k + 1]); });
  return {media: prev, inc90: desvio(membros).multiply(C.chuva_k90)};
}

function montar(f, anual, q90) {
  var meses = MESES.map(function (m, i) { return f(i); });
  var media = ee.Image.cat(meses.map(function (r, i) { return r.media.rename('media_' + MESES[i]); }));
  var inc = ee.Image.cat(meses.map(function (r, i) { return r.inc90.rename('inc90_' + MESES[i]); }));
  return media.addBands(anual(media).rename('media_anual')).addBands(inc)
    .addBands(ee.Image.constant(q90).updateMask(mascara).rename('inc90_anual')).float();
}

var temperatura = montar(temperaturaMes, function (m) {
  return m.multiply(ee.Image.constant(C.pesos_mes)).reduce(ee.Reducer.sum());
}, C.temp_q90_anual);
var chuva = montar(chuvaMes, function (m) { return m.reduce(ee.Reducer.sum()); }, C.chuva_q90_anual);

exports.temperatura = temperatura;
exports.chuva = chuva;

// ---- exportar como asset (opcional): uma região grande por vez ----
// Exemplo: Export.image.toAsset({image: temperatura.select('media_.*').multiply(100).round().toInt16(),
//   description: 'temperatura_30m_sul', assetId: 'projects/.../temperatura_30m_sul', region: regiao,
//   scale: 30, crs: 'EPSG:4326', maxPixels: 1e13, pyramidingPolicy: {'.default': 'mean'}});
exports.exportar = function (nome, regiao, pasta) {
  Export.image.toAsset({image: temperatura.select('media_.*', 'inc90_.*').multiply(100).round().toInt16(),
    description: 'temperatura_30m_' + nome, assetId: pasta + '/temperatura_30m_' + nome, region: regiao,
    scale: 30, crs: 'EPSG:4326', maxPixels: 1e13, pyramidingPolicy: {'.default': 'mean'}});
  Export.image.toAsset({image: chuva.round().toInt16(),
    description: 'chuva_30m_' + nome, assetId: pasta + '/chuva_30m_' + nome, region: regiao,
    scale: 30, crs: 'EPSG:4326', maxPixels: 1e13, pyramidingPolicy: {'.default': 'mean'}});
};
