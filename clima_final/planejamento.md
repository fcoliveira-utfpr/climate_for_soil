# Planejamento — Conjunto final de clima para o SOC (capítulo 6, relatório v6)

**Pergunta.** Qual conjunto de variáveis climáticas recomendar ao MapBiomas Solo no lugar do Köppen IPEF? O
relatório v4 sugeriu, pela importância por permutação, um **conjunto curto** (temperatura decenal + CDD + ARM
com a CAD do solo) e um **híbrido** (temperatura decenal + balanço hídrico estático), mas essa escolha foi
feita nas mesmas dobras que avaliaram o resultado. Aqui os dois são validados em **partições novas**.

## 1. Cenários

| Cenário | Clima | Nº de variáveis | Origem |
|---|---|---|---|
| `koppen_ipef` | Köppen IPEF, dummies L1-L3 da produção | 13 | referência (produção) |
| `sem_clima` | nenhum | 0 | controle |
| `cont_decenal` | `dec_tmean`, `dec_prec`, `dec_cdd` | 3 | v2 |
| `temperatura` | 7 de temperatura em média móvel de 10 anos (`cd_t_media`, `cd_tmax_media`, `cd_tmin_media`, `cd_t_mes_quente`, `cd_t_mes_frio`, `cd_amplitude`, `cd_biotemp`) | 7 | v4 |
| `curto` | temperatura + `dec_cdd` + `cd_arm_csolo` | 9 | **novo** |
| `hibrido` | temperatura + balanço hídrico estático do CHELSA 1991-2020 (`clim_p_anual`, `clim_p_mes_seco`, `clim_p_sazonalidade`, `clim_etp_anual`, `clim_def_anual`) | 12 | **novo** |
| `hibrido_curto` | temperatura + CDD + ARM + balanço hídrico estático | 14 | **novo** |

As normais hídricas do híbrido são as que a seleção aninhada do v2 manteve no modelo final (chuva anual, do
mês seco e sazonalidade; ETP; DEF). As de temperatura do CHELSA ficam de fora: a temperatura entra só
decenal.

## 2. Validação

- Matriz do v4 (`trainingFinal` reconstruída + `cd_*` + `clim_*`), mesmas covariáveis da produção.
- **V2 espacial e V4 espaço-temporal com partição nova** dos blocos de 2° (mesmo procedimento do v2, semente
  2027); a concordância com a partição antiga (índice de Rand) é 0,66-0,67, o mesmo que entre duas
  partições ao acaso (0,68).
- **V3 temporal:** os períodos são fixos (1985-94, 1995-2004, 2005-14, 2015-24); mudam só as sementes dos
  modelos (`VAL_SEMENTE` = 2984 em vez de 1984). A V3 é, portanto, a menos independente da escolha do v4.
- Ranger validado e modelo do mapa (`smileRandomForest`, maxNodes 40, emulado); 3 repetições.
- Métricas do MapBiomas em t/ha; recorte principal: amostras reais de 0-30 cm.
- Ganhos pareados sobre o Köppen IPEF, sobre o contínuo decenal do v2 e sobre a temperatura sozinha.

**Critério de decisão:** o conjunto recomendado é o que ganha do Köppen nos três esquemas e nos dois modelos
com o mesmo sinal nas repetições; entre os que cumprem isso, o de maior ganho médio, e, em empate (diferença
dentro da faixa entre repetições), o de **menos variáveis**.

## 3. Trajetórias

Os cenários levados ao painel 1985-2024 (13.680 locais) com o modelo final de cada um (matriz inteira), com o
ranger e com o modelo do mapa + pós-processamento; comparação com o SOC oficial e com o Köppen.

## 4. Etapas e arquivos

| Etapa | Código | Saída |
|---|---|---|
| 1. Cenários e partições | `codigo/cenarios_final.py` | `dados/matriz_final.parquet`, `codigo/cenarios_final.json`, `tabelas/particoes.csv` |
| 2. Validações | `validacao.R`, `validacao_gee.py` com `VAL_*` | `dados/oof_ranger/`, `dados/oof_mapa/` |
| 3. Métricas | `codigo/metricas_final.py` | `tabelas/final_metricas.csv`, `final_resumo.csv` |
| 4. Painel | `codigo/painel_final.py` | `dados/painel_final.parquet` |
| 5. Predição do painel | `prever_painel.R`, `prever_painel_gee.py` com `VAL_*` | `dados/painel_predicoes*.parquet` |
| 6. Trajetórias | `codigo/trajetorias_final.py` | `tabelas/trajetorias_final_*.csv`, `figuras/trajetorias_final*.png` |
| 7. Relatório | — | `relatorios/relatorio_tecnicov6.md` |

Dados por ponto em `clima_final/dados/` (fora do git).
