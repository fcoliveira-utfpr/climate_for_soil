"""Legenda de Holdridge usada por preparar_dados.py. Fonte: descricao do asset
holdridge_lifezones_chelsa-v2026 (CHELSA V2.1, 1981-2010)."""

HOLDRIDGE = 'projects/mapbiomas-brazil/assets/SOIL/COVARIATES/holdridge_lifezones_chelsa-v2026'

# 38 zonas de vida (HLZ_L2), legenda documentada na propria descricao do asset.
HLZ_L2_LEGENDA = {1:'Polar_Ice',2:'Polar_Desert',3:'Subpolar_Dry_tundra',4:'Subpolar_Moist_tundra',
                  5:'Subpolar_Wet_tundra',6:'Subpolar_Rain_tundra',7:'Boreal_Desert',8:'Boreal_Dry_bush',
                  9:'Boreal_Moist_forest',10:'Boreal_Wet_forest',11:'Boreal_Rain_Forest',
                  12:'Cool_temperate_Desert',13:'Cool_temperate_Desert_bush',14:'Cool_temperate_Steppe',
                  15:'Cool_temperate_Moist_forest',16:'Cool_temperate_Wet_Forest',17:'Cool_temperate_Rain_Forest',
                  18:'Warm_temperate_Desert',19:'Warm_temperate_Desert_bush',20:'Warm_temperate_Thorn_steppe',
                  21:'Warm_temperate_Dry_forest',22:'Warm_temperate_Moist_forest',23:'Warm_temperate_Wet_forest',
                  24:'Warm_temperate_Rain_forest',25:'Subtropical_Desert',26:'Subtropical_Desert_bush',
                  27:'Subtropical_Thorn_steppe',28:'Subtropical_Dry_forest',29:'Subtropical_Moist_forest',
                  30:'Subtropical_Wet_forest',31:'Subtropical_Rain_forest',32:'Tropical_Desert',
                  33:'Tropical_Desert_bush',34:'Tropical_Thorn_steppe',35:'Tropical_Very_dry_forest',
                  36:'Tropical_Dry_forest',37:'Tropical_Moist_forest',38:'Tropical_Wet_forest'}

# HLZ_L1 (7 faixas termicas), agregado das 38 zonas finas; faixas dadas na propria
# descricao do asset (linha "Regiao Latitudinal/Altitudinal" da tabela de legenda).
HLZ_L1_FAIXAS = [(1,2,'Polar_Zone'),(3,6,'Subpolar_Zone'),(7,11,'Boreal_Zone'),(12,17,'Cool_Temperate_Zone'),
                 (18,24,'Warm_Temperate_Zone'),(25,31,'Subtropical_Zone'),(32,38,'Tropical_Zone')]
HLZ_L1_LEGENDA = {i+1: nome for i,(_,_,nome) in enumerate(HLZ_L1_FAIXAS)}
HLZ_L2_PARA_L1 = {codigo: i+1 for i,(lo,hi,_) in enumerate(HLZ_L1_FAIXAS) for codigo in range(lo,hi+1)}
