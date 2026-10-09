/******************************************************************************
 * CDD DECENAL (dias secos consecutivos) - a partir do CDD anual do Xavier (BR-DWGD)
 * ----------------------------------------------------------------------------
 * Gera a coleção projects/fcoliveira/assets/Climas2/CDD_DECENAL_BRDWGD (banda 'cdd_10yr_mean', 1971-2024)
 * no padrão das coleções GT_DECADE_*_CONTI_2026 do GT de clima do MapBiomas Solo: a imagem do ano Y é a
 * média do CDD anual de Y-10 a Y-1 (propriedades year, startYear, endYear). Cada amostra de solo recebe a
 * imagem do seu ano, isto é, o clima da década que antecede a coleta.
 *
 * Entrada: projects/fcoliveira/assets/Climas2/CDD_ANUAL_BRDWGD (script cdd_anual_brdwgd; 1961-2022). A
 * grade pública do BR-DWGD vai até 31/12/2022, então os anos com janela incompleta usam os anos disponíveis
 * e registram n_anos < 10 (2024: 2014-2022, 9 anos).
 *
 * Tradução do código Python climas/analise_espaco_tempo/codigo/cdd_brdwgd.py
 * (GitHub fcoliveira-utfpr/climate_for_soil). Autor: Fabrício C. de Oliveira (UTFPR), 2026-10.
 *
 * Conferência: decenal de 2023 (2013-2022) em Petrolina 107 dias, Cuiabá 59, Curitiba 26, Manaus 12,
 * Boa Vista 36.
 ******************************************************************************/

// --- Parâmetros -------------------------------------------------------------------------------------
var COL_ANUAL = 'projects/fcoliveira/assets/Climas2/CDD_ANUAL_BRDWGD';
var COL_DECENAL = 'projects/fcoliveira/assets/Climas2/CDD_DECENAL_BRDWGD';
var PRIMEIRO_ANO = 1961, ULTIMO_ANO = 2022;     // cobertura do CDD anual
var ANOS_DECENAL = [1971, 2024];

var EXPORTAR = false;                    // true: cria uma tarefa por ano (a coleção já existe; mude o
                                         // destino ou apague as imagens antes de reexportar)
var ANO_MAPA = 2023;                     // ano mostrado no mapa

var anual = ee.ImageCollection(COL_ANUAL);

// Média do CDD anual de Y-10 a Y-1.
function cddDecenal(ano) {
  var ini = ano - 10, fim = ano - 1;
  var janela = anual.filter(ee.Filter.rangeContains('year', ini, fim));
  return janela.mean().rename('cdd_10yr_mean').toFloat()
    .set({
      year: ano,
      startYear: ini,
      endYear: fim,
      n_anos: janela.size(),
      'system:time_start': ee.Date.fromYMD(ano, 1, 1).millis(),
      fonte: COL_ANUAL
    });
}

// --- Conferências -----------------------------------------------------------------------------------
var nAnual = anual.size();
print('Imagens no CDD anual (esperado ' + (ULTIMO_ANO - PRIMEIRO_ANO + 1) + '):', nAnual);
[2020, 2021, 2022, 2023, 2024].forEach(function (ano) {
  print('Anos na média do CDD decenal ' + ano + ':', cddDecenal(ano).get('n_anos'));
});

var pontos = ee.FeatureCollection([
  ee.Feature(ee.Geometry.Point([-40.50, -9.39]), {nome: 'Petrolina'}),
  ee.Feature(ee.Geometry.Point([-60.02, -3.10]), {nome: 'Manaus'}),
  ee.Feature(ee.Geometry.Point([-56.10, -15.60]), {nome: 'Cuiabá'}),
  ee.Feature(ee.Geometry.Point([-49.27, -25.43]), {nome: 'Curitiba'}),
  ee.Feature(ee.Geometry.Point([-60.67, 2.82]), {nome: 'Boa Vista'})
]);
[1971, 2000, 2023, 2024].forEach(function (ano) {
  print('CDD decenal ' + ano + ' (média de ' + (ano - 10) + ' a ' + (ano - 1) + '):',
        cddDecenal(ano).reduceRegions(pontos, ee.Reducer.first(), 11132).aggregate_array('first'),
        pontos.aggregate_array('nome'));
});

// --- Mapa -------------------------------------------------------------------------------------------
var vis = {min: 0, max: 120, palette: ['#ffffff', '#ffffb2', '#fecc5c', '#fd8d3c', '#e31a1c', '#800026']};
Map.setOptions('HYBRID');
Map.setCenter(-52, -14, 4);
Map.addLayer(cddDecenal(ANO_MAPA), vis, 'CDD decenal ' + ANO_MAPA + ' (calculado agora)');
Map.addLayer(ee.ImageCollection(COL_DECENAL).filter(ee.Filter.eq('year', ANO_MAPA)).first(), vis,
             'CDD decenal ' + ANO_MAPA + ' (asset)', false);
Map.addLayer(cddDecenal(1990), vis, 'CDD decenal 1990 (1980-1989)', false);
Map.addLayer(pontos, {color: 'blue'}, 'Pontos de teste');

// --- Exportação: uma tarefa por ano, na grade do CDD anual (0,1°) ------------------------------------
if (EXPORTAR) {
  nAnual.evaluate(function (n) {
    if (n < ULTIMO_ANO - PRIMEIRO_ANO + 1) {
      print('O CDD anual tem ' + n + ' anos; espere todas as tarefas anuais terminarem.');
      return;
    }
    var ref = anual.first();
    ref.projection().evaluate(function (proj) {
      for (var ano = ANOS_DECENAL[0]; ano <= ANOS_DECENAL[1]; ano++) {
        Export.image.toAsset({
          image: cddDecenal(ano),
          description: 'cdd_decenal_' + ano,
          assetId: COL_DECENAL + '/' + ano,
          crs: proj.crs,
          crsTransform: proj.transform,
          region: ref.geometry(),
          maxPixels: 1e9
        });
      }
    });
  });
}
