"""Assets climáticos comparados e como cada código vira classe em cada nível.

Os assets novos (CHELSA V2.1, normal 1991-2020) são gerados em climas/chelsa_climas_brasil/
(koppen_gee.py, holdridge_gee.py, thornthwaite.py); as legendas abaixo são cópias das de lá.
O Köppen IPEF (referência) vem embutido como dummies nas duas matrizes de pontos.
"""

ASSET_KOPPEN = 'projects/fcoliveira/assets/Koppen_CHELSA_BR_1991_2020'
ASSET_HOLDRIDGE = 'projects/fcoliveira/assets/Holdridge_CHELSA_BR_1991_2020'
ASSET_TH100 = 'projects/fcoliveira/assets/Thornthwaite_CHELSA_BR_1991_2020_CAD100'
ASSET_THSOLO = 'projects/fcoliveira/assets/Thornthwaite_CHELSA_BR_1991_2020_CADsolo'

# --- Köppen-Geiger (koppen_gee.LEGENDA) ---------------------------------------------------------
KOPPEN = {1: 'Af', 2: 'Am', 3: 'As', 4: 'Aw', 5: 'BSh', 6: 'BSk', 7: 'BWh', 8: 'BWk',
          9: 'Cfa', 10: 'Cfb', 11: 'Cfc', 12: 'Csa', 13: 'Csb', 14: 'Csc', 15: 'Cwa', 16: 'Cwb',
          17: 'Cwc', 18: 'Dfa', 19: 'Dfb', 20: 'Dfc', 21: 'Dfd', 22: 'Dsa', 23: 'Dsb', 24: 'Dsc',
          25: 'Dsd', 26: 'Dwa', 27: 'Dwb', 28: 'Dwc', 29: 'Dwd', 30: 'ET', 31: 'EF'}

# --- Holdridge (holdridge_gee.TABELA_ZONAS) -----------------------------------------------------
# A numeração 1-38 segue o mesmo esquema da legenda do MapBiomas, mas pela tabela do script JS
# os nomes de lá ficam deslocados (ex.: a zona 36 é ETP/P 0,5-1, "floresta úmida" no Holdridge
# clássico, e não "floresta seca"). Por isso as zonas são rotuladas pela faixa térmica e pela
# faixa da razão ETP/P, que saem direto da tabela.
FAIXA_TERMICA = {2: 'Subpolar', 3: 'Boreal', 4: 'Temperado frio', 5: 'Temperado quente',
                 6: 'Subtropical', 7: 'Tropical'}
# Classe de umidade u (1 = mais seco) -> limites [inferior, superior) da razão ETP/P.
_RETP_LIMITES = {1: (32, None), 2: (16, 32), 3: (8, 16), 4: (4, 8), 5: (2, 4), 6: (1, 2),
                 7: (0.5, 1), 8: (0.25, 0.5), 9: (0.125, 0.25), 10: (None, 0.125)}
_TABELA_ZONAS = [
    (2, 1, 4, 3), (2, 5, 6, 4), (2, 7, 7, 5), (2, 8, 10, 6),
    (3, 1, 3, 7), (3, 4, 4, 8), (3, 5, 5, 9), (3, 6, 7, 10), (3, 8, 10, 11),
    (4, 1, 3, 12), (4, 4, 4, 13), (4, 5, 5, 14), (4, 6, 6, 15), (4, 7, 7, 16), (4, 8, 10, 17),
    (5, 1, 3, 18), (5, 4, 4, 19), (5, 5, 5, 20), (5, 6, 6, 21), (5, 7, 7, 22), (5, 8, 8, 23), (5, 9, 10, 24),
    (6, 1, 3, 25), (6, 4, 4, 26), (6, 5, 5, 27), (6, 6, 6, 28), (6, 7, 7, 29), (6, 8, 8, 30), (6, 9, 10, 31),
    (7, 1, 3, 32), (7, 4, 4, 33), (7, 5, 5, 34), (7, 6, 6, 35), (7, 7, 7, 36), (7, 8, 8, 37), (7, 9, 10, 38),
]


def _faixa_retp(u_min, u_max):
    """Faixa de ETP/P coberta pelas classes de umidade u_min..u_max (u_min é a mais seca)."""
    fmt = lambda x: f'{x:g}'.replace('.', ',')
    inf, sup = _RETP_LIMITES[u_max][0], _RETP_LIMITES[u_min][1]
    if sup is None:
        return f'>={fmt(inf)}'
    if inf is None:
        return f'<{fmt(sup)}'
    return f'{fmt(inf)}-{fmt(sup)}'


HOLDRIDGE_L1 = {z: FAIXA_TERMICA[t] for t, _, _, z in _TABELA_ZONAS}
HOLDRIDGE_L2 = {z: f'{z} {FAIXA_TERMICA[t]}, ETP/P {_faixa_retp(u0, u1)}' for t, u0, u1, z in _TABELA_ZONAS}

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
    'holdridge_l1': ('Holdridge CHELSA', 'L1', 'faixa térmica'),
    'holdridge_l2': ('Holdridge CHELSA', 'L2', 'zona de vida'),
    'th100_l1': ('Thornthwaite CAD 100 mm', 'L1', 'classe de umidade'),
    'th100_l2': ('Thornthwaite CAD 100 mm', 'L2', 'umidade + subtipo'),
    'th100_l3': ('Thornthwaite CAD 100 mm', 'L3', 'tipo completo'),
    'thsolo_l1': ('Thornthwaite CAD do solo', 'L1', 'classe de umidade'),
    'thsolo_l2': ('Thornthwaite CAD do solo', 'L2', 'umidade + subtipo'),
    'thsolo_l3': ('Thornthwaite CAD do solo', 'L3', 'tipo completo'),
}
COLUNAS_CLIMA = list(NIVEIS)
