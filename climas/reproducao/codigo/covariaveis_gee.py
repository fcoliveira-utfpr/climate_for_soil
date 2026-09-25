"""Covariáveis estáticas do modelo de textura do MapBiomas Solo C3, portadas para a API Python do GEE.

Tradução de soil_30m_landsat/collection_03beta/texture/0_covariate_source (mapbiomas/brazil-soil), função
static_covariates(), com os mesmos assets e os mesmos nomes de banda das colunas da matriz de treino. O
Köppen IPEF (L1-L3) fica numa função à parte, porque aqui ele é um dos cenários de clima.
"""
import math

import ee

COV = 'projects/mapbiomas-workspace/SOLOS/COVARIAVEIS/'
C02 = 'projects/mapbiomas-workspace/SOLOS/PRODUTOS_C02/c02v2/'
WRB = COV + 'WRB_ALL_SOILS_SOILGRIDS_30M_GAPFILL'
GEOM = COV + 'OT_GEOMORPHOMETRY_90m'

SIBCS = ['PLANOSSOLO', 'CHERNOSSOLO', 'LATOSSOLO', 'PLINTOSSOLO', 'GLEISSOLO', 'VERTISSOLO', 'LUVISSOLO',
         'NITOSSOLO', 'ESPODOSSOLO', 'ARGISSOLO', 'ORGANOSSOLO', 'CAMBISSOLO', 'NEOSSOLO_FLUVICO',
         'NEOSSOLO_QUARTZARENICO', 'NEOSSOLO_REGOLITICO', 'NEOSSOLO_LITOLICO']


def _preencher(img, nome, mascara29):
    """fillMasked do script original: onde a coleção 2 não tem valor e o uso é afloramento rochoso (29),
    usa 0."""
    m0 = img.mask()
    combinado = img.unmask().where(m0.Not().And(mascara29), 0)
    return combinado.updateMask(m0.Or(mascara29)).rename(nome)


def _grupo(img, classes, nome):
    return img.select(classes).reduce(ee.Reducer.sum()).gt(0).rename(nome)


def estaticas_textura():
    lulc = ee.Image('projects/mapbiomas-public/assets/brazil/lulc/collection10/'
                    'mapbiomas_brazil_collection10_integration_v2').select('classification_2024')
    m29 = lulc.eq(29)
    prev = ee.Image.cat([
        _preencher(ee.Image(C02 + 'mapbiomas_soil_collection2_v2_sand').select('sand_000_030cm'), 'sand_000_030cm', m29),
        _preencher(ee.Image(C02 + 'mapbiomas_soil_collection2_v2_silt').select('silt_000_030cm'), 'silt_000_030cm', m29),
        _preencher(ee.Image(C02 + 'mapbiomas_soil_collection2_v2_clay').select('clay_000_030cm'), 'clay_000_030cm', m29),
    ])

    wrb = ee.Image(WRB)
    solo = ee.Image.cat([
        wrb.select(['Ferralsols', 'Histosols', 'Nitisols', 'Vertisols', 'Plinthosols']),
        wrb.select(['Arenosols', 'Podzols']).reduce('sum').rename('Sandysols'),
        wrb.select(['Chernozems', 'Kastanozems', 'Phaeozems', 'Umbrisols']).reduce('sum').rename('Humisols'),
        wrb.select(['Leptosols', 'Regosols']).reduce('sum').rename('Thinsols'),
        wrb.select(['Alisols', 'Luvisols', 'Acrisols', 'Lixisols', 'Planosols']).reduce('sum').rename('Argisols'),
        wrb.select(['Gleysols', 'Planosols', 'Stagnosols']).reduce('sum').rename('Wetsols'),
        ee.Image(COV + 'FAO_2022_BLACKSOIL_1KM').rename('black_soil_prob'),
    ])

    sibcs = ee.Image(COV + 'IBGE_2023_PEDOLOGIA_250MIL_2025').select(SIBCS).unmask(0)
    rasos = _grupo(sibcs, ['NEOSSOLO_REGOLITICO', 'NEOSSOLO_LITOLICO', 'CAMBISSOLO'], 'sibcs_rasos')
    grupos_sibcs = ee.Image.cat([
        rasos,
        _grupo(sibcs, ['NEOSSOLO_REGOLITICO', 'NEOSSOLO_LITOLICO'], 'sibcs_neossolo'),
        _grupo(sibcs, ['PLANOSSOLO', 'PLINTOSSOLO', 'ARGISSOLO', 'LUVISSOLO'], 'sibcs_btextural'),
        _grupo(sibcs, ['PLINTOSSOLO', 'CAMBISSOLO', 'NEOSSOLO_FLUVICO'], 'sibcs_esqueleto'),
        _grupo(sibcs, ['NEOSSOLO_QUARTZARENICO', 'GLEISSOLO'], 'sibcs_homogeneo'),
        _grupo(sibcs, ['LATOSSOLO', 'NITOSSOLO'], 'sibcs_argiloso'),
    ])

    sub = ee.Image(COV + 'IBGE_PROVINCIAIS_ESTRUTURAIS_250mil_2025_tmp/subprovincias_prob')
    sedimentos = sub.select(['Sedimentos_Subprovincia']).reduce(ee.Reducer.sum()).gt(0).rename('sedimentos')
    sedimentares = sub.select('Sedimentares_Subprovincia').rename('sedimentares')
    vulcanicas = sub.select('Vulcanicas_Subprovincia').rename('vulcanicas')
    plutonicas = sub.select('Plutonicas_Subprovincia').rename('plutonicas')
    metamorficas = sub.select('Metamorficas_Subprovincia').rename('metamorficas')
    geologia = ee.Image.cat([
        sedimentos,
        sub.select(['Sedimentares_Subprovincia', 'Sedimentares_Subprovincia_prob']).reduce('sum').rename('sedimentares_prob'),
        sub.select(['Vulcanicas_Subprovincia', 'Vulcanicas_Subprovincia_prob']).reduce('sum').rename('vulcanicas_prob'),
        sub.select(['Plutonicas_Subprovincia', 'Plutonicas_Subprovincia_prob']).reduce('sum').rename('plutonicas_prob'),
        sub.select(['Metamorficas_Subprovincia', 'Metamorficas_Subprovincia_prob']).reduce('sum').rename('metamorficas_prob'),
        sedimentares, vulcanicas, plutonicas, metamorficas,
    ])

    bioma = ee.Image(COV + 'IBGE_2019_BIOMAS_ZC_250MIL')
    lat_, arg_ = sibcs.select('LATOSSOLO'), sibcs.select('ARGISSOLO')
    combinacoes = ee.Image.cat([
        bioma.select('Pantanal').multiply(sibcs.select('PLINTOSSOLO')).rename('pantanal_plintossolo'),
        bioma.select('Pantanal').multiply(sibcs.select('NEOSSOLO_QUARTZARENICO')).rename('pantanal_neossolo_quartzarenico'),
        bioma.select('Pantanal').multiply(sibcs.select('GLEISSOLO')).rename('pantanal_gleissolo'),
        bioma.select('Pantanal').multiply(sibcs.select('PLANOSSOLO')).rename('pantanal_planossolo'),
        bioma.select('Caatinga').multiply(lat_).rename('caatinga_latossolo'),
        lat_.multiply(vulcanicas).rename('latossolo_vulcanicas'),
        lat_.multiply(sedimentares).rename('latossolo_sedimentares'),
        lat_.multiply(sedimentos).rename('latossolo_sedimentos'),
        lat_.multiply(metamorficas).rename('latossolo_metamorficas'),
        lat_.multiply(plutonicas).rename('latossolo_plutonicas'),
        arg_.multiply(metamorficas).rename('argissolo_metamorficas'),
        arg_.multiply(sedimentares).rename('argissolo_sedimentares'),
        arg_.multiply(sedimentos).rename('argissolo_sedimentos'),
        rasos.multiply(vulcanicas).rename('raso_vulcanica'),
        rasos.multiply(sedimentares).rename('raso_sedimentares'),
        rasos.multiply(plutonicas).rename('raso_plutonica'),
        bioma.select('Pantanal').multiply(sedimentos).rename('pantanal_sedimentos'),
        bioma.select('Amazonia').multiply(sedimentos).rename('amazonia_sedimentos'),
        bioma.select('Cerrado').multiply(sedimentos).rename('cerrado_sedimentos'),
        bioma.select('Pampa').multiply(sedimentos).rename('pampa_sedimentos'),
        bioma.select('Caatinga').multiply(sedimentos).rename('caatinga_sedimentos'),
        bioma.select('Mata_Atlantica').multiply(sedimentos).rename('mata_atlantica_sedimentos'),
    ])

    g = ee.Image(GEOM)
    declive = g.select('slope').multiply(math.pi / 180).tan().multiply(100).round().rename('slope')
    relevo = ee.Image.cat([
        ee.Image('MERIT/DEM/v1_0_3').select(['dem'], ['elevation']).int16(),
        declive,
        g.select('convergence').round(),
        g.select('cti').multiply(10).round(),
        g.select('eastness').multiply(100).round(),
        g.select('northness').multiply(100).round(),
        g.select('roughness').round(),
        g.select('spi').add(1).log10().multiply(100).round().rename('spi'),
        g.select('elev_stdev').round(),
        g.select('dev_magnitude').round(),
        g.select('dev_scale').round(),
    ])
    curv = ee.Image('projects/ee-barbaracosta/assets/soc_mapping/brasil_curvaturas_15x15')
    curvaturas = ee.Image.cat([curv.select('b1').rename('cross_sectional').round(),
                               curv.select('b2').rename('longitudinal_curvature').round()])

    return ee.Image.cat([
        prev, solo, sibcs, grupos_sibcs,
        ee.Image(COV + 'IBGE_PROVINCIAIS_ESTRUTURAIS_250mil_2025/IBGE_PROVINCIAS_250MIL_DUMMY'),
        geologia, combinacoes, relevo, curvaturas, bioma,
        ee.Image(COV + 'IBGE_2023_FITOFISIONOMIA_250MIL_2025'),
        ee.Image(COV + 'DISTANCE_C10_v3/distance_afloramento_rochoso_c10_v3_fd7000_md7000').rename('Distance_to_rock_v33'),
        ee.Image(COV + 'DISTANCE_C10_v3/distance_praia_duna_areal_c10_v3_fd7000_md7000').rename('Distance_to_sand_v33'),
        ee.Image(COV + 'MB_2024_C10_WATER/MB_2024_C10_STATIC_WATER_RECURRENCE_1985_2024').rename('Water_40y_recurrence'),
    ])


def koppen_ipef():
    """Köppen IPEF em dummies L1-L3 (bandas koppen_l1_A, ...), como nos modelos do MapBiomas."""
    base = COV + 'IPEF_2013_KOPPEN_100M_2025/'
    return ee.Image.cat([ee.Image(base + n) for n in ('koppen_l1', 'koppen_l2', 'koppen_l3')])


# --- SOC: covariáveis que o modelo de carbono usa além das da textura ---------------------------------
# Nomes da matriz matriz-collection3_carbon_datac2v2 (versão anterior do módulo de carbono). Conferido
# contra a matriz (300 linhas, ano de cada linha): todas iguais em 100% (antropico = agropecuaria).
IDADES_LULC = {'antropico': 'agropecuaria', 'natural': 'natural', 'formacaoFlorestal': 'formacaoFlorestal',
               'formacaoSavanica': 'formacaoSavanica', 'formacaoCampestre': 'formacaoCampestre',
               'campoAlagadoAreaPantanosa': 'campoAlagadoAreaPantanosa', 'lavouras': 'lavouras',
               'pastagem': 'pastagem', 'mosaicoDeUsos': 'mosaicoDeUsos', 'silvicultura': 'silvicultura',
               'outrasFormacoesFlorestais': 'outrasFormacoesFlorestais', 'restingas': 'restingas'}
FOGO = 'projects/mapbiomas-public/assets/brazil/fire/collection4_1/mapbiomas_fire_collection41_accumulated_burned_v1'


def extras_soc(ano):
    """Covariáveis do SOC fora da pilha de textura, para um ano (idades de uso, índices com decaimento,
    bordas, recorrência de água e de fogo, áreas estáveis e subprovíncias geológicas)."""
    ag = ee.ImageCollection(COV + 'MB_2024_AGELULC_C10_v2')
    idades = [ag.filter(ee.Filter.eq('index', idx)).mosaic().select([f'{idx}_{ano}'], [nome])
              for nome, idx in IDADES_LULC.items()]
    dec = ee.ImageCollection(COV + 'LANDSAT_MB_INDICES_DECAY').filter(ee.Filter.eq('year', ano)).first()
    return ee.Image.cat(idades + [
        dec.select(['mb_ndvi_median_decay', 'mb_evi2_median_decay', 'mb_savi_median_decay']),
        ee.Image(COV + 'MB_DEGRADATION_BETA_SUMMED_EDGES').select(f'edge_sum_{ano}').unmask(0).rename('mb_summed_edges'),
        ee.Image(COV + 'MB_2024_C10_WATER/MB_2024_DYNAMIC_WATER_RECURRENCE')
            .select(f'water_recurrence_1985_{ano}').unmask(0).rename('mb_water_recurrence_dynamic'),
        ee.Image(FOGO).select(f'fire_accumulated_1985_{ano}').unmask(0).rename('mb_fire_recurrence_dynamic'),
        ee.Image(COV + 'MB_2024_STABLEAREAS_C10').unmask(0).rename('Area_Estavel'),
        ee.Image(COV + 'IBGE_PROVINCIAIS_ESTRUTURAIS_250mil_2025/subprovincias'),
    ])
