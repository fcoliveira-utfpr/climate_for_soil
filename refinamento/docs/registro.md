# Registro de execução

## 2026-10-18 — início da implementação de temperatura

Os resultados abaixo distinguem diagnósticos exploratórios de um produto validado.
Esta primeira etapa foi retomada e encerrada em 19/10, conforme a entrada seguinte.
Não houve commits.

### Escopo e decisões

1. Trabalhar somente dentro de `refinamento/`, preservar `instrucoes.md` e manter
   dados, ambiente e temporários ignorados pelo git. Não alterar o README principal.
2. Temperatura antes de chuva; alvo inicial = normal mensal e anual 1991–2020.
3. Usar observações reais da pasta cedida pelo Xavier, sem redistribuí-las.
4. Reservar blocos de teste antes da escolha de modelo e não avaliar esse teste
   durante a exploração. Medir se ML ajuda; não escolher ML por preferência.
5. Interpretar o requisito literal de 30 m como grade projetada em metros;
   documentar a diferença para EPSG:4326 e para o MDE angular nativo.

### O que foi encontrado na leitura

Os relatórios existentes tratam principalmente de clima como covariável do solo.
Não comprovam um produto térmico novo a 30 m. O arquivo
`validacao/dados_xavier_estacoes_1991_2020.csv` contém 2010–2019, apesar do nome.

O histórico `e14ea634fcbd378fffd1a9833578aa99cd644469` foi lido, sem restaurar
arquivos no restante do projeto. O script histórico usa
`(elev_chelsa_fina - dem30) * lapse_rate`, com gradiente negativo. Essa expressão
aquece pixels mais altos e inverte o sinal físico esperado; a nova fórmula é
`T_grade + gamma * (z30 - z_grade)`. Não foi demonstrado que a tabela histórica
de resultados veio exatamente desse script; por isso ela não foi "corrigida"
nem usada como comprovação de ganho.

A página oficial do Xavier foi consultada; o artigo integral não pôde ser obtido.
Os detalhes não reconferidos estão identificados em [referencias.md](referencias.md).

### Dados e qualidade

| Item | Resultado |
|---|---:|
| Estações em Tmax | 1.194 |
| Estações em Tmin | 1.189 |
| IDs em comum | 1.186 |
| Somente Tmax / somente Tmin | 8 / 3 |
| Dias no período 1991–2020 | 10.958 |
| Estação-dias com par válido | 4.964.574 |
| Dias com Tmin > Tmax, excluídos | 8 |
| Estação-meses aceitos com ≥80% dias | 159.922 |
| Estações com os 12 meses e ≥24 anos/mês | 120 |
| Desenvolvimento / teste reservado | 102 / 18 |

Sensibilidade da cobertura por mês: 70% (≥21 anos) deixa 191 estações completas;
80% (≥24 anos), 120; 90% (≥27 anos), 58. Isso mede disponibilidade, não escolhe
automaticamente o melhor limiar. As normais de meses diferentes podem usar anos
diferentes; correção de período reduzido e teste com falhas artificiais não foram
concluídos. Saltos, constância e locais duplicados continuam como sinais de revisão.

Hashes SHA256 dos arquivos obtidos:

- Tmax: `fc5bd48bb0fa5cc9a9ab3973b25df437e12906d5b59982ce941944d9575e66ae`.
- Tmin: `53f304b29258bdf5617833afb8032b280ee54a1990da110a7d93a1d10886b997`.

### C1: diagnóstico separado de 2010–2019

Mesmo conjunto de 2.335 pares e 22 estações, com pelo menos 80% dos dias válidos:

| Base | RMSE (°C) | Viés (°C) |
|---|---:|---:|
| CHELSA | 0,814 | −0,489 |
| Xavier | 0,854 | +0,223 |
| ERA5-Land | 1,635 | −0,739 |
| TerraClimate | 1,506 | −0,998 |

Resultados por UF foram suprimidos porque todas têm menos de cinco estações.
Esse diagnóstico não é a validação das novas normais, não resolve C11 e não
demonstra independência das estações perante as grades.

### Primeiro ensaio: apenas posição, altitude e sazonalidade

RMSE médio das três repetições, com cinco dobras espaciais em cada repetição:

| Método | Blocos de 1° (°C) | Blocos de 2° (°C) |
|---|---:|---:|
| M2 — regressão linear | 1,658 | 1,674 |
| M4 — random forest | 1,134 | 1,148 |
| M5 — LightGBM | 1,100 | 1,078 |
| MX — referência mensal | 0,807 | 0,865 |

**Decisão:** não escolher esse conjunto mínimo como produto. ML melhora sobre a
regressão linear, mas não supera MX. Com blocos de 2°, a diferença de RMSE do
LightGBM menos MX é +0,212 °C, com intervalo bootstrap por blocos de +0,097 a
+0,336 °C. O cálculo do intervalo usa RMSE agrupado das previsões; a tabela acima
mostra a média dos RMSE por repetição, por isso as diferenças podem variar levemente.

Esse MX não é uma reprodução completa do artigo: trabalha com normais mensais e
gradiente fixo. Nenhum resultado desta tabela compara diretamente os números
diários publicados por Xavier com as normais mensais.

### Acesso ao GEE

Inicializar com o projeto consumidor `fcoliveira` falhou com erro 403. A credencial
já existente contém o projeto de quota `mcp-gee`, que permitiu inicialização e
leitura dos assets CHELSA, Copernicus, ERA5-Land, TerraClimate e BR-DWGD mensal.
Não foi necessário alterar permissões, reautenticar ou publicar assets.

### Próximas decisões científicas

- C11: comparar média de extremos com média horária/compensada antes de definir
  a temperatura média final.
- Revisar sinais de qualidade, duplicatas, datum/altitude e homogeneidade.
- C12/C13: testar normal reduzida com falhas artificiais e estabilidade temporal;
  não tratar séries recentes como se fossem observações completas de 1991–2020.
- Comparar bases e métodos com covariáveis reais no mesmo conjunto, incluindo
  formulação de correção da grade. Essa comparação continua exploratória enquanto
  definição térmica e coincidência dos anos observados não estiverem resolvidas.
- C5/C6/C7: testar resolução, contribuição dos grupos de covariáveis e estrutura
  mensal; faltam MODIS, distância ao oceano, terreno multiescala e outros grupos.
- C14/C15: separar estações independentes da grade Xavier e reproduzir corretamente
  o comparador do artigo; só depois avaliar o teste reservado e decidir publicação.
- Produção nacional, limites entre zonas/tiles, incerteza calibrada, área de
  aplicabilidade e upload público permanecem etapas posteriores.

## 2026-10-19 — covariáveis reais, comparação da correção e prévia GeoTIFF

### Extração e conferência do relevo

Foi concluída a extração de CHELSA, Copernicus DSM, declividade e altitude média
da célula CHELSA nas 120 estações, sem escrever assets. São 1.440 linhas mensais,
sem ausências ou duplicatas. O hash da tabela é
`49fc894756ecca954f5c1da48088856e39e61ab83c77bc23a7595bce1d007ef9`.

O DSM menos a altitude cadastrada tem viés de +6,01 m e MAE de 11,77 m; três
estações ultrapassam 50 m em módulo. Essa comparação não resolve diferenças de
datum, vegetação/edificações ou mudança de local. A altitude grosseira é calculada
por média ponderada dos pixels nativos na grade CHELSA, não por uma única amostra.
É uma aproximação da orografia da base, não o MDE original usado pelo CHELSA.

Uma auditoria remota em três locais comparou pixels de treino/inferência e a média
de 961 subpixels por célula. A média grosseira concordou até 0,000023 m; os valores
de treino e raster concordaram dentro do arredondamento do CSV. Corrigiu-se a
validação de extrações contendo `None`, sem mudar cálculos. Nova extração produziu
CSV idêntico. O helper está identificado como versão 1.0.0 no manifesto privado.

### C2/C3/C4: o que a grade mudou

RMSE médio de três repetições, sempre nas mesmas 102 estações de desenvolvimento:

| Método | Direta, blocos 2° | Correção, blocos 2° | Correção, blocos 1° |
|---|---:|---:|---:|
| CHELSA sem ajuste | 0,794 | 0,794 | 0,794 |
| M1 — gradiente fixo | 0,826 | 0,826 | 0,826 |
| M2 — regressão linear | 0,588 | 0,588 | 0,573 |
| M4 — random forest | 0,601 | 0,528 | 0,535 |
| M5 — LightGBM | 0,570 | 0,524 | 0,536 |
| MX — referência mensal | 0,865 | 0,865 | 0,807 |

Valores em °C. M0, M1 e MX são referências compartilhadas; as colunas de formulação
não representam ajustes diferentes dessas referências. A equivalência de M2 é
esperada: regressão linear com intercepto e CHELSA entre os preditores representa
a mesma família de funções nas formulações direta e de correção.

**Decisões e interpretação:**

- C2: o gradiente fixo piorou o resultado neste conjunto. Não adotá-lo sozinho;
  rever gradientes por mês/região e a aproximação da altitude grosseira depois.
- C3: os modelos com CHELSA melhoram sobre a base sem ajuste neste desenvolvimento.
  Não atribuir todo o ganho a microclima de 30 m: redução do viés, definições térmicas
  e covariáveis regionais também podem explicar a melhora.
- C4: a correção teve menor RMSE que a forma direta para as duas famílias de árvores
  no experimento de 2°. É uma formulação promissora para continuar, não prova de
  estabilidade entre décadas; C13 ainda precisa ser feito.
- LightGBM versus CHELSA, blocos 2°: diferença de RMSE agrupado −0,270 °C;
  intervalo bootstrap pareado de −0,340 a −0,196 °C.
- LightGBM versus random forest, blocos 2°: −0,0045 °C; intervalo −0,0251 a
  +0,0164 °C. Com blocos 1°, +0,0005 °C; intervalo −0,0226 a +0,0214 °C.
  **Não há base para declarar um vencedor entre os dois ML.**
- M5 na forma de correção foi escolhido somente como candidato para exercitar a
  produção do piloto. M4 continua candidato. O teste reservado não foi consultado.
- A melhora contra MX vale para o comparador mensal implementado; não comprova
  superioridade ao artigo completo nem à grade Xavier em estações independentes.

As tabelas com incerteza reamostram blocos e mantêm meses/repetições juntos.
São intervalos condicionais às previsões de CV, sem refazer todo o ajuste em cada
amostra bootstrap. C11/C12 ainda limitam a comparação: média de extremos e anos
observados incompletos podem divergir da definição e do período efetivo do CHELSA.
Também falta auditar a participação das estações nos produtos usados como
covariáveis. Retirá-las do treino local não desfaz eventual uso anterior nas grades.

### Produto local entregue nesta execução

Prévia de **12 × 12 km em Curitiba**, WGS84/UTM 22S, EPSG:32722; origem alinhada
a múltiplos de 30 m, **400 × 400 pixels de 30 × 30 m**. As covariáveis do raster
usam o mesmo helper da amostragem de estações, com margem para cálculos de terreno.

Em `dados/piloto/`, ignorado pelo git:

- 13 arquivos `temperatura_media_30m_*.tiff`: 12 meses e anual, int16 × 100,
  nodata −32768, DEFLATE e escala de leitura 0,01 °C.
- 13 arquivos `dispersao_modelos_30m_*.tiff`: desvio padrão entre cinco modelos,
  float32 em °C. **Não é intervalo de previsão.** O anual é calculado depois de
  agregar cada modelo pelos pesos mensais, preservando sua dependência entre meses.
- 13 arquivos `fora_faixa_treino_30m_*.tiff`: flag 0/1 de covariáveis fora do mínimo
  ou máximo do treino, uint8. **Não é área de aplicabilidade multivariada formal.**
- Covariáveis de entrada e manifestos com fontes, parâmetros, grade e hashes.

O candidato foi reajustado nas 102 estações de desenvolvimento, com seleção de
`num_leaves=7` em três dobras internas; 18 estações continuam reservadas. Os cinco
modelos de dispersão usam os hiperparâmetros escolhidos no desenvolvimento.

No raster anual, a temperatura varia de **17,82 a 18,91 °C**, média 18,393 °C.
A dispersão entre modelos varia de 0,010 a 0,319 °C. **0,411%** dos pixels estão
fora da faixa univariada de treino; estar dentro dela não garante validade da
previsão. Os valores do mapa são previsões experimentais, não novas observações.

### Verificações e revisão

- **67 testes passaram** na suíte completa. Cobrem calendário e bissextos,
  pareamento Tmax/Tmin, falhas, QC, IDs legados restritos, métricas, blocos/dobras,
  holdout, comparações pareadas, correção da grade, inferência e formato GeoTIFF.
- Uma inversão de sinal do gradiente feita somente em memória foi detectada pelo
  teste, sem modificar o código de produção.
- Auditoria dos **39 arquivos reais**: hashes, CRS, affine, dimensões, dtype,
  escala/offset, nodata, compressão e metadados experimentais conferidos;
  160.000 pixels válidos por arquivo.
- A média anual confere com os mensais até a quantização: diferença máxima
  0,007527 °C, abaixo do limite de 0,01 °C. A flag anual é a união das mensais.
- Revisão independente não encontrou bug bloqueante; confirmou ausência das
  18 estações de teste nos arquivos de predições e no ajuste do mapa.
- Figuras geradas e inspecionadas: `resultados/figuras/comparacao_modelos.png`
  e `previa_curitiba_anual.png`.

**C10 ainda não aprovado:** a prévia mostra textura fina e descontinuidades ligadas
à base grosseira. Parte desse padrão pode refletir superfície urbana/vegetação do
DSM ou respostas descontínuas das árvores. Não interpretar o detalhe como
microclima comprovado nem suavizar o mapa apenas para melhorar sua aparência.
O próximo trabalho científico deve testar covariáveis/escalas e perfis de terreno,
além das pendências C11–C15 descritas acima.

### Reproduzir e continuar

Os comandos completos estavam no README da época (hoje em [metodologia_reproducao.md](metodologia_reproducao.md)). A prévia já está gravada;
o script recusa sobrescrevê-la. `python -m codigo.auditar_piloto` confere os produtos
locais e `python -m codigo.figuras` atualiza as figuras sem treinar novamente.

Esta execução fecha uma primeira cadeia funcional: observações reais → controle
inicial → normais → covariáveis → validação espacial exploratória → GeoTIFF piloto.
Não fecha o produto nacional, a escolha definitiva do modelo, a validade científica
do detalhe de 30 m ou a publicação pública. Chuva não foi iniciada.

Somente `refinamento/` foi modificado; `instrucoes.md` mantém SHA256
`FFDEB1E2D88320448ED2A8463B2EB273A4BCF905AACD9B1C8873D4B0E533BC4F`.
Nenhum commit, stage, push ou upload de asset foi realizado.

## 2026-11-02 — inspeção da fonte de chuva indicada por Fabrício

Foi consultado `projects/fcoliveira/assets/observados_inmet/pr`, indicado na
mensagem de 29/10/2026. Acesso confirmado com a credencial já configurada,
projeto `mcp-gee`, API Python do Earth Engine 1.7.37. Foram realizadas somente
leituras remotas e gravações locais dentro de `refinamento/`.

**Resultado:** o asset é `TABLE`/`FeatureCollection`, com registros diários de
pluviômetros. Os metadados declaram 13.259 estações de ANA, INMET e redes
estaduais, período 1961-01-01 a 2020-07-31 e 10,34% de preenchimento com BR-DWGD.
A flag `preenchido` distingue medição (0) de preenchimento pela grade (1).
Os números nacionais são declarados pelo organizador, não recontados aqui.

**Verificação executada:** consulta dos metadados, três feições da coleção e
um recorte de uma estação/ano com limite de 370 registros. O recorte retornou
365 datas únicas em 1961, 364 registros observados e um preenchido, todos com
geometria pontual e timestamps presentes, sem valores nulos ou negativos. A
consulta `A807`/2010 do exemplo original retornou vazia; por isso o exemplo na
documentação escolhe uma estação/ano efetivamente presente. Não houve download
da coleção nacional nem validação completa da qualidade das séries.
As verificações locais confirmaram concordância entre as 365 datas e timestamps,
contagens das flags, links da documentação e integridade de `instrucoes.md`.

**Decisões:** registrar como candidata a fonte observacional da próxima fase.
Usar apenas observações reais como alvo; exigir meses completos depois de
retirar preenchimentos; somar chuva diária para totais mensais e somar as 12
normais mensais elegíveis para a anual. A falta de agosto–dezembro de 2020
precisa de complemento ou tratamento explícito de completude/período reduzido.
As estações usadas pelo Xavier não são automaticamente validação independente
dele, mesmo removendo valores preenchidos. Falta comparar o asset com o
`pr.npz` previsto nas instruções, inclusive códigos, cobertura e sobreposição.

Documentação: [fonte_chuva_inmet.md](fonte_chuva_inmet.md), com ligação pelo
README. Metadados, amostras e scripts de consulta permanecem privados em
`.local/chuva_inmet/`. A alteração versionável é documental; não houve mudança
no pipeline nem execução de testes dos modelos. Não foram produzidas normais,
modelos ou mapas de chuva, nem publicados dados.

`instrucoes.md` foi somente lido; SHA256 conferido nesta sessão:
`99612D0AD6F73FBD1EB55D30C681573FB9406AEEBAE48D5C515C498D780499ED`.
Nenhum commit, stage, push ou upload de asset foi realizado.

## 2026-11-03 — auditoria do áudio/escopo, C1, C12 e C13

O usuário forneceu a transcrição do áudio e pediu conferir o trabalho contra o
escopo e executar o que faltava. A revisão tomou `instrucoes.md` como contrato,
com prioridade para temperatura e alterações limitadas a esta pasta. A
[auditoria completa](auditoria_escopo.md) e o
[quadro C1–C15](../resultados/tabelas/status_comparacoes.csv) separam evidência,
decisões e pendências. **O piloto está no escopo, mas não é o produto nacional
validado solicitado.**

### Verificação do ponto de partida

Os 67 testes existentes passaram, após criar a pasta pai dos temporários
`.local/pytest`. Os 39 GeoTIFFs existentes conferiram novamente: hashes, grade,
tipos, escala, nodata, compressão e coerência anual (erro máximo 0,007527 °C).
Os hashes de código e tabela registrados nos manifestos da extração e do piloto
coincidem com os arquivos atuais. As cinco tabelas originais de predições
preservam os blocos/dobras e excluem as 18 estações reservadas.

### C1 — quatro bases no período 1991–2020

Novos módulos `bases_gee.py` e `comparar_bases.py`: extração mensal nas 102
estações de desenvolvimento, conversão de unidades por fonte, validação dos 360
meses, checkpoints privados e comparação pareada com as predições existentes.
Xavier aplica os fatores `MULT/ADD` por banda/imagem; ERA5 subtrai 273,15 K;
TerraClimate usa fator 0,1 e média de Tmax/Tmin. A consulta usa o CRS e os seis
coeficientes da transformação nativa obtidos dos metadados. A primeira tentativa
passou a transformação como texto WKT; a API recusou, e o código foi corrigido
antes da extração bem-sucedida.

Foram obtidas 110.160 combinações estação-mês-base, incluindo 1.440 ausências
no ERA5 (quatro estações) e 360 no Xavier (uma dessas estações). Nenhuma média
focal ou imputação foi usada. A comparação fica com 98 estações comuns, mantendo
os treinos originais de 102 e as mesmas dobras; não houve novo ajuste do piloto.
Normais de grade incompletas são rejeitadas, não calculadas com menos anos sem aviso.

RMSE mensal, média de três repetições nos blocos de 2°: Xavier 0,241 °C;
LightGBM/CHELSA 0,526; RF/CHELSA 0,531; linear 0,593; CHELSA 0,798; gradiente
fixo 0,832; MX mensal 0,836; ERA5 1,228; TerraClimate 1,267. O LightGBM menos
CHELSA tem diferença agrupada −0,272 °C, intervalo [−0,340; −0,195]; contra
Xavier, +0,284 °C, intervalo [+0,220; +0,353]. Também foram calculados anual,
meses, faixas de altitude e comparação das grades nos mesmos anos observados.

**Decisão C1/C9:** a melhora sobre CHELSA permanece, mas superar a grade Xavier
não está demonstrado. Não escolher nova base final só por esse ranking, pois
as estações podem ter participado das grades. C9 avança em altitude; regiões e
biomas continuam pendentes. C11 e C14 ainda limitam a interpretação.

### C12 — falhas artificiais de anos

Novo módulo `falhas_artificiais.py`: 250 séries estação-mês de 43 estações com
30 anos elegíveis e ERA5/TerraClimate completos. São 30 máscaras para retenção
aleatória de 21/24/27 anos e cenários fixos 1991–2000, 2011–2020 e 1997–2020.
Média disponível, método das diferenças e regressão com referência usam as
mesmas máscaras, sem consultar observações retiradas.

Com ERA5 e 24 anos aleatórios, RMSE 0,082 → 0,040 °C pelo método das diferenças;
regressão, 0,037 °C. Com 2011–2020, RMSE 0,408 → 0,210 °C e viés
+0,309 → +0,016 °C. A regressão teve RMSE 0,208 e viés +0,069 °C nesse cenário.

**Decisão C12:** ajuste temporal promissor, sem promoção automática ao alvo do
piloto. O ensaio é parcial: remove anos de séries longas e não testa lacunas
diárias nem garante transporte para estações curtas. Meses de origem passam
pelo QC de 80% dos dias, não exigem todos os dias completos.

### C13 — transferência espacial e temporal com ERA5

Novo módulo `transferencia_temporal.py`: 68 estações com 12 meses elegíveis e
pelo menos oito anos por mês nas duas décadas. M2, M4 e M5 aprendem correção
de ERA5 em 2001–2010; avaliação em 2011–2020 usa outras estações/blocos. Um
controle contemporâneo aprende em 2011–2020, também excluindo o bloco avaliado.
Hiperparâmetros são escolhidos em três dobras internas; cinco externas, três
repetições e blocos de 1°/2°.

Em 2°, RMSE do ERA5 1,267 °C; linear transferido 0,849; RF transferido 0,770;
LightGBM transferido 0,750; LightGBM contemporâneo 0,747. A diferença agrupada
entre os dois LightGBM é +0,003 °C, intervalo [−0,048; +0,046]; transferido
menos ERA5 = −0,517 °C, intervalo [−0,694; −0,330].

**Decisão C13:** há evidência favorável à transferência da correção de ERA5
neste conjunto. Não extrapolar para a correção CHELSA do piloto, para 1991–2000
ou para habilidade espacial em 30 m. O ensaio usa ERA5 da década avaliada e é
uma avaliação retrospectiva, não uma previsão futura sem essa covariável.

### Entrega e verificações finais

- **92 testes passaram** na suíte completa, com temporários em `.local/pytest`.
- Duas mutações somente em memória foram detectadas pelos testes: aceitar 29
  anos como normal integral e inverter o sinal do ajuste temporal. Nenhum arquivo
  de produção foi alterado para essa verificação.
- Confirmada ausência das 18 estações reservadas nas novas séries extraídas,
  predições C1/C13 e resultados por estação de C12.
- Duas figuras agregadas foram geradas por `figuras_auditoria.py` e inspecionadas
  visualmente. O notebook `notebooks/auditoria_temperatura.ipynb` contém 15
  células, com as seis células de código executadas sem erro, lendo apenas tabelas
  agregadas. Links locais foram conferidos.
- Séries, predições, parâmetros e manifestos novos permanecem em `dados/bases/`;
  checkpoints em `.local/bases_gee/`. O `git check-ignore` confirmou a exclusão.
- Os mapas e os scripts anteriores de treino/produção foram preservados.

Permanecem as pendências enumeradas na auditoria: C11/QC, extensão de C12,
independência C14 e comparador C15, escalas/covariáveis/sazonalidade/densidade
C5–C8, regiões/biomas, artefatos, ampliação do piloto e produção nacional.
Não foi declarado produto final nem superioridade independente ao Xavier.

`instrucoes.md` mantém o SHA256 conferido no início desta revisão:
`99612D0AD6F73FBD1EB55D30C681573FB9406AEEBAE48D5C515C498D780499ED`.
Nenhum commit, stage, push, mensagem a terceiros ou publicação foi realizado.

## 03/11/2026 — organização conforme o restante do repositório

**Pedido:** seguir o padrão de `codigo/` e `resultados/`, explicar as entregas ao
professor, esclarecer a abrangência dos mapas de Curitiba, centralizar o
`.gitignore` na raiz e manter `requirements.txt` somente local.

**Referências de organização:** `C4/planejamento.md`, `corelacao/README.md` e
seção 10 de `instrucoes.md`. Mantidos código, tabelas e figuras nas pastas
correspondentes, com notebook e documentação de apoio previstos nas instruções.

- Movidos os dez módulos de teste de `testes/` para `codigo/testes/`. Ajustados
  somente os caminhos relativos de importação e do teste de proteção de saída.
- Reescrito o `README.md` como relatório da etapa: objetivo, 39 GeoTIFFs locais,
  figuras, resultados e situação de cada requisito e comparação C1–C15.
  Explicitado que o pedido é Brasil inteiro e que os 12 × 12 km de Curitiba são
  uma prévia, ainda insuficiente como região-piloto completa.
- Diferenciadas as amostras: 102 estações no desenvolvimento original, 98 na
  comparação comum C1, 43 em C12, 68 em C13 e 18 reservadas. Os indicadores não
  foram apresentados como validação apenas de Curitiba nem como produto final.
- Preservados os detalhes técnicos do README em `docs/metodologia_reproducao.md`,
  com os comandos das novas comparações e instalação reproduzível sem depender
  de um `requirements.txt` versionado. Registrada a ressalva encontrada em C4
  sobre a coleção mensal Xavier: divergência de chuva não demonstra erro de
  temperatura; a equivalência de Tmax/Tmin com agregação diária segue por conferir.
- Migradas as exclusões para o `.gitignore` da raiz, conforme autorização
  explícita do usuário; removido apenas o `.gitignore` de `refinamento/`.
  `requirements.txt` foi mantido no disco e incluído nas exclusões.

**Verificações:** 92 testes passaram antes da movimentação (10,23 s) e a suíte
completa voltou a passar no novo caminho. Foram conferidos 22 links locais da
documentação reorganizada. Os hashes de 103 arquivos de produção, resultados,
rasters, notebook e instruções permaneceram idênticos ao início desta etapa.
`git diff --check` passou e `git check-ignore` confirmou a exclusão de dados,
ambiente, temporários, caches e `requirements.txt` pelas regras da raiz.

Esta etapa alterou organização e documentação; não refez modelos nem mapas.
As pendências científicas registradas permanecem. `instrucoes.md` foi preservado.
Nenhum commit, stage, push ou upload foi realizado.

## 06/11/2026 — avanço nacional solicitado pelo usuário

O usuário ampliou a execução imediata para o Brasil e solicitou um documento
de atendimento de todo o escopo. Criado `docs/entrega_brasil.md`, com matriz por
seção e C1–C15, evidências, métodos e pendências; incluído link no README principal
conforme a seção 9. Atualizados o README de refinamento e a tabela de status.

**C7/C8:** implementado `robustez_temperatura.py` e executadas duas escalas de
bloco, cinco dobras, três repetições e tuning interno. Linear/LightGBM, quatro
estratégias sazonais e densidades 25/50/75/100%, subamostrando somente estações
do treino. Os 18 pontos reservados permaneceram fora. Em 2°, LightGBM harmônicos
100%: RMSE 0,5239 °C; 25%: 0,6204; 50%: 0,5724; 75%: 0,5447. Modelo por mês:
0,5456; diferença contra harmônicos inconclusiva no intervalo pareado. Não foi
alterada a escolha final apenas por estes resultados. Predições e parâmetros
em `dados/modelagem/c7_c8_*`; métricas/diferenças agregadas em `resultados/tabelas/`.

**C9:** `regioes_temperatura.py` atribuiu grandes regiões por polígonos de UFs
obtidos da API IBGE. Desenvolvimento: Sudeste 33, Nordeste 23, Sul 17, Norte 16,
Centro-Oeste 12; uma estação sem atribuição unívoca. Ela não foi removida das
métricas globais. Métricas regionais usam as predições pareadas C1 e grupos de
pelo menos cinco estações; biomas continuam pendentes.

**Grade nacional:** `grade_brasil.py` gerou 743 tiles de 4096 × 4096 pixels,
separados por zona UTM/hemisfério, com máscara de interseção territorial e
origem múltipla de 30 m. Aproximadamente 9,44 bilhões de pixels no território,
estimados por área. Coleção de duas variáveis ×13 períodos: 491 GB sem compressão
somente para clima, 1,72 TB incluindo SD float32 e flag uint8. Havia cerca de
124 GB livres; solicitado destino de armazenamento ao usuário, sem presumir
resposta ou compressão suficiente.

**Proveniência:** a geração recusou inicialmente a mudança de `updateTime` do
Copernicus DEM. O helper existente foi executado novamente nas 120 estações,
com saída separada em `dados/brasil/normais_covariaveis_20261106.csv`. As 1.440
linhas e o SHA256 foram idênticos aos anteriores. O novo manifesto registra a
fonte atual, sem modificar os dados/manifestos do piloto.

**Produção:** `mapa_brasil.py` implementa janela de 512 pixels, 39 GeoTIFFs por
tile, nodata, máscara territorial, predição por covariáveis, anual ponderada,
dispersão e extrapolação min/max. Assinaturas recusam retomada após mudança de
grade, treino, helper ou manifesto. Executada uma janela real e, depois, uma
retomada: duas janelas, 524.288 pixels válidos, sem refazer a primeira. A retomada
levou 90,19 s, incluindo inicialização/ajuste/download; não extrapolar esse
tempo isolado para o lote nacional.

`auditar_brasil.py` confirmou contagem de pixels, máscara e compatibilidade anual
versus mensais (erro máximo 0,0076656 °C). Há **um tile parcial e zero completos**,
39 arquivos iniciados ocupando 12.371.595 bytes. A cobertura nacional ainda não
foi entregue. Arquivos e manifestos estão em `dados/brasil/temperatura/`; somente
progresso agregado vai para `resultados/tabelas/`.

**Chuva:** localizada a versão `pr.npz` na pasta do autor e baixado o README,
que declara 1961–2025. Download de `pr.npz` iniciado, ainda parcial no encerramento
desta atualização. Implementados downloader reproduzível e preparação de chuva:
sem preencher, 0 ≤ pr < 450 mm/dia, todos os dias válidos por mês, sensibilidade
21/24/27 anos, anual somando 12 normais mensais. Quatro testes numéricos passaram.
Não foram declaradas normais reais nem modelos/mapas de chuva concluídos.

**Verificações:** 107 testes passaram em 12,47 s; um aviso de futura depreciação
do operador de Affine, sem falhas. Auditoria real adicional executada após a
retomada. Figuras de C7/C8 e da grade planejada geradas; conferida a legibilidade
e corrigida a posição da legenda de C7. C5, C6, C11, C14, reprodução integral MX,
modelos faltantes, chuva, incerteza calibrada e produção nacional permanecem
pendentes no documento de atendimento. Não houve commit, stage, push ou upload.

## 07/11/2026 — Continuação: observações de chuva e gradientes C2

Retomado o download interrompido de `pr.npz`, aproveitando o parcial de
278.396.928 bytes. Download concluído com 1.345.945.948 bytes e SHA256
`26c4f28f8e4f0f72b3069b0418eb4c05be951d60942a4bf61f1acede74b699fd`.
Fonte e manifesto privados preservados em `dados/brutos/`. Disco C: tinha
aproximadamente 165 GB livres antes do término do download/processamento;
o destino da coleção nacional completa continua sem resposta.

**Chuva executada:** calendário de 23.741 dias/14.170 estações confirmado,
selecionados 10.958 dias de 1991–2020. Dos 5.101.200 pares estação-mês,
1.617.793 passam pela exigência de todos os dias válidos. Foram encontrados
24 valores finitos fora de 0 ≤ pr < 450, 101.355.414 valores não finitos e
555 estações com coordenadas repetidas na fonte completa. Normais com 12 meses
elegíveis: 2.971 estações a 21 anos, 2.360 a 24 e 1.159 a 27. Nenhum preenchimento
foi acrescentado. Ano normal é soma dos meses, não média ponderada.

`auditar_normais_chuva.py` verificou hash, registros por estação, cobertura,
não negatividade, elegibilidade anual e soma dos meses. Erro máximo de
arredondamento: 7,50e-7 mm. Entre as elegíveis, zero flags de coordenadas repetidas
e 602 altitudes ausentes; estas precisam de DEM consistente na modelagem.
Figura `chuva_cobertura.png` gerada e inspecionada. Normais e séries por estação
continuam ignoradas; apenas agregados, figura e código são compartilháveis.

**C2 executada:** `gradientes_temperatura.py` compara CHELSA, gradiente fixo,
global ajustado, mensal e mensal/regional nas mesmas 102 estações, 5 dobras ×
3 repetições e blocos 1°/2°. Ajuste OLS pela origem exclusivamente no treino,
sem hiperparâmetro: resíduo CHELSA contra diferença de altitude fina/grosseira.
Grupos com menos de cinco estações ou denominador nulo usam fallback. Não há
clipping, intercepto ou interpretação do coeficiente como observação atmosférica.

RMSE em 2°: CHELSA 0,7944; fixo 0,8255; global 0,7883; mensal 0,7888;
mensal/regional 0,7751 °C. Diferença pareada regional versus CHELSA −0,0193 °C,
IC [−0,0616; +0,0273]: não conclusiva. Fixo piora +0,0311 °C, IC
[+0,0126; +0,0499]. Conferidas identidade das dobras e previsões CHELSA com
C7/C8 e ausência das 18 estações reservadas. Nenhum modelo de produção trocado.

**Documentação e verificações:** relatório de atendimento, README e tabela
C1–C15 atualizados; notebook com oito células executadas sem erro. Suíte completa:
111 testes passaram em 9,46 s, um aviso conhecido de futura depreciação de Affine.
`instrucoes.md` mantém SHA256
`99612d0ad6f73fbd1eb55d30c681573fb9406aeebae48d5c515c498d780499ed`.
Mantidos código/testes em `codigo/`, figuras/tabelas em `resultados/`; dados,
ambiente, temporários e requirements excluídos pelo `.gitignore` da raiz.

**Pendências reais:** comparação da chuva NPZ com o asset GEE, homogeneidade e
independência, covariáveis/modelagem/validação da chuva, C5/C6/C11/C14,
M3/M6, reprodução completa MX, incerteza calibrada, perfis/emendas e cobertura
nacional efetiva. O progresso de produção continua em um tile parcial, zero
completos de 743; não houve produção adicional de rasters nesta continuação.
Não houve commit, stage, push ou upload.

## 08/11/2026 — conferência das instruções, `mapa.md` e `mapa.html`

**Pedido:** conferir se tudo o que `instrucoes.md` pede foi feito, deixar a pasta no padrão das
demais etapas do repositório para o professor entender, renomear o `README.md` desta pasta para
`mapa.md` e criar uma página HTML que explique as decisões com figuras e exemplos.

- A pasta foi copiada de outro computador (Windows) para este (Linux). Os arquivos versionados do
  repositório tinham chegado com quebra de linha CRLF; voltaram para LF, sem mudança de conteúdo,
  e o repositório passou a usar `core.autocrlf=input`. Isso inclui `instrucoes.md`, que voltou à versão
  do git: o texto é idêntico, mas o SHA256 com LF é `beeb6a51c1f79671be2bbea2a639cd3be96d708732e621d3b8d4afd43e24192b`;
  com CRLF continua `99612d0a…`, o valor registrado nas sessões anteriores. Os arquivos não versionados
  desta pasta (código, documentos e tabelas) ficaram como vieram, para não mudar os hashes guardados nos manifestos.
- Conferência item por item das instruções (§1-§10 e C1-C15) contra as tabelas de
  `resultados/tabelas/`: 25 itens feitos, 12 parciais, 9 faltando, 1 adaptado (UTM no lugar de
  EPSG:4326) e o critério de sucesso não atingido. O quadro está na seção 7 do `mapa.md`.
- O random forest da chuva em blocos de 2° (`chuva_M4_2graus_30m_base.csv`, gravado em 07/11 às
  12:49) terminou depois da consolidação e não aparece em `chuva_metodos_2graus.csv` nem na figura
  correspondente: RMSE mensal de 20,762 mm (direta) e 21,222 mm (correção). Os documentos de 07/11
  ainda o descrevem como em execução; o `mapa.md` traz os números.
- Na chuva, o ERA5-Land é só referência (M0); as covariáveis do modelo são CHELSA, relevo, posição e
  harmônicos do mês (`FEATURES` em `codigo/mapa_chuva.py`). O `mapa.md` descreve assim.
- `README.md` renomeado para `mapa.md` e reescrito com o estado consolidado: situação, dados,
  validação, métodos, resultados, decisões D1-D15, pedido × feito, C1-C15, pendências e a tabela
  etapa × código × saída, no formato do `planejamento.md` das outras etapas.
- Criado `mapa.html`: página autônoma (CSS e JS embutidos, fontes do Google Fonts) que lê as figuras
  de `resultados/figuras/` por caminho relativo. Tem dois gráficos próprios (C1 da temperatura e
  métodos da chuva, já com o random forest), cada um com a tabela equivalente, diagramas e exemplos
  de cada decisão.
- Links atualizados para `mapa.md` em `docs/entrega_brasil.md`, `docs/metodologia_reproducao.md`,
  na entrada de 19/10 deste registro e no README principal, que ganhou `refinamento/` na árvore do
  repositório.
- `AGENTS.md` (instruções para o assistente de código) passou a ser ignorado pelo `.gitignore` da
  raiz, como já acontece com `.claude/`; o arquivo continua no disco.

**Verificações:** os 45 links e caminhos de `mapa.html` e os links relativos de `mapa.md`, do README
principal e dos documentos alterados existem; as tags do HTML estão balanceadas; a página foi
renderizada uma vez no Chrome sem interface e ajustada (parágrafos com link, diagrama de blocos,
legendas da galeria e selo "Parcial"). A suíte de testes não foi executada nesta máquina: o ambiente
`.venv` do outro computador não veio junto, e nenhum código foi alterado. `instrucoes.md` não foi
modificado. Nenhum commit, stage, push ou upload.

## 08/11/2026 (continuação) — pacote do piloto de Curitiba para o GEE

**Pedido:** preparar o piloto para subir na conta GEE do usuário e compartilhar com o professor:
juntar os mapas numa imagem só e deixar um visualizador pronto.

- Ambiente local criado em `.venv/` (ignorado) com `uv`, Python 3.12, `numpy==2.4.4` e
  `rasterio==1.5.2` (GDAL 3.12.2), as mesmas versões de `metodologia_reproducao.md`.
- Novo `codigo/pacote_gee_piloto.py`: confere o SHA256 dos 39 GeoTIFFs de `dados/piloto/` contra
  `manifesto_curitiba_M5_lightgbm_correction.json`, converte a temperatura de int16 × 0,01 para °C e
  grava `dados/gee/piloto_curitiba_30m_39bandas.tif` (float32, DEFLATE, blocos de 256, EPSG:32722,
  30 m, nodata −9999, nomes das bandas nas descrições), com manifesto JSON ao lado. Depois de gravar,
  relê o arquivo e confere as 39 bandas por igualdade exata com as fontes convertidas.
- Ordem das bandas: `temp_01`…`temp_12`, `temp_anual`, `disp_01`…`disp_anual`, `fora_01`…`fora_anual`.
  Temperatura de 13,81 °C (julho) a 22,49 °C (fevereiro); anual de 17,82 a 18,91 °C; dispersão de
  0,010 a 0,379 °C; flag em 0,41% dos pixels em todos os períodos.
- A primeira gravação usou o preditor de ponto flutuante do DEFLATE (10,5 MB). Ele foi retirado, por ser
  dispensável e para evitar qualquer risco na ingestão do GEE; o arquivo final tem 5,1 MB.
- Novo `gee/visualizar_piloto.js` (Code Editor): renomeia as bandas `b1`…`b39`, seletor de camada
  (temperatura, dispersão, flag) e de período, escala por período ou comum (13 a 23 °C), legenda, relevo
  sombreado do Copernicus GLO-30 como contexto, contorno do recorte e ciclo anual no ponto clicado.
  Sintaxe conferida com `node --check`; não foi executado no GEE.
- Novo `gee/descricao_piloto_curitiba.md`: texto para a descrição do asset no formato das descrições do C4,
  com a atribuição do Copernicus DEM exigida no manifesto do piloto.
- `mapa.md`, `mapa.html` e README principal atualizados com a pasta `gee/` e o pacote.

Nenhum upload, compartilhamento, commit, stage ou push foi feito: o upload pelo Code Editor e o
compartilhamento do asset ficam com o usuário.
- Depois, com o projeto GEE informado pelo usuário, o caminho do asset ficou fixo no script e na descrição:
  `projects/mystic-hull-480913-h5/assets/refinamento_30m/piloto_curitiba_30m` (pasta de assets
  `refinamento_30m`, separada do repositório de scripts `users/vitorkenor/refinamento_30m`).

## 08/11/2026 (continuação) — fechamento das pendências que dependem só dos dados locais

**Pedido:** terminar o que estava parcial e fazer o mapa do Paraná inteiro.

**Ambiente.** `.venv/` refeito neste computador (Linux, Python 3.12, mesmas versões de
`metodologia_reproducao.md`); a suíte original passou com 123 testes. Com os testes novos de
`codigo/testes/test_finalizacao.py`, passam 132.

**C3 da chuva.** Random forest em blocos de 1° (20,19 mm direta; 20,68 mm correção) e consolidação
das tabelas com o M4 nos dois blocos. GWR da chuva (`codigo/gwr_chuva.py`, coeficientes por local):
21,38 mm (2°) e 21,28 mm (1°), pior que o LightGBM (+0,49 [0,13; 0,88] e +0,65 [0,23; 1,07] mm).

**C7 da chuva levado ao mapa.** Um LightGBM por mês é o melhor nos dois blocos (−0,92 mm
[−1,25; −0,58] em 1°; −0,57 [−1,00; −0,16] em 2° contra os harmônicos) e passa a ser o modelo de
chuva do mapa do Paraná.

**C15 completo (`codigo/mx_completo.py`).** Temperatura: IDW de 5 vizinhos com gradiente recalibrado
em cada dobra por pares de estações a até 90 km (todas as estações de Tmax/Tmin fora dos blocos de
teste e reservados): −5,36 °C/km (faixa −5,46 a −5,21). MX 0,860 °C contra LightGBM 0,524 °C em 2°
(−0,337 [−0,453; −0,225]); em 1°, 0,797 contra 0,536 (−0,261 [−0,361; −0,154]). Chuva: IDW e ADW de
5 vizinhos, CDD de 346 a 378 km estimada no treino; ADW 27,72 mm contra LightGBM 20,89 mm em 2°
(−6,83 [−8,83; −4,96]); em 1°, 24,56 contra 20,63 (−3,93 [−6,09; −1,91]). Dobras conferidas como
idênticas às das predições gravadas.

**§7, incerteza e AOA (`codigo/incerteza_aplicabilidade.py`).** O intervalo ingênuo (previsão ± 1,645
× dispersão entre 5 modelos) cobre só 43% dos erros na temperatura, 19% na chuva com harmônicos e
28% na chuva por mês. Calibrado por conformidade (k de cada dobra estimado nas outras), cobre
89-90%: k = 6,07 (temperatura) e 10,62 (chuva por mês); meia-largura mediana de ~1,0 °C e ~29 mm.
Anual com largura constante: 0,76 °C e 253 mm. AOA de Meyer & Pebesma: fora dela ficam 6-8% das
linhas de teste na temperatura (RMSE 0,57-0,70 contra 0,50-0,53 °C dentro) e ~2% na chuva (31-33
contra ~20 mm).

**Homogeneidade (`codigo/homogeneidade.py`).** Pettitt e SNHT nas médias anuais de estação − ERA5-Land:
31 de 98 estações com quebra provável (degrau mediano 0,60 °C; quebras concentradas em 1998-2002 e
2011-2015). Erro do modelo igual nas estações com e sem quebra (0,519 e 0,526 °C): estações mantidas
e marcadas para revisão. Primeira versão tinha o índice do SNHT deslocado em um ano; corrigido e com teste.

**C11 em 2008-2024 (`codigo/definicoes_multianual.py`).** Viés de (Tmax + Tmin)/2 contra a média de
24 h: +0,78, +0,83, +0,84, +0,87 e +0,89 °C; compensada estável em −0,06 a −0,07 °C. Por estação, a
diferença varia pouco entre anos (desvio mediano 0,10 °C), mas vai de +0,12 a +1,59 °C entre
estações. Um desconto único não serve; a definição final continua sendo decisão do professor. Os
arquivos de 2008 usam outro formato de data e hora; a leitura nova aceita os dois.

**C12 com falhas diárias (`codigo/falhas_diarias.py`).** Temperatura: 20% dos dias faltando em bloco
contínuo erram a média do mês em 0,28-0,32 °C (RMSE), sorteados em 0,17 °C, sem viés. Chuva: 1 dia
faltando já tira 3,3% da soma do mês, 10% tiram 9,9% e 20% tiram 19,8%; reescalar tira o viés mas
deixa erro de 11 a 30 mm. Regras mantidas.

**C13 e C14.** C13 encerrada com justificativa: as normais exigem 24 de 30 anos dentro de 1991-2020,
então o mapa não depende de transferir a correção entre décadas. C14 vira limitação documentada: não
há estações fora do Xavier com normal 1991-2020; a comparação justa é o C15 e o teste reservado.

**Paraná (`codigo/mapa_parana.py`).** Grade única EPSG:32722 de 30 m (22.132 × 15.494 pixels, 942
janelas de 512, 199.271 km²), uma pilha de 26 bandas por janela (CHELSA de temperatura e chuva,
altitude e declividade), camadas de média, meia-largura de 90% calibrada e fora da AOA. Preparo e
previsão testados com covariáveis sintéticas (35-40 s por janela cheia por variável). A produção
depende da autorização do GEE neste computador. Também prontos: `codigo/teste_reservado.py`
(uso único, protegido) e `codigo/chelsa_bilinear.py` (correção dos degraus do C10, depende do GEE).

Figuras novas: `c15_mx_completo.png`, `incerteza_cobertura.png`, `c11_multianual.png`,
`chuva_metodos_completo_2graus.png`. `status_comparacoes.csv` atualizado (cópia anterior em
`.local/`). Nenhum commit, stage, push ou upload.

## 09/11/2026 — GEE autorizado: degraus do CHELSA, teste reservado e produção do Paraná

**Acesso.** API Python do Earth Engine autorizada pelo usuário com o projeto `mystic-hull-480913-h5`; leitura
dos assets do CHELSA (`projects/fcoliveira/...`) e do Copernicus DEM confirmada. Metadados remotos idênticos
aos do manifesto da extração do treino (`normais_covariaveis_20261106.manifesto.json`). O conector MCP do
Earth Agent foi compilado e registrado nas configurações de usuário do Claude Code (só leitura e execução no
Code Editor; não usado na produção).

**C10, CHELSA bilinear (`codigo/chelsa_bilinear.py`).** Extraído em 2.414 estações (zona UTM de cada uma,
pixel de 30 m), sem falhas. Diferença para o vizinho mais próximo: mediana 0,019 °C (máx. 0,164 °C) e 0,2% na
chuva. Validação em blocos de 2° nas mesmas dobras: temperatura +0,0001 °C [−0,013; +0,013]; chuva por mês
−0,017 mm [−0,075; +0,048]. Pela regra fixada antes (intervalo incluindo zero), **adotado**. Calibração refeita
com o bilinear: k90 = 6,13 (temperatura) e 10,59 (chuva por mês); anual 0,75 °C e 253 mm.

**Método congelado** (`mapa_parana preparar --chelsa-bilinear`): temperatura com LightGBM corrigindo o CHELSA
(15 folhas escolhidas na validação interna), chuva com um LightGBM por mês; 5 membros por modelo; AOA com
limiar por variável e por mês.

**Teste reservado, aberto uma vez (`codigo/teste_reservado.py`).** Temperatura, 18 estações: modelo 0,717 °C
(anual 0,648); CHELSA 0,966; MX 0,875; gradiente fixo 0,966. Modelo − CHELSA −0,249 [−0,407; −0,123];
modelo − MX −0,158 [−0,316; +0,002]. Chuva, 416 estações: modelo 17,05 mm (anual 133,5); CHELSA 19,63; CHIRPS
16,66; ERA5-Land 23,31; MX ADW 21,61. Modelo − CHELSA −2,59 [−4,18; −0,37]; − MX −4,56 [−8,76; −1,93];
− CHIRPS +0,39 [−0,92; +1,95]. Cobertura do intervalo de 90%: chuva 89,9% mensal e 94% anual; temperatura 75%
mensal e 72% anual (o erro nessas estações foi maior que na validação). Fora da AOA: 0% e 1%. O script grava
`resultados/tabelas/teste_reservado.json` e se recusa a rodar de novo.

**Produção do Paraná.** Uma janela de teste levou 73 s (download rápido; o tempo é de cálculo) e foi
descartada antes de congelar o método. Produção iniciada com 10 processos em ordem direta e 8 em ordem
inversa (`--reverse`, acrescentado ao produtor). Com 18 processos em 12 núcleos, uma janela cheia leva
150-240 s; estimativa de ~2h30 para as 942 janelas.

Também: `codigo/pacote_gee_parana.py` (um GeoTIFF int16 de 39 bandas por variável, abaixo do limite de 10 GB
do Code Editor, confirmado na documentação do GEE), `gee/visualizar_parana.js`, `codigo/figuras_parana.py`;
`mapa.md` reescrito e `mapa.html` atualizado com o teste reservado, as decisões D16-D18 e a nova conferência.

## 09/11/2026 (continuação) — Paraná produzido, montado e empacotado

**Produção.** As 942 janelas terminaram às 04:56, sem erro (uma única nova tentativa de download em todo o
estado). A sessão do Orca reiniciou no meio; os processos estavam desligados dela e seguiram. Montagem
(`mapa_parana montar --hash`): status `complete_experimental`, 221.411.999 pixels no Paraná, todos com valor.
Temperatura anual de 14,27 a 25,41 °C (1% e 99%: 16,7 e 24,6; mediana 20,97); os mais quentes no extremo noroeste
(vales do Paranapanema e do Paraná). Chuva anual de 1.191 a 2.899 mm (1% e 99%: 1.286 e 2.327; mediana 1.709),
máximos na Serra do Mar. Fora da AOA em algum mês: 10,2% (temperatura) e 4,1% (chuva). Camadas de 1,1 a 2,0 GB.

**Figuras** (`codigo/figuras_parana.py`): `parana_anual.png`, `parana_janeiro_julho.png`,
`parana_incerteza_aoa.png`. A primeira versão do script usava reamostragem "max" na leitura, que o rasterio não
aceita; trocada por média (o mapa da AOA mostra a fração de pixels fora). Sem degraus de 1 km do CHELSA. A camada
de incerteza mostra retângulos com bordas retas em latitude/longitude, vindos das divisões das árvores nas
coordenadas; registrado como limitação.

**Pacote para o GEE** (`codigo/pacote_gee_parana.py`). A primeira gravação tinha um erro: com o NumPy 2, o nodata
−32768 virava 0 nas bandas uint8 (AOA) ao trocar o nodata, e as bandas de AOA ficariam 0 fora do estado. Corrigido
com conversão para int32 antes da troca, conferência automática de 400 pixels contra as camadas de origem no fim do
script e um teste novo em `codigo/testes/test_finalizacao.py`. Os arquivos foram regravados.

**Earth Agent.** Depois do reinício, as ferramentas apareceram. O `visualizar_piloto.js` rodou no Code Editor sem
erro (painel, legenda de 17,8 a 19 °C, mapa centrado em Curitiba); o asset do piloto tem 39 bandas e bate
exatamente com o arquivo local em três pixels conferidos pela API. O asset ainda não tem leitores (falta o Share).

## 12/11/2026 — Brasil inteiro calculado dentro do GEE

**Pedido do professor:** mapa para o Brasil todo, sem processar estado a estado. **Estratégia:** levar o modelo
congelado para dentro do GEE, em vez de produzir localmente (~130 h e ~340 GB estimados a partir do Paraná).

- `codigo/modelo_gee.py`: converte os 78 LightGBM (temperatura: principal + 5 membros; chuva: 12 meses × 6) para
  o formato de `ee.Classifier.decisionTreeEnsemble` (folhas × número de árvores, porque o GEE tira a média) e grava
  as árvores em 13 tabelas em `projects/mystic-hull-480913-h5/assets/refinamento_30m/modelos/`. Gera
  `gee/brasil_30m.js` (biblioteca, a partir de `gee/brasil_30m_modelo.js`) com as constantes do preparo.
- Tentativas registradas: `Export.classifier.toAsset` gravou os classificadores, mas eles voltam vazios ao carregar
  ("Classifier has no training data"); foram apagados. A primeira exportação das tabelas falhou por feições sem
  geometria; refeita com um ponto fixo. O GEE não tem `log1p`; usado `add(1).log()`.
- **Conferência:** os 78 modelos dão o mesmo valor no GEE e em Python (diferença máxima 5,6e-13). A imagem do GEE
  contra o mapa do Paraná, em 200 pixels: temperatura com diferença mediana 0,005 °C (95% abaixo de 0,18-0,25 °C);
  chuva 0,3-0,4 mm (95% abaixo de 2-3,5 mm). O resto vem do relevo reamostrado na grade do GEE.
  `resultados/tabelas/brasil_gee_x_parana.json`. Valores plausíveis em Manaus, Brasília, Porto Alegre, Petrolina e
  Campos do Jordão.
- Fica de fora no GEE: a área de aplicabilidade (vizinho mais próximo no espaço das covariáveis). A incerteza
  calibrada vai junto (5 membros × k90).
- `gee/visualizar_brasil.js` usa a biblioteca via `require`. Não testado no Code Editor (Earth Agent desconectado);
  exportação de asset por região grande disponível em `exports.exportar`, não executada.
