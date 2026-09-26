# climate_for_soil — clima como base para estimar carbono e textura do solo no Brasil

O MapBiomas Solo usa o **Köppen** (versão IPEF, Alvares et al. 2013) como **única informação climática** dos
seus modelos de carbono orgânico do solo (SOC) e de textura (areia, silte, argila). Este repositório investiga
se existe uma representação do clima **melhor para essa finalidade**: valida bases climáticas contra
estações, constrói classificações climáticas corrigidas a partir do CHELSA V2.1, compara essas classificações
como base para SOC e textura (0-30 cm) e, por fim, testa cada clima **dentro dos modelos do MapBiomas Solo
coleção 3**, reproduzidos em Python, com mapas.

> **Resumo dos resultados:** trocar as dummies do Köppen por **12 variáveis climáticas contínuas** do CHELSA
> e do balanço hídrico é a melhor opção (SOC: +0,025 de R² espacial no modelo fiel, +0,038 sem a textura da
> coleção 2). Se for preciso uma variável categórica, as **zonas climáticas homogêneas k10** (k-means sobre o
> clima do Brasil) são a melhor classificação. O Köppen IPEF, hoje, praticamente não acrescenta informação
> ao modelo de SOC.

**Relatório completo:** [relatorio_tecnico.md](relatorio_tecnico.md) (metodologia, decisões, resultados,
13 figuras). **Registro de decisões:** [corelacao/docs/memoria_fabricio.md](corelacao/docs/memoria_fabricio.md).
**Todos os assets do GEE usados:** [climas/dados_chelsa/assets_utilizados.md](climas/dados_chelsa/assets_utilizados.md).

---

## Sumário

1. [Perguntas e etapas](#1-perguntas-e-etapas)
2. [Principais resultados](#2-principais-resultados)
3. [Estrutura do repositório](#3-estrutura-do-repositório)
4. [Dados](#4-dados)
5. [Metodologia resumida](#5-metodologia-resumida)
6. [Como reproduzir](#6-como-reproduzir)
7. [Limitações](#7-limitações)
8. [Referências](#8-referências)

---

## 1. Perguntas e etapas

Cada etapa respondeu a uma pergunta e motivou a seguinte:

| Etapa | Pergunta | Onde |
|---|---|---|
| **Validação** | Qual base climática em grade reproduz melhor as estações? | [`validacao/`](validacao/) |
| **Pipeline CHELSA** | Como obter normais 1991-2020 confiáveis a ~1 km para o Brasil? | [`climas/chelsa_climas_brasil/`](climas/chelsa_climas_brasil/) |
| **Classificações** | Köppen, Holdridge e Thornthwaite corretos a partir do CHELSA | [`climas/chelsa_climas_brasil/`](climas/chelsa_climas_brasil/) |
| **Comparação** | Qual classificação, **sozinha**, separa melhor SOC e textura? | [`corelacao/comparacao_climas.ipynb`](corelacao/comparacao_climas.ipynb) |
| **Experimento** | O que colocar no lugar do Köppen **dentro** de um modelo com as covariáveis do MapBiomas? | [`corelacao/experimento_clima_modelos.ipynb`](corelacao/experimento_clima_modelos.ipynb) |
| **Reprodução** | O resultado se mantém **reproduzindo fielmente** os modelos do MapBiomas C3? E os mapas? | [`climas/reproducao/reproducao_resultados.ipynb`](climas/reproducao/reproducao_resultados.ipynb) |

---

## 2. Principais resultados

### 2.1 Base climática: CHELSA V2.1

Comparação com 22 estações (2010-2019, ~2.390 pares estação × mês):

| Variável | Base | r | RMSE | NSE | KGE |
|---|---|---|---|---|---|
| Temperatura média | **CHELSA** | 0,990 | 0,82 °C | 0,967 | 0,977 |
| Temperatura média | Xavier | 0,986 | 0,85 °C | 0,965 | 0,919 |
| Temperatura média | ERA5-Land | 0,949 | 1,63 °C | 0,871 | 0,875 |
| Precipitação mensal | **Xavier** | 0,922 | 44,0 mm | 0,846 | 0,903 |
| Precipitação mensal | CHELSA | 0,815 | 66,9 mm | 0,644 | 0,810 |
| Precipitação mensal | ERA5-Land | 0,815 | 66,2 mm | 0,650 | 0,803 |

O CHELSA foi escolhido: temperatura tão boa quanto a do Xavier, chuva empatada com o ERA5-Land, ~1 km e
**ETP de Penman-Monteith** pronta (necessária para Holdridge e Thornthwaite). Um diagnóstico dedicado mostrou
que a primeira normal de chuva no GEE tinha um **artefato de exportação** (subestimativa de 130-250% fora da
faixa 13°S-2°N); os assets foram regerados, um por variável.

### 2.2 Classificações climáticas a partir do CHELSA

Três classificações foram geradas e **corrigidas** em relação aos scripts originais:

- **Holdridge (38 zonas de vida):** correção de latitude só nos meses > 24 °C; numeração de Jungkunst et al.
  (2021), que estava deslocada em uma zona no tropical; duas versões de ETP (Penman-Monteith e a de
  Holdridge, 58,93 × biotemperatura), que mudam 23% dos pixels.
- **Köppen-Geiger (Alvares et al. 2013):** sazonalidade f/s/w dos climas C pelo critério de Kottek et al.
  (2006) (5% da área C ficava sem classe) e troca de estações no hemisfério norte.
- **Thornthwaite (1948) com balanço hídrico (Thornthwaite & Mather 1955):** balanço vetorizado na biblioteca
  `agrometeorologiapy` (v0.2.0), com armazenamento inicial de equilíbrio; tabelas de Aparecido et al. (2016);
  CAD de 100 mm e CAD do solo (AWC). A CAD quase não muda a classificação (98% da área igual).

<p align="center">
<img src="climas/chelsa_climas_brasil/figuras/koppen_chelsa.png" width="32%">
<img src="climas/chelsa_climas_brasil/figuras/holdridge_etpm_eth.png" width="32%">
<img src="climas/chelsa_climas_brasil/figuras/thornthwaite_umidade_subtipo.png" width="32%">
</p>

### 2.3 Qual classificação, sozinha, explica melhor SOC e textura

R² fora da amostra com validação cruzada em **blocos espaciais de 2°** (50 repetições); a classificação é o
único preditor.

| Sistema | log(SOC) | Areia | Silte | Argila |
|---|---|---|---|---|
| **Zonas climáticas k10** | **0,092** | **0,106** | **0,210** | **0,009** |
| Holdridge L2 (ETP de Holdridge) | 0,076 | 0,047 | 0,056 | −0,011 |
| Thornthwaite L2 (CAD 100) | 0,051 | 0,066 | 0,199 | −0,04 |
| Köppen IPEF L3 (referência) | 0,067 | 0,049 | 0,142 | −0,015 |
| Köppen CHELSA L3 | 0,039 | 0,032 | 0,145 | −0,055 |

As zonas k10 vencem todos os sistemas em SOC, areia e silte em **todas** as repetições. Nenhuma classificação
estima argila. Uma classe climática sozinha explica pouco (teto de R² ≈ 0,09-0,10 para SOC).

<p align="center"><img src="corelacao/resultados/figuras/zonas_k10.png" width="60%"></p>

### 2.4 Dentro dos modelos do MapBiomas Solo C3 (reprodução)

Textura por GBM em cada camada de 10 cm sobre razões log; SOC por random forest com a textura prevista como
covariável; 9 cenários de clima; validação em blocos de 2° (5 dobras × 3 repetições, diferenças pareadas).
Duas versões: **fiel** (com os mapas de textura da coleção 2 como covariável, como o MapBiomas faz) e **sem
C2** (esses mapas "entregam" a resposta: com eles o R² da textura vai a 0,82-0,85 e nenhum clima importa).

| Ganho de R² sobre o Köppen IPEF | Textura, fiel | SOC, fiel | Textura, sem C2 | SOC, sem C2 |
|---|---|---|---|---|
| **Clima contínuo (12 variáveis)** | +0,002 | **+0,025** | **+0,023** (silte +0,038) | **+0,038** |
| Zonas k10 | 0,000 | +0,009 | +0,007 | +0,015 |
| Thornthwaite | ~0 | +0,006 | +0,003 | +0,008 a +0,010 |
| Holdridge | ~0 | +0,002 a +0,005 | ~0 | +0,004 a +0,007 |
| Sem clima | ~0 | +0,002 | ~0 | +0,002 |
| Köppen CHELSA | ~0 | −0,001 | +0,002 | −0,002 |

R² de referência (Köppen IPEF): SOC 0,336 (fiel) e 0,232 (sem C2), em log; textura 0,82-0,85 (fiel) e
0,29-0,33 (sem C2). Nas métricas do MapBiomas (ME, MAE, RMSE, MEC, slope), o SOC em t/ha tem MEC de 0,118 com
o Köppen e 0,137 com o clima contínuo (0,156 e 0,176 com a correção de Duan do viés do log).

<p align="center"><img src="climas/reproducao/resultados/figuras/ganho_vs_koppen.png" width="85%"></p>
<p align="center"><img src="climas/reproducao/resultados/figuras/mapa_soc_fiel.png" width="85%"></p>

### 2.5 Recomendação

1. **Trocar as dummies do Köppen pelo clima contínuo** (12 variáveis do CHELSA e do balanço hídrico, todas
   já em assets no GEE).
2. Se for preciso uma covariável categórica, usar as **zonas k10** como dummies. **Não** estratificar os
   modelos por zona (um modelo por zona piora).
3. Discutir o uso da textura da coleção 2 como covariável: ela domina o modelo de textura e esconde a
   contribuição de todas as outras covariáveis, inclusive o clima.

---

## 3. Estrutura do repositório

```
.
├── README.md
├── relatorio_tecnico.md                 # relatório técnico completo
├── validacao/                           # estações × Xavier, CHELSA, ERA5-Land
│   ├── comparacao_v1.ipynb
│   ├── baixar_era5.py, atualizar_dados_chelsa.py
│   ├── *.csv                            # séries das estações e das grades
│   └── figuras/
├── climas/
│   ├── chelsa_climas_brasil/            # normais CHELSA e classificações
│   │   ├── baixar_recortar.py           # baixa só a janela do Brasil dos COGs do CHELSA
│   │   ├── gerar_normal_multibanda.py   # normal 1991-2020, 12 bandas por variável
│   │   ├── diagnostico_chuva_CHELSA_1991_2020.ipynb
│   │   ├── koppen_chelsa.ipynb, koppen_gee.py
│   │   ├── holdridge_chelsa.ipynb, holdridge_gee.py
│   │   ├── thornthwaite_chelsa.ipynb, thornthwaite.py
│   │   └── figuras/
│   ├── dados_chelsa/
│   │   └── assets_utilizados.md         # todos os assets: o que são e onde foram usados
│   └── reproducao/                      # reprodução dos modelos do MapBiomas C3
│       ├── reproducao_resultados.ipynb
│       ├── codigo/                      # config, dados, modelagem, fases, mapas, métricas, rodar.sh
│       └── resultados/                  # tabelas agregadas e figuras
└── corelacao/                           # comparação de climas e experimento dos modelos
    ├── comparacao_climas.ipynb
    ├── experimento_clima_modelos.ipynb
    ├── codigo/                          # preparar_dados, comparar_climas, zonas_clima, experimento_*, testes
    ├── resultados/                      # tabelas agregadas e figuras
    └── docs/memoria_fabricio.md         # registro do que foi feito e decidido
```

**Fora do git** (em `.gitignore`): dados por ponto (`corelacao/.local/`, `climas/dados_reproducao/`),
rasters locais do CHELSA e das classificações (`climas/dados_chelsa/…`) e os mapas gerados.

---

## 4. Dados

### 4.1 Clima (Google Earth Engine, projeto `fcoliveira`)

Normais CHELSA V2.1 1991-2020 (~1 km) e classificações derivadas, geradas neste repositório:

| Asset | Conteúdo |
|---|---|
| `projects/fcoliveira/assets/chelsa_brasil_{tas,pr,pet}_normal_1991_2020` | temperatura, precipitação e ETP de Penman-Monteith mensais (12 bandas cada) |
| `projects/fcoliveira/assets/Koppen_CHELSA_BR_1991_2020` | Köppen-Geiger (31 classes) |
| `projects/fcoliveira/assets/Holdridge_CHELSA_BR_1991_2020_{ETPM,ETH}` | zonas de vida de Holdridge, com as duas ETPs |
| `projects/fcoliveira/assets/Thornthwaite_CHELSA_BR_1991_2020_{CAD100,CADsolo}` | Thornthwaite com balanço hídrico (10 bandas: classes, ETP, DEF, EXC, índices) |

A lista completa, incluindo datasets públicos e as covariáveis do MapBiomas, está em
[assets_utilizados.md](climas/dados_chelsa/assets_utilizados.md).

### 4.2 Solo (MapBiomas Solo, coleção 3)

| Dado | Uso | Acesso |
|---|---|---|
| `…/MATRIZES/collection3/c03_psd_v2025_11_18` | textura (matriz de produção da C3) | restrito |
| `…/MATRIZES/collection3/matriz-collection3_carbon_datac2v2` | SOC na comparação e no experimento (estoques da coleção 2) | restrito |
| `…/ORIGINAIS/collection3/2025_11_26_soildata_soc_trep` | SOC na reprodução (pontos da C3; covariáveis extraídas no GEE) | restrito; os mesmos dados são públicos no SoilData ([doi 10.60502/SoilData/IUZOAK](https://doi.org/10.60502/SoilData/IUZOAK), CC BY 4.0) |

A matriz de produção do SOC da C3 (`c03_soc_v2025_11_26_trep`) não é legível pela conta usada. **Os dados
por ponto não são versionados**: o repositório publica só resultados agregados, e classes com menos de 5
locais são suprimidas nas tabelas.

---

## 5. Metodologia resumida

- **Métrica principal:** R² fora da amostra com **validação cruzada em blocos espaciais** (quadrículas de 2°;
  1° e 5° como sensibilidade). Penaliza classificações com classes demais, evita o otimismo da autocorrelação
  espacial e, com as mesmas dobras para todos os climas, permite **diferenças pareadas**. Sem p-valores (com
  ~12 mil locais, todos os testes seriam significativos); ω² só como descrição.
- **Resposta:** log(SOC) e areia, silte e argila de 0-30 cm.
- **Zonas climáticas k10:** k-means (k = 10, o número de classes do Köppen L3 no Brasil) sobre 9 variáveis
  do CHELSA e do balanço hídrico (temperatura média e do mês mais frio; chuva anual, do mês mais seco e
  sazonalidade; ETP; DEF, EXC e Im), com log nas assimétricas e padronização, ajustado em 300 mil pixels do
  Brasil ponderados pela área, **não nos pontos de solo** (sem vazamento e sem viés da amostra concentrada).
  Pontos e pixels recebem a zona do centróide mais próximo. Detalhes em
  [`zonas_clima.py`](corelacao/codigo/zonas_clima.py) e na memória.
- **Clima contínuo:** 12 variáveis (as 9 acima mais temperatura do mês mais quente, biotemperatura e ETP/P).
- **Reprodução do MapBiomas:** covariáveis do MapBiomas portadas do JavaScript do GEE para Python
  ([`covariaveis_gee.py`](climas/reproducao/codigo/covariaveis_gee.py)) e conferidas contra as matrizes;
  cadeia textura → SOC **sem vazamento** (a textura dos locais de teste vem de modelos que não viram os blocos
  de teste); SOC com a profundidade como covariável e avaliação no estoque de 0-30 cm; mapas numa grade de
  0,05° (~5 km) alinhada ao CHELSA, SOC para 2023, com correção de Duan do viés da retransformação do log.

---

## 6. Como reproduzir

### 6.1 Ambiente

Python ≥ 3.11 e uma conta do Google Earth Engine (projeto `fcoliveira` por padrão, em
[`gee_utils.py`](corelacao/codigo/gee_utils.py)). As matrizes do MapBiomas exigem acesso concedido pela equipe
do MapBiomas Solo.

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r climas/chelsa_climas_brasil/requirements.txt   # rasterio, geemap, geedim, agrometeorologiapy…
pip install -r corelacao/requirements.txt                     # earthengine-api, pandas, scikit-learn, pytest…
earthengine authenticate
```

No Mac Intel, se o `pyproj` falhar ao compilar: `pip install --only-binary=pyproj -r …`. O Thornthwaite
precisa da `agrometeorologiapy` ≥ 0.2.0 (balanço hídrico vetorizado).

### 6.2 Ordem das etapas

```bash
# 1. Normais CHELSA (baixa só o recorte do Brasil) e classificações
python climas/chelsa_climas_brasil/baixar_recortar.py
python climas/chelsa_climas_brasil/gerar_normal_multibanda.py
#    notebooks koppen_chelsa, holdridge_chelsa e thornthwaite_chelsa -> GeoTIFFs -> subir como assets no GEE
#    (classes com --pyramiding_policy=mode)

# 2. Comparação das classificações e experimento dos modelos
cd corelacao
python codigo/preparar_dados.py                     # GEE: matrizes + climas nos pontos
python codigo/comparar_climas.py
python codigo/experimento_dados.py
(cd codigo && python -c "import zonas_clima as z; z.main(ks=(10, 15))")   # zonas k-means + mapa
python codigo/experimento_modelos.py                # ~75 min
python -m pytest codigo
cd ..

# 3. Reprodução dos modelos do MapBiomas C3
cd climas/reproducao/codigo
python dados.py                                     # GEE: textura, pontos de SOC C3 + covariáveis (horas; cache por ano)
./rodar.sh                                          # textura, SOC, mapas — versão fiel (~2,5 h)
REPRODUCAO_SEM_C2=1 ./rodar.sh                      # idem, sem a textura da coleção 2
python metricas_mapbiomas.py                        # ME, MAE, RMSE, MEC, slope
python notebook_resultados.py && jupyter nbconvert --to notebook --execute --inplace ../reproducao_resultados.ipynb
```

Os notebooks de resultados (`comparacao_climas`, `experimento_clima_modelos`, `reproducao_resultados`) são
versionados já executados e podem ser lidos direto no GitHub.

---

## 7. Limitações

- A matriz de produção do SOC da C3 não é acessível; a reprodução usa os mesmos pontos da C3 com covariáveis
  extraídas por nós. A comparação e o experimento (etapas 4 e 5) usam a matriz de SOC com estoques da coleção 2.
- A amostra de solo é concentrada (~26% em Rondônia, ~19% no RS). Os blocos espaciais atenuam, mas não
  eliminam, esse peso.
- Mapas a ~5 km (valor do centro do pixel), não a 30 m; GBM do scikit-learn sem a subamostragem de 0,632 do GEE.
- Validação climática com só 22 estações, poucas na Amazônia.
- Classificações com ETP de Penman-Monteith não são diretamente comparáveis a zoneamentos feitos com a ETP de
  Thornthwaite ou de Holdridge (letras térmicas, fronteiras de umidade).
- O k das zonas foi fixado por analogia com o Köppen, não otimizado.

---

## 8. Referências

- Alvares, C. A. et al. (2013). Köppen's climate classification map for Brazil. *Meteorologische Zeitschrift* 22(6).
- Aparecido, L. E. O. et al. (2016). Köppen, Thornthwaite and Camargo climate classifications for climatic zoning in the State of Paraná, Brazil. *Ciência e Agrotecnologia* 40(4).
- Holdridge, L. R. (1947). Determination of world plant formations from simple climatic data. *Science* 105; (1967) *Life Zone Ecology*.
- Jungkunst, H. F. et al. (2021). New uses for old tools: Reviving Holdridge Life Zones in soil carbon persistence research. *Journal of Plant Nutrition and Soil Science* 184:5-11.
- Karger, D. N. et al. (2017). Climatologies at high resolution for the earth's land surface areas (CHELSA). *Scientific Data* 4.
- Kottek, M. et al. (2006). World map of the Köppen-Geiger climate classification updated. *Meteorologische Zeitschrift* 15(3).
- Leemans, R. (1990, 1992). Global Holdridge life zone classifications.
- Thornthwaite, C. W. (1948). An approach toward a rational classification of climate. *Geographical Review* 38(1).
- Thornthwaite, C. W.; Mather, J. R. (1955). *The water balance*.
- MapBiomas Solo, coleção 3 — [brasil.mapbiomas.org](https://brasil.mapbiomas.org/iniciativas-e-produtos/solo/); dados de treino no [SoilData](https://soildata.mapbiomas.org).

---

**Autor:** Fabrício Correia de Oliveira (UTFPR) · GitHub [fcoliveira-utfpr](https://github.com/fcoliveira-utfpr)
