"""Configuração da reprodução dos modelos do MapBiomas Solo C3 com os climas CHELSA.

Pergunta: trocando o Köppen IPEF por cada um dos nossos climas, as estimativas de textura e de SOC do
MapBiomas melhoram? Fase 1 avalia por validação cruzada espacial; fase 2 gera os mapas.

Código e notebook ficam em climas/reproducao/; o que é gerado (dados por ponto, que são restritos, e mapas)
fica em climas/dados_reproducao/, fora do git.
"""
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[3]                  # MapBiomas_analises/
PASTA = Path(__file__).resolve().parents[1]                 # climas/reproducao/
TABELAS = PASTA / 'resultados' / 'tabelas'
FIGURAS = PASTA / 'resultados' / 'figuras'
DADOS = RAIZ / 'climas' / 'dados_reproducao'
PONTOS = DADOS / 'pontos'
MAPAS = DADOS / 'mapas'

# Reaproveita a extração de climas e o zoneamento da análise solo-clima (corelacao/codigo).
CORELACAO = RAIZ / 'corelacao' / 'codigo'
if str(CORELACAO) not in sys.path:
    sys.path.insert(0, str(CORELACAO))

MATRIZ_TEXTURA = 'projects/mapbiomas-workspace/SOLOS/AMOSTRAS/MATRIZES/collection3/c03_psd_v2025_11_18'
# SOC: pontos da coleção 3 (o mesmo conjunto publicado no SoilData, doi 10.60502/SoilData/IUZOAK), sem
# covariáveis; elas são extraídas no GEE com as imagens de covariaveis_gee.py. A matriz com covariáveis
# da C3 (MATRIZES/collection3/c03_soc_v2025_11_26_trep) não é legível por esta conta; a matriz usada antes,
# matriz-collection3_carbon_datac2v2, tem os estoques da coleção 2.
ASSET_SOC = 'projects/mapbiomas-workspace/SOLOS/AMOSTRAS/ORIGINAIS/collection3/2025_11_26_soildata_soc_trep'
COVARIAVEIS_SOC = [l.strip() for l in (Path(__file__).parent / 'covariaveis_soc.txt').read_text().splitlines()
                   if l.strip() and not l.startswith('#')]
ANO_MAX_COVARIAVEIS = 2023       # as bordas (edge_sum) vão até 2023; amostras de 2024 usam 2023, como os mapas
PROF_SOC = 30                    # profundidade (cm) do estoque avaliado e mapeado

# --- Textura: como no script texture/2_model_prediction do MapBiomas -------------------------------
# Um GBM por alvo e por camada; camada = horizontes com centro a até 5 cm do centro da camada.
CAMADAS = {'000_010cm': 5, '010_020cm': 15, '020_030cm': 25}
MEIA_JANELA = 5
ALVOS_TEXTURA = ['log_areia1p_argila1p', 'log_silte1p_argila1p']     # ln((x + 1) / (argila + 1)), g/kg
PARAMS_GBM = dict(max_iter=400, learning_rate=0.01, max_leaf_nodes=25)   # MapBiomas: 400 árvores,
#   shrinkage 0,01, maxNodes 25 (smileGradientTreeBoost); o samplingRate 0,632 não existe no
#   HistGradientBoosting do scikit-learn.
TEXTURA_C2 = ['sand_000_030cm', 'silt_000_030cm', 'clay_000_030cm']      # covariáveis no modelo deles

# Variante: sem os mapas de textura da coleção 2 como covariável (REPRODUCAO_SEM_C2=1). Esses mapas foram
# ajustados com praticamente as mesmas amostras, então "entregam" a resposta mesmo na validação espacial;
# sem eles, a validação mede a capacidade real de estimar onde não há amostra, e o efeito do clima aparece.
import os
SEM_C2 = os.environ.get('REPRODUCAO_SEM_C2') == '1'
SUFIXO = '_semC2' if SEM_C2 else ''

# --- SOC: random forest (ranger no MapBiomas), com a textura de 0-30 cm como covariável -------------
PARAMS_RF = dict(n_estimators=300, max_features=0.33, min_samples_leaf=2, n_jobs=-1)

# --- Cenários de clima (só o clima muda entre eles) ------------------------------------------------
CLIMA_CONTINUO = ['clim_t_media', 'clim_t_mes_frio', 'clim_t_mes_quente', 'clim_biotemp', 'clim_p_anual',
                  'clim_p_mes_seco', 'clim_p_sazonalidade', 'clim_etp_anual', 'clim_etp_p', 'clim_def_anual',
                  'clim_exc_anual', 'clim_im']
CENARIOS = {
    # nome: (rótulo, colunas, tipo)   tipo: 'dummies' (classes) | 'numerico' | None
    'koppen_ipef': ('Köppen IPEF (referência)', ['koppen_ipef_l1', 'koppen_ipef_l2', 'koppen_ipef_l3'], 'dummies'),
    'sem_clima': ('Sem clima', [], None),
    'koppen_chelsa': ('Köppen CHELSA', ['koppen_chelsa_l1', 'koppen_chelsa_l2', 'koppen_chelsa_l3'], 'dummies'),
    'holdridge_etpm': ('Holdridge ETP Penman', ['holdridge_l1', 'holdridge_etpm_l2'], 'dummies'),
    'holdridge_eth': ('Holdridge ETP Holdridge', ['holdridge_l1', 'holdridge_eth_l2'], 'dummies'),
    'th_cad100': ('Thornthwaite CAD 100 mm', ['th100_l1', 'th100_l2'], 'dummies'),
    'th_cadsolo': ('Thornthwaite CAD do solo', ['thsolo_l1', 'thsolo_l2'], 'dummies'),
    'clima_continuo': ('Clima contínuo', CLIMA_CONTINUO, 'numerico'),
    'zonas_k10': ('Zonas climáticas k10', ['zona_k10'], 'dummies'),
}
REFERENCIA = 'koppen_ipef'

# --- Validação ---------------------------------------------------------------------------------------
TAM_BLOCO = 2.0          # graus
N_DOBRAS = 5
N_REPETICOES = 3
SEMENTE = 2026
