# Instruções — refinamento da temperatura média e da precipitação para 30 m

**Para:** Vitor
**Objetivo final:** mapas de **temperatura média** e de **precipitação** do Brasil a **30 m**, gerados por
**modelos** (não por interpolação), validados contra estações e entregues como **GeoTIFF prontos para subir
manualmente como asset no Google Earth Engine (GEE)**.

---

## 1. Contexto

Este repositório (`climate_for_soil`) usa o clima como base para estimar carbono e textura do solo. Hoje a
base climática é o **CHELSA V2.1** (normal 1991-2020, ~1 km), validado contra estações em
[`validacao/`](../validacao/) e descrito na seção 2 do [relatório técnico](../relatorio_tecnico.md):

| Base | Temperatura (RMSE, viés) | Precipitação mensal (RMSE, viés) |
|---|---|---|
| Xavier | 0,85 °C, +0,22 °C | 44,0 mm, +5,0 mm |
| CHELSA | 0,82 °C, −0,50 °C | 66,9 mm, −1,4 mm |
| ERA5-Land | 1,63 °C, −0,75 °C | 66,2 mm, +2,0 mm |
| TerraClimate | 1,51 °C, −1,00 °C | 68,6 mm, +8,8 mm |

Os mapas de solo do MapBiomas são de **30 m**, mas o clima que entra neles tem 1 km ou mais. A ideia é
fazer algo **no espírito do Xavier** (grade brasileira construída a partir das estações, que é a melhor base
em chuva na tabela acima), mas:

- **a 30 m**, aproveitando o relevo de 30 m;
- **com modelos**, e não com interpolação: o valor de cada pixel sai de uma relação aprendida entre o clima
  e covariáveis (relevo, posição, produtos de satélite e de reanálise), e não de uma média ponderada das
  estações vizinhas;
- comparando **métodos estatísticos** com **aprendizado de máquina (ML)**.

> **Regra do projeto: nada de interpolação espacial.** Ficam de fora IDW, ADW (os métodos do Xavier),
> krigagem, splines e também a krigagem dos resíduos (*regression kriging*). Todo pixel tem que sair de um
> modelo aplicado às covariáveis daquele pixel. Isso torna o mapa reprodutível em qualquer lugar,
> inclusive onde não há estação, e permite aplicar o mesmo modelo no GEE.

---

## 2. Escopo e decisões iniciais

| Item | Decisão sugerida | Observação |
|---|---|---|
| Variáveis | temperatura média do ar (°C) e precipitação (mm) | começar pela **temperatura** (mais fácil e com mais ganho a 30 m) |
| Período | **normal 1991-2020**, igual ao CHELSA usado no projeto | séries anuais ficam para uma fase futura |
| Escala temporal | **climatologia mensal** (12 valores) e **anual** | entregar primeiro a anual, depois a mensal |
| Área | Brasil inteiro | desenvolver e testar antes numa região-piloto com relevo (por exemplo, Sul ou Sudeste) |
| Resolução final | 30 m, EPSG:4326, alinhada ao MDE de 30 m | ver o custo de armazenamento na seção 8 |

---

## 3. Dados

### 3.1 Observações (a variável-resposta)

**Base principal: os dados observados do Xavier et al. (2022).** São as séries de estação que os autores
usaram para montar a grade, cedidas pelo autor
([pasta no Google Drive](https://drive.google.com/drive/folders/1urYczkKxBcXWHAmx04lle6jcbiTQS-bR);
~1,8 GB; não vão para o git). Diário, **1961-2025**, em arquivos NumPy (`.npz`):

| Arquivo | Conteúdo | Estações |
|---|---|---|
| `Tmax.npz`, `Tmin.npz` | temperatura máxima e mínima diária (°C) | 1.194 |
| `RH.npz`, `Rs.npz`, `u2.npz` | umidade relativa, radiação solar, vento a 2 m | 1.194 |
| `pr.npz` | precipitação diária (mm/dia) | **14.170** pluviômetros |

Cada arquivo tem `data` (linhas = dias de 1961-01-01 a 2025-12-31, colunas = estações), `lat_lon_alt` e
`ID` (códigos INMET como `A001` e códigos numéricos das convencionais):

```python
import numpy as np, pandas as pd
f = np.load('pr.npz')
dados, coords, ids = f['data'], f['lat_lon_alt'], f['ID']
dias = pd.date_range('1961-01-01', '2025-12-31')
```

Citar: Xavier, Scanlon, King & Alves (2022), *Int. J. Climatol.*, doi 10.1002/joc.7731.

**Complemento: INMET, [dados históricos](https://portal.inmet.gov.br/dadoshistoricos), 2000-2026.**
Dados horários das estações automáticas. Usos:
- conferir e completar séries do Xavier (por exemplo, 2026 e estações que não estejam no conjunto dele);
- **validação independente**: estações que **não** estão no conjunto do Xavier nunca foram vistas pela grade
  dele. É a única forma justa de comparar o novo mapa com o Xavier, que tem vantagem nas estações que usou.
  Cruzar os `ID` das duas fontes para separar.
- A série das convencionais do INMET desde 1961 está no BDMEP, mas já deve estar coberta pelo Xavier.

**ANA (HidroWeb):** só se faltar pluviômetro em alguma região; boa parte já está no `pr.npz`.

**Definição da temperatura média.** O Xavier fornece Tmax e Tmin. A média (Tmax + Tmin)/2 não é igual à
média das 24 horas (o que o CHELSA e o ERA5-Land representam) nem à média compensada do INMET. Medir a
diferença nas estações automáticas, que têm dados horários, e decidir uma definição única antes de modelar
(comparação C11).

**Controle de qualidade (documentar cada critério e quantas estações saem):**
- cobertura mínima no período, por exemplo ≥ 80% dos meses de 1991-2020 (testar 70%, 80% e 90%);
- agregação diária → mensal com critério mínimo de dias válidos; na chuva, mês com dia faltando conta como
  falha (a soma subestima);
- valores fisicamente impossíveis, saltos e séries constantes;
- coordenadas e altitude conferidas contra o MDE (altitude da estação × MDE com diferença grande indica
  coordenada errada);
- estações duplicadas (o mesmo local com dois códigos);
- homogeneidade: troca de sensor convencional → automático e mudança de local. Os pares das duas redes no
  mesmo lugar permitem medir a diferença.

**Falhas e normal de período reduzido.** Para a normal 1991-2020, não é preciso preencher a série inteira:
- **Método das diferenças (normal de período reduzido, OMM):** normal da estação = média nos anos que ela
  tem + (média da grade de referência em 1991-2020 − média da grade nos mesmos anos da estação). Permite
  usar estações curtas, como as automáticas que começam em 2006-2008.
- **Preenchimento, só quando necessário:** temperatura por regressão da estação contra o ERA5-Land diário no
  próprio pixel (não com estações vizinhas, para não virar interpolação); chuva, de preferência, sem
  preencher.
- **Avaliar com falhas artificiais:** apagar dados conhecidos, preencher ou aplicar o método das diferenças, e
  medir o erro antes de usar (comparação C12).

**Período e transferência no tempo.** Se o modelo aprender o valor absoluto com dados recentes, o mapa de
1991-2020 sai quente demais (o Brasil aqueceu no período). Por isso a formulação **correção da grade**
(seção 5) é a preferida: o modelo aprende *estação − grade no mesmo período* (na chuva, a razão), que muda
pouco entre décadas, e a correção é aplicada à grade de 1991-2020. Testar a estabilidade: treinar em
2001-2010 e prever 2011-2020 (comparação C13).

### 3.1b O que já foi testado (ponto de partida)

Numa primeira tentativa, o Fabrício testou a correção do CHELSA por elevação (*lapse rate*, método M1)
contra 255 estações com boa cobertura em 1991-2020:
- RMSE 0,831 → 0,817 °C, MAE 0,696 → 0,682 °C, viés −0,49 → −0,47 °C: melhora pequena e consistente;
- o ganho vem de poucos pontos extremos (Pico do Couto, 1.777 m: RMSE de 1,37 para 0,21 °C);
- a correlação entre a diferença de elevação (estação × célula do CHELSA) e o erro do CHELSA foi **~0,05**: no
  geral, o erro do CHELSA não vem do relevo, e sim de viés do modelo, microclima ou período;
- o *lapse rate* calibrado nas estações deu −4,4 °C/km (o padrão é −6,5).

Ou seja, a correção por elevação sozinha não basta. É justamente o motivo para testar modelos com mais
covariáveis (M2-M6). Os arquivos desse teste (lista de estações, climatologia, validação) podem ser
recuperados do histórico do git, commit `e14ea63`, por exemplo:
`git show e14ea63:refinamento/validacao_temperatura_255estacoes.csv > validacao_temperatura_255estacoes.csv`.

**Controle de qualidade (documentar cada critério e quantas estações saem):**
- cobertura mínima no período, por exemplo ≥ 80% dos meses de 1991-2020 (testar 70%, 80% e 90%);
- valores fisicamente impossíveis, saltos e séries constantes;
- coordenadas e altitude conferidas contra o MDE (altitude da estação × MDE com diferença grande indica
  coordenada errada);
- estações duplicadas (INMET × ANA no mesmo lugar).

**Normal da estação:** média de cada mês sobre os anos disponíveis. Registrar quantos anos cada estação tem
e testar se exigir mais anos melhora a validação.

### 3.2 Covariáveis (o que o modelo usa para prever cada pixel)

| Grupo | Covariáveis | Fonte (GEE) | Resolução |
|---|---|---|---|
| Relevo | elevação, declividade, orientação (seno/cosseno), TPI e TRI em várias janelas (300 m, 1 km, 5 km), curvatura | Copernicus GLO-30 (`COPERNICUS/DEM/GLO30`), NASADEM, SRTM | 30 m |
| Posição | latitude, longitude, distância ao oceano, continentalidade | derivadas | — |
| Exposição | índice de barlavento/sotavento para o vento predominante, sombra orográfica | derivadas do MDE + vento do ERA5 | 30 m–10 km |
| Clima de grade | CHELSA (tas, pr, pet), ERA5-Land, TerraClimate, Xavier | assets do projeto e catálogos do GEE | 1–10 km |
| Satélite, temperatura | temperatura de superfície MODIS (`MODIS/061/MOD11A2`, dia e noite), climatologia mensal | MODIS | 1 km |
| Satélite, chuva | CHIRPS (`UCSB-CHG/CHIRPS/DAILY`), IMERG (`NASA/GPM_L3/IMERG_V07`) | — | 5–10 km |
| Superfície | NDVI/EVI climatológico, cobertura da terra (MapBiomas), corpos d'água | MODIS, Landsat, MapBiomas | 30 m–1 km |

As covariáveis de 30 m (relevo) são as que dão detalhe ao mapa final. As grosseiras (CHELSA, ERA5, satélite)
dão o padrão regional.

---

## 4. Como validar (definir antes de rodar qualquer modelo)

- **Validação cruzada em blocos espaciais** (por exemplo, blocos de 1° e 2°, 5 dobras × várias repetições),
  como no resto do projeto ([`corelacao/`](../corelacao/), seção 5 do relatório). Nunca validar com dobras
  aleatórias de estações: vizinhas no treino inflam o resultado.
- **Conjunto de teste independente:** separar desde o início um grupo de estações que nunca entra em ajuste
  nem em escolha de hiperparâmetros (por exemplo, 15% dos blocos).
- **Métricas:** as mesmas de [`validacao/comparacao_v1.ipynb`](../validacao/comparacao_v1.ipynb): viés,
  PBIAS, MAE, RMSE, r, NSE, d de Willmott e KGE. Reportar globalmente, por região/bioma, por faixa de
  altitude e por mês.
- **Linhas de base obrigatórias** (todo método novo é comparado com elas, nas mesmas estações e dobras):
  CHELSA, Xavier, ERA5-Land e TerraClimate amostrados nas estações de teste.
- **Comparações pareadas:** todos os métodos com as mesmas dobras, para que a diferença entre dois métodos
  tenha intervalo de confiança.

---

## 5. Métodos a comparar (do mais simples ao mais complexo)

A ideia é subir a escada um degrau por vez e só avançar quando o degrau anterior estiver validado.

### 5.1 O método do Xavier como régua

O objetivo é chegar a métodos **semelhantes aos do Xavier ou melhores**. Artigo de referência: Xavier,
Scanlon, King & Alves (2022), *Int. J. Climatol.* 42: 8390-8404,
**[doi.org/10.1002/joc.7731](https://doi.org/10.1002/joc.7731)** (acesso pelo portal de periódicos da
instituição; ler antes de começar). Resumo do método:

**Dados e controle de qualidade**
- ANA e INMET (APIs), 01/01/1961 a 31/07/2020: **1.252 estações** (642 convencionais, 610 automáticas) e
  **11.473 pluviômetros**.
- Limites físicos: 0 ≤ pr < 450 mm/dia; −30 °C < Tmax, Tmin < 50 °C; 0,03·Ra ≤ Rs ≤ Ra; 0 ≤ u2 < 100 m/s.
  Depois, inspeção visual da homogeneidade de cada estação contra as vizinhas. Descartes de 0,19% a 3,42%
  dos dados, conforme a variável.
- A densidade de estações muda muito no tempo e no espaço: a Amazônia tem ~1 estação de temperatura por
  250.000 km² até 2003 (150.000 km² hoje) contra 5.000-12.000 km² no litoral leste; o número de estações de
  temperatura salta entre 2003 e 2008 (automáticas).

**Métodos**
- Em 2016 foram testados seis métodos (média aritmética, *thin plate spline*, vizinho natural, IDW, ADW e
  krigagem ordinária); IDW e ADW foram os melhores, e só eles foram usados em 2022.
- **IDW:** peso = d⁻ᵖ, com **p = 2**. **ADW** (New et al. 2000; Hofstra et al. 2008): um peso pela distância
  de decaimento da correlação e outro pela posição angular das estações em torno do ponto.
- Nos dois, **as 5 estações mais próximas**.
- **Temperatura com ajuste de relevo (ElAdj):** gradiente estimado com 1.375 pares de estações próximas
  (≤ 90 km), regressão da diferença de Tmean = (Tmax + Tmin)/2 contra a diferença de altitude:
  **−0,006 °C/m** (R² = 0,89). Antes de interpolar, cada Tmax/Tmin observado é levado à altitude do ponto
  de destino com esse gradiente. A altitude do ponto vem do GMTED2010 (30″) agregado por média para 0,1°.
- **Escolha do método:** validação cruzada *leave-one-out* diária (cada estação/dia estimada pelas 5 vizinhas)
  e um ranking das métricas (R, Bias, RMSE, MAE, CRE, PC, CSI, CSIL, CSIH); vence o de menor rank médio.
- **Escolhidos:** ADW para chuva, Rs, RH e u2; **IDW com ajuste de relevo** para Tmax e Tmin. Grade de 0,1°,
  com duas camadas de controle por célula: número de estações na célula (*Count*) e distância até a estação
  mais próxima (*dist_nearest*).

**Resultados de referência (validação cruzada diária, Brasil)**

| Variável | Método | R | RMSE | MAE | Bias |
|---|---|---|---|---|---|
| Precipitação | ADW | 0,653 | 8,23 mm | 3,23 mm | 0,004 mm |
| Tmax | IDW sem ajuste | 0,912 | 1,93 °C | 1,37 °C | −0,02 °C |
| Tmax | **IDW com ajuste de relevo** | 0,943 | 1,56 °C | 1,10 °C | 0,05 °C |
| Tmin | **IDW com ajuste de relevo** | 0,934 | 1,62 °C | 1,14 °C | 0,02 °C |

O ajuste de relevo reduziu o RMSE de Tmax em ~17%. Na chuva, o desempenho depende da densidade de
pluviômetros: R = 0,38 na Amazônia contra 0,74 no Atlântico Sul.

**Pistas do próprio artigo para melhorar:**
- As bacias do litoral atlântico têm **viés positivo** de Tmax, e as do interior, **negativo**. Os autores
  sugerem incluir efeitos oceânicos e de relevo, que é exatamente o que as covariáveis da seção 3.2
  (distância ao oceano, continentalidade, exposição) permitem.
- Onde não há estação a menos de ~50 km, a grade tem valor limitado. Um modelo com covariáveis deveria
  ganhar justamente nesses lugares (comparação C14). A camada *dist_nearest* do Xavier é útil como
  covariável e para separar os resultados por distância à estação mais próxima.

**Atenção à comparação:** os números do Xavier são de validação **diária**. Este projeto mira a **normal
mensal**, então o MX tem de ser recalculado para o mesmo alvo (normais), com as mesmas dobras em blocos dos
modelos. Os números diários acima não servem de comparação direta.

Como IDW e ADW são interpolação, eles **não podem ser o produto final** (regra da seção 1), mas entram como
**método de referência MX**: reproduzidos a 30 m, com os mesmos dados, as mesmas dobras e as mesmas
estações de teste dos modelos. "Melhor que o Xavier" passa a ser um critério objetivo: o modelo escolhido
tem de ganhar do MX fora da amostra (comparação C15), e não só da grade pública do Xavier (que tem a
vantagem de ter usado as estações de teste).

### 5.2 Escada de métodos

| Código | Método | Tipo | Temperatura | Precipitação |
|---|---|---|---|---|
| **M0** | Base de grade reamostrada para 30 m, sem correção (CHELSA, Xavier, ERA5-Land) | referência | ✓ | ✓ |
| **MX** | **Método do Xavier reproduzido a 30 m:** 5 estações mais próximas; temperatura por IDW (p = 2) com os valores levados à altitude do pixel (−0,006 °C/m, recalibrar com os pares de estações); chuva por ADW | interpolação, **só referência** | ✓ | ✓ |
| **M1** | **Correção por elevação** (*lapse rate*): T₃₀ = T_grade + Γ·(z₃₀ − z_grade), com Γ fixo (−6,5 °C/km), por mês e por região | estatístico | ✓ | — |
| **M2** | **Regressão linear múltipla** com relevo, posição e o clima de grade como covariáveis (global e por região/mês) | estatístico | ✓ | ✓ (em log) |
| **M3** | **GWR** (regressão geograficamente ponderada): coeficientes variam no espaço | estatístico | ✓ | ✓ |
| **M4** | **Random forest** | ML | ✓ | ✓ |
| **M5** | **Gradient boosting** (LightGBM ou XGBoost) | ML | ✓ | ✓ |
| **M6** | **Híbrido:** M1 ou M2 + ML modelando o resíduo a partir das covariáveis (sem interpolar o resíduo) | estatístico + ML | ✓ | ✓ |
| **M7** (opcional) | Rede neural (MLP) ou modelo de *downscaling* aprendido entre escalas | ML | ✓ | ✓ |

**Duas formas de definir a variável-resposta (testar as duas):**
- **Direta:** o modelo prevê o valor da estação (°C ou mm).
- **Correção da grade:** o modelo prevê a diferença (temperatura) ou a razão (chuva) entre a estação e a base
  de grade (por exemplo, T_estação − T_CHELSA). O mapa final é a grade + a correção. Costuma extrapolar
  melhor onde não há estações.

**Cuidados específicos da precipitação:**
- Modelar log(P + 1) ou usar uma perda Tweedie/Gamma no gradient boosting.
- Chuva a 30 m tem pouco sinal físico próprio. O ganho real vem do efeito orográfico (barlavento e
  sotavento, altitude), então medir se 30 m é de fato melhor que 1 km (seção 6, comparação C5).
- Os produtos de satélite (CHIRPS, IMERG) costumam ser as covariáveis mais fortes. Conferir se não estão
  "vazando" estações: o CHIRPS usa estações na calibração.

**Escolha de hiperparâmetros:** sempre dentro da validação em blocos (validação aninhada), nunca olhando o
conjunto de teste.

---

## 6. Comparações a fazer à medida que os resultados saírem

Cada comparação tem uma pergunta e uma decisão. Registrar o resultado de cada uma numa tabela em
`resultados/` e uma linha de decisão em `docs/registro.md`.

| # | Comparação | Pergunta | Decisão que ela orienta |
|---|---|---|---|
| **C1** | M0 (CHELSA, Xavier, ERA5) nas estações de teste | Qual é a melhor base de partida? | base usada em M1 e na forma "correção da grade" |
| **C2** | M1 × M0 (temperatura) | A simples correção por elevação já resolve a maior parte? Γ fixo, por mês ou por região? | se M1 bastar, o ML só precisa ganhar dele |
| **C3** | M2/M3 × M4/M5 | **Estatístico × ML:** o ML ganha fora da amostra ou só decora as estações? | método principal |
| **C4** | Variável direta × correção da grade | Qual formulação extrapola melhor (nas regiões sem estação)? | formulação final |
| **C5** | Covariáveis a 30 m × 90 m × 1 km | O detalhe de 30 m melhora a validação ou só deixa o mapa "bonito"? | resolução que realmente se justifica, sobretudo na chuva |
| **C6** | Com e sem satélite (MODIS LST, CHIRPS, IMERG) | Quanto cada grupo de covariáveis contribui? | conjunto final de covariáveis |
| **C7** | Modelo único × um modelo por mês × mês como covariável | Como tratar a sazonalidade? | estrutura do modelo mensal |
| **C8** | Densidade de estações (subamostrar 25%, 50%, 75%) | Quanto o resultado depende de ter muitas estações? Onde o mapa é confiável? | mapa de incerteza e áreas de cautela |
| **C9** | Resultado × Xavier e × CHELSA por região, bioma, altitude | Onde o novo mapa é melhor e onde é pior? | texto de limitações |
| **C10** | Mapa final × perfis de relevo (vales, serras, litoral) | O mapa tem artefatos (bordas de tiles, degraus de MDE, ruído de satélite)? | ajustes finais antes de exportar |
| **C11** | (Tmax + Tmin)/2 × média de 24 h × média compensada, nas estações automáticas | Quanto as definições de temperatura média diferem, e se a diferença varia no espaço? | definição da temperatura média |
| **C12** | Falhas artificiais: método das diferenças × preenchimento × só anos completos | Qual forma de lidar com falhas dá a normal mais correta? | regra de falhas e de cobertura mínima |
| **C13** | Treino em 2001-2010, previsão em 2011-2020 | A correção aprendida é estável no tempo? Pode ser aplicada a 1991-2020? | se dá para usar dados recentes para a normal 1991-2020 |
| **C14** | Estações usadas pelo Xavier × estações fora do conjunto dele | O novo mapa ganha do Xavier também onde o Xavier não tinha estação? | comparação justa com o Xavier |
| **C15** | Melhor modelo (M2-M6) × MX (IDW/ADW reproduzido), mesmas dobras | Os modelos com covariáveis são melhores que o método do Xavier? Onde (relevo, áreas com poucas estações)? | se o produto final pode ser só de modelo; se não ganhar, levar ao Fabrício a opção do híbrido com resíduo interpolado (exceção à regra) |

**Critério de sucesso** (a confirmar depois de C1): o mapa de 30 m deve ser **pelo menos tão bom quanto o
método do Xavier reproduzido (MX)** e que a grade pública do Xavier, em temperatura e precipitação, nas
estações de teste (inclusive nas que o Xavier não usou, C14), e **melhor que o CHELSA**, com ganho
concentrado nas áreas de relevo.

---

## 7. Incerteza

Entregar junto com cada mapa uma camada de incerteza:
- **ML:** intervalo de previsão por random forest quantílico ou pela dispersão entre árvores ou entre
  modelos das dobras;
- **Estatístico:** erro padrão da previsão;
- **Extrapolação:** uma máscara de "área de aplicabilidade" (pixels cujas covariáveis estão fora da faixa das
  estações de treino).

---

## 8. Produção do mapa de 30 m e entrega como asset

**Tamanho:** o Brasil tem ~9 bilhões de pixels a 30 m. Uma banda em `int16` ocupa ~19 GB sem compressão;
as 12 médias mensais + a anual, das duas variáveis, passam de 400 GB. Por isso:

- **Gerar por tiles** (por exemplo, 1° × 1°, ~3.700 × 3.700 pixels), com sobreposição para evitar bordas
  em covariáveis de janela (TPI, TRI).
- **Formato:** GeoTIFF/COG, EPSG:4326, alinhado à grade do MDE de 30 m, compressão DEFLATE ou LZW.
- **Escala inteira para economizar espaço:** temperatura em `int16` com fator 100 (°C × 100); precipitação
  em `uint16` (mm). Registrar o fator nas propriedades do asset.
- **Nomes:** `temperatura_media_30m_<mes>_<tile>.tif` e `precipitacao_30m_<mes>_<tile>.tif` (mês `01`…`12`
  e `anual`).
- **Upload manual no GEE:** subir os tiles como **ImageCollection** (um asset por tile) e montar o mosaico
  com `.mosaic()`. Conferir o limite atual de tamanho por arquivo no upload do Code Editor antes de definir o
  tamanho dos tiles. Usar *pyramiding policy* **mean**.
- **Sugestão de pasta no GEE:** `projects/fcoliveira/assets/CHELSA/refinamento_30m/`.

**Alternativa a considerar (sem gerar TIFF local):** os modelos lineares (M1, M2) e as florestas (M4,
M5) podem ser aplicados direto no GEE: os lineares com álgebra de bandas e as florestas com
`ee.Classifier.smileRandomForest` / `smileGradientTreeBoost` em modo regressão, ou carregando as árvores
treinadas em Python. O resultado é exportado como asset sem passar pela máquina local. Vale comparar o
custo das duas rotas na fase de produção.

**Antes do Brasil inteiro:** gerar a região-piloto completa, conferir visualmente (C10) e validar.

---

## 9. Fases sugeridas

| Fase | Entregas | Comparações |
|---|---|---|
| **0. Dados** | estações com controle de qualidade, normais por estação, tabela de covariáveis extraídas nas estações | C11, C12, C13 |
| **1. Linhas de base** | métricas de CHELSA, Xavier, ERA5-Land e TerraClimate nas estações de teste | C1 |
| **2. Temperatura** | M1 → M2/M3 → M4/M5 → M6 na região-piloto e depois no Brasil | C2, C3, C4, C5, C6, C7 |
| **3. Precipitação** | M2 → M4/M5 → M6 (log ou Tweedie) | C3 a C7 para a chuva |
| **4. Robustez** | subamostragem de estações, incerteza, área de aplicabilidade | C8, C9, C14 |
| **5. Produção** | tiles de 30 m da região-piloto → Brasil, upload no GEE | C10 |
| **6. Documentação** | relatório da pasta, notebook de resultados, entrada no README principal | — |

---

## 10. Organização da pasta

```
refinamento/
├── instrucoes.md            # este arquivo
├── README.md                # o que foi feito e como reproduzir (escrever ao longo do projeto)
├── docs/registro.md         # decisões tomadas, com data e motivo
├── codigo/                  # scripts (dados, covariáveis, modelos, validação, produção dos tiles)
├── notebooks/               # resultados com texto explicando método e leitura
├── resultados/
│   ├── tabelas/             # métricas por método, por região, por mês
│   └── figuras/
└── dados/                   # FORA DO GIT: estações brutas, covariáveis extraídas, tiles
```

- Os dados pesados (séries de estações, tiles de 30 m) ficam fora do git: incluir no `.gitignore`.
- Versionar só código, tabelas agregadas e figuras.
- Em cada notebook, explicar em português o método e a interpretação, como nos notebooks do projeto.

---

## 11. Referências de partida

- Xavier, A. C.; King, C. W.; Scanlon, B. R. (2016). Daily gridded meteorological variables in Brazil
  (1980–2013). *International Journal of Climatology* 36: 2644–2659.
  [doi.org/10.1002/joc.4518](https://doi.org/10.1002/joc.4518)
- Xavier, A. C.; Scanlon, B. R.; King, C. W.; Alves, A. I. (2022). New improved Brazilian daily weather
  gridded data (1961–2020). *International Journal of Climatology* 42: 8390–8404.
  [doi.org/10.1002/joc.7731](https://doi.org/10.1002/joc.7731)
- Grade e dados do Xavier (BR-DWGD): [github.com/AlexandreCandidoXavier/BR-DWGD](https://github.com/AlexandreCandidoXavier/BR-DWGD)
  (download e asset no GEE, atualizado em março de 2025).
- Karger, D. N. et al. (2017). Climatologies at high resolution for the earth's land surface areas (CHELSA).
  *Scientific Data* 4.
- Fick, S. E.; Hijmans, R. J. (2017). WorldClim 2: new 1-km spatial resolution climate surfaces for global
  land areas. *International Journal of Climatology* 37: 4302–4315 (uso de covariáveis de satélite).
- Ploton, P. et al. (2020). Spatial validation reveals poor predictive performance of large-scale ecological
  mapping models. *Nature Communications* 11 (por que validar em blocos).
- Meyer, H.; Pebesma, E. (2021). Predicting into unknown space? Estimating the area of applicability of
  spatial prediction models. *Methods in Ecology and Evolution* 12 (área de aplicabilidade).

Conferir as referências antes de citá-las em texto final.
