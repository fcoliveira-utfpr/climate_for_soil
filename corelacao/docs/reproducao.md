# Reprodução e critérios metodológicos

O notebook (`solo_clima_consolidado.ipynb`) é a leitura principal. Este documento descreve como refazer
os cálculos sem incluir dados brutos nem ferramentas editoriais na entrega ao professor.
As [orientações originais](orientacoes_solo_clima.md) foram preservadas sem alteração.

## 1. Conferir somente o material entregue

Python 3.11 ou superior. As versões efetivamente usadas estão em `resultados/fontes/ambiente.json`.

```powershell
python -m pip install -r requirements.txt
python codigo/verificar_resultados.py --entrega
python -m unittest discover -s codigo -p "test_*.py"
```

O primeiro comando de verificação confere tabelas, arquivos, hashes e notebook usando apenas a entrega
publicada — não depende de `.local/`, credenciais ou consultas ao GEE. Nos hashes da entrega, quebras
de linha CRLF/LF de arquivos textuais são normalizadas para permitir checkout do Git em Windows, Linux
ou macOS. O notebook também pode ser aberto no Jupyter/VS Code; sua execução padrão usa só os CSVs e
figuras já publicados, com a opção `RECALCULAR` desligada.

## 2. Recalcular a partir das fontes (exige acesso restrito)

Exige uma conta do Earth Engine com acesso liberado às duas matrizes de treino abaixo — não é acesso
público (ver [docs/assets.md](assets.md)):

- `projects/mapbiomas-workspace/SOLOS/AMOSTRAS/MATRIZES/collection3/matriz-collection3_carbon_datac2v2`
- `projects/mapbiomas-workspace/SOLOS/AMOSTRAS/MATRIZES/collection3/c03_psd_v2025_11_18`

```powershell
earthengine authenticate
python codigo/preparar_dados.py
```

Baixa as duas matrizes paginando por `ee.data.listFeatures` (evita o limite de payload de `getInfo`
numa matriz deste tamanho), aplica os critérios de filtragem (seção 5), e extrai Holdridge por asset
com legenda confirmada nas coordenadas de cada ponto. `EE_PROJECT` pode indicar o projeto do GEE;
a conexão tenta a credencial Earth Engine e, como alternativa, ADC.

## 3. Recalcular as análises a partir do cache

```powershell
python codigo/reproduzir.py
```

Ordem: testes sobre os locais → regressões e validação → figuras → consolidação da entrega →
verificação numérica. Nenhuma consulta externa é feita por esse comando — exige que a seção 2 já
tenha rodado (checa a presença de `textura.parquet`/`soc.parquet`/`joint.parquet` em `.local/dados/`).
A validação com random forest pode levar alguns minutos.

Os resultados intermediários ficam em `.local/resultados/`; as tabelas consolidadas e as 18 figuras são
exportadas para `resultados/`. Todas as comparações de Dunn são preservadas, uma única vez por par.
O notebook é o documento editorial da execução entregue e **não é sobrescrito** pelo pipeline — precisa
ser reexecutado manualmente depois de qualquer recálculo. Se dados, parâmetros ou versões mudarem, as
conclusões e o notebook precisam ser revisados também.

## 4. Papel dos arquivos de código

| Arquivo em `codigo/` | Responsabilidade |
| --- | --- |
| `gee_utils.py` | Inicialização configurável do Earth Engine |
| `clima_legendas.py` | Legenda de Holdridge (asset, faixas L1, códigos), compartilhada |
| `preparar_dados.py` | Baixa as duas matrizes GEE, filtra, agrega por local e extrai Holdridge |
| `analise_solo_clima.py` | Descritivas, KW, ANOVA/Welch, Dunn, ponto-bisserial e Spearman |
| `regressoes_corrigidas.py` | Modelos M1-M5, validação aleatória/espacial e logística |
| `graficos_relatorio.py` | Figuras analíticas e esquemas didáticos reproduzíveis |
| `importancia_climatica.py` | Köppen vs. Holdridge no mesmo random forest, permutação em bloco por variável |
| `exportar_resultados.py` | Consolidação integral das tabelas e seleção das figuras da entrega |
| `reproduzir.py` | Execução ordenada do pipeline científico (seção 3) |
| `test_metodologia.py` | Casos de teste dos principais filtros e cálculos |
| `verificar_resultados.py` | Checagem da entrega e recálculo numérico independente dos CSVs |

## 5. Regras que afetam os resultados

- **Camada-alvo:** filtrar textura em `profundidade ≤ 30 cm`; excluir amostras artificiais
  (`clay-copy-`/pseudo); mediana por local quando há mais de um registro na camada; exigir
  areia + silte + argila = 100% (±1 ponto percentual) depois da agregação.
- **Carbono:** selecionar `profund_inf = 30`. Remover pseudoamostras (`PSEUDO_index`), valores
  inválidos e coordenadas impossíveis; mediana por local quando o mesmo ponto se repete por ano
  (até ~40 vezes na matriz bruta). Esta matriz não tem a variável qmap (correção de viés por
  quantile mapping) — só a fonte pública SoilData (fora do escopo desta análise) a disponibiliza.
- **Coordenadas:** longitude em [-180, 180] e latitude em [-90, 90]; não se presume correção decimal.
  Arredondar a seis casas identifica repetições de local, mas não equivale a agregar por pixel.
- **Clima:** Köppen já vem como dummy nas duas matrizes (mesma fonte, `IPEF_2013_KOPPEN_100M_2025`).
  Holdridge (HLZ_L1/L2) vem de uma extração à parte, com legenda confirmada no próprio asset
  (`holdridge_lifezones_chelsa-v2026`) — não das dummies embutidas nem de um vetor de terceiros.
- **Amostra dos testes:** resposta finita, classe presente e pelo menos 30 observações válidas por
  grupo. O mesmo subconjunto alimenta KW, Dunn, ponto-bisserial e boxplots.
- **Multiplicidade:** Holm nos 20 testes KW, em uma única família. Dunn e ponto-bisserial por
  resposta/nível; Spearman em três pares. ANOVA/Welch são complementares, com p nominais.
- **Associação:** η²H = max[0, (H-k+1)/(n-k)] e ε² = H/(n-1), baseados em postos. Não são percentuais
  de variância causalmente explicada. P pequeno não implica magnitude grande nem todos os pares diferentes.
- **Regressões:** resposta log(SOC); duas frações (areia/argila), porque silte é redundante; uma dummy
  climática omitida como referência. Coeficientes M4 com HC3, que não corrige dependência espacial.
- **Validação:** cinco dobras, semente 42 para embaralhamento; RF com 200 árvores e mínimo de cinco
  observações por folha. OLS/RF usam as mesmas covariáveis e dobras. Grades de 1°, 2° e 5° não têm buffer
  e não equivalem a distância fixa em km. R² OOF é calculado reunindo todas as predições fora de treino.

## 6. Pendências

A matriz `c03_soc_v2025_trainingFinal`, indicada nas orientações originais do trabalho, continua
bloqueada mesmo com acesso liberado às outras duas matrizes desta análise — permissão por asset, não
por pasta inteira. A matriz de carbono usada é a substituta declarada; supre tudo que a Etapa 2
precisa, exceto a variável qmap.

Mediação causal, modelos mistos e GWR não foram estabelecidos/ajustados; as duas últimas eram
extensões opcionais do escopo original.

`.local/` inteira é ignorada pelo Git: contém dados brutos e resultados intermediários, não deve ser
incluída manualmente no envio ao professor.
