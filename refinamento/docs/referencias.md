# Referências verificadas e decisões cartográficas

Consulta em **18/10/2026**. As instruções originais permanecem preservadas.

## Xavier: o que foi confirmado

O [resumo oficial do artigo](https://rmets.onlinelibrary.wiley.com/doi/abs/10.1002/joc.7731)
confirma o uso de IDW/ADW, seleção por validação cruzada e ajuste da temperatura
com altitude e gradiente térmico. O trabalho publicado cobre 1961–2020, usa
1.252 estações meteorológicas e 11.473 pluviômetros e produz uma grade de 0,1°.
É uma referência de interpolação; ML precisa demonstrar ganho fora da amostra.
**Não foi obtido o texto integral do artigo nesta execução.** Os detalhes de
cinco vizinhos, expoente 2 e gradiente −0,006 °C/m constam de `instrucoes.md`,
mas não foram reconferidos no texto integral. Não declarar essa leitura concluída.

A [página mantida pelo autor](https://sites.google.com/site/alexandrecandidoxavierufes/brazilian-daily-weather-gridded-data)
informa atualização **v3.2.4**, de abril/maio de 2026, cobrindo 01/01/1961 a
31/12/2025. Além da série diária, já existe coleção mensal no GEE:

```javascript
ee.ImageCollection('projects/ee-alexandrexavier/assets/BR-DWGD');
ee.ImageCollection('projects/ee-alexandrexavier/assets/BR-DWGD_Monthly');
```

O [GitHub do autor](https://github.com/AlexandreCandidoXavier/BR-DWGD) tem exemplos
de acesso. Fixar a versão e conferir bandas, escala e offset do asset escolhido
antes da extração: não transportar fatores de escala de outra distribuição.
Temperatura calculada de `(Tmax + Tmin)/2` deve ser identificada como tal até a
comparação C11 com média horária/compensada. Temperatura de superfície MODIS é
covariável, e não observação equivalente à temperatura do ar.

## Disponibilidade das observações

A [pasta cedida pelo autor](https://drive.google.com/drive/folders/1urYczkKxBcXWHAmx04lle6jcbiTQS-bR)
foi acessível por HTTP e listava os seis arquivos NPZ previstos. A inspeção da
listagem encontrou `Tmax.npz` com 113.411.874 bytes e `Tmin.npz` com 112.936.954
bytes: aproximadamente 226 MB para começar a temperatura. O arquivo `pr.npz`
sozinho tem cerca de 1,35 GB. Esta consulta da listagem não valida conteúdo,
formato interno ou qualidade das séries. Dados cedidos ficam em `dados/`, fora
do git; registrar hashes e a inspeção do conteúdo ao baixar.

## O que significa pixel de 30 m

A instrução sugere simultaneamente EPSG:4326, alinhamento ao MDE e 30 m. São
condições diferentes: EPSG:4326 mede coordenadas em graus; um espaçamento angular
fixo não tem lados de 30 m constantes em todo o Brasil. A escala nominal do GEE
é definida no [ponto de escala verdadeira da projeção](https://developers.google.com/earth-engine/apidocs/ee-projection-nominalscale).

Para cumprir a ênfase do usuário no tamanho do pixel, o escritor local exige
**CRS projetado em metros, pixels de 30 × 30 unidades e ausência de rotação**.
A origem de cada tile é múltipla de 30 m nos dois eixos, na grade com origem
(0, 0). O CRS deve ser apropriado à região: preferir a zona UTM local no piloto.
Os testes usam SIRGAS 2000 / UTM 23S (EPSG:31983), apenas como caso de teste.
Toda projeção tem distorção: 30 m na grade não garante lados geodésicos exatamente
iguais a 30 m. Uma estratégia por zonas/tiles ainda precisa ser definida para o
Brasil; zonas UTM distintas não compartilham a mesma grade nacional.

Consequência: a grade de trabalho terá de ser explicitamente definida e as
covariáveis alinhadas a ela. Isso não equivale a manter todos os pixels nativos
de um MDE angular. EPSG:4326 poderá ser uma derivação nominal documentada, mas o
helper recusa essa projeção para impedir uma entrega rotulada incorretamente.
Resolução da grade também não comprova habilidade climática em escala de 30 m;
a comparação C5 continua necessária.

## MDE e GEE

O catálogo atual marca [`COPERNICUS/DEM/GLO30`](https://developers.google.com/earth-engine/datasets/catalog/COPERNICUS_DEM_GLO30)
como depreciado e indica [`COPERNICUS/DEM/GLO30_2024_1`](https://developers.google.com/earth-engine/datasets/catalog/COPERNICUS_DEM_GLO30_2024_1).
O produto é um **modelo digital de superfície**, incluindo vegetação e edifícios,
e usa datum vertical EGM2008. Esses fatores importam na conferência de altitude
das estações. O catálogo orienta definir a projeção do mosaico antes das
operações de terreno; os termos de atribuição devem acompanhar eventual produto.

Na [exportação do GEE](https://developers.google.com/earth-engine/guides/exporting_images),
`crs` e `crsTransform` controlam a grade completa. Definir somente `scale` pode
deslocar pixels por não fixar a origem. Há opções de GeoTIFF/COG e `noData`.
O helper desta fase produz **GeoTIFF comum**, sem afirmar conformidade COG.

A [documentação de ingestão](https://developers.google.com/earth-engine/guides/image_upload)
aceita GeoTIFF de até **10 GB no Code Editor**; arquivos maiores exigem a CLI.
DEFLATE e LZW são aceitos, assim como CRS projetado. A política `mean` serve
para temperatura e incerteza contínuas; máscaras categóricas exigem outra
política, como `sample` ou `mode`. Tiles enviados como uma única imagem precisam
ter mesmo CRS, resolução, bandas, tipo, nodata e deslocamentos inteiros de pixel.

A temperatura é armazenada em `int16`, °C × 100, com nodata −32768; ler em °C
significa multiplicar o valor válido por 0,01. O arquivo registra fator, offset,
unidade, período, método e caráter experimental. Após ingestão, configurar a
máscara e aplicar `multiply(0.01)` explicitamente no GEE; não pressupor que um
fator escrito no TIFF será aplicado automaticamente.

## Normais e comparação justa

A [OMM define normais climatológicas padrão](https://wmo.int/wmo-climatological-normals)
como médias de períodos consecutivos de 30 anos, incluindo 1991–2020.
A [orientação OMM 1203](https://www.ncei.noaa.gov/pub/data/normals/WMO/Guidelines%20for%20the%20Calculation%20of%20Climate%20Normals.WMO%20No1203_en.pdf)
é a referência para agregação e completude. O projeto deve explicitar definição
da temperatura, regra de dias válidos, anos por mês e ajuste de períodos curtos.
As métricas diárias publicadas no artigo não são comparáveis diretamente aos
erros das normais mensais. O comparador MX deve ser recalculado dentro das mesmas
dobras espaciais; a grade publicada do Xavier pode ter usado estações de teste.
