# Planejamento — Köppen dinâmico por média móvel de 30 anos (capítulo 5, relatório v5)

**Pergunta.** Uma classificação climática que **anda com o tempo**, calculada sempre sobre os 30 anos
anteriores a cada ano, representa melhor o clima para o SOC do que o Köppen IPEF estático usado pelo
MapBiomas?

**Diferença em relação aos capítulos anteriores:**
- capítulo 3 (`climas_tempo/`, relatório v3): Köppen por **década fixa** (normal de 10 anos: 1985-1994,
  1995-2004…), que troca de classe só de 10 em 10 anos e com normais curtas;
- capítulo 4 (`clima_decenal/`, relatório v4): variáveis **contínuas** em média móvel de 10 anos;
- **aqui:** uma **classificação** (Köppen) em **média móvel de 30 anos**, o período de uma normal climatológica
  (OMM), recalculada **a cada ano**. Muda devagar e de forma contínua, e cada ano usa uma normal completa.

## 1. Cenários (só estes dois)

| Cenário | Clima | Muda no tempo? |
|---|---|---|
| `koppen_ipef` (referência) | Köppen IPEF (Alvares et al. 2013), dummies L1-L3 da produção | não |
| `koppen_movel30` | Köppen do Xavier, normal de **Y−30 a Y−1** para cada ano Y, dummies L1-L3 | **sim, a cada ano** |

Todo o resto (covariáveis da produção, amostras, dobras, modelo) é igual entre os dois; só o clima muda.

## 2. Dados

- **Xavier et al. (2022), BR-DWGD v3.2.2** no GEE (`projects/sat-io/open-datasets/BR-DWGD/`), diário, 0,1°
  (391 × 393 pixels). Mesmo download mensal do capítulo 3 (`climas_tempo/codigo/baixar_xavier.py`): T média
  mensal = média de (Tmax + Tmin)/2 diários; chuva mensal = soma. Escalas: T = b1 × 0,001068148 + 15 (°C);
  chuva = b1 × 0,006866665 + 225 (mm).
- **Cobertura:** temperatura de 1961 a 31/07/2020; chuva de 1961 a 2022.
- **Matriz de SOC e painel:** os do relatório v2 (`climas/dados_espaco_tempo/matriz_cenarios.parquet` = a
  `trainingFinal` reconstruída, com as dobras V2/V3/V4; `painel_*`), fora do git.

### 2.1 Janelas de 30 anos e anos incompletos

Para o ano Y: normal mensal de T e de chuva sobre os anos Y−30 a Y−1 disponíveis; registrar `n_anos_T` e
`n_anos_P` por ano.

| Ano Y | Janela | Anos com T | Anos com chuva | Observação |
|---|---|---|---|---|
| 1985 | 1955-1984 | 24 (1961-1984) | 24 | o Xavier começa em 1961 |
| 1991 | 1961-1990 | 30 | 30 | primeira janela completa |
| 1991-2020 | … | 30 | 30 | completas |
| 2021 | 1991-2020 | 29,6 (T até 07/2020) | 30 | |
| 2024 | 1994-2023 | 26,6 | 29 | T termina em 07/2020; chuva em 2022 |

A partir de 2021, a janela da temperatura perde os anos depois de 07/2020. Para um clima que muda devagar,
26-30 anos ainda dão uma normal estável; registrar e conferir se a classe muda por isso (§4).
**Alternativa, se fizer diferença:** a grade do Xavier atualizada em março de 2025 (download no GitHub do
BR-DWGD, NetCDF) cobre anos mais recentes que o asset do GEE.

## 3. Classificação

- `classificacao_koppen_grade(T, P, lat)` da `agrometeorologiapy` (a mesma do capítulo 3, validada: 100% de
  concordância com o Köppen do relatório v1 nas normais do CHELSA). Conferir que a versão instalada dá o
  mesmo resultado que a 0.3.0 usada no capítulo 3.
- **Filtro de moda 3 × 3** em todos os anos, como no capítulo 3 (decisão do usuário, 13/10/2026).
- Saída: pilha `koppen_movel30` (40, 393, 391), um mapa por ano de 1985 a 2024.

## 4. Conferências antes de modelar

- **Consistência:** o mapa de 2021 (janela 1991-2020) deve ser quase igual ao Köppen estático do Xavier
  1991-2020 do capítulo 3; e parecido com o Köppen do CHELSA 1991-2020 (relatório v1).
- **Quanto muda:** fração da área do Brasil e fração dos pontos de SOC que mudam de classe entre 1985 e 2024;
  área de cada classe ano a ano; mapa de mudança (A ↔ C no Sudeste, Am ↔ Aw no arco do desmatamento,
  BSh ↔ Aw no semiárido são as transições esperadas).
- **Efeito das janelas incompletas:** comparar a classe de 2021-2024 com a de 2020.

## 5. Nos pontos de SOC

- Cada linha da matriz recebe o Köppen do **seu ano** (o ano da coleta, como as covariáveis dinâmicas);
  cada ano do painel 1985-2024 recebe o do ano correspondente.
- Dummies hierárquicas L1 (A, B, C), L2 (Af, Am, As, Aw, BS, BW, Cf, Cs, Cw) e L3 (classe), como as do Köppen
  na produção; dummies com menos de 30 ocorrências são descartadas (regra do R 26). Ponto em pixel sem dado
  (litoral) recebe a classe do pixel válido mais próximo (como no capítulo 3).

## 6. Validação (mesma do relatório v2)

- **V2** espacial (blocos de 2°), **V3** temporal (deixa uma década de fora), **V4** espaço-temporal; as mesmas
  dobras e 3 repetições; ganho do `koppen_movel30` sobre o `koppen_ipef` por repetição.
- Com o **ranger validado** (`climas/analise_espaco_tempo/codigo/validacao.R`, via `VAL_MATRIZ`,
  `VAL_CENARIOS`, `VAL_OOF`) e com o **modelo do mapa oficial** (`validacao_gee.py`).
- Métricas do MapBiomas (ME, MAE, RMSE, MEC, slope) em t/ha, 0-30 cm, com amostras reais e com todas as
  linhas.
- **Trajetórias 1985-2024** no painel: tendência e variação ano a ano dos dois cenários e do SOC oficial; se a
  mudança de classe ao longo do tempo aparece nas trajetórias.

## 7. Leitura esperada (hipóteses a testar)

- No **espaço** (V2), os dois devem empatar: em quase todo o país a classe de 30 anos não muda ao longo de
  1985-2024 e é próxima da do IPEF.
- No **tempo** (V3, V4), é onde o dinâmico pode ganhar, se as poucas mudanças de classe acompanharem o SOC.
  O capítulo 3 sugere cautela: lá, o Köppen decenal não ganhou do estático, porque o Köppen perde por ser
  **classe** (sem gradiente), não por ser estático; com 30 anos o sinal fica mais estável e menos ruidoso
  que com 10.

## 8. Etapas e arquivos

| Etapa | Código | Saída |
|---|---|---|
| 1. Xavier mensal 1961-2022 | `climas_tempo/codigo/baixar_xavier.py` (reaproveitado) | `climas_tempo/dados/xavier_mensal/` |
| 2. Köppen móvel 1985-2024 | `codigo/classificar_movel30.py` | `climas/dados_koppen_movel30/koppen_movel30.npz` |
| 3. Mapas e conferências | `codigo/mapas.py` | `resultados/figuras/`, `resultados/tabelas/` |
| 4. Cenários nos pontos | `codigo/cenarios.py` | `matriz_movel30.parquet`, `cenarios_movel30.json` |
| 5. Validação V2/V3/V4 (ranger e modelo do mapa) | `validacao.R`, `validacao_gee.py` com `VAL_*` | `resultados/tabelas/validacao_*.csv` |
| 6. Trajetórias | `prever_painel*` com `VAL_*` | tabelas e figuras |
| 7. Relatório | — | `relatorios/relatorio_tecnicov5.md` |

Dados por pixel e por ponto em `climas/dados_koppen_movel30/` (fora do git).

## 9. Onde rodar

Nesta máquina (Mac) faltam a matriz e o painel (`climas/dados_espaco_tempo/`, restritos, ficaram no outro
PC) e o pacote `ranger` do R. As etapas 1-3 rodam aqui (só GEE e Python); a 4-6 precisam da matriz: copiar
`climas/dados_espaco_tempo/` do outro PC para cá (e instalar o `ranger`) ou rodar essas etapas no outro PC.
