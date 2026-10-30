# Planejamento — C4: conjunto curto com o Xavier v3.2.4 (1961-2025) (relatório v7)

**Pergunta.** O conjunto curto recomendado no v6 (7 variáveis de temperatura decenal + CDD + ARM com a CAD do
solo) foi calculado com o Xavier do catálogo comunitário do GEE (`projects/sat-io/open-datasets/BR-DWGD/`,
v3.2.2), em que temperatura, umidade, radiação e vento terminam em 07/2020 e a chuva em 2022. Com isso, as
janelas de 10 anos de 2021-2024 ficavam incompletas (6 a 9 anos de temperatura). O autor publicou a v3.2.4
(abril de 2026; no GEE em `projects/ee-alexandrexavier/assets/BR-DWGD` desde maio de 2026), com **todas as
variáveis até 31/12/2025**. Com ela:

1. o resultado da validação do v6 se mantém?
2. as trajetórias 1985-2024 mudam, sobretudo depois de 2020?

## 1. Dados

- **Xavier v3.2.4**, diário, 0,1° (a mesma grade 391 × 393), 1961-2025, agregado em meses a partir do diário
  (a coleção mensal do autor não bate com a soma dos dias num teste e não é usada). Escalas lidas das
  propriedades de cada imagem.
- **Conferência com a v3.2.2 em 2010:** médias mensais quase iguais, r = 0,97 (vento) a 0,999 (Tmax).
- **CDD anual** calculado no GEE com o mesmo algoritmo de `cdd_brdwgd.py` (v2), da chuva diária da v3.2.4, e
  baixado como array (sem asset). Entra como `cd_cdd`.
- Altitude, latitude e CAD do solo: as já calculadas (`clima_decenal/dados/altitude.npy`,
  `climas_tempo/dados/grade.npz`), lidas no lugar.

## 2. Cenários e validação

- Só os cenários que dependem do Xavier são refeitos: `temperatura` (7) e `curto` (7 + `cd_cdd` +
  `cd_arm_csolo`).
- **Mesma matriz, partições e sementes do v6** (partição nova das dobras V2/V4 com semente 2027,
  `VAL_SEMENTE` = 2984): as predições das referências (Köppen IPEF, sem clima, contínuo decenal do GT) são as
  do v6, e a comparação v6 × C4 do mesmo cenário mede **só o efeito da versão do Xavier**.
- Ranger validado e modelo do mapa; 3 repetições; amostras reais de 0-30 cm.

## 3. Trajetórias

Painel de 13.680 locais × 1985-2024 com as cd_* da v3.2.4; modelo final de cada cenário; comparação com o
conjunto curto do v6, o Köppen e o SOC oficial.

## 4. Etapas e arquivos

| Etapa | Código (em `C4/codigo/`) | Saída |
|---|---|---|
| 1. Xavier v3.2.4 mensal + CDD anual | `baixar_xavier.py` | `dados/xavier_mensal/<ano>.npz` |
| 2. ETo pelo Rn | `eto_rn.py` | `dados/eto_rn/<ano>.npz`, `tabelas/conferencia_eto.csv` |
| 3. Variáveis decenais (1985-2026) | `variaveis.py` | `dados/variaveis/<ano>.npz`, `n_anos.csv` |
| 4. Pontos e cenários | `pontos.py` | `dados/matriz_c4.parquet`, `codigo/cenarios_c4.json`, `tabelas/variaveis_c4.csv` |
| 5. Validações | `validacao.R`, `validacao_gee.py` com `VAL_*` | `dados/oof_ranger/`, `dados/oof_mapa/` |
| 6. Métricas | `metricas_c4.py` | `tabelas/c4_metricas.csv`, `c4_resumo.csv` |
| 7. Painel | `painel_c4.py` | `dados/painel_c4.parquet` |
| 8. Predição do painel e trajetórias | `prever_painel*` com `VAL_*`; `trajetorias_c4.py` | `tabelas/trajetorias_c4_*.csv`, `figuras/trajetorias_c4*.png` |
| 9. Relatório | — | `relatorios/relatorio_tecnicov7.md` |

Dados em `C4/dados/` (fora do git).
