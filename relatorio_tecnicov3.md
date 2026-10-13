# Relatório técnico v3: classificações climáticas que mudam no tempo (Xavier, 1985-2024) no modelo de SOC

**Repositório:** `MapBiomas_analises` (GitHub `fcoliveira-utfpr/climate_for_soil`), pasta `climas_tempo/`
**Período das análises:** 13 de outubro de 2026
**Escopo:** classificar o clima do Brasil por década (1985-1994, 1995-2004, 2005-2014, 2015-2024) com os
dados diários do Xavier (BR-DWGD), em quatro sistemas (Köppen-Geiger, Holdridge com a ETP original,
Thornthwaite com a CAD do solo e zonas k10), mapear as mudanças e testar no modelo de SOC do MapBiomas Solo C3
se uma classificação que **muda no tempo** representa o clima melhor do que as normais estáticas. Continua os
relatórios [v1](relatorio_tecnico.md) (classificações a partir do CHELSA) e [v2](relatorio_tecnicov2.md)
(reconstrução do pipeline de produção e validação espaço-temporal).

---

## Sumário

1. [Pergunta](#1-pergunta)
2. [Dados e método](#2-dados-e-método)
3. [A biblioteca agrometeorologiapy](#3-a-biblioteca-agrometeorologiapy)
4. [Mapas: o clima do Brasil por década](#4-mapas-o-clima-do-brasil-por-década)
5. [As classificações no modelo de SOC](#5-as-classificações-no-modelo-de-soc)
6. [Síntese](#6-síntese)
7. [Limitações e próximos passos](#7-limitações-e-próximos-passos)
8. [Anexo: arquivos, comandos e reprodução](#8-anexo-arquivos-comandos-e-reprodução)

---

## 1. Pergunta

No relatório v2, o Köppen IPEF (a única variável de clima do modelo de SOC do MapBiomas) ficou entre os
piores cenários, e o melhor no tempo foi o **clima contínuo decenal** (temperatura, chuva e dias secos
consecutivos da década anterior à amostra). Ficou em aberto **por que** o Köppen perde:

- por ser **classe** (13 dummies, sem gradiente, quase toda a informação já presente em biomas e
  fitofisionomias; relatório v2, §5.7); ou
- por ser **estático** (uma normal só, 1991-2020 no CHELSA ou ~1950-1990 no IPEF, aplicada a amostras de
  1985 a 2024).

Este capítulo separa os dois efeitos: cada sistema de classificação entra no modelo em duas versões, com a
**mesma fonte de dados (Xavier)** e o **mesmo sistema**, uma **estática** (normal 1991-2020) e uma
**decenal** (a década de cada amostra). A diferença entre as duas é o efeito de o clima mudar no tempo.

---

## 2. Dados e método

### 2.1 Xavier (BR-DWGD)

Xavier et al. (2022, *Int. J. Climatol.*, doi 10.1002/joc.7731), versão 3.2.2 no GEE
(`projects/sat-io/open-datasets/BR-DWGD/`): dados diários interpolados de estações e pluviômetros, grade de
0,1° (391 × 393 pixels sobre o Brasil). Os valores estão codificados como inteiros:

| Variável | Coleção | Conversão | Cobertura no GEE |
|---|---|---|---|
| Temperatura máxima e mínima (°C) | `TMAX`, `TMIN` | valor × 0,001068148 + 15 | 01/01/1961 a 31/07/2020 |
| Chuva (mm) | `PR` | valor × 0,006866665 + 225 | 01/01/1961 a 31/12/2022 |
| ETo, Penman-Monteith FAO-56 (mm) | `ET` | valor × 0,051181102 | 01/01/1961 a 31/07/2020 |

`codigo/baixar_xavier.py` agrega no GEE, para cada ano de 1961 a 2022, a temperatura média mensal (média de
(Tmax + Tmin)/2), a chuva e a ETo mensais, e baixa os arrays (`computePixels`, ~22 MB por ano).
Conferência em Curitiba, 2010: temperatura de 15,1 °C (agosto) a 23,8 °C (fevereiro), chuva de 332 mm em
janeiro, ETo de 46 a 114 mm/mês.

### 2.2 Décadas

Uma classificação por década, alinhada à série anual de SOC do MapBiomas (1985-2024): **1985-1994,
1995-2004, 2005-2014 e 2015-2024** (os mesmos períodos da validação temporal V3 do relatório v2). A normal da
década é a média de cada mês nos anos disponíveis. Como a temperatura e a ETo terminam em 07/2020 e a chuva em
2022, **a última década tem 5 a 6 anos de temperatura e 8 de chuva**. Para a conferência com o relatório v1,
também foi calculada a normal 1991-2020.

### 2.3 Classificações

Feitas localmente, pixel a pixel, com a biblioteca do autor, `agrometeorologiapy` 0.3.0 (§3):

| Sistema | Entradas | Função | Níveis usados no modelo |
|---|---|---|---|
| Köppen-Geiger (Alvares et al. 2013; f/s/w de Kottek et al. 2006) | T, P mensais | `classificacao_koppen_grade` | L1 (A, B, C), L2 (Af, Am, As, Aw, BS, BW, Cf, Cs, Cw), L3 (classe) |
| Holdridge, ETP original (58,93 × biotemperatura) | T, P mensais | `classificacao_holdridge_grade` | L1 (faixa térmica), L2 (zona de vida) |
| Thornthwaite (1948), CAD do solo | P e ETo mensais | `classificacao_thornthwaite_grade` | L1 (umidade), L2 (umidade + subtipo) |
| Zonas k10 | 9 variáveis do clima contínuo | k-means (§2.4) | zona |

- **CAD do solo:** a AWC do relatório v1 (mm por metro de solo, grade de 1 km), média em cada pixel de 0,1°.
- **Filtro de moda 3 × 3 em todas as classificações** (decisão do autor): o `focalMode` que no v1 só
  existia no Holdridge (vinha do script JS original) passa a valer para os quatro sistemas. Na grade de
  0,1° a janela cobre ~33 km (no CHELSA, ~3 km). No Thornthwaite, a moda é tomada no código L2.

### 2.4 Zonas k10 reajustadas no Xavier

As zonas do v1 foram ajustadas no CHELSA; com os centróides do CHELSA, as zonas do Xavier concordavam só em
67% da área, por diferença de base (a ETo do Xavier é ~12% menor que a ETP do CHELSA). Por decisão do autor,
o k-means foi **reajustado no Xavier**, com o mesmo método do v1 (`corelacao/codigo/zonas_clima.py`): k = 10,
as 9 variáveis (temperatura média e do mês mais frio, chuva anual e do mês mais seco, sazonalidade da chuva,
ETP anual, DEF, EXC e Im do balanço hídrico com CAD de 100 mm), padronizadas, chuva/DEF/EXC em log, ajuste na
normal 1991-2020 do Xavier com peso pela área (cos da latitude), zonas numeradas da mais quente para a mais
fria. Cada década recebe a zona do centróide mais próximo.

| Zona | T média (°C) | T mês frio | Chuva (mm) | Chuva mês seco | ETP (mm) | DEF (mm) | EXC (mm) | Im |
|---|---|---|---|---|---|---|---|---|
| 1 | 27,2 | 26,0 | 1.432 | 2 | 1.544 | 557 | 423 | 9,7 |
| 2 | 27,2 | 26,5 | 2.639 | 126 | 1.242 | 0 | 1.378 | 114,8 |
| 3 | 27,2 | 26,4 | 2.328 | 50 | 1.312 | 82 | 1.109 | 82,2 |
| 4 | 26,6 | 25,5 | 1.940 | 13 | 1.361 | 272 | 855 | 52,0 |
| 5 | 26,5 | 24,6 | 653 | 1 | 1.848 | 1.158 | 0 | −38,0 |
| 6 | 24,7 | 22,0 | 1.301 | 4 | 1.453 | 428 | 242 | 3,2 |
| 7 | 24,6 | 21,5 | 769 | 17 | 1.511 | 612 | 0 | −27,4 |
| 8 | 24,2 | 20,8 | 1.376 | 38 | 1.422 | 108 | 92 | 2,4 |
| 9 | 21,6 | 18,3 | 1.375 | 13 | 1.254 | 193 | 324 | 18,0 |
| 10 | 19,5 | 14,6 | 1.702 | 92 | 1.140 | 2 | 549 | 51,5 |

---

## 3. A biblioteca agrometeorologiapy

A versão instalada era a 0.2.0 (sem classificação climática); a 0.3.0, do GitHub do autor, tem o módulo
`classificacao_climatica` (Köppen, Thornthwaite, Camargo e Holdridge, cada um em versão pontual e vetorizada
para grade).

**Revisão das regras.** Köppen (grupos, limiar de aridez 2T/2T+14/2T+28, Af/Am/As/Aw, f/s/w de Kottek,
a/b/c/d, troca de estações no hemisfério norte), Holdridge (correção de latitude só acima de 24 °C, ETP
original, 38 zonas de Leemans/Jungkunst) e Thornthwaite (Im = Ih − 0,6 Ia, Tabelas de Aparecido et al. 2016
com as três correções pelo original) conferem com a literatura e com as correções feitas no relatório v1.
Única ressalva: no grupo D (frio continental), a letra *d* (Tmin < −38 °C) tem precedência sobre *a*/*b*,
quando pelo Kottek só vale depois delas; não ocorre no Brasil.

**Teste numérico.** Com as normais do CHELSA 1991-2020 em 3.000 locais, a 0.3.0 reproduz o Köppen dos mapas
do v1 em **100%** (2.998 de 2.998) e o Holdridge (ETP original) em **98,9%**; as 32 diferenças estão em
fronteiras de classe (biotemperatura perto de 18 e 24 °C, ETP/P perto de 0,5, 1 e 2) e vêm do filtro de moda
do mapa do v1, já que a biblioteca classifica pixel a pixel.

---

## 4. Mapas: o clima do Brasil por década

Código: `codigo/classificar.py` e `codigo/mapas.py`. Paletas do v1, exceto o Holdridge, que ganhou uma
família de cores por faixa térmica (a paleta do v1 repetia os azuis entre temperado quente e subtropical).

### 4.1 Köppen-Geiger

![Köppen por década](climas_tempo/resultados/figuras/koppen_decadas.png)
*Figura 1. Köppen-Geiger por década, Xavier.*

| Classe (% da área) | 1985-1994 | 1995-2004 | 2005-2014 | 2015-2024 |
|---|---|---|---|---|
| Aw | 42,9 | 46,0 | 48,4 | 46,7 |
| Am | 20,2 | 18,1 | 17,7 | 19,1 |
| Af | 18,8 | 18,3 | 17,2 | 17,6 |
| Cfa | 7,0 | 5,7 | 5,7 | 5,7 |
| BSh | 5,1 | 6,3 | 7,3 | 7,3 |
| As | 3,0 | 3,2 | 1,5 | 1,6 |
| Cwa | 1,7 | 1,3 | 1,2 | 1,0 |
| Cfb | 1,1 | 0,9 | 0,8 | 0,5 |

O Aw avança sobre o sul da Amazônia, o semiárido (BSh) cresce de 5,1% para 7,3% e surge o **BWh (árido)** no
centro do semiárido a partir de 2005-2014; o Cfb das serras do Sul encolhe.

### 4.2 Holdridge (ETP original)

![Holdridge por década](climas_tempo/resultados/figuras/holdridge_decadas.png)
*Figura 2. Zonas de vida de Holdridge por década, Xavier.*

| Zona (% da área) | 1985-1994 | 1995-2004 | 2005-2014 | 2015-2024 |
|---|---|---|---|---|
| 37 Tropical moist forest | 49,7 | 47,7 | 45,4 | 42,0 |
| 29 Subtropical moist forest | 23,0 | 23,9 | 25,8 | 23,9 |
| 28 Subtropical dry forest | 10,9 | 12,0 | 12,0 | 17,3 |
| 36 Tropical dry forest | 7,9 | 7,8 | 6,9 | 5,9 |
| 35 Tropical very dry forest | 3,4 | 4,0 | 3,9 | 3,3 |
| 38 Tropical wet forest | 2,4 | 1,5 | 2,1 | 3,8 |
| 27 Subtropical thorn steppe | 1,6 | 1,8 | 2,9 | 2,9 |
| 22 Warm temperate moist forest | 1,2 | 1,0 | 0,9 | 0,6 |

**O Holdridge não enxerga o aquecimento.** A temperatura média do Brasil sobe 1 °C (25,13 → 26,10 °C) e a
ETo sobe 100 mm, mas a biotemperatura fica em ~24,1 °C nas quatro décadas: a correção de latitude
(t − 3·|lat|/100·(t − 24)², nos meses acima de 24 °C) desconta cada vez mais à medida que os meses quentes
esquentam. Como o Brasil está em média na fronteira tropical/subtropical (24 °C), a mudança aparece como
"tropical → subtropical" no Brasil Central, um efeito do método, não um resfriamento.

| Média do Brasil | 1985-1994 | 1995-2004 | 2005-2014 | 2015-2024 |
|---|---|---|---|---|
| Temperatura (°C) | 25,13 | 25,62 | 25,80 | 26,10 |
| Chuva (mm/ano) | 1.775 | 1.732 | 1.753 | 1.771 |
| ETo (mm/ano) | 1.331 | 1.392 | 1.423 | 1.430 |
| Biotemperatura (°C) | 24,12 | 24,18 | 24,19 | 24,11 |

### 4.3 Thornthwaite (CAD do solo)

![Thornthwaite por década](climas_tempo/resultados/figuras/thornthwaite_decadas.png)
*Figura 3. Classe de umidade de Thornthwaite por década, Xavier.*

| Classe de umidade (% da área) | 1985-1994 | 1995-2004 | 2005-2014 | 2015-2024 |
|---|---|---|---|---|
| A (superúmido) | 14,1 | 8,8 | 9,4 | 12,6 |
| B4 | 11,6 | 9,1 | 9,8 | 10,3 |
| B3 | 14,7 | 15,4 | 13,9 | 11,3 |
| B2 | 12,3 | 15,5 | 13,7 | 12,7 |
| B1 | 14,4 | 14,7 | 12,9 | 11,0 |
| C2 | 13,3 | 13,8 | 16,4 | 15,1 |
| C1 | 8,4 | 10,5 | 11,2 | 12,9 |
| D (semiárido) | 9,3 | 9,2 | 8,7 | 10,1 |
| E (árido) | 1,9 | 3,0 | 4,0 | 4,0 |

Ressecamento: com a chuva estável e a ETo 100 mm/ano maior, o índice de umidade cai e as classes secas (C1,
D, E) crescem. Como as faixas de umidade são estreitas (20 pontos de Im), **52% da área muda de classe**. A ETo
do Xavier depende de vento, radiação e umidade, interpolados de bem menos estações que a chuva, e deixa
"anéis" em torno das estações (Figura 5), o que amplia a mudança.

### 4.4 Zonas k10 (reajustadas no Xavier)

![k10 por década](climas_tempo/resultados/figuras/k10_decadas.png)
*Figura 4. Zonas climáticas k10 por década, Xavier.*

| Zona (% da área) | 1985-1994 | 1995-2004 | 2005-2014 | 2015-2024 |
|---|---|---|---|---|
| 1 (a mais quente, DEF 557 mm) | 8,2 | 11,5 | 14,4 | **16,5** |
| 2 (quente e superúmida) | 11,9 | 10,7 | 10,7 | 10,1 |
| 3 (quente e úmida) | 20,9 | 16,9 | 16,9 | 19,9 |
| 4 (quente, seca moderada) | 18,9 | 20,5 | 18,5 | 15,5 |
| 5 (semiárido) | 6,1 | 7,1 | 7,7 | 8,4 |
| 6 | 10,6 | 12,1 | 11,7 | 10,0 |
| 7 (semiárido ameno) | 4,0 | 5,5 | 4,8 | 5,9 |
| 8 | 5,2 | 4,5 | 4,5 | 4,5 |
| 9 (amena) | 7,1 | 4,6 | 4,2 | **2,9** |
| 10 (a mais fria, Sul) | 7,2 | 6,6 | 6,4 | 6,3 |

A zona mais quente e com seca marcada (1) dobra de área; a zona amena (9) cai para menos da metade.

### 4.5 Mudança de classe e conferência com o CHELSA

![Mudanças](climas_tempo/resultados/figuras/mudancas_1985_2024.png)
*Figura 5. Pixels que mudaram de classe entre 1985-1994 e 2015-2024.*

| Sistema | Área que mudou de classe | Principais transições | Concordância Xavier × CHELSA, 1991-2020 |
|---|---|---|---|
| Köppen | 16,7% | Am → Aw, Af → Am, Aw → BSh | **88%** |
| Holdridge | 24,1% | 29 → 28, 37 → 29, 37 → 38 | 83% |
| Thornthwaite (umidade) | 52,5% (L2: 57,6%) | B1 → C2, C2 → C1, B3 → B2 | 41% |
| k10 | 27,7% | 4 → 1, 3 → 4, 9 → 6 | 76% (após parear as zonas) |

![Conferência com o CHELSA](climas_tempo/resultados/figuras/conferencia_chelsa.png)
*Figura 6. Normal 1991-2020: CHELSA (relatório v1, em cima) e Xavier (embaixo).*

A concordância alta no Köppen confirma que o Xavier e o CHELSA descrevem o mesmo clima; a baixa no
Thornthwaite vem da ETo do Xavier ser ~200 mm/ano (12%) menor que a ETP do CHELSA (1.401 × 1.600 mm, média do
Brasil), o que deixa o país mais úmido no Xavier.

---

## 5. As classificações no modelo de SOC

<!-- SOC -->

---

## 6. Síntese

<!-- SINTESE -->

---

## 7. Limitações e próximos passos

<!-- LIMITACOES -->

---

## 8. Anexo: arquivos, comandos e reprodução

<!-- ANEXO -->
