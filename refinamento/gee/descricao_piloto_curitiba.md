# Refinamento a 30 m — Temperatura média do ar, normal 1991-2020, piloto de Curitiba (prévia experimental)

## Resumo

Prévia experimental da temperatura média do ar com pixel de 30 m num recorte de 12 × 12 km em Curitiba (PR),
para a normal 1991-2020: 12 meses e a média anual. Cada pixel é estimado por um modelo (LightGBM que aprende a
correção do CHELSA a partir de relevo, posição e época do ano), sem interpolar estações. Junto vão a dispersão
entre cinco modelos e uma flag de extrapolação. **Ainda não validada:** o detalhe de 30 m não foi aprovado, e o
modelo não superou a grade Xavier nas estações de desenvolvimento. Detalhes em `refinamento/mapa.md` do
repositório `climate_for_soil`.

## Especificações

- Variável: temperatura média do ar, definida como (Tmax + Tmin)/2 diária, média de 1991 a 2020
- Observações de treino: 102 estações de Tmax e Tmin de Xavier et al. (2022); 18 estações reservadas, não usadas
- Modelo: LightGBM corrigindo o CHELSA V2.1 (resposta = estação − CHELSA do mês)
- Covariáveis: CHELSA do mês, altitude e declividade do Copernicus GLO-30 (DSM), latitude, longitude e harmônicos do mês
- Resolução espacial: 30 m
- Sistema de referência: EPSG:32722 (WGS 84 / UTM 22S)
- Extensão: 400 × 400 pixels, origem (667.950 m E; 7.192.320 m N)
- Tipo: float32, em unidades físicas (sem fator de escala)
- Bandas: 39 (13 de temperatura, 13 de dispersão e 13 de flag)
- NoData: −9999 (nenhum pixel do recorte)

## Bandas

O upload pelo Code Editor nomeia as bandas `b1` a `b39`. Na ordem:

| Bandas | Nome | Conteúdo |
|---|---|---|
| `b1`-`b12`, `b13` | `temp_01`-`temp_12`, `temp_anual` | temperatura média do ar (°C); a anual é a média dos meses ponderada pelo número de dias |
| `b14`-`b25`, `b26` | `disp_01`-`disp_12`, `disp_anual` | desvio padrão entre cinco modelos treinados nas dobras (°C); **não é intervalo de previsão** |
| `b27`-`b38`, `b39` | `fora_01`-`fora_12`, `fora_anual` | 1 = alguma covariável fora do mínimo/máximo do treino (0,4% dos pixels); não é área de aplicabilidade multivariada |

## Valores no recorte

| Período | Temperatura (°C) | Período | Temperatura (°C) |
|---|---|---|---|
| Janeiro | 21,33 a 22,36 | Julho | 13,81 a 15,04 |
| Fevereiro | 21,43 a 22,49 | Agosto | 14,91 a 16,05 |
| Março | 20,53 a 21,57 | Setembro | 16,04 a 17,12 |
| Abril | 18,59 a 19,75 | Outubro | 17,84 a 18,90 |
| Maio | 15,40 a 16,63 | Novembro | 19,08 a 20,11 |
| Junho | 14,25 a 15,51 | Dezembro | 20,74 a 21,78 |
| **Anual** | **17,82 a 18,91** | | |

## Validação (estações de desenvolvimento, blocos espaciais de 2°)

RMSE mensal nas 98 estações com todas as bases: LightGBM corrigindo o CHELSA 0,526 °C; CHELSA 0,798 °C;
grade Xavier 0,241 °C (o Xavier provavelmente usou essas estações). Os números valem para o Brasil, não só
para Curitiba, e não incluem o teste reservado.

## Limitações

- (Tmax + Tmin)/2 fica cerca de +0,9 °C acima da média de 24 horas (INMET, 2020); nenhum desconto foi aplicado.
- A textura fina e os degraus nas bordas das células do CHELSA ainda estão em análise (comparação C10).
- Nos testes, o relevo agregado a 1 km foi tão bom quanto o de 30 m: o pixel de 30 m não demonstrou ganho de previsão.

## Uso no GEE

```javascript
var nomes = [];
['temp', 'disp', 'fora'].forEach(function (p) {
  ['01','02','03','04','05','06','07','08','09','10','11','12','anual'].forEach(function (m) { nomes.push(p + '_' + m); });
});
var piloto = ee.Image('projects/mystic-hull-480913-h5/assets/refinamento_30m/piloto_curitiba_30m').rename(nomes);
Map.centerObject(piloto, 13);
Map.addLayer(piloto.select('temp_anual'), {min: 17.8, max: 19.0, palette: ['313695', 'ffffbf', 'a50026']}, 'Temperatura anual (°C)');
```

Visualizador completo, com seletor de mês e ciclo anual no ponto clicado: `refinamento/gee/visualizar_piloto.js`.

## Atribuição

Produced using Copernicus WorldDEM-30 © DLR e.V. 2010-2014 and © Airbus Defence and Space GmbH 2014-2018
provided under COPERNICUS by the European Union and ESA; all rights reserved.

Xavier, A. C.; Scanlon, B. R.; King, C. W.; Alves, A. I. (2022). New improved Brazilian daily weather gridded
data (1961–2020). *International Journal of Climatology* 42: 8390–8404. doi:10.1002/joc.7731.

Karger, D. N. et al. (2017). Climatologies at high resolution for the earth's land surface areas. *Scientific Data* 4.
