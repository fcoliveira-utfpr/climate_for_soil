// ===== Xavier v3.2.4 | Conjunto curto de clima decenal | Uso no modelo de SOC =====
var COLECAO = 'projects/fcoliveira/assets/Climas2/xavier_conjunto_curto_decenal';
var BANDAS = ['cd_t_media', 'cd_tmax_media', 'cd_tmin_media', 'cd_t_mes_quente', 'cd_t_mes_frio',
              'cd_amplitude', 'cd_biotemp', 'cd_cdd', 'cd_arm_csolo'];

// As 9 variáveis do ano (1985-2026), com interpolação bilinear; anos fora da faixa usam o extremo mais próximo
function climaDoAno(ano) {
  var a = ee.Number(ano).max(1985).min(2026);
  return ee.Image(ee.ImageCollection(COLECAO).filter(ee.Filter.eq('year', a)).first())
    .select(BANDAS).resample('bilinear');
}

// Clima de cada amostra no ano dela (campoAno: propriedade com o ano)
function amostrar(amostras, campoAno, escala) {
  amostras = ee.FeatureCollection(amostras);
  var anos = amostras.aggregate_array(campoAno).distinct();
  return ee.FeatureCollection(anos.map(function (a) {
    return climaDoAno(a).sampleRegions({
      collection: amostras.filter(ee.Filter.eq(campoAno, a)), scale: escala, geometries: true
    });
  })).flatten();
}

// ---------- Treino: amostras de teste (troque pelas amostras de SOC) ----------
var amostras = ee.FeatureCollection([
  ee.Feature(ee.Geometry.Point([-47.90, -15.80]), {local: 'Brasília', year: 1990, carbono: 40}),
  ee.Feature(ee.Geometry.Point([-47.90, -15.80]), {local: 'Brasília', year: 2020, carbono: 38}),
  ee.Feature(ee.Geometry.Point([-60.02, -3.10]),  {local: 'Manaus', year: 2005, carbono: 55}),
  ee.Feature(ee.Geometry.Point([-54.33, -24.86]), {local: 'Santa Helena', year: 2015, carbono: 45})
]);
var treino = amostrar(amostras, 'year', 30);
print('Amostras com as 9 variáveis do ano de cada uma:', treino);

// ---------- Mapa do ano: demais covariáveis + clima do mesmo ano ----------
var ano = 2020;
var clima = climaDoAno(ano);
// var pilha = covariaveisDoAno.addBands(clima);
// var rf = ee.Classifier.smileRandomForest(...).setOutputMode('REGRESSION')
//            .train(treino, 'carbono', BANDAS.concat(outrasBandas));
// var soc = pilha.classify(rf);

Map.setCenter(-52, -14, 4);
Map.addLayer(clima.select('cd_t_media'), {min: 14, max: 28,
  palette: ['#313695', '#74add1', '#ffffbf', '#f46d43', '#a50026']}, 'T média ' + ano + ' (bilinear)');
Map.addLayer(treino, {color: '000000'}, 'Amostras');
