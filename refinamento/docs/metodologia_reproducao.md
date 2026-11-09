# Metodologia e reprodução da temperatura

Atualização de 07/11/2026: os comandos de M3/M6, C5/C6, biomas e INMET estão
em [comparações complementares](comparacoes_complementares.md); os de chuva,
em [modelagem da chuva](modelagem_chuva.md). A leitura dos biomas usa adicionalmente
`pyshp==2.3.1` e `shapely==2.1.2`, instalados no ambiente local. O arquivo de
dependências permanece local e ignorado, conforme solicitado.

O [mapa da pasta](../mapa.md) apresenta as entregas e o atendimento às
instruções. Este documento conserva os detalhes técnicos e os comandos, todos
executados a partir de `refinamento/`. Os resultados registrados são experimentais.

## Ambiente e reprodução

Python **3.12 ou superior**; ambiente executado: Python 3.14.2, Windows.
O arquivo `requirements.txt` fica apenas na máquina local, ignorado pelo
`.gitignore` da raiz. Para reproduzir a partir de um clone, instalar as versões
usadas abaixo, sem depender desse arquivo. No PowerShell:

```powershell
New-Item -ItemType Directory -Force .local/tmp | Out-Null
$env:TEMP = (Resolve-Path .local/tmp).Path
$env:TMP = $env:TEMP
$env:PYTHONDONTWRITEBYTECODE = '1'
python -m venv .venv
.venv/Scripts/python.exe -m pip install --no-cache-dir numpy==2.4.4 pandas==3.0.2 scipy==1.17.1 scikit-learn==1.9.0 lightgbm==4.7.0 rasterio==1.5.2 pyproj==3.8.0 gdown==6.4.2 earthengine-api==1.7.37 requests==2.32.5 matplotlib==3.10.8 pytest==7.4.2
```

Preparar as observações e o diagnóstico histórico:

```powershell
.venv/Scripts/python.exe -B -m codigo.baixar_observacoes
.venv/Scripts/python.exe -B -m codigo.dados_temperatura
.venv/Scripts/python.exe -B -m codigo.diagnostico_bases --salvar-painel
```

O download inclui somente Tmax e Tmin, aproximadamente 226 MB. Arquivos já
presentes são reutilizados e têm o hash registrado. Os NPZ de origem representam
1961–2025; a análise usa apenas 1991–2020. O código não presume que Tmax e Tmin
têm as mesmas colunas e não habilita `allow_pickle=True` indiscriminadamente:
IDs legados usam desserialização restrita aos construtores NumPy necessários.

Executar o ensaio com posição, altitude cadastrada e sazonalidade:

```powershell
.venv/Scripts/python.exe -B -m codigo.modelos dados/processados/normais_temperatura.csv --block-size 2 --repeats 3
.venv/Scripts/python.exe -B -m codigo.modelos dados/processados/normais_temperatura.csv --block-size 1 --repeats 3
```

Os arquivos `modelos_exploratorios_*.csv` registram métricas por repetição e mês;
`diferencas_mx_*.csv` registra diferenças pareadas de RMSE. Predições, hiperparâmetros
e partições por estação ficam em `dados/modelagem/`.

Extrair covariáveis usando uma credencial GEE já configurada e comparar as duas
formulações. O projeto padrão é obtido de `quota_project_id`; `--project` permite
informar outro projeto autorizado. Nesta execução, o projeto configurado `mcp-gee`
permitiu ler os assets. Os scripts não alteram permissões nem publicam dados.

```powershell
.venv/Scripts/python.exe -B -m codigo.covariaveis_gee
.venv/Scripts/python.exe -B -m codigo.modelos dados/processados/normais_covariaveis.csv --block-size 2 --repeats 3 --formulation direct
.venv/Scripts/python.exe -B -m codigo.modelos dados/processados/normais_covariaveis.csv --block-size 2 --repeats 3 --formulation correction
.venv/Scripts/python.exe -B -m codigo.modelos dados/processados/normais_covariaveis.csv --block-size 1 --repeats 3 --formulation correction
```

Executar a comparação das quatro bases, as falhas artificiais e a transferência
temporal, depois das etapas anteriores:

```powershell
.venv/Scripts/python.exe -B -m codigo.bases_gee
.venv/Scripts/python.exe -B -m codigo.comparar_bases
.venv/Scripts/python.exe -B -m codigo.falhas_artificiais
.venv/Scripts/python.exe -B -m codigo.transferencia_temporal
.venv/Scripts/python.exe -B -m codigo.figuras_auditoria
```

`bases_gee` reutiliza a seleção de desenvolvimento e extrai Xavier mensal,
ERA5-Land e TerraClimate de 1991–2020. `comparar_bases` avalia as predições já
geradas nas estações comuns, sem retreinar os modelos. C12 e C13 usam seleções
próprias de séries completas, descritas na [auditoria](auditoria_escopo.md).
Séries por estação, predições e manifestos ficam em `dados/bases/`; tabelas
agregadas e figuras ficam em `resultados/`. As 18 estações reservadas continuam
fora desses ensaios.

A C1 atual usa `projects/ee-alexandrexavier/assets/BR-DWGD_Monthly`. A etapa
[C4 do repositório](../../C4/codigo/baixar_xavier.py) registra uma divergência
entre chuva mensal desse asset e soma dos dias em um ponto. Essa observação
é sobre precipitação; não demonstra erro em Tmax/Tmin, mas a equivalência da
temperatura mensal com a agregação diária ainda precisa ser conferida.

Produzir a prévia, auditar os arquivos e gerar as figuras:

```powershell
.venv/Scripts/python.exe -B -m codigo.mapa_piloto --method M5_lightgbm --formulation correction
.venv/Scripts/python.exe -B -m codigo.auditar_piloto
.venv/Scripts/python.exe -B -m codigo.figuras
```

Os 39 produtos já existem nesta máquina, em `dados/piloto/`. O comando de produção
recusa sobrescrevê-los; auditoria e figuras podem ser executadas novamente.
O arquivo anual principal é
`dados/piloto/temperatura_media_30m_anual_curitiba_M5_lightgbm_correction.tiff`.
Os mensais usam `01`…`12` no lugar de `anual`. O manifesto privado registra fontes,
grade, parâmetros, hashes e a separação entre desenvolvimento e teste.

`diferencas_pareadas_*.csv` acrescenta comparações com CHELSA, regressão linear e
random forest. Os arquivos `auditoria_covariaveis.csv` e `auditoria_piloto.csv`
registram as conferências realizadas, sem publicar dados por estação.

Executar os testes com todos os temporários dentro desta pasta:

```powershell
New-Item -ItemType Directory -Force .local/pytest | Out-Null
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD = '1'
.venv/Scripts/python.exe -B -m pytest codigo/testes -q -p no:cacheprovider --basetemp .local/pytest/execucao
```

## Regras científicas desta versão

**Temperatura observada:** média diária dos extremos `(Tmax + Tmin)/2`, somente
quando ambos são válidos. Essa variável não equivale automaticamente à média das
24 horas nem à temperatura compensada do INMET. A comparação C11 ainda está pendente.

**Controle inicial:** limites estritos −30 < T < 50 °C, Tmin ≤ Tmax, pelo menos
80% dos dias pareados para aceitar um mês e pelo menos 24 de 30 anos para aceitar
cada normal mensal. O CSV conserva as normais reprovadas como ausentes; o ensaio
balanceado usa apenas estações com os 12 meses aprovados. Não há preenchimento.
Saltos, séries constantes e coordenadas duplicadas são sinalizados para revisão,
sem excluir observações silenciosamente. Altitudes ainda precisam de conferência
com datum, mudança de local e histórico dos instrumentos.

**Normal anual:** média dos 12 valores mensais, ponderada pelo número médio de
dias de cada mês em 1991–2020, incluindo anos bissextos. `n_years` anual registra
o mínimo entre os meses; não é a quantidade de anos completos comuns aos 12 meses.

**Validação:** reservar 15% dos blocos de 2° com semente fixa antes do ajuste.
O desenvolvimento usa 5 dobras externas, 3 repetições e 3 dobras internas para
escolher os hiperparâmetros. Todos os meses de uma estação e todas as estações de
um bloco ficam juntos. A partição reservada é a mesma nos ensaios de 1° e 2°.
Não há buffer entre blocos: estações próximas à fronteira podem continuar próximas;
esse é um limite da validação atual, não uma prova de independência completa.
Excluir uma estação do ajuste local também não garante independência de grades
que possam tê-la usado anteriormente. A procedência das estações nos produtos de
referência e nas covariáveis deve ser auditada antes de afirmar validação independente.

**Métodos:** M2 é regressão linear com latitude, longitude, altitude e harmônicos
anuais com interação latitude × estação do ano; M4 é random forest; M5 é LightGBM.
Hiperparâmetros são escolhidos apenas nas dobras internas. O comparador MX usa
cinco vizinhos do treino, distâncias geográficas, peso inverso ao quadrado e
gradiente fixo −0,006 °C/m. É uma **referência mensal inspirada no método do
artigo**, sem reproduzir toda a sequência diária ou recalibrar o gradiente;
a comparação C15 completa continua pendente. MX não é candidato ao mapa final.

Com grade, os modelos usam altitude do **mesmo DSM** disponível nos pixels,
declividade e CHELSA, além de posição e sazonalidade. Na forma de correção, o alvo
é observado − CHELSA e a previsão final soma CHELSA uma única vez. M0 mantém
CHELSA; M1 aplica −0,0065 °C/m à diferença entre DSM de 30 m e DSM agregado à
célula CHELSA. Essa altitude agregada é uma aproximação, não o relevo original
interno do CHELSA. Os meses observados podem conter 24–30 anos, enquanto CHELSA
representa a normal completa. C12 já testou correções com falhas artificiais de
anos, mas esses ajustes ainda não foram incorporados ao alvo do piloto.

O DSM é reamostrado por bilinear; CHELSA e a altitude agregada, por vizinho mais
próximo. Essas operações alinham covariáveis raster. O valor climático final sai
do modelo; não há interpolação de estações ou de resíduos no produto.

**Métricas:** RMSE, MAE e viés em °C orientam a análise; viés = previsto − observado.
PBIAS, r, NSE, d e KGE são calculados para compatibilidade com o projeto. PBIAS e
KGE em °C dependem da origem da escala e não devem decidir o vencedor. Os intervalos
pareados reamostram blocos, mantendo meses e repetições juntos: são intervalos
condicionais às previsões de validação cruzada, não intervalos de previsão por pixel
nem quantificação completa da incerteza de reajustar todo o experimento.

## GeoTIFF e GEE

Para cumprir o requisito de 30 m, a grade é projetada em metros. EPSG:4326 usa
graus; não fornece pixels de 30 × 30 m constantes. No piloto, usar UTM local e
origem múltipla de 30. Isso exige alinhar as covariáveis à grade escolhida e difere
da sugestão angular das instruções, sem alterar o documento original.

Temperatura: `int16`, fator 100 no armazenamento, fator 0,01 na leitura, nodata
−32768, DEFLATE. Metadados incluem período, método e caráter experimental.
Os arquivos são GeoTIFF comuns; não são anunciados como COG.

A prévia usa **WGS84 / UTM 22S, EPSG:32722**, com a mesma convenção de grade usada
na extração das estações. O modelo principal é ajustado somente nas 102 estações
de desenvolvimento. A dispersão vem de cinco modelos ajustados em subconjuntos
desse desenvolvimento, com hiperparâmetros fixados nele; não é intervalo preditivo
calibrado. A flag `fora_faixa_treino` vale 1 quando alguma covariável está fora do
mínimo/máximo de treino; não substitui uma área de aplicabilidade multivariada.

| Camada | Tipo | Escala de leitura | Nodata | Política GEE |
|---|---|---:|---:|---|
| Temperatura | int16 | × 0,01 °C | −32768 | mean |
| Dispersão entre modelos | float32 | × 1 °C | −9999 | mean |
| Fora da faixa de treino | uint8 | 0/1 | 255 | sample |

A inspeção visual encontrou textura fina e descontinuidades associadas à base
grosseira. O detalhe não foi validado como microclima; C5 e C10 permanecem abertos.
O Copernicus é um modelo de superfície e inclui vegetação/edificações.

No GEE, configurar `pyramiding_policy=mean` para temperatura e aplicar o fator
0,01 explicitamente após a ingestão. Máscaras categóricas precisam de política
apropriada (`sample`/`mode`). O upload será manual, depois da validação científica.

Fontes: CHELSA do projeto e Copernicus DEM GLO30 2024_1. Atribuição Copernicus:
produced using Copernicus WorldDEM-30 © DLR e.V. 2010-2014 and © Airbus Defence
and Space GmbH 2014-2018 provided under COPERNICUS by the European Union and ESA;
all rights reserved. Detalhes e links estão em [referencias.md](referencias.md).
