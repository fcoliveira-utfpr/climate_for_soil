/******************************************************************************
 * SIMULAÇÃO DE MAPAS ANUAIS DE SOC (0-30 cm, t/ha) - MapBiomas Solo C3, trocando o clima e o modelo
 * ----------------------------------------------------------------------------
 * Gera, para os anos de ANOS, três versões do mapa de estoque de carbono orgânico do solo e compara com o
 * produto oficial da C3:
 *   A  oficial reproduzido: receita de carbon/2_model_prediction (smileRandomForest com maxNodes 40,
 *      Köppen IPEF como clima, carbono_gm2_qmap);
 *   B  decenal: o mesmo modelo, com o clima decenal (temperatura, chuva e CDD da década anterior) no
 *      lugar das 13 dummies de Köppen;
 *   C  decenal + árvores profundas: smileRandomForest sem limite de nós (o equivalente do ranger que o
 *      MapBiomas validou: MEC 0,73 / 0,58), com o clima decenal.
 *
 * Mesma matriz, mesmos filtros e mesmas covariáveis da produção:
 *   - covariáveis: módulo de produção users/taciaraz/mapbiomas_solo:collection3/carbon/0_covariate_source;
 *   - treino: projects/fcoliveira/assets/SOC_C3_FABRICIO/matriz_soc_c3_fabricio_treino (matriz da C3
 *     reconstruída a partir dos pontos ORIGINAIS/collection3/2025_11_26_soildata_soc_trep, 35.235 linhas, com
 *     as covariáveis no ano de cada linha e o clima decenal; filtros abaixo = os do script da trainingFinal,
 *     que levam a 27.425 linhas);
 *   - pós-processamento: 0 onde o uso do ano é 23 (dunas/praias), 24 (urbano) ou 30 (mineração) ou o grupo
 *     textural é 1; arredondamento para t/ha inteiras. A máscara de areia (MB_2024_SANDMASK, 10 t/ha) só
 *     entra se USAR_MASCARA_AREIA = true e a conta tiver acesso; a correção de 1985-1987 não se aplica.
 *
 * Validação (relatório técnico v2, GitHub fcoliveira-utfpr/climate_for_soil): nas amostras reais, o modelo
 * raso acerta menos que o profundo (MEC 0,18 x 0,24 na validação espacial) e subestima ~7 t/ha; o clima
 * decenal ganha do Köppen nos três esquemas de validação (espaço, tempo, espaço-tempo).
 *
 * Autor: Fabrício C. de Oliveira (UTFPR), 2026-10.
 ******************************************************************************/

// --- Parâmetros -------------------------------------------------------------------------------------
var ANOS = [2000, 2020];
var USAR_MODELOS_SALVOS = true;          // true: carrega os modelos já treinados (rápido); false: treina aqui
var MODELOS = 'projects/fcoliveira/assets/SOC_C3_FABRICIO/modelos/rf_';   // gerados por gee_modelos.py
// Versão C: o modelo sem limite de nós (41,7 MB) não cabe na memória do mapa interativo; na tela usa-se o de
// 1.000 folhas por árvore (6,8 MB; MEC 0,248 contra 0,251 na validação espacial) e na exportação o completo.
var MODELO_C_MAPA = 'C_decenal_1000';        // ou 'C_decenal_3000' (18,9 MB, mais lento)
var MODELO_C_EXPORT = 'C_decenal_profundo';  // sem limite de nós (só em exportação)
var NUM_ARVORES = 300;                   // só para USAR_MODELOS_SALVOS = false
var MAXNODES_PROFUNDO = null;            // null = sem limite (versão C)
var USAR_MASCARA_AREIA = false;          // MB_2024_SANDMASK (exige acesso ao asset)

var EXPORTAR = false;                    // true: uma tarefa por ano e versão
var ESCALA_EXPORT = 30;                  // 30 m como o produto; 250 m para uma prévia nacional rápida
var REGIAO_EXPORT = null;                // null = Brasil (extensão do mapa oficial); ou desenhe uma geometria
var SAIDA = 'projects/fcoliveira/assets/SOC_C3_FABRICIO/simulacao_mapas';   // ImageCollection

var TREINO = 'projects/fcoliveira/assets/SOC_C3_FABRICIO/matriz_soc_c3_fabricio_treino';
var OFICIAL = 'projects/mapbiomas-workspace/SOLOS/PRODUTOS_C03/mapbiomas_soil_collection3_soc_t_ha_000_030cm';
var COV = 'projects/mapbiomas-workspace/SOLOS/COVARIAVEIS/';

// --- Matriz de treino e filtros (idênticos ao script da trainingFinal) --------------------------------
var datatraining_all = ee.FeatureCollection(TREINO);
function descartar(fc, filtro) { return fc.filter(filtro.not()); }
var datatraining = datatraining_all;
datatraining = descartar(datatraining, ee.Filter.and(ee.Filter.eq('PSEUDOROCK_index', 1), ee.Filter.eq('afloramento', 0)));
datatraining = descartar(datatraining, ee.Filter.and(ee.Filter.eq('PSEUDOSAND_index', 1), ee.Filter.eq('areia', 0)));
datatraining = descartar(datatraining, ee.Filter.and(ee.Filter.eq('PSEUDOROCK_index', 1), ee.Filter.gt('mb_ndvi_median_decay', 147)));
datatraining = descartar(datatraining, ee.Filter.and(ee.Filter.eq('PSEUDOROCK_index', 1), ee.Filter.gt('black_soil_prob', 10)));
datatraining = descartar(datatraining, ee.Filter.and(ee.Filter.eq('PSEUDOROCK_index', 1), ee.Filter.gt('argila_000_030cm', 0)));
datatraining = descartar(datatraining, ee.Filter.and(ee.Filter.eq('PSEUDOSAND_index', 1), ee.Filter.gt('argila_000_030cm', 0)));
datatraining = descartar(datatraining, ee.Filter.and(ee.Filter.eq('PSEUDOSAND_index', 1), ee.Filter.gt('black_soil_prob', 10)));
datatraining = descartar(datatraining, ee.Filter.and(ee.Filter.eq('PSEUDOSAND_index', 1), ee.Filter.gt('Wetsols', 10)));
// 'resingas' como no original: a propriedade não existe e o filtro remove todo o IFN e todo o YEAR_index -26
datatraining = descartar(datatraining, ee.Filter.and(ee.Filter.eq('IFN_index', 1), ee.Filter.gt('resingas', 0)));
datatraining = descartar(datatraining, ee.Filter.and(ee.Filter.eq('YEAR_index', -26), ee.Filter.gt('resingas', 0)));
datatraining = descartar(datatraining, ee.Filter.and(ee.Filter.gt('black_soil_prob', 10), ee.Filter.gt('areia', 0)));
datatraining = descartar(datatraining, ee.Filter.and(ee.Filter.gt('black_soil_prob', 10), ee.Filter.gt('areia_000_030cm', 70)));
datatraining = descartar(datatraining, ee.Filter.and(ee.Filter.eq('PSEUDOSAND_index', 0), ee.Filter.eq('PSEUDOROCK_index', 0),
                                                     ee.Filter.lt('mb_evi2_median_decay', 100), ee.Filter.gt('Water_40y_recurrence', 0)));
print('Linhas de treino (esperado 27.425):', datatraining.size());

// --- Covariáveis (listas do script da trainingFinal) ---------------------------------------------------
var KOPPEN = ['koppen_l1_A', 'koppen_l2_Af', 'koppen_l2_Am', 'koppen_l2_As', 'koppen_l2_Aw', 'koppen_l3_Bsh',
              'koppen_l1_C', 'koppen_l2_Cf', 'koppen_l3_Cfa', 'koppen_l3_Cfb', 'koppen_l2_Cw', 'koppen_l3_Cwa',
              'koppen_l3_Cwb'];
var INDICES = ['profundidade', 'IFN_index', 'YEAR_index', 'PSEUDOROCK_index', 'PSEUDOSAND_index'];
var ESTATICAS = [
  'areia_000_030cm', 'silte_000_030cm', 'argila_000_030cm',
  'Ferralsols', 'Histosols', 'Nitisols', 'Vertisols', 'Plinthosols', 'Humisols', 'Sandysols', 'Thinsols', 'Wetsols',
  'PLANOSSOLO', 'CHERNOSSOLO', 'LATOSSOLO', 'PLINTOSSOLO', 'GLEISSOLO', 'LUVISSOLO', 'NITOSSOLO', 'ESPODOSSOLO',
  'ARGISSOLO', 'ORGANOSSOLO', 'CAMBISSOLO', 'NEOSSOLO_FLUVICO', 'NEOSSOLO_QUARTZARENICO', 'NEOSSOLO_LITOLICO',
  'sibcs_rasos', 'sibcs_btextural', 'sibcs_esqueleto', 'sibcs_homogeneo', 'sibcs_argiloso', 'black_soil_prob',
  'slope', 'convergence', 'cti', 'eastness', 'northness', 'spi', 'dev_magnitude', 'dev_scale', 'cross_sectional',
  'longitudinal_curvature', 'elevation',
  'Amazonia', 'Caatinga', 'Cerrado', 'Mata_Atlantica', 'Pampa', 'Pantanal', 'Zona_Costeira',
  'Campinarana', 'Estepe', 'Floresta_Estacional_Decidual', 'Floresta_Estacional_Semidecidual',
  'Floresta_Estacional_Sempre_Verde', 'Floresta_Ombrofila_Aberta', 'Floresta_Ombrofila_Densa',
  'Floresta_Ombrofila_Mista', 'Formacao_Pioneira', 'Savana', 'Savana_Estepica',
  'Amazonas_Solimoes_Provincia', 'Amazonia_Provincia', 'Borborema_Provincia', 'Cobertura_Cenozoica_Provincia',
  'Costeira_Margem_Continental_Provincia', 'Mantiqueira_Provincia', 'Parecis_Provincia', 'Parnaiba_Provincia',
  'Reconcavo_Tucano_Jatoba_Provincia', 'Sao_Francisco_Provincia', 'Tocantis_Provincia',
  'sedimentos', 'sedimentares', 'vulcanicas', 'metamorficas',
  'pantanal_plintossolo', 'pantanal_neossolo_quartzarenico', 'pantanal_gleissolo', 'pantanal_planossolo',
  'caatinga_latossolo', 'latossolo_vulcanicas', 'latossolo_sedimentares', 'latossolo_sedimentos',
  'argissolo_metamorficas', 'argissolo_sedimentares', 'argissolo_sedimentos', 'raso_vulcanica', 'raso_sedimentares',
  'pantanal_sedimentos', 'amazonia_sedimentos', 'cerrado_sedimentos', 'caatinga_sedimentos',
  'mata_atlantica_sedimentos', 'Distance_to_sand_v33', 'Distance_to_rock_v33', 'Area_Estavel'
];
var DINAMICAS = ['mb_ndvi_median_decay', 'mb_evi2_median_decay', 'formacaoFlorestal', 'outrasFormacoesFlorestais',
                 'formacaoCampestre', 'formacaoSavanica', 'campoAlagadoAreaPantanosa', 'restingas', 'afloramento',
                 'vegNatural', 'lavouras', 'pastagem', 'silvicultura', 'mosaicoDeUsos', 'agropecuaria', 'areia'];
var DECENAIS = ['dec_tmean', 'dec_prec', 'dec_cdd'];

var ENTRADAS_OFICIAL = INDICES.concat(ESTATICAS, KOPPEN, DINAMICAS);     // as 131 da produção
var ENTRADAS_DECENAL = INDICES.concat(ESTATICAS, DINAMICAS, DECENAIS);   // Köppen -> decenal (121)

// --- Modelos -----------------------------------------------------------------------------------------
function floresta(maxNodes) {
  var p = {numberOfTrees: NUM_ARVORES, variablesPerSplit: 24, minLeafPopulation: 2, bagFraction: 0.632, seed: 2021};
  if (maxNodes !== null) p.maxNodes = maxNodes;
  return ee.Classifier.smileRandomForest(p).setOutputMode('REGRESSION');
}
// Treinar 300 árvores profundas a cada tile estoura o tempo do mapa interativo ("Computation timed out"):
// por isso os três modelos foram treinados uma vez (mesmo treino, mesmos parâmetros) e salvos como asset.
var VERSOES = USAR_MODELOS_SALVOS ? {
  A_oficial_koppen: ee.Classifier.load(MODELOS + 'A_oficial_koppen'),
  B_decenal: ee.Classifier.load(MODELOS + 'B_decenal'),
  C_decenal_profundo: ee.Classifier.load(MODELOS + MODELO_C_MAPA)
} : {
  A_oficial_koppen: floresta(40).train(datatraining, 'carbono_gm2_qmap', ENTRADAS_OFICIAL),
  B_decenal: floresta(40).train(datatraining, 'carbono_gm2_qmap', ENTRADAS_DECENAL),
  C_decenal_profundo: floresta(MAXNODES_PROFUNDO).train(datatraining, 'carbono_gm2_qmap', ENTRADAS_DECENAL)
};
var C_EXPORT = USAR_MODELOS_SALVOS ? ee.Classifier.load(MODELOS + MODELO_C_EXPORT) : VERSOES.C_decenal_profundo;

// --- Covariáveis no ano -------------------------------------------------------------------------------
var modulo = require('users/taciaraz/mapbiomas_solo:collection3/carbon/0_covariate_source');
var estaticas = modulo.static_covariates().addBands(ee.Image.cat([
  ee.Image.constant(30).int16().rename('profundidade'),
  ee.Image.constant(0).int16().rename('IFN_index'),
  ee.Image.constant(0).int16().rename('YEAR_index'),
  ee.Image.constant(0).int16().rename('PSEUDOROCK_index'),
  ee.Image.constant(0).int16().rename('PSEUDOSAND_index')
]));
var dinamicas = modulo.dynamic_covariates();

// Vazios das grades de 0,1° (litoral) = média dos vizinhos numa janela de 7 x 7 células (igual à matriz).
function preencher(img) {
  return img.unmask(img.focalMean(3, 'square', 'pixels').reproject(img.projection()));
}
function decenal(ano) {
  function um(col, banda, nome) {
    return preencher(ee.Image(ee.ImageCollection(col).filter(ee.Filter.eq('year', ano)).first()).select([banda], [nome]));
  }
  return ee.Image.cat([
    um(COV + 'GT_DECADE_TMEAN_CONTI_2026', 'tmean_10yr_mean', 'dec_tmean'),
    um(COV + 'GT_DECADE_PRECIPITATION_CONTI_2026', 'prec_10yr_mean', 'dec_prec'),
    um('projects/fcoliveira/assets/Climas2/CDD_DECENAL_BRDWGD', 'cdd_10yr_mean', 'dec_cdd')
  ]);
}
function covariaveis(ano) {
  return estaticas
    .addBands(ee.Image(dinamicas.filter(ee.Filter.eq('year', ano)).first()))
    .addBands(decenal(ano));
}

// --- Predição e pós-processamento (como em carbon/2_model_prediction) -----------------------------------
var lulc = ee.Image('projects/mapbiomas-public/assets/brazil/lulc/collection10/mapbiomas_brazil_collection10_integration_v2');
var textura = ee.Image('projects/mapbiomas-workspace/SOLOS/PRODUTOS_C03/mapbiomas_soil_collection3_textural_group')
  .select('textural_group_000_030cm');
// Área do produto: a do próprio mapa oficial da C3 (o contorno dos biomas em AUXILIAR não é legível).
var oficial = ee.Image(OFICIAL);
var mascaraBrasil = oficial.select(0).mask().selfMask();

function prever(nome, ano, classificador) {
  var uso = lulc.select('classification_' + ano);
  var zeros = ee.Image()
    .blend(uso.eq(23).selfMask()).blend(uso.eq(24).selfMask()).blend(uso.eq(30).selfMask())
    .blend(textura.eq(1).selfMask())
    .multiply(0);
  var pred = covariaveis(ano).classify(classificador || VERSOES[nome]).rename('soc_t_ha');
  if (USAR_MASCARA_AREIA) {
    pred = pred.blend(ee.Image(COV + 'MB_2024_SANDMASK').selfMask().multiply(1000).rename('soc_t_ha'));
  }
  return pred.blend(zeros.rename('soc_t_ha')).divide(100).round().int16()
    .updateMask(mascaraBrasil)
    .set({versao: nome, year: ano, 'system:time_start': ee.Date.fromYMD(ano, 1, 1).millis(),
          num_arvores: NUM_ARVORES, fonte: 'simulacao_mapas_soc (users/fcoliveira/mapbiomas)'});
}

// --- Mapa ---------------------------------------------------------------------------------------------
var visSOC = {min: 0, max: 120, palette: ['#fff7bc', '#fec44f', '#d95f0e', '#8c510a', '#543005', '#252525']};
var visDif = {min: -15, max: 15, palette: ['#2166ac', '#67a9cf', '#f7f7f7', '#ef8a62', '#b2182b']};
Map.setOptions('HYBRID');
Map.setCenter(-52, -14, 4);
ANOS.forEach(function (ano) {
  var of = oficial.select('carbon_' + ano);
  var a = prever('A_oficial_koppen', ano), b = prever('B_decenal', ano), c = prever('C_decenal_profundo', ano);
  Map.addLayer(of, visSOC, ano + ' SOC oficial C3', false);
  Map.addLayer(a, visSOC, ano + ' A oficial reproduzido (Köppen, maxNodes 40)', false);
  Map.addLayer(b, visSOC, ano + ' B decenal (maxNodes 40)', false);
  Map.addLayer(c, visSOC, ano + ' C decenal, árvores profundas (' + MODELO_C_MAPA + ')', ano === ANOS[ANOS.length - 1]);
  Map.addLayer(a.subtract(of), visDif, ano + ' A - oficial (conferência)', false);
  Map.addLayer(b.subtract(a), visDif, ano + ' B - A (efeito do clima decenal)', false);
  Map.addLayer(c.subtract(a), visDif, ano + ' C - A (clima + árvores profundas)', false);
});
if (ANOS.length > 1) {
  var ini = ANOS[0], fim = ANOS[ANOS.length - 1];
  Map.addLayer(oficial.select('carbon_' + fim).subtract(oficial.select('carbon_' + ini)), visDif,
               'Variação ' + ini + '-' + fim + ' oficial', false);
  Map.addLayer(prever('C_decenal_profundo', fim).subtract(prever('C_decenal_profundo', ini)), visDif,
               'Variação ' + ini + '-' + fim + ' C', false);
}

// Clique no mapa: valores das quatro versões no ponto.
var painel = ui.Panel({style: {position: 'bottom-left', width: '330px'}});
painel.add(ui.Label('Clique no mapa para ver o SOC (t/ha) no ponto'));
Map.add(painel);
Map.onClick(function (coords) {
  var pt = ee.Geometry.Point([coords.lon, coords.lat]);
  painel.clear();
  painel.add(ui.Label('Lon ' + coords.lon.toFixed(4) + ', lat ' + coords.lat.toFixed(4)));
  ANOS.forEach(function (ano) {
    var img = ee.Image.cat([
      oficial.select(['carbon_' + ano], ['oficial']),
      prever('A_oficial_koppen', ano).rename('A'),
      prever('B_decenal', ano).rename('B'),
      prever('C_decenal_profundo', ano).rename('C')
    ]);
    img.reduceRegion(ee.Reducer.first(), pt, 30).evaluate(function (v) {
      painel.add(ui.Label(ano + ': oficial ' + v.oficial + ' | A ' + v.A + ' | B ' + v.B + ' | C ' + v.C));
    });
  });
});

// --- Exportação ---------------------------------------------------------------------------------------
if (EXPORTAR) {
  var regiao = REGIAO_EXPORT || oficial.geometry().bounds();
  ANOS.forEach(function (ano) {
    Object.keys(VERSOES).forEach(function (nome) {
      var id = nome + '_' + ano + '_' + ESCALA_EXPORT + 'm';
      var clf = nome === 'C_decenal_profundo' ? C_EXPORT : VERSOES[nome];
      Export.image.toAsset({
        image: prever(nome, ano, clf),
        description: 'soc_' + id,
        assetId: SAIDA + '/' + id,
        pyramidingPolicy: {'.default': 'mean'},
        region: regiao,
        scale: ESCALA_EXPORT,
        maxPixels: 1e13
      });
    });
  });
}
