# Planejamento — avaliação espaço-temporal dos climas no modelo de SOC do MapBiomas C3 (1985-2024)

**Objetivo.** Refazer a comparação dos cenários de clima no modelo de **SOC** do MapBiomas Solo coleção 3,
agora **o mais próximo possível do pipeline de produção** (o script de matriz enviado e os scripts R
públicos) e para **toda a série 1985-2024**. A avaliação passa a ser **espacial e temporal**. Não serão
gerados mapas, só a matriz, os modelos e a validação. A textura fica de fora: na reprodução anterior, a
troca do clima quase não mudou a textura.

**Cenários de clima (só o clima muda entre eles):**

| Cenário | Covariáveis de clima | Papel |
|---|---|---|
| **Köppen IPEF** | dummies do Köppen, como na produção | referência (o que o MapBiomas usa hoje) |
| **Zonas k10** | dummies das 10 zonas climáticas homogêneas | melhor classificação nas análises anteriores |
| **Holdridge ETH** | dummies das zonas de vida com a ETP original de Holdridge (58,93 × biotemperatura) | melhor classificação clássica para SOC |
| **Thornthwaite CAD do solo** | dummies do nível **L2** (classe de umidade + subtipo), CAD = AWC do solo | balanço hídrico |
| **Clima contínuo** | variáveis numéricas escolhidas numa etapa de seleção (§4.3), a partir das 12 do CHELSA e do balanço hídrico, das 2 decenais do GT de clima (temperatura e chuva) e do CDD decenal calculado do Xavier | melhor cenário da reprodução anterior; agora com clima que pode variar por década |
| Sem clima (controle interno) | nenhuma | mede quanto o clima acrescenta; custo quase zero |

**Saída com nome próprio.** A matriz reconstruída não é a do MapBiomas e não deve ter o mesmo nome. Sugestão:
`matriz_soc_c3_fabricio` (treino) e `painel_soc_c3_fabricio_1985_2024` (predição local × ano), em
`climas/dados_espaco_tempo/`.

---

## 1. O que muda em relação à reprodução anterior (`climas/reproducao/`)

| | Reprodução anterior | Agora |
|---|---|---|
| Ano | covariáveis dinâmicas de 2023 nos mapas; nos pontos, ano de coleta | **cada amostra no seu ano**, e predição nos pontos em **todos os anos de 1985 a 2024** |
| Pontos | asset `ORIGINAIS/.../2025_11_26_soildata_soc_trep`, **sem** pseudoamostras e **sem** réplicas `trep` | o mesmo asset, **com** pseudoamostras e réplicas `trep`, filtradas pelas regras da produção (§3.3) |
| Covariáveis | as 106 da matriz antiga (`carbon_datac2v2`) | a lista da C3 do script enviado: WRB, `black_soil_prob`, morfometria, distâncias a areia e rocha, combinações solo × bioma × geologia, uso da terra da Coleção 10 (§3.2) |
| Textura como covariável | prevista na cadeia (versões com C2 e sem C2) | `areia/silte/argila_000_030cm` da **coleção 3**, como na produção |
| Resposta | log de `carbono_gm2_qmap` | `carbono_gm2_qmap` em g/m² (como na validação deles, §4.1) ou em log, o que validar melhor (§4.3a) |
| Modelo | random forest do scikit-learn | **ranger com os hiperparâmetros da C3** (§4.1) |
| Validação | blocos espaciais de 2° | blocos espaciais **+ validação temporal + espaço-temporal** + o OOB por perfil que o MapBiomas usa (§5) |
| Profundidade | covariável, R² só em 0-30 cm | igual (todas as profundidades empilhadas; métricas em todas e em 0-30 cm) |

---

## 2. Fontes (o que foi conferido nesta conta do GEE)

| Item | Onde | Acesso |
|---|---|---|
| Matriz de produção `c03_soc_v2025_11_26_trep` e a exportada `c03_soc_v2025_trainingFinal` | `.../AMOSTRAS/MATRIZES/collection3/` | **sem acesso** |
| Pontos da C3 (35.235 linhas: 18.325 perfis, 1.944 pseudoamostras de rocha, 1.365 de areia, 4.620 réplicas `trep`) | `.../AMOSTRAS/ORIGINAIS/collection3/2025_11_26_soildata_soc_trep` | OK |
| Covariáveis da C3: WRB, `FAO_2022_BLACKSOIL_1KM`, `DISTANCE_C10_v3`, `OT_GEOMORPHOMETRY_90m`, IBGE (pedologia, biomas, fitofisionomia, províncias, subprovíncias), água | `projects/mapbiomas-workspace/SOLOS/COVARIAVEIS/` | OK (`MB_2024_SANDMASK` aparece na pasta, mas não abriu; não é covariável do modelo) |
| Textura da C3 (`psd_final`, por camada de 10 cm) | `.../SOLOS/PRODUTOS_C03/psd_final` | OK |
| **SOC oficial da C3**, 0-30 cm, t/ha, 40 bandas (`carbon_1985` … `carbon_2024`) | `.../PRODUTOS_C03/mapbiomas_soil_collection3_soc_t_ha_000_030cm` | OK |
| Módulo de covariáveis do carbono, filtros, treino e validação | GitHub `mapbiomas/brazil-soil`, `soil_30m_landsat/collection_03beta/carbon/` e `.../soildata/` (24 a 30) | público |
| Climas dos cenários | assets do projeto (`projects/fcoliveira/assets/CHELSA/`) e funções de `corelacao/codigo` | OK |

**Consequência:** a matriz de produção não pode ser lida, então ela será **reconstruída**: os pontos do
asset `ORIGINAIS` + as covariáveis extraídas por nós com o módulo da C3 portado para Python (como já foi
feito com a textura em `climas/reproducao/codigo/covariaveis_gee.py`).

---

## 3. Matriz

### 3.1 Linhas

- Uma linha por **perfil × profundidade** (estoque acumulado até `profundidade`), como na produção.
- Mantém pseudoamostras e réplicas `trep10`/`trep20`; o filtro do §3.3 remove as incoerentes.
- **Ano das covariáveis dinâmicas = `ano` de cada linha** (amostras anteriores a 1985 já vêm com `ano` =
  1985 e `YEAR_index` negativo; as réplicas `trep` têm o ano recuado em 10 e 20 anos).
- `YEAR_index`, `IFN_index`, `PSEUDOROCK_index` e `PSEUDOSAND_index` entram como covariáveis, como na
  produção.

### 3.2 Covariáveis

- **Estáticas e dinâmicas:** exatamente as listas `covariates_names_static` e `covariates_names_dynamic`
  do script enviado, portando `carbon/0_covariate_source` do GitHub para Python.
- **Clima:** o bloco Köppen da lista vira a coluna do cenário. Nos demais cenários, as dummies do Köppen saem
  e entram as do cenário.
- **Conferência:** como na reprodução anterior, comparar as covariáveis extraídas com as de alguma matriz
  legível (a `carbon_datac2v2` e a de textura `c03_psd_v2025_11_18`) nos pontos em comum.

### 3.3 Filtros (regras da produção)

Há duas versões dos filtros, que diferem em dois pontos:
- o JS usa `'resingas'` (erro de digitação) nos dois filtros de restinga, que por isso não removem nada; o R
  usa `restingas`;
- no filtro solo escuro × textura arenosa, o JS usa `black_soil_prob > 10` e o R usa `> 50`.

**Revisto e conferido em 08/10/2026:** a matriz que de fato treinou e validou o modelo
(`c03_soc_v2025_trainingFinal`) foi gerada pelo **script JS**
([`codigo/referencia/soc_trainingFinal_c3_2025_11_26.js`](codigo/referencia/soc_trainingFinal_c3_2025_11_26.js)),
e a regra passa a ser **o JS, com os desvios dele**. Resultado na matriz reconstruída
([`codigo/matriz.py`](codigo/matriz.py), tabela `resultados/tabelas/filtros_matriz.csv`):
- **versão R:** as 13 contagens anotadas no `26_soc_filter_matrix.R` saem idênticas (1071, 273, ... 5;
  32.399 linhas);
- **versão JS:** 27.425 linhas, 14.704 ids e 13.108 grupos, **exatamente** a `trainingFinal`. O
  `'resingas'` não deixa de filtrar: no GEE a comparação com a propriedade inexistente dá nulo e o `.not()`
  de `and(IFN_index == 1, nulo)` descarta o ponto, então saem **todas** as linhas do IFN (4.429) e todas
  as de `YEAR_index == -26` (106), não só as de restinga. Os dados do IFN, portanto, não entram no modelo
  de produção.

Seleção de colunas: as listas `covariates_names_static/dynamic` do mesmo script (já incorporam o que o R
26 e o 28 removeram: constantes, binárias com menos de 30 ocorrências, quase sem variância, correlação
≥ 0,95 e importância zero). Não é preciso repetir essas etapas.

### 3.4 Painel de predição (sem mapas)

Para a avaliação temporal das trajetórias, montar também uma matriz **local × ano**: cada local de
amostra real (sem pseudoamostras), com as covariáveis dinâmicas de **cada ano de 1985 a 2024** e
profundidade = 30 cm. São ~13,5 mil locais × 40 anos ≈ 540 mil linhas. Só as covariáveis dinâmicas mudam com o
ano; as estáticas e o clima são extraídos uma vez.

---

## 4. Modelo

### 4.1 Como o MapBiomas faz (scripts R públicos)

- `ranger`, **resposta em g/m² sem log**.
- `28_soc_train_model.R`: busca em grade, e o modelo final usa `carbono_gm2` com 400 árvores, mtry = 24,
  min.node.size = 2, max.depth = 40.
- `30_soc_model_validation.R`: usa **`carbono_gm2_qmap`**, 300 árvores e os mesmos mtry, min.node.size e
  max.depth, semente 1984. Métricas em t/ha (÷ 100) em todas as profundidades e só na camada mais funda
  de cada perfil. Também roda uma versão **"sem vazamento"**: o bootstrap sorteia **perfis** (com as
  réplicas `trep` no mesmo grupo do perfil original), e o OOB vem dos perfis fora da amostra.

### 4.2 Aqui

- Mesmo algoritmo e hiperparâmetros (300 árvores, mtry 24, min.node.size 2, max.depth 40), **a mesma
  resposta (`carbono_gm2_qmap`)** e a mesma regra de grupos (perfil + réplicas). Rodar o `ranger` pelo R, ou
  usar um equivalente em Python e conferir antes que ele reproduz o OOB do `ranger` no cenário Köppen.
- Como o número de covariáveis muda entre cenários, manter o mtry de 24 (como na produção) e testar mtry
  proporcional (≈ 1/3 das covariáveis) como sensibilidade.

A textura da C3 fica como covariável em todos os cenários, como na produção (sem variante sem textura).

### 4.3 Decisões a tomar com dados, antes de rodar os cenários

**(a) Resposta em log ou sem log.** No cenário Köppen, com a validação espacial (V2), comparar:
- `carbono_gm2_qmap` direto (como na produção);
- log(`carbono_gm2_qmap`), voltando para g/m² com a correção de Duan (*smearing*), como na reprodução anterior.

Critério: **MEC em t/ha, em 0-30 cm**, e viés (ME). Se o log for melhor, ele é usado em todos os cenários;
senão, fica a resposta direta. Em caso de empate, fica a direta (a da produção).

**(b) Quais variáveis entram no clima contínuo.** Candidatas:
- as 12 do CHELSA e do balanço hídrico (temperatura média, do mês mais frio e do mais quente,
  biotemperatura, chuva anual, do mês mais seco e sazonalidade, ETP, ETP/P, DEF, EXC, Im);
- as decenais do GT de clima do MapBiomas Solo (`projects/mapbiomas-workspace/SOLOS/COVARIAVEIS/`),
  conferidas em 07/10/2026:

  | Asset | Banda | Imagens | Grade |
  |---|---|---|---|
  | `GT_DECADE_TMEAN_CONTI_2026` | `tmean_10yr_mean` (°C) | 56, anos 1971-2026 | 0,1° |
  | `GT_DECADE_PRECIPITATION_CONTI_2026` | `prec_10yr_mean` (mm) | 56, anos 1971-2026 | 0,1° |

  A imagem do ano Y é a **média dos 10 anos anteriores** (Y−10 a Y−1; propriedades `startYear`/`endYear`).
  A grade de 0,1° é a do Xavier (BR-DWGD), provável fonte. Cada linha da matriz recebe a imagem do **seu
  ano**, ou seja, o clima da década que antecede a amostra. São as únicas covariáveis de clima que **mudam
  no tempo**.
- **CDD decenal (dias secos consecutivos), calculado por nós.** A coleção do GT (`GT_DECADE_CDD_CONTI_2026`)
  está vazia, então o CDD é gerado por [`codigo/cdd_brdwgd.py`](codigo/cdd_brdwgd.py) no mesmo padrão:
  - CDD anual (índice ETCCDI) = maior sequência de dias com chuva < 1 mm no ano; a estiagem que vem do ano
    anterior continua contando (importante no norte, onde a seca vai de dezembro a março);
  - fonte: chuva diária do Xavier no GEE (`projects/sat-io/open-datasets/BR-DWGD/PR`, 1961-2022, 0,1°, a
    mesma grade das decenais do GT);
  - CDD decenal do ano Y = média do CDD anual de Y−10 a Y−1. A grade pública vai até 2022, então **2024 usa
    9 anos** (2014-2022), registrado na propriedade `n_anos`;
  - saídas: `projects/fcoliveira/assets/Climas2/CDD_ANUAL_BRDWGD` (1961-2022) e
    `.../CDD_DECENAL_BRDWGD` (1971-2024, banda `cdd_10yr_mean`);
  - teste (`python cdd_brdwgd.py teste`): CDD de 2010 e 2012 em Petrolina 97 e 208 dias (seca de 2012),
    Cuiabá 77 e 88, Curitiba 23 e 27, Manaus 14 e 9, Boa Vista 17 e 15. **Limitação:** uma grade interpolada
    espalha chuvas fracas e encurta as sequências secas, sobretudo onde há poucos pluviômetros (Boa Vista
    deveria ter estiagem mais longa). O CDD da grade tende a ser menor que o de um pluviômetro.

Seleção, sempre **dentro da validação** (aninhada, sem olhar as dobras de teste):
1. tirar as redundantes: em pares com |r| > 0,9, fica a de maior importância;
2. comparar conjuntos: **só CHELSA/BHC**, **só decenais** (temperatura, chuva e CDD), **CHELSA/BHC + decenais**;
3. dentro do melhor conjunto, eliminação para trás por importância por permutação, enquanto o MEC na
   validação espacial (V2) não piorar;
4. conferir o conjunto escolhido também na validação temporal (V3), já que as decenais podem ajudar no
   tempo e não no espaço.

O conjunto escolhido define o cenário **clima contínuo**, que então entra na comparação com os demais.

---

## 5. Validação

| # | Esquema | O que mede | Como |
|---|---|---|---|
| **V1** | OOB por perfil (o "sem vazamento" do MapBiomas) | comparabilidade com os números deles | bootstrap de perfis no `ranger` |
| **V2** | **Espacial**: blocos de 2° | estimar onde não há amostra | 5 dobras × 3 repetições; perfil e réplicas sempre na mesma dobra |
| **V3** | **Temporal**: deixa um período de fora | estimar em anos sem amostra | dobras por período (por exemplo 1985-1994, 1995-2004, 2005-2014, 2015-2024); réplicas `trep` vão com o perfil original, nunca com o período delas |
| **V4** | **Espaço-temporal**: deixa bloco **e** período de fora | o caso mais difícil (lugar e época novos) | dobras cruzadas bloco × período; teste = bloco e período fora do treino |

- **Métricas:** as do MapBiomas (`error_statistics`: ME, MAE, RMSE, MEC, slope), em t/ha, em todas as
  profundidades e em 0-30 cm; por período, por bioma e por cenário.
- **Diferenças pareadas:** todos os cenários com as mesmas dobras, ganho de cada um sobre o Köppen por
  repetição (como nas análises anteriores).

### 5.1 Avaliação das trajetórias 1985-2024 (painel do §3.4)

- **Fidelidade:** a trajetória prevista no cenário Köppen deve acompanhar o **SOC oficial da C3** nos mesmos
  locais e anos (asset com 40 bandas). Se não acompanhar, a reconstrução da matriz tem problema.
- **Efeito do clima no tempo:** para cada cenário, comparar com o Köppen a tendência 1985-2024 (inclinação
  por local), a variação ano a ano e a resposta às mudanças de uso da terra (desmatamento, pastagem →
  lavoura).
- **Locais com mais de uma coleta em anos diferentes:** contar quantos existem. Se forem suficientes, são a
  única verdade de campo para a variação temporal.

**Limitação importante:** as quatro classificações são **normais estáticas** (1991-2020). Elas não mudam de
ano para ano, então não explicam a variação temporal diretamente; a variação no tempo vem das covariáveis
dinâmicas (uso da terra, índices de vegetação). O que se avalia é se o clima melhora a estimativa em períodos e
lugares novos (V3, V4) e se muda a forma das trajetórias. A exceção é o **clima contínuo**, se as variáveis
decenais do GT de clima forem selecionadas (§4.3b): aí o clima também varia por década, e vale comparar as
trajetórias dele com as das classificações estáticas.

---

## 6. Etapas

| Etapa | Entrega | Esforço estimado |
|---|---|---|
| 1. Portar `0_covariate_source` (carbono) e conferir contra matrizes legíveis | `codigo/covariaveis_c3.py` | médio |
| 2. Extrair covariáveis nos pontos, por ano, e aplicar os filtros | matriz de treino (fora do git) + tabela de filtros | horas de GEE |
| 3. Painel local × ano 1985-2024 | matriz de predição (fora do git) | várias horas de GEE |
| 4. Climas dos cenários nos pontos | colunas de clima | rápido (código existente) |
| 5. Reproduzir o OOB do MapBiomas no cenário Köppen (V1) | tabela de fidelidade | curto |
| 6. V2, V3 e V4 nos cenários | tabelas de métricas e ganhos | horas de processamento |
| 7. Trajetórias e comparação com o SOC oficial | figuras e tabelas | médio |
| 8. Notebook de resultados e entrada no relatório | `analise_espaco_tempo.ipynb` | médio |

Organização: `codigo/`, `resultados/{tabelas,figuras}/` versionados; dados por ponto em
`climas/dados_espaco_tempo/` (fora do git, como em `dados_reproducao/`).

---

## 7. Decisões (Fabrício, 07/10/2026)

1. **Cenários:** Köppen IPEF, zonas k10, Holdridge ETH, Thornthwaite CAD do solo e **clima contínuo**, este
   depois da seleção de variáveis (§4.3b), incluindo as variáveis decenais do GT de clima. Sem clima fica como
   controle interno.
2. **Thornthwaite:** nível L2 (umidade + subtipo).
3. **Resposta:** com log se o log for melhor; senão, sem log (§4.3a).
4. **Textura da C3:** mantida como covariável; sem variante sem textura.
5. **Validação temporal:** quatro períodos de 10 anos (1985-1994, 1995-2004, 2005-2014, 2015-2024).
6. **Avaliação temporal:** painel de trajetórias 1985-2024 + comparação com o SOC oficial da C3.
7. **Matriz do MapBiomas:** não pedir; a nossa saída tem nome próprio (`matriz_soc_c3_fabricio`).

**Acesso:** os assets `GT_DECADE_*_2026` foram liberados para esta conta em 07/10/2026. Entram temperatura e
chuva decenais (1971-2026). O CDD do GT está vazio; o CDD decenal é calculado por nós a partir da chuva
diária do Xavier (`codigo/cdd_brdwgd.py`).
