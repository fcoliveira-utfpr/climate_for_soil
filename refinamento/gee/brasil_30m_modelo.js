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

var C = __CONSTANTES__;

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
