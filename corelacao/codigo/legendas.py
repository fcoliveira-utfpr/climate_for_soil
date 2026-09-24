"""Assets climáticos comparados e como cada código vira classe em cada nível.

Os assets novos (CHELSA V2.1, normal 1991-2020) são gerados em climas/chelsa_climas_brasil/
(koppen_gee.py, holdridge_gee.py, thornthwaite.py); as legendas abaixo são cópias das de lá.
O Köppen IPEF (referência) vem embutido como dummies nas duas matrizes de pontos.
"""

ASSET_KOPPEN = 'projects/fcoliveira/assets/Koppen_CHELSA_BR_1991_2020'
# Holdridge em duas versões da ETP na razão ETP/P: Penman-Monteith do CHELSA (ETPM) e a de Holdridge,
# 58,93 x biotemperatura (ETH). A biotemperatura (faixa térmica, L1) é a mesma nas duas.
ASSET_HOLDRIDGE_ETPM = 'projects/fcoliveira/assets/Holdridge_CHELSA_BR_1991_2020_ETPM'
ASSET_HOLDRIDGE_ETH = 'projects/fcoliveira/assets/Holdridge_CHELSA_BR_1991_2020_ETH'
ASSET_TH100 = 'projects/fcoliveira/assets/Thornthwaite_CHELSA_BR_1991_2020_CAD100'
ASSET_THSOLO = 'projects/fcoliveira/assets/Thornthwaite_CHELSA_BR_1991_2020_CADsolo'
# Temperatura média mensal (12 bandas, °C): só para o diagnóstico da fronteira A/C do Köppen.
ASSET_TAS = 'projects/fcoliveira/assets/chelsa_brasil_tas_normal_1991_2020'

# --- Köppen-Geiger (koppen_gee.LEGENDA) ---------------------------------------------------------
KOPPEN = {1: 'Af', 2: 'Am', 3: 'As', 4: 'Aw', 5: 'BSh', 6: 'BSk', 7: 'BWh', 8: 'BWk',
          9: 'Cfa', 10: 'Cfb', 11: 'Cfc', 12: 'Csa', 13: 'Csb', 14: 'Csc', 15: 'Cwa', 16: 'Cwb',
          17: 'Cwc', 18: 'Dfa', 19: 'Dfb', 20: 'Dfc', 21: 'Dfd', 22: 'Dsa', 23: 'Dsb', 24: 'Dsc',
          25: 'Dsd', 26: 'Dwa', 27: 'Dwb', 28: 'Dwc', 29: 'Dwd', 30: 'ET', 31: 'EF'}

# --- Holdridge (holdridge_gee.LEGENDA) ----------------------------------------------------------
# Numeração e nomes das 38 zonas de Jungkunst et al. (2021, J. Plant Nutr. Soil Sci. 184:5-11, Tab. 1),
# base Leemans (1990). L1 = faixa térmica (latitudinal).
HOLDRIDGE_NOMES = {
    1: 'Polar ice', 2: 'Polar desert',
    3: 'Subpolar dry tundra', 4: 'Subpolar moist tundra', 5: 'Subpolar wet tundra', 6: 'Subpolar rain tundra',
    7: 'Boreal desert', 8: 'Boreal dry bush', 9: 'Boreal moist forest', 10: 'Boreal wet forest',
    11: 'Boreal rain forest',
    12: 'Cool temperate desert', 13: 'Cool temperate desert bush', 14: 'Cool temperate steppe',
    15: 'Cool temperate moist forest', 16: 'Cool temperate wet forest', 17: 'Cool temperate rain forest',
    18: 'Warm temperate desert', 19: 'Warm temperate desert bush', 20: 'Warm temperate thorn steppe',
    21: 'Warm temperate dry forest', 22: 'Warm temperate moist forest', 23: 'Warm temperate wet forest',
    24: 'Warm temperate rain forest',
    25: 'Subtropical desert', 26: 'Subtropical desert bush', 27: 'Subtropical thorn steppe',
    28: 'Subtropical dry forest', 29: 'Subtropical moist forest', 30: 'Subtropical wet forest',
    31: 'Subtropical rain forest',
    32: 'Tropical desert', 33: 'Tropical desert bush', 34: 'Tropical thorn steppe',
    35: 'Tropical very dry forest', 36: 'Tropical dry forest', 37: 'Tropical moist forest',
    38: 'Tropical wet forest',
}
_FAIXAS = [(1, 2, 'Polar'), (3, 6, 'Subpolar'), (7, 11, 'Boreal'), (12, 17, 'Temperado frio'),
           (18, 24, 'Temperado quente'), (25, 31, 'Subtropical'), (32, 38, 'Tropical')]
HOLDRIDGE_L1 = {z: nome for lo, hi, nome in _FAIXAS for z in range(lo, hi + 1)}
HOLDRIDGE_L2 = {z: f'{z} {n}' for z, n in HOLDRIDGE_NOMES.items()}

# --- Thornthwaite (thornthwaite.py) -------------------------------------------------------------
TH_UMIDADE = {1: 'A', 2: 'B4', 3: 'B3', 4: 'B2', 5: 'B1', 6: 'C2', 7: 'C1', 8: 'D', 9: 'E'}
TH_SUBTIPO = {1: 'r', 2: 's', 3: 'w', 4: 's2', 5: 'w2', 6: 'd', 7: 's', 8: 'w', 9: 's2', 10: 'w2'}
TH_TERMICA = {1: "A'", 2: "B4'", 3: "B3'", 4: "B2'", 5: "B1'", 6: "C2'", 7: "C1'", 8: "D'", 9: "E'"}
TH_CONCENTRACAO = {1: "a'", 2: "b4'", 3: "b3'", 4: "b2'", 5: "b1'", 6: "c2'", 7: "c1'", 8: "d'"}

# --- Sistemas e níveis comparados ---------------------------------------------------------------
# coluna -> (sistema, nível, descrição curta do nível)
NIVEIS = {
    'koppen_ipef_l1': ('Köppen IPEF (referência)', 'L1', 'grupo (A, B, C)'),
    'koppen_ipef_l2': ('Köppen IPEF (referência)', 'L2', 'tipo (Af, Am, Aw, Cf...)'),
    'koppen_ipef_l3': ('Köppen IPEF (referência)', 'L3', 'subtipo (Cfa, Cfb...)'),
    'koppen_chelsa_l1': ('Köppen CHELSA', 'L1', 'grupo (A, B, C)'),
    'koppen_chelsa_l2': ('Köppen CHELSA', 'L2', 'tipo (Af, Am, Aw, Cf...)'),
    'koppen_chelsa_l3': ('Köppen CHELSA', 'L3', 'classe completa (Aw, Cfa...)'),
    'holdridge_l1': ('Holdridge ETP Penman', 'L1', 'faixa térmica (igual nas duas ETPs)'),
    'holdridge_etpm_l2': ('Holdridge ETP Penman', 'L2', 'zona de vida'),
    'holdridge_eth_l2': ('Holdridge ETP Holdridge', 'L2', 'zona de vida'),
    'th100_l1': ('Thornthwaite CAD 100 mm', 'L1', 'classe de umidade'),
    'th100_l2': ('Thornthwaite CAD 100 mm', 'L2', 'umidade + subtipo'),
    'th100_l3': ('Thornthwaite CAD 100 mm', 'L3', 'tipo completo'),
    'thsolo_l1': ('Thornthwaite CAD do solo', 'L1', 'classe de umidade'),
    'thsolo_l2': ('Thornthwaite CAD do solo', 'L2', 'umidade + subtipo'),
    'thsolo_l3': ('Thornthwaite CAD do solo', 'L3', 'tipo completo'),
}
COLUNAS_CLIMA = list(NIVEIS)
