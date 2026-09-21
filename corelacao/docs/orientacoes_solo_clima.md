# Orientações — Correlação Textura e Carbono do Solo x Clima (Köppen e Holdridge)

# 1\. Objetivo da análise

Análise em **duas etapas**, ambas cruzando variáveis do solo com a classificação climática, considerando dois sistemas, cada um com nível de **classe** e **subclasse**:

| Sistema | Nível "classe" | Nível "subclasse" |
| :---- | :---- | :---- |
| Köppen | koppen\_l1 (A, B, C) | koppen\_l2 (Af, Am, As, Aw, Bs, Cf, Cs, Cw) e koppen\_l3 (Bsh, Cfa, Cfb, Csa, Csb, Cwa, Cwb, Cwc) |
| Holdridge (HLZ) | HLZ\_L1 (zona de vida) | HLZ\_L2 (subzona) |

* **Etapa 1**: frações granulométricas do solo (areia, silte, argila) × classe/subclasse climática.

* **Etapa 2**: carbono orgânico do solo (SOC/COS) × classe/subclasse climática — mesma metodologia estatística da Etapa 1, aplicada às variáveis carbono\_gm2 / carbono\_gm2\_qmap (ou ao produto final SOC\_t\_ha, na rota raster).

**Fonte dos dados:** [mapbiomas/brazil-soil](https://github.com/mapbiomas/brazil-soil), pasta soil\_30m\_landsat/collection\_03beta (já importada localmente em collection\_03beta/).

# 2\. Dados identificados no repositório (assets do Google Earth Engine)

Todos os caminhos abaixo são asset IDs do GEE, não URLs de navegador — eles são acessados via ee.Image(...) / ee.FeatureCollection(...) depois de autenticado. Vários pertencem a projetos privados do MapBiomas (ver seção 3 — Acesso).

## 2.2 Rota — produtos finais em raster (cobertura contínua do Brasil)

Use esta rota se quiser estatística espacializada (não só nos pontos de amostra), ex.: área/proporção de cada classe textural dentro de cada zona climática em todo o país.

### Textura (produto final, 30 m):

| Asset | Conteúdo | Script |
| :---- | :---- | :---- |
| projects/mapbiomas-workspace/SOLOS/PRODUTOS\_C03/psd\_final/areia | % areia (0–30cm) | texture/6\_density |
| projects/mapbiomas-workspace/SOLOS/PRODUTOS\_C03/psd\_final/silte | % silte | idem |
| projects/mapbiomas-workspace/SOLOS/PRODUTOS\_C03/psd\_final/argila | % argila | idem |
| projects/mapbiomas-workspace/SOLOS/PRODUTOS\_C03/mapbiomas\_soil\_collection3\_textural\_class | Classe textural (L1) | texture/5\_classify\_texture |
| projects/mapbiomas-workspace/SOLOS/PRODUTOS\_C03/mapbiomas\_soil\_collection3\_textural\_subgroup | Subgrupo textural (L2) | idem |
| projects/mapbiomas-workspace/SOLOS/PRODUTOS\_C03/mapbiomas\_soil\_collection3\_textural\_group | Agrupamento textural (L3) | idem |

Legendas/paletas dessas classes estão prontas em legends (TEXTURA\_LEGEND.L1/L2/L3).

### Carbono orgânico do solo — SOC (produto final, 30 m, para a Etapa 2):

| Asset | Conteúdo | Script |
| :---- | :---- | :---- |
| projects/mapbiomas-workspace/SOLOS/PRODUTOS\_C03/soc/SOC\_t\_ha | Estoque de carbono orgânico do solo (t/ha) | carbon/2\_model\_prediction (linhas \~17–18, 664–672) |

Paleta/faixa de valores em legends (CARBON.carbon, min 0 / max 90).

### Köppen (produto de covariável, 100 m — bandas dummy 0/1 por classe):

| Asset | Nível | Script |
| :---- | :---- | :---- |
| projects/mapbiomas-workspace/SOLOS/COVARIAVEIS/IPEF\_2013\_KOPPEN\_100M\_2025/koppen\_l1 | Classe (A/B/C) | covariate\_export/IPEF\_2013\_KOPPEN\_100M |
| .../IPEF\_2013\_KOPPEN\_100M\_2025/koppen\_l2 | Subclasse (Af, Am, As, Aw, Bs, Cf, Cs, Cw) | idem |
| .../IPEF\_2013\_KOPPEN\_100M\_2025/koppen\_l3 | Subclasse detalhada (Bsh, Cfa, Cfb, Csa, Csb, Cwa, Cwb, Cwc) | idem |
| projects/mapbiomas-solos-workspace/assets/covariates/climate/IPEF\_koppen\_30m | Mapa base (1 banda, valores 1–12) — mais fácil para zonal stats, já que as bandas acima são one-hot | idem |

### Holdridge (HLZ) — asset confirmado:

| Asset | Conteúdo | Observação |
| :---- | :---- | :---- |
| projects/fcoliveira/assets/holdridge\_38BR\_1km | Zona/subzona de vida de Holdridge para o Brasil, 1 km, valores de classe em banda única (não dummy) | Precisa confirmar a legenda (valor numérico → zona/subzona de vida) antes de rotular HLZ\_L1/L2. Ao contrário do Köppen (já one-hot), aqui a codificação dummy precisa ser feita — ver seção 5\. |

*Este asset substitui a referência anterior a MB\_2025\_CLIMATE\_HOLDRIDGE/HLZ\_L1 e HLZ\_L2 (chamada comentada no script carbon/0\_covariate\_source, sem exportação equivalente à do Köppen). Se, por algum motivo, o novo asset também não estiver disponível, os nomes de colunas HLZ\_L1\_\*/HLZ\_L2\_\* já presentes na matriz de amostras (seção 2.1) continuam válidos como alternativa.*

# 3\. Acesso aos dados

* **Conta Google Earth Engine:** crie em [https://signup.earthengine.google.com/](https://signup.earthengine.google.com/) caso ainda não tenha.

* **Code Editor** (para inspeção visual rápida): [https://code.earthengine.google.com/](https://code.earthengine.google.com/)

* **Repositório fonte:** [github.com/mapbiomas/brazil-soil](https://github.com/mapbiomas/brazil-soil/tree/main/soil_30m_landsat/collection_03beta)

# 4\. API (Python) ou direto no GEE Code Editor?

| Critério | Code Editor (JavaScript) | API Python (earthengine-api \+ geemap) |
| :---- | :---- | :---- |
| Extração/zonal stats sobre raster | Ótimo, é o ambiente nativo dos scripts do repositório | Também funciona (mesmas chamadas ee.\*), um pouco mais verboso |
| Análise estatística (ANOVA, correlação, testes de hipótese) | Não disponível — precisa exportar e abrir em outra ferramenta | Nativo, com pandas/scipy/statsmodels |
| Gráficos (boxplot, dispersão, matriz de correlação) | Limitado | Nativo, com seaborn/matplotlib |
| Reprodutibilidade / versionamento do notebook | Fraco | Bom (.ipynb versionável, como o restante do repositório) |
| Reaproveitar os scripts existentes do repositório | Direto (são .js) | Precisa reescrever as chamadas em Python (mapeamento quase 1:1) |

**Recomendação:** use a API Python via Jupyter Notebook, como o próprio pedido do projeto (.ipynb com earthengine-api). Motivo: a pergunta é estatística (correlação classe/subclasse x variável contínua), não apenas cartográfica — o Code Editor não tem ferramentas de teste estatístico ou de visualização de correlação. Use o GEE apenas para extrair/consultar os dados (via ee/geemap); faça toda a análise estatística em pandas/scipy/statsmodels.

Se precisar apenas inspecionar visualmente as camadas (conferir cobertura, paleta, alinhamento de classes) antes de programar, use o Code Editor pontualmente — os scripts já prontos no repositório (ex.: covariate\_export/IPEF\_2013\_KOPPEN\_100M) servem para isso.

# 5\. Codificação dummy do Holdridge (etapa nova)

O Köppen já chega pronto em bandas dummy (one-hot) nos assets da seção 2\. O novo asset de Holdridge (holdridge\_38BR\_1km) não: é uma única banda com o código numérico da zona/subzona. Por isso entra uma etapa extra, comum às duas rotas, antes das estatísticas da seção 6\.

## 5.1 Rota A — matriz de amostras (pontos)

* Extrair o valor bruto da classe de Holdridge em cada ponto da amostra via reduceRegion/sampleRegions.

* Mapear o valor numérico para o rótulo da zona/subzona (via legenda a confirmar) → coluna categórica HLZ\_L1/HLZ\_L2.

* pd.get\_dummies(df\['HLZ\_L1'\], prefix='HLZ\_L1') (e o mesmo para L2) — gera as colunas 0/1 equivalentes às que o Köppen já traz prontas.

## 5.2 Rota B — raster (Brasil inteiro)

* Para cada classe *k* presente na legenda: holdridge\_img.eq(k).rename(f'HLZ\_dummy\_{k}') — gera uma banda binária por classe.

* Empilhar essas bandas dummy junto com Köppen e as imagens de textura/SOC antes do reduceRegions por zona (seção 6.2/6.4).

*Pré-requisito para as duas rotas: confirmar a legenda de classes do asset (valor inteiro → nome da zona/subzona de vida de Holdridge) antes de gerar os dummies — sem isso, as colunas HLZ\_L1\_\*/HLZ\_L2\_\* ficam sem rótulo interpretável.*

# 6\. Métodos de análise sugeridos

Ponto de atenção estatístico: koppen\_l1/l2/l3 e HLZ\_L1/L2 são variáveis categóricas nominais (aqui representadas como colunas dummy 0/1), enquanto areia/silte/argila e o carbono orgânico do solo (SOC) são variáveis contínuas. Correlação de Pearson "pura" não se aplica a categórica × contínua — os métodos abaixo são os adequados para esse desenho, e a mesma metodologia é aplicada nas duas etapas, trocando apenas a variável-resposta.

## Etapa 1 — Textura (areia/silte/argila) × Clima

### 6.2 Rota B — a partir dos rasters (cobertura espacial completa do Brasil)

Use se quiser ir além dos pontos de amostra e caracterizar a relação em toda a área mapeada:

* Empilhar as imagens de textura final (seção 2.2) com o mapa-base do Köppen (1 banda, classes 1–12) e os dummies de Holdridge gerados na seção 5.2.

* Fazer amostragem estratificada por classe climática com reduceRegions/reduceRegion com reducer=ee.Reducer.mean().combine(ee.Reducer.stdDev(), sharedInputs=True) agrupado por classe (ee.Reducer...group()), para obter médias zonais de areia/silte/argila por classe e subclasse climática em todo o Brasil.

* Exportar o resultado (tabela) para pandas e aplicar os mesmos testes estatísticos da Rota A (Kruskal-Wallis, post-hoc, eta², boxplots, Pearson).

*A Rota B é mais cara computacionalmente (raster de 30 m para o Brasil inteiro) — comece pela Rota A para validar a hipótese e a metodologia, e só parta para B se precisar de representatividade espacial completa (não só nos pontos amostrados em campo).*

## Etapa 2 — Carbono Orgânico do Solo (SOC) × Clima

Repita exatamente os passos 6.1–6.2 acima, trocando a variável-resposta de areia/silte/argila para o carbono orgânico do solo. Os dados e a lógica de análise são os mesmos; só muda a coluna/asset de origem.

### 6.3 Rota A — matriz de amostras (recomendada para começar)

* Usar a mesma FeatureCollection da seção 2.1 (c03\_soc\_v2025\_trainingFinal — já é a matriz do modelo de carbono, então já tem carbono\_gm2 e carbono\_gm2\_qmap nativamente, sem precisar de outra consulta ao GEE).

* Repetir a reconstituição das colunas categóricas (Köppen L1/L2/L3, HLZ L1/L2 via dummy — seção 5\) já feita na Etapa 1 — o mesmo df serve para as duas etapas.

* Estatística descritiva de carbono\_gm2 (e carbono\_gm2\_qmap, a versão com correção quantil-mapping) por classe/subclasse climática.

* Mesmos testes da Etapa 1: Kruskal-Wallis (scipy.stats.kruskal) \+ ANOVA complementar, post-hoc Dunn (Bonferroni/Holm) ou Tukey HSD, e eta²/epsilon² como tamanho de efeito.

* Correlação ponto-bisserial entre cada dummy climática e carbono\_gm2.

* Boxplot/violinplot de carbono\_gm2 por classe e subclasse climática, Köppen vs Holdridge.

* Extra recomendado (já que ambas são contínuas): correlação de Spearman (scipy.stats.spearmanr — mais robusta que Pearson para dados de solo, que raramente são normais) entre carbono\_gm2 e cada uma das frações de textura (areia\_000\_030cm, silte\_000\_030cm, argila\_000\_030cm), já que solos mais argilosos costumam reter mais carbono — é um cruzamento natural entre as Etapas 1 e 2 e ajuda a interpretar se o efeito do clima sobre o SOC é direto ou mediado pela textura.

### 6.4 Rota B — produto raster final (SOC\_t\_ha)

* Empilhar projects/mapbiomas-workspace/SOLOS/PRODUTOS\_C03/soc/SOC\_t\_ha com o mapa-base do Köppen e os dummies de Holdridge (seção 5.2) — mesma lógica da seção 6.2.

* stratifiedSample() ou reduceRegions agrupado por classe climática para obter estoque médio de carbono por classe/subclasse em todo o Brasil.

* Exportar para pandas e aplicar os mesmos testes estatísticos (Kruskal-Wallis, post-hoc, eta², Spearman com textura, boxplots).

# 7\. Extensão sugerida — regressões

Como o clima é categórico, a "regressão" já está embutida no Kruskal-Wallis/ANOVA (que é regressão linear com dummies). As opções abaixo vão além disso:

* **Regressão múltipla com dummies climáticas \+ covariáveis:** SOC \~ dummies\_clima \+ latitude \+ elevação — estima o efeito de cada classe controlando por outras variáveis.

* **Regressão múltipla combinando textura e clima como preditores de SOC:** SOC \~ areia \+ silte \+ argila \+ dummies\_clima — responde se o efeito do clima é direto ou mediado pela textura, comparando R² com e sem as dummies.

* **Regressão logística multinomial (direção invertida):** prever classe/subclasse climática a partir de textura \+ SOC — útil se o interesse for o quanto essas variáveis discriminam as zonas climáticas.

* **Modelo misto (mixed-effects):** se os pontos amostrais tiverem agrupamento espacial (mesma bacia/região), um efeito aleatório evita pseudo-replicação.

* **GWR (regressão geograficamente ponderada):** só faz sentido na Rota B (raster), quando o interesse é ver se a relação solo×clima varia espacialmente pelo Brasil.

*Dado que os dados de solo raramente são normais (o mesmo motivo pelo qual o documento já prefere Spearman a Pearson), um random forest regressor pode servir como checagem de que a regressão linear não está mascarando não-linearidades — não é essencial, mas é uma validação de baixo custo.*

# 8\. Checklist de execução

☐  Confirmar acesso aos projetos GEE mapbiomas-workspace e mapbiomas-solos-workspace

☐  Confirmar acesso ao asset projects/fcoliveira/assets/holdridge\_38BR\_1km e à sua legenda de classes

☐  ee.Authenticate() / ee.Initialize() no ambiente Python

☐  Baixar a matriz de amostras (c03\_soc\_v2025\_trainingFinal) com geemap.ee\_to\_df — serve para as duas etapas

☐  Reconstituir colunas categóricas a partir das dummies (Köppen L1/L2/L3 já prontos)

☐  Gerar dummies de HLZ\_L1/L2 a partir de holdridge\_38BR\_1km (pd.get\_dummies na Rota A, .eq() por classe na Rota B — seção 5\)

**Etapa 1 — Textura:**

☐  Estatística descritiva de areia/silte/argila por classe/subclasse

☐  Kruskal-Wallis \+ post-hoc (Dunn) \+ eta² por variável de textura × cada nível climático

☐  Correlação ponto-bisserial por classe individual

☐  Boxplots comparativos (Köppen vs Holdridge, classe vs subclasse)

**Etapa 2 — SOC:**

☐  Estatística descritiva de carbono\_gm2/carbono\_gm2\_qmap por classe/subclasse

☐  Kruskal-Wallis \+ post-hoc (Dunn) \+ eta² para SOC × cada nível climático

☐  Correlação ponto-bisserial por classe individual

☐  Correlação de Spearman entre SOC e textura (areia/silte/argila)

☐  Boxplots comparativos (Köppen vs Holdridge, classe vs subclasse)

☐  (Opcional) Rota B — estatística zonal espacial em todo o Brasil (textura e SOC)

☐  (Opcional) Extensão — regressões múltiplas / mistas / GWR (seção 7\)

☐  Consolidar achados das duas etapas no notebook .ipynb

# 9\. Referências rápidas

* **Earth Engine Python API:** [developers.google.com/earth-engine/guides/python\_install](https://developers.google.com/earth-engine/guides/python_install)

* **geemap** (ponte Earth Engine ↔ pandas/geopandas): [geemap.org](https://geemap.org/)

* **Repositório de origem dos scripts:** [github.com/mapbiomas/brazil-soil](https://github.com/mapbiomas/brazil-soil)

* **Contato MapBiomas Solo:** [contato@mapbiomas.org](mailto:contato@mapbiomas.org)