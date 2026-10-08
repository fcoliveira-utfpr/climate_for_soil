// Cópia de referência do script do MapBiomas Solo que gera a matriz c03_soc_v2025_trainingFinal
// (filtros + seleção final de covariáveis). Enviado pelo Fabrício em 08/10/2026; não está no GitHub
// público. Usado por ../covariaveis_c3.py (listas) e pelos filtros da matriz.

/*
 * MAPBIOMAS SOIL
 * @contact: contato@mapbiomas.org
 * @date: November 26, 2025
 */

// SCRIPT 2: PREDICTING AND MAPPING SOIL ORGANIC CARBON STOCK

var version_in = 'c03_soc_v2025_11_26_trep'
var seed = 2021;  // Semente para reprodutibilidade do modelo

// -------------------------
// 1. CARREGAR MATRIZ
// -------------------------
// Caminho da matriz de treinamento (todas as profundidades empilhadas)
var matriz_path = 'projects/mapbiomas-workspace/SOLOS/AMOSTRAS/MATRIZES/collection3/' + version_in;
var saida_collection = 'projects/mapbiomas-workspace/SOLOS/PRODUTOS_C03/soc/';
var t_ha = 'SOC_t_ha';
var kg_m2 = 'SOC_kg_m2';

// Carrega todas as amostras empilhadas (todas as profundidades)
var datatraining_all = ee.FeatureCollection(matriz_path);

///////////////////////////////////////////////////////////////////////////////////////////////
// Filter out pseudo-samples of rock outcrops that do not fall on rock outcrops
// Logic: PSEUDOROCK_index IS 1 AND afloramento IS 0
var conditionToRemoveRock = ee.Filter.and(
  ee.Filter.eq('PSEUDOROCK_index', 1),
  ee.Filter.eq('afloramento', 0)
);
var datatraining_filter_rock = datatraining_all.filter(conditionToRemoveRock.not());
// Removed Count: 1071

// Filter out pseudo-samples of sands that do not fall on sands
// Logic: PSEUDORSAND_index IS 1 AND areia IS 0
var conditionToRemoveSand = ee.Filter.and(
  ee.Filter.eq('PSEUDOSAND_index', 1),
  ee.Filter.eq('areia', 0)
);
var datatraining_filter_sand = datatraining_filter_rock.filter(conditionToRemoveSand.not());
// Removed Count: 273

// Filter out pseudo-samples of rock outcrops that have high NDVI values
// Logic: PSEUDOROCK_index IS 1 AND mb_ndvi_median_decay IS > 147
var conditionToRemoveNDVI = ee.Filter.and(
  ee.Filter.eq('PSEUDOROCK_index', 1),
  ee.Filter.gt('mb_ndvi_median_decay', 147)
);
var datatraining_filter_ndvi = datatraining_filter_sand.filter(conditionToRemoveNDVI.not());
// Removed Count: 420

// Filter out pseudo-samples of rock outcrops that have high black soil probability
// Logic: PSEUDOROCK_index IS 1 AND black_soil_prob IS > 10
var conditionToRemoveBlack = ee.Filter.and(
  ee.Filter.eq('PSEUDOROCK_index', 1),
  ee.Filter.gt('black_soil_prob', 10)
);
var datatraining_filter_black = datatraining_filter_ndvi.filter(conditionToRemoveBlack.not());
// Removed Count: 186

// Filter out pseudo-samples of rock outcrops that have clay content > 0
// Logic: PSEUDOROCK_index IS 1 AND argila_000_030cm IS > 0
var conditionToRemoveClay = ee.Filter.and(
  ee.Filter.eq('PSEUDOROCK_index', 1),
  ee.Filter.gt('argila_000_030cm', 0)
);
var datatraining_filter_clay = datatraining_filter_black.filter(conditionToRemoveClay.not());
// Removed Count: 45

// Filter out pseudo-samples of sand spots that have clay content > 0
// Logic: PSEUDOSAND_index IS 1 AND argila_000_030cm IS > 0
var conditionToRemoveClaySand = ee.Filter.and(
  ee.Filter.eq('PSEUDOSAND_index', 1),
  ee.Filter.gt('argila_000_030cm', 0)
);
var datatraining_filter_claysand = datatraining_filter_clay.filter(conditionToRemoveClaySand.not());
// Removed Count: 66

// Filter out pseudo-samples of sand spots that have high black soil probability
// Logic: PSEUDOSAND_index IS 1 AND black_soil_prob IS > 10
var conditionToRemoveSandBlack = ee.Filter.and(
  ee.Filter.eq('PSEUDOSAND_index', 1),
  ee.Filter.gt('black_soil_prob', 10)
);
var datatraining_filter_sandblack = datatraining_filter_claysand.filter(conditionToRemoveSandBlack.not());
// Removed Count: 462

// Filter out pseudo-samples of sand spots that have high wetsols probability
// Logic: PSEUDOSAND_index IS 1 AND Wetsols IS > 10
var conditionToRemoveSandWet = ee.Filter.and(
  ee.Filter.eq('PSEUDOSAND_index', 1),
  ee.Filter.gt('Wetsols', 10)
);
var datatraining_filter_sandwet = datatraining_filter_sandblack.filter(conditionToRemoveSandWet.not());
// Removed Count: 279

// Filter out samples from IFN that are on 'resingas'
// Logic: IFN_index IS 1 AND restingas IS > 0
var conditionToRemoveIFNrestinga = ee.Filter.and(
  ee.Filter.eq('IFN_index', 1),
  ee.Filter.gt('resingas', 0)
);
var datatraining_filter_ifnrestinga = datatraining_filter_sandwet.filter(conditionToRemoveIFNrestinga.not());

// Filter out samples with YEAR_index == -26 and restigas > 0
var conditionToRemoveYEARrestinga = ee.Filter.and(
  ee.Filter.eq('YEAR_index', -26),
  ee.Filter.gt('resingas', 0)
);
var datatraining_filter_yearrestinga = datatraining_filter_ifnrestinga.filter(conditionToRemoveYEARrestinga.not());

// Filter out samples with black_soil_prob > 10 and areia > 0
var conditionToRemoveBlackSand = ee.Filter.and(
  ee.Filter.gt('black_soil_prob', 10),
  ee.Filter.gt('areia', 0)
);
var datatraining_filter_blacksand = datatraining_filter_yearrestinga.filter(conditionToRemoveBlackSand.not());

// Filter out samples with black_soil_prob > 10 and areia_000_030cm > 70
var conditionToRemoveBlackSandy = ee.Filter.and(
  ee.Filter.gt('black_soil_prob', 10),
  ee.Filter.gt('areia_000_030cm', 70)
);
var datatraining_filter_blacksandy = datatraining_filter_blacksand.filter(conditionToRemoveBlackSandy.not());

// Filter out samples with PSEUDOSAND_index == 0 and PSEUDOROCK_index == 0 and
// mb_evi2_median_decay < 100 and Water_40y_recurrence > 0
var conditionToRemoveWater = ee.Filter.and(
  ee.Filter.eq('PSEUDOSAND_index', 0),
  ee.Filter.eq('PSEUDOROCK_index', 0),
  ee.Filter.lt('mb_evi2_median_decay', 100),
  ee.Filter.gt('Water_40y_recurrence', 0)
);
var datatraining_filter_water = datatraining_filter_blacksandy.filter(conditionToRemoveWater.not());

var datatraining = datatraining_filter_water;

// ======================================================
var lulc = ee.Image('projects/mapbiomas-public/assets/brazil/lulc/collection10/mapbiomas_brazil_collection10_integration_v2');
var col3_texture = ee.Image('projects/mapbiomas-workspace/SOLOS/PRODUTOS_C03/mapbiomas_soil_collection3_textural_group');
var sand_mask = ee.Image('projects/mapbiomas-workspace/SOLOS/COVARIAVEIS/MB_2024_SANDMASK');
// ======================================================

// -------------------------
// 2. DEFINIR TARGETS
// -------------------------
// Atençao - o id foi adicionado para construir a matriz final apenas.
var targets = [
  'carbono_gm2',
  'carbono_gm2_qmap',
  'id',
  'ano'
];

// -------------------------
// 3. DEFINIR AS COVARIÁVEIS DE TREINO
// -------------------------
var allProps = ee.Feature(datatraining.first()).propertyNames();

var covariates_names_static  = [
  // profundidade alvo
  'profundidade',
  // Indicadores
  'IFN_index',
  'YEAR_index',
  'PSEUDOROCK_index',
  'PSEUDOSAND_index',
  // predição da coleção atual
  'areia_000_030cm',
  'silte_000_030cm',
  'argila_000_030cm',
  // classes de solo WRB (probabilidade)
  'Ferralsols', 'Histosols', 'Nitisols', 'Vertisols', 'Plinthosols',
 // 'Argisols',
  'Humisols', 'Sandysols', 'Thinsols', 'Wetsols',
  // Pedologia IBGE
  'PLANOSSOLO', 'CHERNOSSOLO', 'LATOSSOLO', 'PLINTOSSOLO',
  'GLEISSOLO',
  // 'VERTISSOLO', // Zero importance for random forest
  'LUVISSOLO', 'NITOSSOLO',
  'ESPODOSSOLO', 'ARGISSOLO', 'ORGANOSSOLO', 'CAMBISSOLO',
  'NEOSSOLO_FLUVICO', 'NEOSSOLO_QUARTZARENICO',
  // 'NEOSSOLO_REGOLITICO', // Near-zero variance covariate in the design matrix
  'NEOSSOLO_LITOLICO',
  'sibcs_rasos',
  'sibcs_btextural',
  'sibcs_esqueleto',
  'sibcs_homogeneo',
  'sibcs_argiloso',
  // black soils
  'black_soil_prob',
  // morfometria / relevo
  'slope',
  'convergence',
  'cti',
  'eastness',
  'northness',
  // 'roughness', // high correlation with slope and elev_stdev in the design matrix
  'spi',
  // 'elev_stdev', // high correlation with slope and roughness in the design matrix
  'dev_magnitude',
  'dev_scale',
  'cross_sectional',
  'longitudinal_curvature',
  // altitude
  'elevation',
  // clima Köppen
  'koppen_l1_A',
  'koppen_l2_Af',
  'koppen_l2_Am',
  'koppen_l2_As',
  'koppen_l2_Aw',
  // 'koppen_l1_B', // Exactly coincident with koppen_l2_Bs and koppen_l3_Bsh
  // 'koppen_l2_Bs', // Exactly coincident with koppen_l1_B and koppen_l3_Bsh
  'koppen_l3_Bsh',
  'koppen_l1_C',
  'koppen_l2_Cf',
  'koppen_l3_Cfa',
  'koppen_l3_Cfb',
  'koppen_l2_Cw',
  'koppen_l3_Cwa',
  'koppen_l3_Cwb',
  // 'koppen_l3_Cwc', // Zero-variance (constant) in the desing matrix
  // 'koppen_l2_Cs', // Low-sample count in the design matrix (n = 2)
  // 'koppen_l3_Csa', // Low-sample count in the design matrix (n = 2)
  // 'koppen_l3_Csb', // Zero-variance (constant) in the desing matrix
  // biomas IBGE
  'Amazonia',
  'Caatinga',
  'Cerrado',
  'Mata_Atlantica',
  'Pampa',
  'Pantanal',
  'Zona_Costeira',
  // fitofisionomias IBGE
  'Campinarana',
  'Estepe',
  'Floresta_Estacional_Decidual',
  'Floresta_Estacional_Semidecidual',
  'Floresta_Estacional_Sempre_Verde',
  'Floresta_Ombrofila_Aberta',
  'Floresta_Ombrofila_Densa',
  'Floresta_Ombrofila_Mista',
  'Formacao_Pioneira',
  'Savana',
  'Savana_Estepica',
  // províncias estruturais (IBGE)
  'Amazonas_Solimoes_Provincia',
  'Amazonia_Provincia',
  'Borborema_Provincia',
  'Cobertura_Cenozoica_Provincia',
  'Costeira_Margem_Continental_Provincia',
  // 'Gurupi_Provincia', // Low-sample count in the design matrix (n = 3)
  'Mantiqueira_Provincia',
//  'Parana_Provincia',
  'Parecis_Provincia',
  'Parnaiba_Provincia',
  'Reconcavo_Tucano_Jatoba_Provincia',
  'Sao_Francisco_Provincia',
  // 'Sao_Luis_Provincia', // Low-sample count in the design matrix (n = 8)
  'Tocantis_Provincia',
  // subprovíncias (litologia)
  'sedimentos',
  'sedimentares',
  'vulcanicas',
  // 'plutonicas', // Zero importance for random forest
  'metamorficas',
  // ocorrência conjunta de bioma e solo
  'pantanal_plintossolo',
  'pantanal_neossolo_quartzarenico',
  'pantanal_gleissolo',
  'pantanal_planossolo',
  'caatinga_latossolo',
  // ocorrência conjunta de solo e litologia
  'latossolo_vulcanicas',
  'latossolo_sedimentares',
  'latossolo_sedimentos',
  // 'latossolo_metamorficas', // Zero importance for random forest
  // 'latossolo_plutonicas', // Low-sample count in the design matrix (n = 7)
  'argissolo_metamorficas',
  'argissolo_sedimentares',
  'argissolo_sedimentos',
  'raso_vulcanica',
  'raso_sedimentares',
  // 'raso_plutonica', // Zero importance for random forest
  // ocorrência conjunta de bioma e litologia
  'pantanal_sedimentos',
  'amazonia_sedimentos',
  'cerrado_sedimentos',
  // 'pampa_sedimentos', // Zero importance for random forest
  'caatinga_sedimentos',
  'mata_atlantica_sedimentos',
  // Distâncias Euclidianas
  'Distance_to_sand_v33', // dunas, praias e areiais
  'Distance_to_rock_v33', // afloramentos de rocha
  // 'latitude',
  // 'longitude',
  // 'Water_40y_recurrence', // many issues in the data creating empty areas on steep land surfaces
  // estabilidade de LULC
  'Area_Estavel'
]

var covariates_names_dynamic  = [
  'mb_ndvi_median_decay',
  'mb_evi2_median_decay',
  // 'mb_savi_median_decay', // high correlation with mb_evi2_median_decay in the design matrix
  // 'mb_edges', // The data is not ready for use: agricultural areas and large forests have the same value
  // 'mb_water_accumulate_dynamic',
  // 'mb_water_recurrence_dynamic', // high correlation with mb_edges in the design matrix (WHY?)
  // 'mb_fire_accumulate_dynamic',
  // 'mb_fireRecurrence', // high correlation with mb_fire_time_after_fire in the design matrix
  // 'mb_fire_time_after_fire',
  'formacaoFlorestal',
  'outrasFormacoesFlorestais',
  'formacaoCampestre',
  'formacaoSavanica',
  'campoAlagadoAreaPantanosa',
  'restingas',
  'afloramento',
  'vegNatural',
  // 'lavourasTemp', // high correlation with lavouras in the design matrix
  // 'lavourasPerene', // Near-zero variance in the design matrix
  'lavouras',
  'pastagem',
  'silvicultura',
  'mosaicoDeUsos',
  'agropecuaria',
  'areia',
];

var covariatesModule = require('users/taciaraz/mapbiomas_solo:collection3/carbon/0_covariate_source');
var static_image  = covariatesModule.static_covariates();
var dynamic_images = covariatesModule.dynamic_covariates();

// Covariáveis constantes de apoio (usadas no mapa: profundidade 30 cm e índices 0)
var profundidade_img    = ee.Image.constant(30).int16().rename('profundidade');
var IFN_index_img     = ee.Image.constant(0).int16().rename('IFN_index');
var YEAR_index_img    = ee.Image.constant(0).int16().rename('YEAR_index');
var PSEUDOROCK_index_img    = ee.Image.constant(0).int16().rename('PSEUDOROCK_index');
var PSEUDOSAND_index_img    = ee.Image.constant(0).int16().rename('PSEUDOSAND_index');

var constant_indices = ee.Image.cat([
  profundidade_img,
  IFN_index_img,
  YEAR_index_img,
  PSEUDOROCK_index_img,
  PSEUDOSAND_index_img
]);

var staticCovariates = static_image.addBands(constant_indices);
var staticNames  = staticCovariates.bandNames();
var dynamicNames = dynamic_images.first().bandNames();

// INTERSEÇÃO MATRIZ X LISTAS DESEJADAS
var cols = datatraining.first().propertyNames();
var selectedStatic  = staticNames
  .filter( ee.Filter.inList('item', covariates_names_static) )
  .filter( ee.Filter.inList('item', cols) );
var selectedDynamic = dynamicNames
  .filter( ee.Filter.inList('item', covariates_names_dynamic) )
  .filter( ee.Filter.inList('item', cols) );
var selectedCovariates = selectedStatic.cat(selectedDynamic);

var propsUsed = selectedCovariates.sort();
var propsRemoved = cols.removeAll(propsUsed).sort();
var propsMissing = ee.List(covariates_names_static)
  .cat(ee.List(covariates_names_dynamic))
  .removeAll(cols)
  .sort();

// DEFINIÇÃO FINAL DO DATASET DE TREINO SOC
var colunasParaExportar = propsUsed.cat(targets);
var trainingFinal = datatraining.select(colunasParaExportar);
print('Total de colunas selecionadas:', colunasParaExportar.length());
print('Exemplo da primeira linha filtrada com targets:', trainingFinal.first());

var version_matrix = 'c03_soc_v2025' + '_trainingFinal';
var assetId = 'projects/mapbiomas-workspace/SOLOS/AMOSTRAS/MATRIZES/collection3/' + version_matrix;

Export.table.toDrive({
  collection: trainingFinal,
  description: version_matrix,
  folder: 'MapBiomas_Solo_Colection3',
  fileNamePrefix: 'matriz-final-' + version_matrix,
  fileFormat: 'CSV'
});
