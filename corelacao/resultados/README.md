# Resultados para avaliação

Os resultados foram consolidados: as tabelas mantêm todas as classes e comparações, sem duplicar
dezenas de arquivos por variável.

## Tabelas completas

| CSV em `tabelas/` | Conteúdo |
| --- | --- |
| [testes_globais.csv](tabelas/testes_globais.csv) | 20 testes; KW, ANOVA, Welch e tamanhos de associação |
| [descritivas.csv](tabelas/descritivas.csv) | n, média, desvio-padrão, mediana, quartis e unidade de cada grupo |
| [dunn_pares.csv](tabelas/dunn_pares.csv) | Todos os 252 pares únicos, com p ajustado por Holm |
| [ponto_bisserial.csv](tabelas/ponto_bisserial.csv) | Cada classe versus demais classes elegíveis; r, n e p ajustado |
| [spearman.csv](tabelas/spearman.csv) | SOC × textura, no mesmo local |
| [cobertura.csv](tabelas/cobertura.csv) | Tamanho da base, ausência de classe e n efetivo dos testes |
| [comparacao_mesmos_pontos.csv](tabelas/comparacao_mesmos_pontos.csv) | Köppen-Holdridge L1/L2 com conjuntos idênticos em cada par |
| [regressao_modelos.csv](tabelas/regressao_modelos.csv) | Modelos M1-M5, n, R², R² ajustado e AIC |
| [regressao_coeficientes.csv](tabelas/regressao_coeficientes.csv) | Coeficientes e intervalos HC3 de M4, em log(SOC) |
| [validacao_modelos.csv](tabelas/validacao_modelos.csv) | Desempenho OOF, OLS/RF e baseline do treino |
| [validacao_folds.csv](tabelas/validacao_folds.csv) | Métricas e tamanhos amostrais de cada dobra |
| [logistica_validacao.csv](tabelas/logistica_validacao.csv) | Acurácia, acurácia balanceada e baseline da classe majoritária |
| [importancia_climatica.csv](tabelas/importancia_climatica.csv) | Queda de R² por bloco (Köppen L2, Holdridge L2, relevo, textura) no mesmo random forest, por variável |
| [importancia_climatica_folds.csv](tabelas/importancia_climatica_folds.csv) | O mesmo, detalhado por dobra espacial |

`p_holm_omnibus` corrige os 20 testes de Kruskal-Wallis em uma única família.
`p_anova` e `p_welch` são nominais e complementares. Dunn e ponto-bisserial têm ajuste por resposta/nível.
Um p numérico igual a zero pode indicar subfluxo; não é probabilidade literalmente nula.

## Figuras e rastreabilidade

`figuras/` contém 13 figuras principais e cinco painéis complementares, todos usados no notebook. Os painéis
agrupam os 20 boxplots pedidos (quatro respostas × cinco níveis) em cinco arquivos, com rótulos ampliáveis.
`fontes/proveniencia.json` registra os assets do Earth Engine usados; `amostras.json`, critérios de
inclusão/exclusão; `legenda_holdridge.csv`, os rótulos usados; `ambiente.json`, versões dos pacotes;
`verificacao.json`, controles numéricos e integridade da entrega.

A legenda de Holdridge (HLZ_L1/L2) vem do asset `holdridge_lifezones_chelsa-v2026`, documentada na própria
descrição do asset (ver [docs/assets.md](../docs/assets.md)).
