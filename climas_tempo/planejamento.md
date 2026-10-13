# Planejamento: classificações climáticas no tempo (decenais) a partir do Xavier (BR-DWGD)

**Objetivo.** Testar se uma classificação climática que **muda no tempo** representa melhor o clima para o
SOC do que as normais estáticas. Separa dois efeitos vistos no relatório v2: o Köppen IPEF perde por ser
**classe** (dummies sem gradiente) ou por ser **estático**? O contínuo decenal foi o melhor no tempo.

**Sistemas** (como no relatório v1, §4, agora por década):

| Sistema | Entradas | Função (`agrometeorologiapy` 0.3.0) |
|---|---|---|
| Köppen-Geiger (Alvares et al. 2013; f/s/w de Kottek et al. 2006) | T, P mensais | `classificacao_koppen_grade` |
| Holdridge, ETP original (58,93 × biotemperatura) | T, P mensais | `classificacao_holdridge_grade` (ETP=None) |
| Thornthwaite (1948), CAD do solo | P, ETP mensais (ETo do Xavier, Penman-Monteith) | `classificacao_thornthwaite_grade` |
| Zonas k10 | 9 variáveis do clima contínuo (T, P, ETP, balanço hídrico CAD 100) | centróides de `corelacao/codigo/zonas_clima.py` |

**Dados.** Xavier et al. (2022), BR-DWGD v3.2.2 no GEE (`projects/sat-io/open-datasets/BR-DWGD/`), diário,
0,1° (391 × 393 pixels). Inteiros codificados: T = b1 × 0,001068148 + 15 (°C); chuva = b1 × 0,006866665 + 225
(mm); ETo = b1 × 0,051181102 (mm). **Cobertura no GEE:** temperatura e ETo de 1961 a 31/07/2020; chuva de
1961 a 2022.

**Filtro de moda 3 × 3 em todas as classificações** (decisão do usuário, 13/10/2026): o `focalMode` que no
relatório v1 só existia no Holdridge (vinha do script JS original) passa a valer para os quatro sistemas. Na
grade de 0,1° a janela cobre ~33 km (no CHELSA, ~3 km). No Thornthwaite, a moda é tomada no código L2
(umidade + subtipo).

**Décadas** (decisão do usuário, 13/10/2026): uma classificação por década, alinhada à série de predições do
MapBiomas: **1985-1994, 1995-2004, 2005-2014 e 2015-2024** (os mesmos períodos da V3 do relatório v2). Cada
amostra de SOC recebe a classe da sua década. Na última década a normal tem ~5,5 anos de temperatura (até
07/2020) e 8 de chuva (até 2022); registrado em `n_anos_T` e `n_anos_P`.

**Validação da biblioteca (13/10/2026).** Com as normais do CHELSA 1991-2020 em 3.000 locais, a 0.3.0
reproduz o Köppen dos mapas do relatório v1 em **100%** e o Holdridge ETH em **98,9%** (as diferenças são de
fronteira: o mapa do v1 passou por filtro de moda 3 × 3, a biblioteca classifica pixel a pixel).

**Etapas**

1. `baixar_xavier.py`: médias/somas mensais de cada ano (1961-2022) no GEE, baixadas como arrays (fora do git).
2. `classificar.py`: normais das quatro décadas e as quatro classificações (com moda 3 × 3); normal 1991-2020.
3. `mapas.py`: figuras como as do relatório v1 (§4), por década, mapa de mudança de classe e área por classe
   ao longo do tempo; conferência contra o CHELSA 1991-2020.
4. Avaliação no SOC (como o capítulo 1 do relatório v2): classes de cada ano nos pontos, cenários nas
   validações V2/V3/V4, contra o Köppen IPEF e o contínuo decenal.

Dados por pixel em `climas_tempo/dados/` (fora do git).
