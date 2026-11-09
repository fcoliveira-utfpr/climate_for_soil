# Fonte de precipitação indicada por Fabrício

## Atualização de 07/11/2026 — pareamento com o NPZ

[Código](../codigo/conferir_fonte_chuva.py) executado em dez estações de
desenvolvimento, espaçadas na ordenação por latitude, nos meses de janeiro
de 1991, 2010 e 2020. Foram encontrados **930 registros**, sem duplicatas por
ID/data e sem estação vazia. O pareamento usa código exato e data UTC.

Dos 889 registros com `preenchido=0`, todos tinham valor finito no NPZ;
835 coincidiram a 0,001 mm. A diferença absoluta média foi 0,000730 mm e a
máxima 0,05 mm. Não presumir equivalência perfeita nem corrigir os dados para
forçar igualdade. Os **41 registros preenchidos** estavam todos ausentes no
NPZ; não entraram como observações no alvo dos modelos.

[Resumo agregado](../resultados/tabelas/chuva_fontes_amostra.csv) e
[proveniência](../resultados/tabelas/chuva_fontes_amostra.json). A amostra
confirma a utilidade da flag, mas não certifica os milhões de registros,
homogeneidade, aliases ou independência. Não houve concatenação das fontes.
Normais e modelos da chuva agora estão descritos em [modelagem da chuva](modelagem_chuva.md).
As seções abaixo preservam o registro da inspeção inicial de 02/11.

Indicação recebida em **29/10/2026**; consulta ao Earth Engine realizada em
**02/11/2026**, com a credencial existente e o projeto `mcp-gee`.

```text
projects/fcoliveira/assets/observados_inmet/pr
```

**Uso previsto:** fonte de observações de estação para a futura modelagem de
precipitação. O asset é uma tabela (`TABLE`, acessível como `ee.FeatureCollection`),
com uma feição por estação-dia. A consulta confirmou acesso e estrutura; não é
uma auditoria nacional das séries nem uma decisão de substituir o `pr.npz`.

## Metadados declarados pelo organizador

| Item | Conteúdo do asset |
|---|---|
| Variável e unidade | Precipitação diária, `valor`, mm dia⁻¹ |
| Redes | ANA, INMET e redes estaduais usadas por Xavier et al. (2022) |
| Estações | 13.259 |
| Período global | 1961-01-01 a 2020-07-31 |
| Cobertura individual | Do primeiro ao último dia com observação em cada estação |
| Registros | 120.686.394 estação-dias, segundo a descrição |
| Fração preenchida | 10,34%, segundo a propriedade `pct_preenchido` |
| Origem do preenchimento | `projects/sat-io/open-datasets/BR-DWGD/PR` |
| Flag de origem | `preenchido = 0`: observado; `preenchido = 1`: preenchido com Xavier |
| Última atualização informada | 2026-10-19T18:46:06.206095Z |

As contagens nacionais e o período acima foram lidos nos metadados, sem
recontar a coleção inteira. A descrição informa preenchimento pelo pixel de
0,1° da grade BR-DWGD; em pixels costeiros mascarados, usou média focal de dois
pixels. A procedência declarada é Xavier, Scanlon, King & Alves (2022),
[doi:10.1002/joc.7731](https://doi.org/10.1002/joc.7731), com organização por
F. C. de Oliveira (UTFPR) em 2026.

## Conferência efetivamente realizada

- Três registros confirmaram os campos `cod_estacao`, `cod_ibge`, `municipio`,
  `uf`, `lat`, `lon`, `alt`, `data`, `ano`, `mes`, `valor`, `preenchido` e
  `system:time_start`. Os códigos são texto; preservar zeros à esquerda.
- Uma estação efetivamente presente foi consultada em 1961, com limite de 370
  registros: retornou **365 registros e 365 datas distintas**, de 01/01 a 31/12,
  com geometria `Point`, **364 observados e um preenchido**, sem valores nulos
  ou negativos e sem timestamps ausentes. O limite não foi atingido.
- O exemplo `A807`, em 2010, fornecido na descrição do asset retornou **zero
  registros**. Isso não demonstra indisponibilidade da coleção nem explica a
  ausência dessa estação nesse período. O exemplo abaixo escolhe uma estação
  efetivamente presente, em vez de depender daquele código.

Essas verificações são amostrais: não demonstram completude, homogeneidade,
ausência de duplicatas ou correção de coordenadas em toda a base. Não foram
calculadas normais ou treinados modelos de chuva nesta execução.

## Como usar na etapa de chuva

1. **Separar observado de preenchido.** Para construir o alvo observado e
   avaliar modelos, começar por `preenchido = 0`. Preservar a flag na ingestão
   e registrar contagens antes/depois do filtro. Preenchimento com Xavier não
   é medição independente e não deve entrar silenciosamente como verdade de campo.
2. **Tratar a cobertura temporal.** O asset não inclui agosto–dezembro de 2020.
   O filtro 1991–2020, sozinho, não produz uma série completa de 30 anos. Na
   ausência de complemento, cada mês tem de registrar seus anos efetivamente
   válidos e passar pela regra explícita de completude/período reduzido.
3. **Agregar chuva como chuva.** Somar os valores diários apenas em meses com
   todos os dias observados válidos, conferindo calendário e duplicatas após
   retirar preenchimentos. Um mês com dia faltante permanece ausente; zero
   observado é válido. A normal mensal é a média dos totais mensais elegíveis.
   A normal anual exige os 12 meses elegíveis e é a soma das normais mensais,
   em mm/ano; não usar a média ponderada adotada para temperatura.
4. **Auditar a independência.** Segundo a descrição, as estações participaram
   da construção do Xavier. Mesmo com `preenchido = 0`, elas não constituem
   automaticamente teste independente dessa grade. Cruzar códigos, localização
   e períodos com as outras fontes antes de escolher treino, validação espacial
   e teste reservado. O mesmo cuidado vale para grades usadas como covariáveis.
5. **Comparar com a fonte já prevista.** As instruções citam `pr.npz` com
   14.170 pluviômetros e dados até 2025; este asset declara 13.259 e termina em
   julho de 2020. Não assumir que são versões equivalentes nem concatená-las
   sem pareamento por estação e data. Essa comparação de conteúdo ainda não foi feita.
6. **Modelar e validar antes de produzir o mapa.** Usar as normais observadas
   como alvo e covariáveis no pixel, conforme a proposta do refinamento. A
   conversão de pontos em raster não resolve a estimativa espacial da chuva.
   A utilidade preditiva de uma grade de 30 m continua dependendo de validação.

## Leitura no Code Editor do GEE

Consulta de metadados e recorte pequeno, sem exportação. O exemplo evita
materializar os milhões de registros no cliente.

```javascript
var asset = 'projects/fcoliveira/assets/observados_inmet/pr';
var tabela = ee.FeatureCollection(asset);
print('Metadados declarados', ee.data.getAsset(asset));
print('Amostra da estrutura', tabela.limit(3));

// Uma estação e um ano efetivamente presentes na coleção.
var exemplo = ee.Feature(tabela.first());
var serie = tabela
  .filter(ee.Filter.eq('cod_estacao', exemplo.get('cod_estacao')))
  .filter(ee.Filter.eq('ano', exemplo.get('ano')));
print('Amostra observada', serie.filter(ee.Filter.eq('preenchido', 0)).limit(5));
print('Amostra preenchida', serie.filter(ee.Filter.eq('preenchido', 1)).limit(5));

// Fim exclusivo; este filtro não cria os meses ausentes de 2020.
var observados1991a2020 = tabela
  .filterDate('1991-01-01', '2021-01-01')
  .filter(ee.Filter.eq('preenchido', 0));
print('Amostra para preparar as normais', observados1991a2020.limit(5));
```

Referência da consulta:
[`ee.data.getAsset`](https://developers.google.com/earth-engine/apidocs/ee-data-getasset)
e [tipos e leitura de assets](https://developers.google.com/earth-engine/cloud/assets).
O snippet é orientativo; as consultas desta execução usaram a API Python 1.7.37.

Os metadados, as amostras por estação e os scripts desta inspeção ficaram em
`.local/chuva_inmet/`, ignorado pelo git. `resumo.json` registra inclusive a
consulta vazia; `resumo_estacao_ano.json` registra a amostra não vazia.
Nenhuma observação individual é incluída na documentação versionável.
