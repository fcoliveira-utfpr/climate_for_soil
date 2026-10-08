"""Configuração da avaliação espaço-temporal do SOC C3 (planejamento.md).

Código e resultados ficam em climas/analise_espaco_tempo/; os dados por ponto (restritos) ficam em
climas/dados_espaco_tempo/, fora do git.
"""
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[3]                  # MapBiomas_analises/
PASTA = Path(__file__).resolve().parents[1]                 # climas/analise_espaco_tempo/
TABELAS = PASTA / 'resultados' / 'tabelas'
FIGURAS = PASTA / 'resultados' / 'figuras'
DADOS = RAIZ / 'climas' / 'dados_espaco_tempo'

CORELACAO = RAIZ / 'corelacao' / 'codigo'
if str(CORELACAO) not in sys.path:
    sys.path.insert(0, str(CORELACAO))

# Pontos da C3 com pseudoamostras e réplicas trep (35.235 linhas).
ASSET_PONTOS = 'projects/mapbiomas-workspace/SOLOS/AMOSTRAS/ORIGINAIS/collection3/2025_11_26_soildata_soc_trep'
PROPS_PONTOS = ['id', 'ano', 'profundidade', 'carbono_gm2', 'carbono_gm2_qmap',
                'IFN_index', 'YEAR_index', 'PSEUDOROCK_index', 'PSEUDOSAND_index']

# Saídas (nome próprio: não é a matriz do MapBiomas).
PASTA_GEE = 'projects/fcoliveira/assets/SOC_C3_FABRICIO'
MATRIZ_BRUTA_GEE = f'{PASTA_GEE}/matriz_soc_c3_fabricio_bruta'      # antes dos filtros
MATRIZ_BRUTA = DADOS / 'matriz_soc_c3_fabricio_bruta.parquet'
MATRIZ = DADOS / 'matriz_soc_c3_fabricio.parquet'                    # depois dos filtros
PAINEL = DADOS / 'painel_soc_c3_fabricio_1985_2024.parquet'

# Clima contínuo: as 12 do CHELSA e do BHC (candidatas da seleção do §4.3b, com as decenais).
CLIMA_CONTINUO = ['clim_t_media', 'clim_t_mes_frio', 'clim_t_mes_quente', 'clim_biotemp', 'clim_p_anual',
                  'clim_p_mes_seco', 'clim_p_sazonalidade', 'clim_etp_anual', 'clim_etp_p', 'clim_def_anual',
                  'clim_exc_anual', 'clim_im']
CLIMA_DECENAL = ['dec_tmean', 'dec_prec', 'dec_cdd']

# Referência: a matriz final da produção (c03_soc_v2025_trainingFinal), segundo o R 30.
TRAINING_FINAL = {'linhas': 27425, 'ids': 14704, 'grupos': 13108, 'colunas': 136}
