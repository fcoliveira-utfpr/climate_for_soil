# Assets utilizados no projeto

Todos os assets do Google Earth Engine (GEE) e fontes de dados usados em `MapBiomas_analises`, com o que
cada um é e onde foi usado. Caminhos relativos à raiz do repositório.

Pastas citadas:
- `climas/chelsa_climas_brasil/`: geração do clima CHELSA e das classificações climáticas
- `corelacao/`: comparação de climas × solo e experimento dos modelos
- `climas/reproducao/`: reprodução dos modelos do MapBiomas Solo C3
- `validacao/`: validação das bases climáticas contra estações

---

## 1. Clima gerado neste projeto (`projects/fcoliveira/assets/`)

CHELSA V2.1, normal 1991-2020, ~1 km (30″). Gerados localmente e subidos ao GEE pelo usuário.

| Asset | O que é | Onde foi usado |
|---|---|---|
| `chelsa_brasil_tas_normal_1991_2020` | Temperatura média mensal (12 bandas, °C) | Geração: `chelsa_climas_brasil/gerar_normal_multibanda.py`, `chelsa_brasil.ipynb`. Uso: `holdridge_chelsa.ipynb`, `koppen_chelsa.ipynb`; `corelacao/codigo/legendas.py` e `preparar_dados.py` (mês mais frio, diagnóstico do Köppen), `experimento_dados.py` (clima contínuo nos pontos) |
| `chelsa_brasil_pr_normal_1991_2020` | Precipitação mensal (12 bandas, mm) | Geração: idem. Uso: `holdridge_chelsa.ipynb`, `koppen_chelsa.ipynb`, `diagnostico_chuva_CHELSA_1991_2020.ipynb`; `corelacao/codigo/experimento_dados.py` |
| `chelsa_brasil_pet_normal_1991_2020` | ETP de Penman-Monteith mensal (12 bandas, mm) | Geração: idem. Uso: `holdridge_chelsa.ipynb` (versão ETPM); `corelacao/codigo/experimento_dados.py` |
| `Koppen_CHELSA_BR_1991_2020` | Köppen-Geiger (Alvares et al. 2013; sazonalidade dos climas C por Kottek et al. 2006; estações trocadas ao norte do equador), classe 1-31 | Geração: `koppen_chelsa.ipynb` / `koppen_gee.py`. Uso: `corelacao` (comparação e experimento) e `climas/reproducao` (cenário Köppen CHELSA) |
| `Holdridge_CHELSA_BR_1991_2020_ETPM` | Zonas de vida de Holdridge (38 zonas, numeração de Jungkunst et al. 2021), razão ETP/P com a ETP de Penman-Monteith | Geração: `holdridge_chelsa.ipynb` / `holdridge_gee.py`. Uso: `corelacao` e `climas/reproducao` |
| `Holdridge_CHELSA_BR_1991_2020_ETH` | Idem, com a ETP de Holdridge (58,93 × biotemperatura) | Idem |
| `Thornthwaite_CHELSA_BR_1991_2020_CAD100` | Thornthwaite (1948) com balanço hídrico de CAD 100 mm e ETP Penman-Monteith; 10 bandas: umidade, subtipo, térmica, concentração, ETP, DEF, EXC, Ih, Ia, Im | Geração: `thornthwaite_chelsa.ipynb` / `thornthwaite.py`. Uso: `corelacao` (classes; DEF/EXC/Im no clima contínuo e nas zonas k10) e `climas/reproducao` |
| `Thornthwaite_CHELSA_BR_1991_2020_CADsolo` | Idem, com a CAD do solo (AWC × 1000 × 1 m) | Idem |
| `AWC_br` | **Tabela** de ~95 mil polígonos de solo com a água disponível (AWC, m³/m³); corpos d'água e afloramentos de rocha sem valor | `thornthwaite_chelsa.ipynb` (rasterizado na grade do CHELSA para a CAD do solo) |

**Obsoleto, já apagado do GEE:** `Holdridge_CHELSA_BR_1991_2020` (versão única, com a numeração das zonas
tropicais deslocada; substituído pelas versões ETPM e ETH).

## 2. Clima de diagnóstico e versões antigas (`projects/fcoliveira/assets/`)

| Asset | O que é | Onde foi usado |
|---|---|---|
| `CHELSA/CHELSA_pr_1981-2010` (e `CHELSA_{tas,pet,pr}_MM_1981-2010`, pasta `CHELSA/`) | Normais CHELSA 1981-2010 (mensais e anuais), anteriores ao pipeline de 1991-2020 | `diagnostico_chuva_CHELSA_1991_2020.ipynb` (comparação com a normal nova) |
| `diag_DR_chelsa_pr` | Imagem de diagnóstico do erro na chuva da normal 1991-2020. **Citada no notebook, mas não existe mais no GEE** | `diagnostico_chuva_CHELSA_1991_2020.ipynb` |

## 3. Datasets públicos do GEE

| Asset | O que é | Onde foi usado |
|---|---|---|
| `FAO/GAUL/2015/level0` | Limite do Brasil (FAO GAUL) | `holdridge_chelsa.ipynb`, `koppen_chelsa.ipynb`, `thornthwaite_chelsa.ipynb` (recorte e máscara do Brasil), `diagnostico_chuva_CHELSA_1991_2020.ipynb` |
| `FAO/GAUL/2015/level1` | Limites estaduais (FAO GAUL) | Mapas dos notebooks de Holdridge, Köppen e diagnóstico |
| `IDAHO_EPSCOR/TERRACLIMATE` | TerraClimate mensal (~4 km) | `diagnostico_chuva_CHELSA_1991_2020.ipynb` (comparação da chuva) |
| `ECMWF/ERA5_LAND/MONTHLY_AGGR` | ERA5-Land mensal (temperatura e precipitação) | `validacao/baixar_era5.py` → `validacao/dados_era5.csv` |
| `MERIT/DEM/v1_0_3` | Elevação MERIT DEM (covariável `elevation` do MapBiomas) | `climas/reproducao/codigo/covariaveis_gee.py` (mapas) |

## 4. MapBiomas Solo: matrizes de amostras (acesso restrito)

| Asset | O que é | Onde foi usado |
|---|---|---|
| `projects/mapbiomas-workspace/SOLOS/AMOSTRAS/MATRIZES/collection3/matriz-collection3_carbon_datac2v2` | Matriz de treino de carbono: estoque de SOC 0-30 cm por ponto e ano, com as covariáveis do MapBiomas e o Köppen IPEF em dummies | `corelacao/codigo/preparar_dados.py`, `experimento_dados.py`; `climas/reproducao/codigo/dados.py` |
| `projects/mapbiomas-workspace/SOLOS/AMOSTRAS/MATRIZES/collection3/c03_psd_v2025_11_18` | Matriz de treino da textura (a de produção da C3): areia, silte e argila (g/kg) por horizonte, com profundidade, covariáveis e Köppen IPEF | Idem |

**Referenciada, sem acesso de leitura:** `.../collection3/c03_soc_v2025_11_26_trep` (matriz de produção do SOC
da C3; em seu lugar foi usada a `carbon_datac2v2`).

## 5. MapBiomas Solo: covariáveis dos modelos C3

Portadas do módulo `0_covariate_source` do repositório `mapbiomas/brazil-soil` para
`climas/reproducao/codigo/covariaveis_gee.py` e usadas para gerar os mapas de `climas/reproducao`
(`mapas_textura.py`, `mapas_soc.py`). Prefixo `COV` = `projects/mapbiomas-workspace/SOLOS/COVARIAVEIS/`.

| Asset | O que é |
|---|---|
| `projects/mapbiomas-workspace/SOLOS/PRODUTOS_C02/c02v2/mapbiomas_soil_collection2_v2_{sand,silt,clay}` | Mapas de textura 0-30 cm da coleção 2 (covariáveis `*_000_030cm`) |
| `projects/mapbiomas-public/assets/brazil/lulc/collection10/mapbiomas_brazil_collection10_integration_v2` | Cobertura e uso da terra, coleção 10 (máscara de afloramento rochoso, classe 29) |
| `COV WRB_ALL_SOILS_SOILGRIDS_30M_GAPFILL` | Probabilidades das classes de solo WRB (SoilGrids), individuais e agrupadas |
| `COV FAO_2022_BLACKSOIL_1KM` | Probabilidade de solos pretos (FAO) |
| `COV IBGE_2023_PEDOLOGIA_250MIL_2025` | Classes de solo SiBCS (IBGE 1:250 mil) e seus agrupamentos |
| `COV IBGE_PROVINCIAIS_ESTRUTURAIS_250mil_2025/IBGE_PROVINCIAS_250MIL_DUMMY` | Províncias estruturais (IBGE), dummies |
| `COV IBGE_PROVINCIAIS_ESTRUTURAIS_250mil_2025/subprovincias` | Subprovíncias geológicas (sedimentos, sedimentares, vulcânicas, plutônicas, metamórficas) |
| `COV IBGE_PROVINCIAIS_ESTRUTURAIS_250mil_2025_tmp/subprovincias_prob` | Idem, com probabilidades |
| `COV IBGE_2019_BIOMAS_ZC_250MIL` | Biomas IBGE (dummies) |
| `COV IBGE_2023_FITOFISIONOMIA_250MIL_2025` | Fitofisionomias IBGE (dummies) |
| `COV OT_GEOMORPHOMETRY_90m` | Geomorfometria (declividade, CTI, SPI, rugosidade etc.) |
| `projects/ee-barbaracosta/assets/soc_mapping/brasil_curvaturas_15x15` | Curvaturas do relevo (janela 15×15) |
| `COV DISTANCE_C10_v3/distance_afloramento_rochoso_c10_v3_fd7000_md7000` | Distância a afloramento rochoso |
| `COV DISTANCE_C10_v3/distance_praia_duna_areal_c10_v3_fd7000_md7000` | Distância a praias, dunas e areais |
| `COV MB_2024_C10_WATER/MB_2024_C10_STATIC_WATER_RECURRENCE_1985_2024` | Recorrência de água 1985-2024 (estática) |
| `COV MB_2024_C10_WATER/MB_2024_DYNAMIC_WATER_RECURRENCE` | Recorrência de água acumulada por ano (SOC) |
| `COV MB_2024_AGELULC_C10_v2` | Idade de cada classe de uso da terra por ano (SOC; `antropico` = `agropecuaria`) |
| `COV LANDSAT_MB_INDICES_DECAY` | NDVI, EVI2 e SAVI com decaimento, por ano (SOC) |
| `COV MB_DEGRADATION_BETA_SUMMED_EDGES` | Bordas somadas por ano (SOC) |
| `COV MB_2024_STABLEAREAS_C10` | Áreas estáveis de uso (SOC) |
| `projects/mapbiomas-public/assets/brazil/fire/collection4_1/mapbiomas_fire_collection41_accumulated_burned_v1` | Fogo acumulado por ano, coleção 4.1 pública (SOC) |
| `COV IPEF_2013_KOPPEN_100M_2025/koppen_l1`, `koppen_l2`, `koppen_l3` | Köppen IPEF em dummies: a referência dos modelos do MapBiomas |

As 110 covariáveis da textura e as 24 extras do SOC foram conferidas contra as colunas da matriz (nomes e,
para as dinâmicas, valores em 300 linhas: 100% iguais).

## 6. Fontes externas (fora do GEE) e arquivos locais gerados

| Fonte / arquivo | O que é | Onde foi usado |
|---|---|---|
| `https://os.unil.cloud.switch.ch/chelsa02/chelsa/global/monthly/{var}/{ano}/CHELSA_{var}_{mes}_{ano}_V.2.1.tif` | CHELSA V2.1 mensal global (tas, pr, pet), 1991-2020 | `chelsa_climas_brasil/baixar_recortar.py` → `climas/dados_chelsa/mensal_recortado/`; normais em `climas/dados_chelsa/normal_1991_2020/`; `validacao/atualizar_dados_chelsa.py` |
| `climas/dados_chelsa/{koppen,holdridge,thornthwaite,awc}/*.tif` | GeoTIFFs locais das classificações e do AWC rasterizado (os mesmos dos assets da seção 1) | `corelacao/codigo/zonas_clima.py`; `climas/reproducao/codigo/mapas_textura.py` (clima de cada pixel) |
| `climas/dados_chelsa/zonas/zonas_climaticas_k10.tif` (e `k15`) | Zonas climáticas homogêneas (k-means sobre o clima do Brasil). **Ainda não é asset** | `corelacao` (experimento) e `climas/reproducao` (cenário zonas k10) |
| `climas/dados_reproducao/mapas/*.tif` | Mapas de textura e SOC 0-30 cm (~5 km) dos 9 cenários de clima, com e sem textura C2. **Ainda não são assets** | `climas/reproducao/reproducao_resultados.ipynb` |
