# Memória de execução — Fabrício

Registro do que já foi feito neste ambiente (Windows, `C:\Python\MapBiomas_analises\corelacao`),
para continuar em outro dia sem repetir passos. Não é parte da entrega ao professor.

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
