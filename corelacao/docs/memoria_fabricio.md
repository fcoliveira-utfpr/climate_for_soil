# Memória de execução — Fabrício

Registro do que já foi feito neste ambiente (Windows, `C:\Python\MapBiomas_analises\corelacao`),
para continuar em outro dia sem repetir passos. Não é parte da entrega ao professor.

> **Estado atual: ver a última seção ("Reestruturação: comparação de climas CHELSA", 2026-09-23).**
> As seções anteriores são históricas: descrevem a análise antiga (testes, regressões, importância
> climática), cujos scripts, notebook e resultados foram apagados nessa data.

## Ambiente

- Python 3.13.14, pip 26.
- Repositório clonado de https://github.com/VitorEduardoLimaKenor/solo-clima-mapbiomas
  para `C:\Python\MapBiomas_analises\corelacao` em 2026-09-17.
- Dependências do `requirements.txt` instaladas (faltavam `statsmodels`, `scikit-posthocs`,
  `pypdf`, e `earthengine-api` foi atualizado de 1.7.31 para 1.7.43).
- Earth Engine autenticado com `earthengine authenticate` (token salvo localmente).
- Projeto GEE: `fcoliveira`. Definido como padrão em
  [codigo/gee_utils.py](../codigo/gee_utils.py) na constante `PROJETO_PADRAO`, para não precisar
  passar `--projeto` toda vez. `conectar(projeto=None)` usa esse valor quando nada é informado.

## Pipeline já executado (2026-09-17, ~16h)

Nesta ordem, seguindo [docs/reproducao.md](reproducao.md):

1. `python codigo/baixar_soildata.py` — baixou OXSR2N v6.0 e IUZOAK v3.0 para `.local/dados/soildata/`.
2. `python codigo/preparar_dados.py` — 10.219 pontos de textura válidos, 11.266 perfis de carbono válidos,
   11.981 pontos para extração climática.
3. `python codigo/extrair_clima.py` — clima extraído para os 11.981 pontos (usa o projeto GEE padrão).
4. `python codigo/rota_b_raster.py --baixar --pontos 250 --escala 1000 --ano 2023` — 2.000 pixels amostrados.
5. `python codigo/reproduzir.py` — recalculou tudo: preparação, testes estatísticos, regressões/validação
   (OLS e Random Forest, dobras aleatórias e espaciais de 1º/2º/5º), análise da Rota B, as 18 figuras,
   e consolidou a entrega (`exportar_resultados.py`): 45 testes, 1.342 pares Dunn, 12 CSVs e 18 figuras.

Resultado: `resultados/tabelas/` e `resultados/figuras/` foram todos regravados com timestamp de hoje.

### Pendência conhecida, não é erro

A última etapa do `reproduzir.py` chama `verificar_resultados.py --entrega`, que compara as figuras
recalculadas com as que já estão **embutidas no PDF entregue** (`relatorio_solo_clima.pdf`, execução de
11/09/2026). Essa checagem falhou em `rel_amostragem.png`:

```
AssertionError: Figura do PDF desatualizada: rel_amostragem.png
```

Motivo: a Rota B (`rota_b_raster.py`) sorteia pixels aleatoriamente sem semente fixa, então cada execução
gera uma amostra ligeiramente diferente, mudando essa figura de esquema de amostragem. O PDF é um
documento editorial congelado (não é sobrescrito pelo pipeline); os outros 16 testes automatizados
(`unittest`) passaram sem problema. Isso não indica falha de configuração do ambiente.

**Se for continuar depois:** decidir se vale fixar uma semente na Rota B para bater com o PDF, ou se
o PDF deve ser considerado desatualizado em relação à nova execução (e nesse caso o relatório/notebook
precisariam ser revisados, conforme o aviso no próprio `docs/reproducao.md`).

## Mudança de escopo — remoção da Rota B (2026-09-18)

Decisão: manter só a Rota A (perfis de campo, valor real medido em laboratório). A Rota B (raster,
2.000 pixels) foi removida do código e dos resultados:

- `codigo/rota_b_raster.py` apagado.
- `reproduzir.py` não chama mais esse script nem exige `raster_amostra.parquet` em cache.
- `exportar_resultados.py` não consolida mais `B_raster` em nenhuma tabela publicada.
- `verificar_resultados.py` não faz mais a checagem numérica cruzada de raster; os totais esperados
  caíram de 45 para 25 testes e de 1.342 para 830 pares Dunn.
- Apagados: `.local/dados/raster_amostra.parquet`, todo `.local/resultados/raster_*`,
  `resultados/figuras/rel_raster_soc.png`.
- `resultados/tabelas/*.csv` e `resultados/figuras/` já foram regravados só com `rota = A_perfis`
  (`python codigo/exportar_resultados.py` rodou limpo: 25 testes, 830 pares, 17 figuras).
- Detalhe completo e assets climáticos candidatos (Holdridge CHELSA v2026, Köppen 30 m) em
  [docs/assets.md](assets.md).

**Pendência nova, maior que a anterior:** `relatorio_solo_clima.pdf` e `solo_clima_consolidado.ipynb`
não foram tocados — ainda descrevem a Parte II com Rota B (30 páginas, 21 figuras). Por isso
`python codigo/verificar_resultados.py --entrega` **falha agora**, na comparação de figuras com o PDF
(esperado — não é bug). Falta decidir e reescrever a narrativa/figuras desses dois documentos antes de
rodar `--entrega` de novo com sucesso. Por essa mesma razão, `resultados/fontes/verificacao.json`
ficou com conteúdo desatualizado (a função para antes de regravá-lo).

## Troca do asset de Holdridge (2026-09-18)

`codigo/extrair_clima.py` passou a extrair HLZ_L1/HLZ_L2 de
`projects/mapbiomas-brazil/assets/SOIL/COVARIATES/holdridge_lifezones_chelsa-v2026` (banda única
`zone38_id`, legenda documentada na própria descrição do asset — CHELSA V2.1). Antes vinha de bandas
dummy em `MB_2025_CLIMATE_HOLDRIDGE`, sem legenda confirmada. Köppen não mudou (continua em
`IPEF_2013_KOPPEN_100M_2025`); um candidato a `IPEF_koppen_30m` foi avaliado e descartado por não ter
legenda documentada em lugar nenhum.

Efeito real nos dados (não é só troca de rótulo): `HLZ_L1` caiu de 7 classes presentes na amostra para
só 2 (`Tropical_Zone`: 8.532 pontos; `Subtropical_Zone`: 3.432) — as classes fisicamente implausíveis
no Brasil (Polar, Boreal etc.) simplesmente não aparecem mais. `HLZ_L2` caiu de 15 para 8 classes.
Köppen, Spearman SOC×textura e as regressões M1-M5 (que usam `koppen_l2`, não Holdridge) ficaram
idênticos. `codigo/reproduzir.py` rodou de novo até `verificar_resultados.py`, que passou nos 16 testes
unitários e na verificação numérica cruzada — só falhou no `--entrega` pela pendência do PDF acima.

O vetor antigo (`holdridge_38BR_1km`) continua sendo extraído, renomeado para `zone38_id_vetor`, só
como coluna de auditoria/comparação — não alimenta mais HLZ_L1/L2.

Nada disso foi commitado ainda. Detalhe completo em [docs/assets.md](assets.md).

## Notebook atualizado, PDF removido da entrega (2026-09-18)

Decisão do usuário: `relatorio_solo_clima.pdf` vai ser excluído da entrega (ele mesmo apaga); o notebook
passa a ser o documento principal. `solo_clima_consolidado.ipynb` foi reescrito e reexecutado (220
células, 0 erros) para refletir só a Rota A e o Holdridge atual:

- Removida a seção "Rota B: amostra do produto raster" (texto e a figura que ela mostrava).
- Tabelas de η²H de Holdridge (Etapa 1 e 2) atualizadas com os números novos (seção anterior).
- Textos que chamavam a legenda de Holdridge de "provisória" ou "pendente" foram corrigidos.
- Comparação Parte I × Parte II atualizada (testes globais, η² SOC×Holdridge L1) com uma nota
  explicando por que esse número caiu (legenda corrigida depois da Parte II original, não mudança de base).
- Seções renumeradas depois da remoção (## 26 Conclusões → ## 25, e daí em diante).
- Contagens corrigidas em todo o caderno: 25 testes, 315 pares Dunn, 17 figuras.

`docs/assets.md` foi reescrito para mostrar só o que está em uso hoje (sem log de decisões — esse log
é este arquivo). `README.md` também foi limpo de linguagem de "mudança"/data, deixando só o estado atual.

Pendências que ainda restam: `verificar_resultados.py --entrega` continua comparando com
`relatorio_solo_clima.pdf`, que vai deixar de existir — essa checagem específica vai passar a falhar
por arquivo ausente (não é bug; o script não foi adaptado para funcionar sem PDF, porque isso não foi
pedido ainda). `resultados/fontes/verificacao.json` segue desatualizado pelo mesmo motivo.

## Notebook resistente ao diretório de trabalho (2026-09-18)

O usuário rodou o notebook e tomou `FileNotFoundError` em `resultados/fontes/amostras.json` — o VS Code
tinha iniciado o kernel com o workspace raiz na pasta pai (`C:\Python\MapBiomas_analises`), não em
`corelacao`. A primeira célula do notebook agora se autocorrige (detecta e troca para o diretório certo
antes de ler qualquer resultado). Testado executando com cwd na pasta pai e na pasta do repositório.

Depois disso o usuário tentou de novo e caiu num erro diferente: kernel "colab" selecionado por engano
(traceback com caminhos `/tmp/ipykernel_.../usr/lib/python3.13` — máquina do Google, sem acesso aos
arquivos locais). Não era bug do notebook; orientei a trocar o kernel para
`C:\Users\fabri\AppData\Local\Programs\Python\Python313\python.exe` no VS Code.

## Parte I recalculada com acesso liberado (2026-09-18)

Ao discutir por que a Parte I aparecia como "não reprodutível", o usuário informou que tinha acesso à
parte restrita do Earth Engine. Testei direto (`ee.data.getAsset`) e confirmei: as duas matrizes que a
Parte I efetivamente usou (`matriz-collection3_carbon_datac2v2`, `c03_psd_v2025_11_18`) estão acessíveis
a esta conta agora — só `c03_soc_v2025_trainingFinal` (nunca usada, mesmo antes) continua bloqueada.

Construí um pipeline novo, paralelo ao da Parte II, reaproveitando o mesmo código de teste estatístico:

- `codigo/clima_legendas.py` — legenda de Holdridge extraída de `extrair_clima.py` para módulo comum.
- `codigo/preparar_dados_parte1.py` — baixa as duas matrizes por paginação (`ee.data.listFeatures`,
  padrão dos scripts originais em `git show fd6e14e:baixar_matriz*.py`), aplica os mesmos critérios de
  auditoria da Parte II (exclui pseudoamostras, confere fechamento das frações, deduplica por ponto por
  mediana), e extrai HLZ_L1/L2 do mesmo asset confirmado que a Parte II usa (não mais das dummies
  embutidas na matriz nem do dicionário parcial `LEGENDA_HLZ` de 22/38 códigos da execução original).
- `codigo/analise_parte1.py`, `codigo/regressoes_parte1.py` — chamam as mesmas funções de
  `analise_solo_clima.py`/`regressoes_corrigidas.py` da Parte II, sem duplicar lógica estatística.
- `codigo/exportar_parte1.py` — consolida em `resultados/analise_anterior/`, mesmo formato enxuto da
  Parte II, substituindo o retrato congelado.

Resultado: 12.286 pontos de SOC, 12.353 de textura, **10.007 pareados — bate exatamente com o número já
publicado em 10/09**, apesar de ter sido baixado e filtrado de novo, de forma independente. HLZ_L1 caiu
para 2 classes (mesmo padrão da Parte II); o "carbono 2,5× maior em zonas frias" da execução original
não se sustenta (não há zona fria na amostra; a diferença real é ≈1,4×). Random forest replicou quase
exatamente os números da Parte II na validação espacial (0,413→0,238 vs. 0,410→0,237 em blocos de 5°).

`solo_clima_consolidado.ipynb` foi reescrito de novo: as 68 células da Parte I (seções 1-10) viraram 52,
com números, tabelas e figuras novas (as figuras vêm de `resultados/analise_anterior/figuras/`, geradas
por este pipeline, não mais uma seleção curada de 8). A comparação Parte I × Parte II (seções 26-27) foi
reescrita com os números novos dos dois lados. `README.md`, `resultados/README.md`,
`resultados/analise_anterior/README.md` e `docs/reproducao.md` (nova seção 4) atualizados: Parte I deixa
de ser descrita como "não reprodutível" — passa a exigir só a mesma conta com acesso liberado.

Reexecutei o notebook inteiro depois de cada rodada de edição (204 células no final, 0 erros).

## SOC: só a versão qmap, Parte II (2026-09-18)

Discussão sobre a diferença entre `soc_stock_g_m2` (original) e `soc_qmap_g_m2` (correção por
quantile mapping) levou a checar os dados brutos: a correção só altera 1.449 dos 11.266 locais
(13%), concentrada em apenas 8 dos ~200 datasets de origem que compõem o SoilData — assinatura
clássica de harmonização de viés entre fontes, não um ajuste genérico. Decisão: usar só a versão
qmap daqui pra frente (mais coerente para uma análise que cruza dados de ~200 estudos independentes
contra uma variável espacial — viés de fonte não corrigido pode se confundir com efeito de clima).

Mudança em `codigo/`: `preparar_dados.py` (`preparar_carbono`) carrega só
`soc_stock_gm2_cum_qmap`, renomeada para `soc_g_m2` (nome único, sem sufixo `_qmap`/`_stock`, já
que não há mais duas variantes para distinguir). `analise_solo_clima.py` (`SOC`), `regressoes_corrigidas.py`
e `verificar_resultados.py` ajustados para uma variável só (removida a constante `SOC_QMAP` e os
loops que rodavam tudo em dobro). `graficos_relatorio.py`: as figuras que comparavam original vs.
qmap lado a lado (`rel_modelos_r2.png`, `rel_soc_koppen.png`, painéis, heatmap de η²) viraram
gráficos de série única; adicionada a função `barra_unica()`. Isso reduziu a Parte II de 25 para
20 testes globais (SOC deixou de contar em dobro) e de 315 para 252 pares de Dunn — Parte I e
Parte II agora têm o mesmo número de testes (20), pura coincidência da estrutura (4 ou 5 variáveis
× 5 níveis, sem duplicar SOC em nenhuma das duas).

Parte I não muda: nunca teve qmap (a matriz `matriz-collection3_carbon_datac2v2` só tem o estoque
bruto), então `codigo/preparar_dados_parte1.py` e afins continuam como estavam.

`solo_clima_consolidado.ipynb` teve 27 células atualizadas (Parte II, comparação Parte I×II, fontes,
painéis) tirando a dualidade original/qmap e corrigindo as contagens. Reexecutado limpo (204
células, 0 erros) — esse mesmo reexecute também resolveu, de brinde, uma célula (a 1, a que corrige
o diretório de trabalho) que estava com `execution_count` `None` por uma execução anterior
incompleta; não tinha relação com o qmap, só apareceu junto.

## Como retomar

- Ambiente já está pronto (pacotes instalados, GEE autenticado, projeto configurado). Não precisa repetir
  os passos 1-3 originais a menos que queira dados atualizados (a Rota B, passo 4 antigo, não existe mais).
- Para só re-rodar o cálculo da Parte II com os dados já baixados: `python codigo/reproduzir.py` (vai
  falhar no último passo, `verificar_resultados.py --entrega`, porque essa checagem ainda depende do
  PDF removido — ver acima).
- Para recalcular a Parte I: `python codigo/preparar_dados_parte1.py && python codigo/analise_parte1.py
  && python codigo/regressoes_parte1.py && python codigo/exportar_parte1.py` (precisa da conta com
  acesso liberado às duas matrizes; ver `docs/assets.md`).
- Para reexecutar só o notebook: abrir `solo_clima_consolidado.ipynb` no Jupyter/VS Code e rodar tudo,
  ou `jupyter nbconvert --to notebook --execute --inplace solo_clima_consolidado.ipynb`.
- `.local/` (dados brutos e resultados intermediários) não é versionada — só existe nesta máquina.

## Só a Parte I: reestruturação completa (2026-09-18)

Depois de discutir se a Parte II ainda fazia sentido (ela existia sobretudo para o professor conseguir
reproduzir sem acesso restrito — argumento que ainda vale), o usuário decidiu que não precisa dela e
pediu pra manter só a Parte I como a análise inteira, sem comparação nem numeração "Parte I/II".

Reestruturação de verdade, não só cosmética:

- **`codigo/preparar_dados.py` reescrito do zero** — era o script da Parte II (SoilData); virou o que
  antes era `preparar_dados_parte1.py` (as duas matrizes GEE), com nomes de arquivo sem sufixo
  (`textura.parquet`, `soc.parquet`, `joint.parquet`, coluna `soc_g_m2`) e uma `carregar_bases()` nova.
  Ganhou um filtro que não existia antes: depois de agregar por local (mediana por fração, quando há
  mais de um registro em 0-30cm), 291 locais não fechavam mais ~100% — a mediana coluna a coluna pode
  não bater mesmo que cada registro original fechasse. Esses locais passaram a ser excluídos
  (`pontos_agregados_sem_fechar`), como a Parte II já fazia. Números finais mudaram um pouco por causa
  disso: textura 12.062 (não mais 12.353), pareados 9.792 (não mais 10.007).
- **Apagados** (SoilData/Parte II e os scripts "_parte1" que agora são os únicos): `baixar_soildata.py`,
  `extrair_clima.py`, `preparar_dados_parte1.py`, `analise_parte1.py`, `regressoes_parte1.py`,
  `exportar_parte1.py`. `analise_solo_clima.py` e `regressoes_corrigidas.py` não precisaram mudar nada
  — já eram genéricos o bastante (só liam de `carregar_bases()`), reaproveitados como estão.
- **`graficos_relatorio.py`**: textos que citavam SoilData/OXSR2N/IUZOAK trocados pelos nomes reais das
  duas matrizes GEE; a figura didática de integração por horizonte (exemplo "90%/30% ponderado por
  espessura") não fazia sentido pra Parte I, que não integra por espessura — virou um exemplo sobre
  filtrar por profundidade e agregar por mediana. `rel_efeitos_25_testes.png` renomeado
  `rel_efeitos_testes.png` (não hardcodar contagem no nome do arquivo).
- **`verificar_resultados.py` finalmente livre do PDF** — a checagem de páginas/figuras embutidas no
  `relatorio_solo_clima.pdf` foi removida (não só contornada); no lugar, checa que os arquivos que o
  notebook referencia (`resultados/figuras/...`) existem de fato. Resultado: `--entrega` **passa limpo**
  agora, pela primeira vez desde a remoção do PDF — antes sempre falhava numa checagem contra ele.
- **`resultados/analise_anterior/` apagada**; seu conteúdo (já recalculado antes) virou o `resultados/`
  principal — não existe mais distinção entre as duas pastas.
- **`solo_clima_consolidado.ipynb` reconstruído do zero** (não editado célula a célula) — 105 células,
  sem "Parte I"/"Parte II" em nenhum título, sem seções de comparação. Reexecutado limpo, e também
  validado rodando de dentro da cópia isolada que `verificar_resultados.py --entrega` usa (30 células,
  sem `.local/` nem GEE).
- `README.md`, `resultados/README.md`, `docs/reproducao.md`, `docs/assets.md` reescritos por completo.

Resultado: `python codigo/verificar_resultados.py` e `python codigo/verificar_resultados.py --entrega`
passam os dois limpos agora — nenhuma pendência conhecida em aberto (a do PDF, que durou o dia inteiro
de hoje, acabou junto com o PDF).

### Como retomar (atualizado)

- `python codigo/preparar_dados.py` baixa as duas matrizes e extrai Holdridge (precisa de GEE + acesso
  liberado). `python codigo/reproduzir.py` recalcula tudo a partir do cache local, sem GEE.
- Depois de qualquer recálculo, reexecutar o notebook manualmente (ele não é sobrescrito pelo pipeline).
- `python codigo/verificar_resultados.py --entrega` confere a entrega publicada sozinha, sem `.local/`.

## Importância climática: Köppen vs. Holdridge no mesmo modelo (2026-09-18)

O usuário trouxe um texto de terceiro sugerindo comparar Köppen e Holdridge por importância de
variável (RF/XGBoost + SHAP + Boruta/RFE), com covariáveis contínuas de clima e espectrais, pra decidir
"qual sistema entra no pipeline de mapeamento". Avaliei: isso é conselho pra quem constrói um modelo
preditivo espacial nacional (o texto até fala em "seu pipeline de mapeamento"), não pro desenho deste
trabalho, que é um estudo exploratório de associação categórica. Sugeri uma versão enxuta, sem dado
novo nem biblioteca nova: `permutation_importance` (block, não coluna a coluna) no random forest que
`regressoes_corrigidas.py` já roda, nos mesmos blocos espaciais de 2° que já existem. O usuário topou.

`codigo/importancia_climatica.py`: pra cada variável-resposta (areia, silte, argila, SOC), monta um RF
com Köppen L2 (dummy) + Holdridge L2 (dummy) + relevo (elevação, latitude) — e, só para SOC, textura
(areia, argila) — junto no mesmo modelo (M4-equivalente). Em cada uma das 5 dobras espaciais de 2°, mede
a queda de R² ao embaralhar, em bloco, todas as dummies de um sistema por vez (não uma dummy por vez —
isso criaria combinações inválidas, tipo duas classes "ativas"). `N_REPEATS=20` por bloco/dobra.

Resultado, sem vencedor único (como a "Camada 3" do texto original previa): Holdridge contribui mais
pra areia (0,077 vs. 0,013) e SOC (0,023 vs. 0,010); Köppen contribui mais pra silte (0,085 vs. 0,041) e
argila (0,039 vs. 0,013). Achado extra, não pedido mas relevante: relevo (só elevação + latitude) supera
os dois sistemas climáticos **combinados** nas quatro respostas — geografia contínua carrega mais
informação que classificação climática categórica, uma vez que os dois já competem no mesmo modelo.
Desvio-padrão entre dobras é grande (poucos blocos espaciais, cobertura desigual) — documentei isso como
ressalva explícita, não escondi atrás da média.

Integrado ao pipeline como os demais scripts: `reproduzir.py` roda `importancia_climatica.py` antes de
`exportar_resultados.py`; os dois CSVs e a figura (`rel_importancia_climatica.png`) entram na
consolidação normal (14 CSVs, 18 figuras agora, era 12/17). Adicionei ao notebook como seção 10 nova
(as duas seções seguintes, Síntese e Fontes, viraram 11 e 12), com a figura, a tabela ao vivo, e o
texto interpretativo com a ressalva do desvio-padrão. Reexecutei tudo e `verificar_resultados.py` (com
e sem `--entrega`) passam limpos.


## Reestruturação: comparação de climas CHELSA (2026-09-23, Mac)

**Decisão do usuário:** refazer tudo com os assets climáticos novos (já no GEE) em torno de uma pergunta
só: *qual classificação climática serve melhor de base para estimar SOC e textura?* Só o Köppen IPEF fica
como referência (nada do Holdridge do MapBiomas). As outras análises e o documento do orientador saem; o
registro fica só neste arquivo.

**Apagado** (recuperável pelo git, commit anterior a esta reestruturação): `solo_clima_consolidado.ipynb`;
`codigo/` analise_solo_clima, clima_legendas, exportar_resultados, graficos_relatorio,
importancia_climatica, regressoes_corrigidas, reproduzir, test_metodologia, verificar_resultados;
`docs/` orientacoes_solo_clima (documento do orientador), assets, reproducao; `resultados/` inteira.

**Assets comparados** (projeto `fcoliveira`, CHELSA V2.1 1991-2020, ~928 m):
`Koppen_CHELSA_BR_1991_2020`, `Holdridge_CHELSA_BR_1991_2020` (versão corrigida, limiar 24 °C: só zonas
21-37), `Thornthwaite_CHELSA_BR_1991_2020_CAD100` e `_CADsolo` (bandas sem nome, b1-b4 = umidade,
subtipo, térmica, concentração). Referência: Köppen IPEF das dummies das matrizes.

**Pipeline novo:** `codigo/preparar_dados.py` (mesma limpeza auditada de antes: 12.286 locais SOC,
12.062 textura; + amostragem dos 4 assets na grade nativa) -> `.local/dados/*.parquet`;
`codigo/comparar_climas.py` -> `resultados/tabelas/` (amostra, desempenho, diferencas_pareadas,
classes); `codigo/test_comparar_climas.py` (6 testes com dados sintéticos); `comparacao_climas.ipynb`
lê só as tabelas (roda sem GEE).

**Métrica escolhida e por quê:** R² fora da amostra com cada sistema/nível como único preditor (média da
classe no treino), validação em blocos espaciais (2° principal; aleatória, 1° e 5° como sensibilidade),
5 dobras x 50 repetições, mesmas dobras para todos -> diferenças pareadas com IC 95%. ω² como
complemento descritivo. Motivos: classe climática é nominal (Pearson/Spearman não se aplicam); sistemas
têm número de classes diferente (3 a 32) e η² premia classes demais; com ~12 mil locais todo p-valor é
< 0,001 e não discrimina.

**Detalhes de implementação decididos no caminho:**
- Köppen IPEF L3 só existe para B e C; nos locais do grupo A foi completado com o L2 (Af/Am/As/Aw já são
  a classe completa). Sem isso a amostra comum perderia ~60% dos locais.
- SOC > 0 exigido (log). Locais sem classe em algum sistema (~1%, litoral/corpos d'água) saem da amostra
  comum; 12.151 SOC e 11.934 textura.
- Nomes das zonas de Holdridge: a numeração 1-38 é a mesma da legenda do MapBiomas, mas pela tabela do
  script JS os nomes de lá ficam deslocados em uma posição (zona 36 = ETP/P 0,5-1, "moist" no Holdridge
  clássico, não "dry"). Rotulei pela faixa térmica + faixa de ETP/P. **Pendente:** conferir a tabela de
  zonas do script JS original contra o Holdridge clássico.

**Resultados (R² espacial, blocos de 2°):**
- SOC: todos baixos (≤ 0,07). Empate entre Thornthwaite L1, Holdridge L1/L2 e Köppen IPEF L3; a 5° o
  Holdridge L2 fica melhor (0,095) e o Thornthwaite L1 cai (0,047) -> **recomendado Holdridge L2**.
- Argila: nenhum sistema estima (R² ≤ 0 em blocos).
- Areia: fraco (≤ 0,07); Thornthwaite L2 lidera a 1°/2° mas zera a 5°.
- Silte: **Thornthwaite L2** vence todos em todas as escalas (0,20 vs 0,15 do melhor Köppen).
- CAD 100 mm ≈ CAD do solo em tudo. Köppen CHELSA sempre abaixo do Köppen IPEF.
- Conclusão no notebook: não há sistema único; Holdridge L2 para SOC, Thornthwaite L2 para textura; se
  for um só, Thornthwaite L2.

**Ambiente no Mac:** rodado com o venv `climas/chelsa_climas_brasil/.venv` (kernel `chelsa-venv`), que
já tem earthengine-api, pandas, pyarrow, matplotlib, pytest.

## Por que o Köppen CHELSA fica abaixo do IPEF; correção do Köppen CHELSA (2026-09-23)

**Investigação (amostra de SOC, 12.151 locais):** os dois Köppen concordam em só 56% dos pontos.
Discordâncias: Am (IPEF) -> Aw (CHELSA), 3.152 pontos, quase todos num aglomerado em Rondônia
(~62°W, 11,6°S); C (IPEF) -> A (CHELSA), 765 pontos no Sudeste (~46°W, 20°S). Classificações híbridas
(R² blocos 2°): trocar só o **grupo** onde há A <-> C/B pela resposta do IPEF recupera toda a diferença
(SOC 0,040 -> 0,066; areia 0,031 -> 0,061); trocar o subtipo Am/Aw quase não ajuda. Nos pontos C -> A
o mês mais frio do CHELSA fica entre 18,2 e 20 °C (metade entre 18 e 19): estão na fronteira A/C e o
CHELSA (1991-2020) é um pouco mais quente. O SOC desses pontos (45 Mg/ha) é de clima C (49), não A
(36). Interpretação: o solo integra o clima de séculos; uma fronteira recente deslocada por pouco pesa
contra. Não dá para separar aquecimento recente x método do IPEF (regressão com altitude a 100 m) sem
as temperaturas do IPEF. Colateral: ~1/4 da amostra de SOC está num único aglomerado em Rondônia
(limitação a registrar no notebook).

**Revisão do método do Köppen CHELSA** (`climas/chelsa_climas_brasil/koppen_gee.py`) contra Kottek et
al. (2006) / Peel et al. (2007): grupos, limiar do B, Af/Am/As/Aw, h/k e a/b/c corretos -- a fronteira
A/C (Tcold >= 18 °C) está certa, então a queda em relação ao IPEF vem dos dados. Dois erros corrigidos:
1. Sazonalidade C/D: `f` era "mês mais seco >= 40 mm" e s/w exigiam mês seco < 40 mm; pixels C com
   mês seco < 40 mm sem seca sazonal forte ficavam **sem classe** (50.040 pixels, ~5% da área C; causa
   de 56 dos 59 pontos de SOC sem Köppen CHELSA). Agora Kottek: s e w mutuamente exclusivos, f = nem
   s nem w.
2. Verão/inverno não eram trocados ao norte do equador (As/Aw, limiar do B, s/w em RR e AP; ~7,6% dos
   pixels A, ~240 pontos).

TIF regenerado (`koppen_chelsa.ipynb`): sem buracos (cobre todo pixel que o Holdridge cobre); Cfa
5,79% -> 6,13%, Cfb 1,92% -> 2,02%, As 2,04% -> 1,80%.

**Feito (2026-09-24):** asset corrigido já está no GEE (atualizado 2026-09-24 02:34 UTC; conferido: 56 dos
59 pontos de SOC antes sem Köppen CHELSA agora têm classe, 37 Cfa e 19 Cfb; os 3 restantes são litoral).
~~Pendente: o usuário subir o TIF novo substituindo~~ `projects/fcoliveira/assets/Koppen_CHELSA_BR_1991_2020`
(com `--pyramiding_policy=mode`, que também acaba com as classes intermediárias falsas nas escalas
reduzidas). Depois: rodar de novo `codigo/preparar_dados.py` e `codigo/comparar_climas.py`, reexecutar
`comparacao_climas.ipynb`, revisar o texto (a conclusão sobre o Köppen CHELSA provavelmente se mantém,
porque os 765 pontos C -> A não são afetados pelas correções) e acrescentar a seção "por que o Köppen
CHELSA fica abaixo" + a limitação do aglomerado de Rondônia.

## Análise refeita com o Köppen corrigido (2026-09-24)

- `preparar_dados.py` passou a extrair também a temperatura do mês mais frio do CHELSA
  (`chelsa_brasil_tas_normal_1991_2020`, mínimo das 12 bandas), usada no diagnóstico da fronteira A/C.
- Amostra comum maior com o Köppen sem buracos: 12.207 locais SOC e 11.978 textura (antes 12.151 /
  11.934). Resultados praticamente iguais; conclusões mantidas (Holdridge L2 para SOC, Thornthwaite L2
  para textura, argila sem sistema, CAD indiferente, Köppen CHELSA < IPEF).
- `comparar_climas.py` gera também `koppen_concordancia.csv`, `koppen_hibridos.csv` e
  `koppen_fronteira.csv` (diagnóstico agregado) e, em `amostra.csv`, a concentração espacial.
- Notebook: nova seção 6 "Por que o Köppen CHELSA fica abaixo do Köppen IPEF" (concordância 55,7%;
  híbridos: trocar só o grupo A x C/B recupera SOC 0,039 -> 0,065 e areia 0,032 -> 0,062; 765 locais C -> A
  com mês mais frio 18,2-20 °C e SOC de clima C, 45 vs 50/36 Mg/ha). Seções seguintes renumeradas (7-10).
- **Correção do registro anterior:** a amostra não tem "1/4 num único aglomerado em Rondônia". São duas
  regiões: ~26% na região de Rondônia e ~19% no Rio Grande do Sul; 20 dos ~200 blocos de 2° têm 56-60%
  dos locais. Limitação atualizada no notebook com essa tabela.

## Holdridge: nomes das zonas x tabela do script (2026-09-24, em aberto)

O usuário segue os nomes de Jungkunst et al. (2021), J. Plant Nutr. Soil Sci., doi 10.1002/jpln.202100008
(38 zonas, base Leemans). Não consegui ler o texto completo (acesso bloqueado); pedi a tabela das 38 zonas
ao usuário.

Achados até agora:
- Numerações de Leemans publicadas diferem entre si: NOAA/NGDC (Leemans 1992) vai de 0 a 39 (1 gelo ...
  37 Tropical Moist, 38 Tropical Wet, 39 Tropical Rain); a legenda do MapBiomas é essa sem a 39; a tabela
  `projects/fcoliveira/assets/gesivaldo/Holdridge_Leemans` usa outra (36 = Tropical Wet Forest).
- Pelo diagrama de Holdridge, cada tipo de vegetação = mesma faixa de ETP/P em qualquer faixa térmica
  (moist 0,5-1; wet 0,25-0,5; rain 0,125-0,25; dry 1-2; very dry 2-4). Na `TABELA_ZONAS` do script
  (holdridge_gee.py): temperado quente e subtropical corretos; **tropical deslocado em uma zona** (usa o
  padrão de 7 zonas das outras faixas, mas a faixa tropical tem 8: inclui "very dry"). A zona 36 do
  asset (ETP/P 0,5-1, ~43% do Brasil) é Tropical Moist Forest = 37 na numeração NOAA/Leemans; a 38 do
  asset (<0,25) seria Tropical Rain (39). Temperado frio e boreal também deslocados (quase ausentes no BR).
- Não afeta a comparação de climas (as fronteiras de ETP/P são as mesmas; a análise rotula pela faixa
  ETP/P), mas afeta mapas e textos com os nomes.

**Resolvido em parte (2026-09-24):** o usuário pôs o PDF do artigo em `climas/chelsa_climas_brasil/` (CC-BY).
A Tab. 1 usa a numeração NOAA/Leemans (1 gelo ... 37 Tropical moist forest, 38 Tropical wet forest; sem
tropical rain) e a Fig. 1 mostra onde cada faixa térmica começa na ETP/P (tropical 32, subtropical/temp.
quente 16, temp. frio 8, boreal 4, subpolar 2). Confirmado: a `TABELA_ZONAS` estava certa só no temperado
quente e no subtropical. Corrigida em `holdridge_gee.py` (tropical, temperado frio, boreal, subpolar) +
`LEGENDA` com os nomes do artigo; `holdridge_chelsa.ipynb` reexecutado, TIF regenerado. No Brasil a
mudança é só de número/nome (partição igual): a antiga 36 (43%, Amazônia) agora é 37 Tropical moist
forest; a 17 (1 pixel) virou 16. `corelacao/codigo/legendas.py` passou a usar os nomes do artigo.

**Pendente:** (1) o usuário subir o TIF novo do Holdridge substituindo
`projects/fcoliveira/assets/Holdridge_CHELSA_BR_1991_2020` (`--pyramiding_policy=mode`); (2) depois,
rodar de novo `preparar_dados.py` + `comparar_climas.py` + notebook da corelacao (métricas devem ficar
iguais; mudam só os rótulos) e commitar.

**Decisão em aberto: ETP do Holdridge.** O script usa na razão ETP/P a ETP de Penman-Monteith do CHELSA;
Holdridge, Leemans e o artigo usam ETP = 58,93 x biotemperatura. Teste local (1/16 dos pixels): 23% dos
pixels mudam de zona; com a ETP de Holdridge o Brasil fica mais úmido (Subtropical moist forest 8,5% ->
20,1%, Subtropical dry forest 23,9% -> 14,4%, Tropical moist forest 42,8% -> 48,0%). ETP mediana: Penman
1569 mm x Holdridge 1444 mm. Primeiro o usuário escolheu manter Penman-Monteith; em seguida decidiu **testar as duas na corelacao**.
`holdridge_gee.classificar_holdridge(..., etp="penman"|"holdridge")`; o notebook do Holdridge gera dois TIFs:
`Holdridge_CHELSA_BR_1991_2020_ETPM.tif` e `..._ETH.tif` (o TIF único antigo foi apagado). Áreas no Brasil
(ETPM x ETH): Tropical moist 43,0 x 48,1%; Subtropical dry 24,2 x 14,3%; Subtropical moist 8,3 x 20,3%.

**Pendente:** o usuário subir `projects/fcoliveira/assets/Holdridge_CHELSA_BR_1991_2020_ETPM` e `..._ETH`
(`--pyramiding_policy=mode`). A corelacao já está preparada (`legendas.py`: `holdridge_l1` comum,
`holdridge_etpm_l2` e `holdridge_eth_l2`; notebook com os dois sistemas e cor violeta para ETH, paleta
validada). Depois: `preparar_dados.py` + `comparar_climas.py` + notebook, revisar texto/conclusões
(Holdridge ETPM x ETH), commitar. O asset antigo `Holdridge_CHELSA_BR_1991_2020` (numeração errada) pode
ser apagado do GEE depois.

## Holdridge ETPM x ETH na corelacao (2026-09-24)

Assets `Holdridge_CHELSA_BR_1991_2020_ETPM` e `_ETH` subidos pelo usuário e conferidos (ETPM: 42,8% na zona
37; ETH: 20,2% na 29). Extração e comparação refeitas; `holdridge_l1` (faixa térmica, igual nas duas),
`holdridge_etpm_l2`, `holdridge_eth_l2`.

log(SOC), R² espacial (1° / 2° / 5°): ETH L2 0,082 / 0,076 / 0,093; ETPM L2 0,080 / 0,068 / 0,094. ETH é
agora o melhor sistema para SOC nos blocos de 2° (vence o ETPM em 94% das repetições, IC toca o zero;
empata com Thornthwaite L1 e Köppen IPEF L3). Silte: ETPM 0,075 x ETH 0,056 (os dois bem atrás do
Thornthwaite L2, 0,20). Recomendação no notebook: SOC -> Holdridge L2 com ETP de Holdridge (definição
original, comparável a Jungkunst et al. 2021); textura -> Thornthwaite L2. Figura 1 com eixo x menos
denso (rótulos se sobrepunham). Paleta: ETH em violeta (#4a3aa7), validada.

O asset antigo `Holdridge_CHELSA_BR_1991_2020` (numeração errada) pode ser apagado do GEE. O PDF do artigo
(`climas/chelsa_climas_brasil/`) continua fora do git (o usuário ainda não decidiu).

## Experimento: o que pôr no lugar do Köppen nos modelos do MapBiomas (2026-09-24, em andamento)

**Contexto (repositório mapbiomas/brazil-soil, collection_03beta):** o Köppen IPEF não estratifica; entra
como dummies L1-L3 num único random forest nacional (`ranger` no SOC; GBM por profundidade na textura), ao
lado de ~100 covariáveis (solo, geologia, relevo, bioma, fitofisionomia, uso, NDVI, água, fogo). É a
**única informação climática** dos modelos (precipitação só como comentário "a fazer"; Holdridge do
MapBiomas comentado com a nota "treinar e avaliar um modelo com koppen e outro com holdridge").

**Objetivo do usuário:** substituir o Köppen para melhorar as estimativas; pediu também um cenário com
zonas homogêneas.

**Desenho** (`codigo/experimento_dados.py`, `zonas_clima.py`, `experimento_modelos.py`):
- Base comum: todas as covariáveis das matrizes, menos identificadores, alvos, razões log (`log_*`),
  produtos de textura (`*_000_030cm`, `textura_l1_030cm`), profundidade e dummies de Köppen/HLZ antigas
  (103 covariáveis no SOC, 107 na textura). Uma linha por local (mediana), como na comparação de climas.
- RF (sklearn, 200 árvores, max_features 0,33) para os 4 alvos (log SOC, areia, silte, argila %).
- Cenários: A Köppen IPEF; B sem clima; C Holdridge ETH (L1+L2); D Thornthwaite CAD100 (L1+L2); E clima
  contínuo (12 variáveis: T média/mês frio/mês quente, biotemperatura, P anual/mês seco/sazonalidade, ETP,
  ETP/P, DEF, EXC, Im); F1 zonas k-means como dummies; F2 um RF por zona k-means; F3 zonas
  supervisionadas (árvore de regressão no clima, multivariada na textura, ajustada dentro da dobra, 10
  folhas) como dummies; F4 um RF por zona supervisionada (zona com < 300 locais de treino -> RF global).
- Validação: blocos de 2°, 5 dobras x 3 repetições, mesmas dobras para todos -> diferenças pareadas vs A.
- Zonas k-means (`zonas_clima.py`): ajustadas nos **pixels do Brasil** (300 mil, ponderados pela área),
  não nos locais — descrevem o clima do país, viram mapa e não são moldadas pela amostra concentrada. 9
  variáveis padronizadas (chuva/DEF/EXC em log). k = 10 (principal) e 15. Mapas em
  `climas/dados_chelsa/zonas/zonas_climaticas_k{10,15}.tif`; centróides em `resultados/tabelas/`.
  Zonas k10 coerentes (3-5 Amazônia úmida; 2 e 7 semiárido; 9-10 Sul); zona do ponto = zona do mapa em 100%.
- Teste rápido (20 árvores, 1 rep): B ≈ A; E lidera em SOC e silte.

**Resultados (rodada completa, 200 árvores, 3 repetições; ΔR² vs Köppen, mín-máx entre repetições):**
- E clima contínuo: SOC +0,026 (+0,018/+0,033), silte +0,029 (+0,019/+0,038), areia +0,009 (+0,008/+0,010),
  argila +0,004 (empate). R² SOC 0,17 -> 0,20.
- F1 zonas k-means como covariável: SOC +0,019, silte +0,027, areia +0,007 (todas as reps > 0), argila +0,005.
- D Thornthwaite L2: SOC +0,016; textura ~0. C Holdridge ETH: ~0 (o que era melhor para SOC isolado não
  acrescenta no modelo completo). B sem clima: SOC +0,007, areia −0,009 (o Köppen contribui pouco hoje).
- F3 zonas supervisionadas: intermediário. F2/F4 estratificado: pior em SOC, areia e argila (−0,02 a
  −0,04 em areia/argila); silte empata.
- **Recomendação:** trocar as dummies do Köppen pelas 12 variáveis contínuas (E); se quiserem categórica,
  zonas k10 como dummies (F1); não estratificar. Próximo passo sugerido: repetir dentro do pipeline deles.
- Notebook `experimento_clima_modelos.ipynb`; figura `resultados/figuras/zonas_k10.png`; mapa
  `climas/dados_chelsa/zonas/zonas_climaticas_k10.tif` (fora do git; pode virar asset no GEE).

## Reprodução dos modelos do MapBiomas com os climas (2026-09-24, em andamento)

Pasta criada pelo usuário: `climas/reproducao/` (código, notebook, resultados agregados); dados gerados em
`climas/dados_reproducao/` (fora do git). Pedido: dois experimentos (textura, depois SOC), com **todos** os
nossos climas, e notebook com gráficos e mapas.

**Como o MapBiomas trata a profundidade (lido no repositório):** textura = GBM (400 árvores, shrinkage 0,01,
samplingRate 0,632, maxNodes 25) por alvo (ln((areia+1)/(argila+1)), ln((silte+1)/(argila+1)), esqueleto)
e por camada de 10 cm (centros 5..95, horizontes a ±5 cm; `profundidade` = ponto médio do horizonte e
também covariável), mapas 0-10 ... 90-100 cm, textura da coleção 2 como covariável. SOC = RF, matriz de
produção `c03_soc_v2025_11_26_trep` com profundidades empilhadas, predição com profundidade = 30 (estoque
0-30 cm) e textura 0-30 da C3 como covariável. **Esta conta não lê as matrizes de SOC da C3** (lista a pasta,
mas leitura negada); lê `c03_psd_v2025_11_18` (a de produção da textura) e a `carbon_datac2v2`.

**Decisões:** textura fiel (GBM por camada nas razões log, 0-30 cm = camadas 5/15/25, com C2 e
profundidade); SOC com a `carbon_datac2v2` e a textura da cadeia (modelo de textura com as 88
covariáveis comuns às duas matrizes, previsto nos locais de SOC dentro da dobra). Mapas numa grade de
0,05° (~5 km) alinhada ao CHELSA (usuário concordou; 1 km no GEE fica para os mapas finais dos melhores
cenários). Covariáveis do MapBiomas portadas para Python (`covariaveis_gee.py`): as 110 da textura batem
com a matriz; as 24 extras do SOC (idades de uso, índices com decaimento, bordas, água, fogo, áreas
estáveis, subprovíncias) conferidas contra 300 linhas da matriz no ano de cada linha: 100% iguais
(`antropico` = idade de `agropecuaria`; fogo pela coleção 4.1 pública). SOC mapeado para 2023.

**Resultados da reprodução (2026-09-25):**
- Versão fiel (com textura C2 como covariável, como o MapBiomas): textura R² 0,82-0,85 e nenhum clima muda
  (|ΔR²| ≤ 0,003; só o clima contínuo +0,002-0,003 em todas as reps). A C2 foi ajustada com as mesmas
  amostras e "entrega" a resposta mesmo na validação espacial -> rodada também a **variante sem C2**
  (`REPRODUCAO_SEM_C2=1`, saídas `_semC2`).
- SOC fiel: Köppen 0,275; clima contínuo 0,289 (+0,014, todas as reps); Holdridge ETPM, Thornthwaite
  (as duas CADs), zonas k10 e Holdridge ETH +0,002 a +0,005 (todas as reps); Köppen CHELSA empata.
- Sem C2: textura R² 0,29-0,33 (Köppen); clima contínuo +0,023 (silte +0,038, areia +0,018, argila +0,013;
  as três frações em todas as reps); zonas k10 +0,007 (areia e silte em todas as reps). SOC 0,171 ->
  clima contínuo 0,194 (+0,023), zonas k10 +0,016, Thornthwaite solo +0,008.
- Mapas (grade 0,05°, 36 GeoTIFFs em `climas/dados_reproducao/mapas/`): SOC mediano ~40 t/ha. O clima
  contínuo é o que mais muda o mapa (|Δ| SOC ~4,8 t/ha sem C2): mais SOC no arco RO-MT-sul do PA, menos no
  litoral norte. Pixels sem covariável do MapBiomas vinham como -inf no download: tratados como sem dado e
  mascarados.
- Notebook `climas/reproducao/reproducao_resultados.ipynb` (gerado por `codigo/notebook_resultados.py`);
  figuras em `climas/reproducao/resultados/figuras/`. Execução: `codigo/rodar.sh` (lição: não usar
  `pgrep -f` com o nome do script para encadear etapas, porque o próprio comando de espera casa com o padrão).
- Recomendação: trocar o Köppen pelo clima contínuo; zonas k10 se precisar de categórica; discutir com o
  MapBiomas a textura C2 como covariável (esconde a contribuição das outras e infla a validação).

## Zonas k10 na comparação de climas (2026-09-25)

As zonas climáticas k10 entraram como mais um sistema no `comparacao_climas` (`legendas.NIVEIS['zona_k10']`,
`COLUNAS_COMPARACAO`; `COLUNAS_CLIMA` continua sem elas porque dependem do clima contínuo, extraído depois).
Resultado (R² em blocos de 2°): zonas k10 melhores nas 4 variáveis — SOC 0,092 (Holdridge ETH 0,076), areia
0,106 (Thornthwaite L2 0,071), silte 0,210 (Thornthwaite L2 0,199), argila 0,009 (única positiva) —, vencendo
todos os sistemas em 100% das repetições em SOC, areia e silte. A 5°: melhores no silte (0,19); no SOC atrás
do Holdridge L2 (0,083 x 0,094); na areia atrás do Köppen IPEF L1. Conclusão do notebook reescrita:
zonas k10 = melhor classificação isolada; notebook enquadrado como "classificação sozinha" com ponteiros para
o experimento e a reprodução. `experimento_clima_modelos.ipynb` ganhou a seção 9 com a atualização da
reprodução.

## Métricas do MapBiomas na reprodução (2026-09-25)

`climas/reproducao/codigo/metricas_mapbiomas.py` calcula o `error_statistics` do MapBiomas (ME, MAE, RMSE,
MEC, slope; MEC = mesma fórmula do nosso R²) nas predições fora da amostra (1ª repetição), textura em % e
SOC em t/ha (com e sem smearing de Duan). Achado: SOC em t/ha tem MEC ~0,10 (fiel) contra R² 0,275 em log;
viés de ~−10 t/ha pela retransformação do log (smearing elimina, MEC 0,14-0,16) e cauda longa (máx ~1.190
t/ha). **Correção:** antes eu tinha dito que nosso SOC (0,275, log) estava "na mesma faixa" do MEC do
MapBiomas por bioma (0,25-0,27, t/ha) — escalas diferentes, comparação errada; corrigido no relatório
(seção 7.6) e no notebook da reprodução (seção 5). Ranking dos climas igual em t/ha.
