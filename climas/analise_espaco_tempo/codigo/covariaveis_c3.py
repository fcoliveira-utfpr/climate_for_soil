"""Covariáveis do modelo de SOC do MapBiomas Solo C3, portadas para a API Python do GEE.

Tradução de soil_30m_landsat/collection_03beta/carbon/0_covariate_source (mapbiomas/brazil-soil, versão
2025-10-23), funções static_covariates() e dynamic_covariates(), com os mesmos assets, a mesma ordem de
bandas e os mesmos nomes. As listas de bandas usadas na matriz são as covariates_names_static/dynamic do
script que gera c03_soc_v2025_trainingFinal (referencia/soc_trainingFinal_c3_2025_11_26.js); as bandas de
imagem coincidem com as de carbon/1_data_matrix (versão c03_soc_v2025_11_24), que arredonda tudo antes de
amostrar. As cinco colunas restantes da lista estática (INDICES_PONTOS) vêm dos pontos, não de imagens.

Desvios do original, todos por falta de acesso desta conta:
- recorrência de fogo: o asset do workspace (FOGO_COL4/2_Subprodutos_col41/...) não abre; usa-se a cópia
  pública da coleção 4.1 (mesmo produto, mesmas bandas).
"""
import math

import ee

COV = 'projects/mapbiomas-workspace/SOLOS/COVARIAVEIS/'
PSD = 'projects/mapbiomas-workspace/SOLOS/PRODUTOS_C03/psd_final/'
WRB = COV + 'WRB_ALL_SOILS_SOILGRIDS_30M_GAPFILL'
GEOM = COV + 'OT_GEOMORPHOMETRY_90m'
FOGO_ACUM = 'projects/mapbiomas-public/assets/brazil/fire/collection4_1/mapbiomas_fire_collection41_accumulated_burned_v1'
FOGO_TAF = 'projects/mapbiomas-public/assets/brazil/fire/collection4_1/mapbiomas_fire_collection41_time_after_fire_v1'
MOSAICOS = 'projects/nexgenmap/MapBiomas2/LANDSAT/BRAZIL/mosaics-2'
BORDAS = 'projects/mapbiomas-brazil/assets/DEGRADATION/COLLECTION-10/edge-area'

SIBCS = ['PLANOSSOLO', 'CHERNOSSOLO', 'LATOSSOLO', 'PLINTOSSOLO', 'GLEISSOLO', 'VERTISSOLO', 'LUVISSOLO',
         'NITOSSOLO', 'ESPODOSSOLO', 'ARGISSOLO', 'ORGANOSSOLO', 'CAMBISSOLO', 'NEOSSOLO_FLUVICO',
         'NEOSSOLO_QUARTZARENICO', 'NEOSSOLO_REGOLITICO', 'NEOSSOLO_LITOLICO']

# --- Listas da matriz (referencia/soc_trainingFinal_c3_2025_11_26.js) ------------------------------------
# Colunas da lista estática que são propriedades dos pontos (no mapa: profundidade 30 e índices 0).
INDICES_PONTOS = ['profundidade', 'IFN_index', 'YEAR_index', 'PSEUDOROCK_index', 'PSEUDOSAND_index']
KOPPEN = ['koppen_l1_A', 'koppen_l2_Af', 'koppen_l2_Am', 'koppen_l2_As', 'koppen_l2_Aw', 'koppen_l3_Bsh',
          'koppen_l1_C', 'koppen_l2_Cf', 'koppen_l3_Cfa', 'koppen_l3_Cfb', 'koppen_l2_Cw', 'koppen_l3_Cwa',
          'koppen_l3_Cwb']
ESTATICAS = [
    'areia_000_030cm', 'silte_000_030cm', 'argila_000_030cm',
    'Ferralsols', 'Histosols', 'Nitisols', 'Vertisols', 'Plinthosols',
    'Humisols', 'Sandysols', 'Thinsols', 'Wetsols',
    'PLANOSSOLO', 'CHERNOSSOLO', 'LATOSSOLO', 'PLINTOSSOLO', 'GLEISSOLO', 'LUVISSOLO', 'NITOSSOLO',
    'ESPODOSSOLO', 'ARGISSOLO', 'ORGANOSSOLO', 'CAMBISSOLO', 'NEOSSOLO_FLUVICO', 'NEOSSOLO_QUARTZARENICO',
    'NEOSSOLO_LITOLICO',
    'sibcs_rasos', 'sibcs_btextural', 'sibcs_esqueleto', 'sibcs_homogeneo', 'sibcs_argiloso',
    'black_soil_prob',
    'slope', 'convergence', 'cti', 'eastness', 'northness', 'spi', 'dev_magnitude', 'dev_scale',
    'cross_sectional', 'longitudinal_curvature',
    'elevation',
] + KOPPEN + [
    'Amazonia', 'Caatinga', 'Cerrado', 'Mata_Atlantica', 'Pampa', 'Pantanal', 'Zona_Costeira',
    'Campinarana', 'Estepe', 'Floresta_Estacional_Decidual', 'Floresta_Estacional_Semidecidual',
    'Floresta_Estacional_Sempre_Verde', 'Floresta_Ombrofila_Aberta', 'Floresta_Ombrofila_Densa',
    'Floresta_Ombrofila_Mista', 'Formacao_Pioneira', 'Savana', 'Savana_Estepica',
    'Amazonas_Solimoes_Provincia', 'Amazonia_Provincia', 'Borborema_Provincia', 'Cobertura_Cenozoica_Provincia',
    'Costeira_Margem_Continental_Provincia', 'Mantiqueira_Provincia', 'Parecis_Provincia', 'Parnaiba_Provincia',
    'Reconcavo_Tucano_Jatoba_Provincia', 'Sao_Francisco_Provincia', 'Tocantis_Provincia',
    'sedimentos', 'sedimentares', 'vulcanicas', 'metamorficas',
    'pantanal_plintossolo', 'pantanal_neossolo_quartzarenico', 'pantanal_gleissolo', 'pantanal_planossolo',
    'caatinga_latossolo',
    'latossolo_vulcanicas', 'latossolo_sedimentares', 'latossolo_sedimentos',
    'argissolo_metamorficas', 'argissolo_sedimentares', 'argissolo_sedimentos',
    'raso_vulcanica', 'raso_sedimentares',
    'pantanal_sedimentos', 'amazonia_sedimentos', 'cerrado_sedimentos', 'caatinga_sedimentos',
    'mata_atlantica_sedimentos',
    'Distance_to_sand_v33', 'Distance_to_rock_v33',
    'Area_Estavel',
]
DINAMICAS = [
    'mb_ndvi_median_decay', 'mb_evi2_median_decay',
    'formacaoFlorestal', 'outrasFormacoesFlorestais', 'formacaoCampestre', 'formacaoSavanica',
    'campoAlagadoAreaPantanosa', 'restingas', 'vegNatural', 'lavouras', 'pastagem', 'silvicultura',
    'mosaicoDeUsos', 'agropecuaria', 'afloramento', 'areia',
]
# Bandas que os filtros da matriz usam e que não estão nas listas acima.
PARA_FILTROS = ['Water_40y_recurrence']

# Índices da coleção de idades de uso (ageLulc.aggregate_array('index').distinct() no original, que devolve
# esta lista nesta ordem; fixada aqui para não repetir a agregação a cada ano).
IDADES = ['afloramento', 'agropecuaria', 'areia', 'campoAlagadoAreaPantanosa', 'formacaoCampestre',
          'formacaoFlorestal', 'formacaoSavanica', 'lavouras', 'lavourasPerene', 'lavourasTemp', 'mosaicoDeUsos',
          'natural', 'outrasFormacoesFlorestais', 'pastagem', 'restingas', 'silvicultura', 'vegNatural']

# Satélite do mosaico do MapBiomas por ano (year_sat do original).
SATELITE = {a: 'l5' for a in range(1985, 2025)}
SATELITE.update({a: 'l7' for a in (2001, 2002, 2011, 2012)})
SATELITE.update({a: 'l8' for a in range(2013, 2025)})


def _grupo(img, classes, nome):
    return img.select(classes).reduce(ee.Reducer.sum()).gt(0).rename(nome)


def _textura(prefixo):
    img = ee.Image(f'{PSD}{prefixo}_gbm_prev')
    camadas = [f'{prefixo}_{c}' for c in ('000_010cm', '010_020cm', '020_030cm')]
    return img.select(camadas).reduce(ee.Reducer.mean()).rename(f'{prefixo}_000_030cm').round()


def koppen_ipef():
    """Köppen IPEF em dummies L1-L3 (bandas koppen_l1_A, ...), como no modelo de produção."""
    base = COV + 'IPEF_2013_KOPPEN_100M_2025/'
    return ee.Image.cat([ee.Image(base + n) for n in ('koppen_l1', 'koppen_l2', 'koppen_l3')])


def estaticas():
    """static_covariates() do módulo do carbono, na mesma ordem de bandas."""
    textura = ee.Image.cat([_textura('areia'), _textura('silte'), _textura('argila')])

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

    prov = COV + 'IBGE_PROVINCIAIS_ESTRUTURAIS_250mil_2025/'
    provincias = ee.Image.cat([ee.Image(prov + 'IBGE_PROVINCIAS_250MIL_DUMMY'), ee.Image(prov + 'subprovincias')])

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
    pantanal, caatinga = bioma.select('Pantanal'), bioma.select('Caatinga')
    lat_, arg_ = sibcs.select('LATOSSOLO'), sibcs.select('ARGISSOLO')
    combinacoes = ee.Image.cat([
        pantanal.multiply(sibcs.select('PLINTOSSOLO')).rename('pantanal_plintossolo'),
        pantanal.multiply(sibcs.select('NEOSSOLO_QUARTZARENICO')).rename('pantanal_neossolo_quartzarenico'),
        pantanal.multiply(sibcs.select('GLEISSOLO')).rename('pantanal_gleissolo'),
        pantanal.multiply(sibcs.select('PLANOSSOLO')).rename('pantanal_planossolo'),
        caatinga.multiply(lat_).rename('caatinga_latossolo'),
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
        pantanal.multiply(sedimentos).rename('pantanal_sedimentos'),
        bioma.select('Amazonia').multiply(sedimentos).rename('amazonia_sedimentos'),
        bioma.select('Cerrado').multiply(sedimentos).rename('cerrado_sedimentos'),
        bioma.select('Pampa').multiply(sedimentos).rename('pampa_sedimentos'),
        caatinga.multiply(sedimentos).rename('caatinga_sedimentos'),
        bioma.select('Mata_Atlantica').multiply(sedimentos).rename('mata_atlantica_sedimentos'),
    ])

    g = ee.Image(GEOM)
    # slope.expression('tan(3.141593/180 * degrees)*100'): declive em graus -> porcentagem
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
        textura, solo, sibcs, grupos_sibcs,
        provincias, geologia, combinacoes, relevo, curvaturas,
        koppen_ipef(),
        bioma,
        ee.Image(COV + 'IBGE_2023_FITOFISIONOMIA_250MIL_2025'),
        ee.Image(COV + 'DISTANCE_C10_v3/distance_afloramento_rochoso_c10_v3_fd7000_md7000').rename('Distance_to_rock_v33'),
        ee.Image(COV + 'DISTANCE_C10_v3/distance_praia_duna_areal_c10_v3_fd7000_md7000').rename('Distance_to_sand_v33'),
        ee.Image(COV + 'MB_2024_C10_WATER/MB_2024_C10_STATIC_WATER_RECURRENCE_1985_2024').rename('Water_40y_recurrence'),
        ee.Image(COV + 'MB_2024_STABLEAREAS_C10').select('Area_Estavel'),
    ])


def ano_alternativo(ano):
    """Ano das imagens dinâmicas: antes de 1985 usa 1985; 2024 usa 2023 (os índices com decaimento vão até 2023)."""
    return 1985 if ano < 1985 else 2023 if ano == 2024 else ano


def _gapfill(img):
    """applyGapFill do original: preenche os pixels sem dado de cada banda com a banda anterior (ida) e
    depois com a seguinte (volta). É um preenchimento entre bandas, não entre anos; reproduzido como está."""
    nomes = img.bandNames()

    def ida(nome, anterior):
        anterior = ee.Image(anterior)
        return img.select(ee.String(nome)).unmask(anterior.select([0])).addBands(anterior)

    t0tn = ee.Image(nomes.iterate(ida, img.select([nomes.get(0)])))
    invertidos = nomes.reverse()

    def volta(nome, anterior):
        anterior = ee.Image(anterior)
        atual = t0tn.select(ee.String(nome)).unmask(anterior.select(anterior.bandNames().length().subtract(1)))
        return anterior.addBands(atual)

    tnt0 = ee.Image(invertidos.slice(1).iterate(volta, t0tn.select([invertidos.get(0)])))
    return tnt0.select(nomes)


def dinamicas(ano):
    """dynamic_covariates() do módulo do carbono, para um ano (imagem com a propriedade year = ano)."""
    ya = ano_alternativo(ano)
    ag = ee.ImageCollection(COV + 'MB_2024_AGELULC_C10_v2')
    idades = ee.Image.cat([ag.filter(ee.Filter.eq('index', idx)).mosaic().select([f'{idx}_{ya}'], [idx])
                           for idx in IDADES])

    dec = ee.ImageCollection(COV + 'LANDSAT_MB_INDICES_DECAY').filter(ee.Filter.eq('year', ya))
    bordas = ee.ImageCollection(BORDAS).filter(ee.Filter.eq('year', ya)).first().rename('mb_edges')
    img = ee.Image.cat([
        idades,
        dec.select('mb_ndvi_median_decay').first(),
        dec.select('mb_evi2_median_decay').first(),
        dec.select('mb_savi_median_decay').first(),
        bordas,
        ee.Image(COV + 'MB_2024_C10_WATER/MB_2024_DYNAMIC_WATER_RECURRENCE')
            .select(f'water_recurrence_1985_{ya}').rename('mb_water_recurrence_dynamic'),
        ee.Image(FOGO_ACUM).select(f'fire_accumulated_1985_{ya}').rename('mb_fireRecurrence'),
        ee.Image(FOGO_TAF).select(f'classification_{1986 if ya == 1985 else ya}').rename('mb_fire_time_after_fire'),
    ])
    mosaico = ee.ImageCollection(MOSAICOS).filter(ee.Filter.eq('year', ya))
    for banda in ('ndvi_median', 'evi2_median', 'savi_median'):
        img = img.addBands(mosaico.select([banda], ['mb_' + banda])
                           .filter(ee.Filter.eq('satellite', SATELITE[ya])).median().int16())
    return _gapfill(img).set('year', ano)


def pilha(ano, estaticas_img=None, extras=PARA_FILTROS):
    """Pilha da matriz para um ano, como em 1_data_matrix: estáticas e dinâmicas selecionadas, arredondadas,
    mais a banda year. `extras` acrescenta bandas estáticas fora da lista (as que os filtros usam)."""
    est = estaticas_img if estaticas_img is not None else estaticas()
    return ee.Image.cat([
        est.select(ESTATICAS + list(extras)).round(),
        dinamicas(ano).select(DINAMICAS).round(),
        ee.Image.constant(ano).int16().rename('year'),
    ])
