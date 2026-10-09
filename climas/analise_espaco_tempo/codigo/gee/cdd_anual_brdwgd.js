/******************************************************************************
 * CDD ANUAL (dias secos consecutivos) - chuva diária do Xavier (BR-DWGD)
 * ----------------------------------------------------------------------------
 * Gera a coleção projects/fcoliveira/assets/Climas2/CDD_ANUAL_BRDWGD (banda 'cdd', 1961-2022), usada como
 * base do CDD decenal (script cdd_decenal_brdwgd) no padrão das coleções GT_DECADE_*_CONTI_2026 do GT de
 * clima do MapBiomas Solo (a de CDD, GT_DECADE_CDD_CONTI_2026, está vazia).
 *
 * CDD anual (índice ETCCDI): maior número de dias seguidos, no ano, com chuva diária < 1 mm. Uma estiagem
 * que começa no ano anterior e termina no ano Y conta em Y (a sequência atravessa a virada do ano, como no
 * ETCCDI/climdex); importa no norte do país, onde a seca vai de dezembro a março.
 *
 * Cálculo sem laço dia a dia (o iterate era pesado demais para o GEE): os dias do ano viram um vetor
 * (array) por pixel, 1 = seco e 0 = chuvoso. A sequência seca até cada dia é a soma acumulada dos dias
 * secos menos o valor dessa soma no último dia chuvoso; o CDD é o máximo do vetor. A sequência que estava
 * em curso em 31/12 do ano anterior é somada aos dias do novo ano até a primeira chuva.
 *
 * Fonte: projects/sat-io/open-datasets/BR-DWGD/PR (Xavier et al. 2022, doi 10.1002/joc.7731), diário,
 * 0,1°, inteiro codificado: mm = b1 * 0,006866665 + 225. Grade pública: 1961-2022.
 *
 * Tradução do código Python climas/analise_espaco_tempo/codigo/cdd_brdwgd.py
 * (GitHub fcoliveira-utfpr/climate_for_soil). Autor: Fabrício C. de Oliveira (UTFPR), 2026-10.
 *
 * Teste (sem exportar): CDD de 2010 e 2012 em Petrolina 97 e 208 dias (seca de 2012), Cuiabá 77 e 88,
 * Curitiba 23 e 27, Manaus 14 e 9, Boa Vista 17 e 15. Limitação: a grade interpolada espalha chuvas
 * fracas e encurta as estiagens onde há poucos pluviômetros (o CDD da grade tende a ser menor que o de
 * um pluviômetro).
 ******************************************************************************/

// --- Parâmetros -------------------------------------------------------------------------------------
var PR = 'projects/sat-io/open-datasets/BR-DWGD/PR';
var ESCALA = 0.006866665, DESLOCAMENTO = 225;
var LIMIAR_MM = 1;                       // dia seco: chuva < 1 mm
var PRIMEIRO_ANO = 1961, ULTIMO_ANO = 2022;
var COL_ANUAL = 'projects/fcoliveira/assets/Climas2/CDD_ANUAL_BRDWGD';

var EXPORTAR = false;                    // true: cria uma tarefa por ano (a coleção já existe; mude o
var ANOS_EXPORTAR = [PRIMEIRO_ANO, ULTIMO_ANO];   // destino ou apague as imagens antes de reexportar)
var ANO_MAPA = 2012;                     // ano mostrado no mapa

// --- Chuva diária em mm -------------------------------------------------------------------------------
var chuvaDiaria = ee.ImageCollection(PR).map(function (im) {
  return im.multiply(ESCALA).add(DESLOCAMENTO).rename('pr')
    .copyProperties(im, ['system:time_start']);
});

function dias(ano) {
  return chuvaDiaria.filterDate(ee.Date.fromYMD(ano, 1, 1), ee.Date.fromYMD(ano + 1, 1, 1))
    .sort('system:time_start');
}

// Vetor (array 1-D por pixel) com 1 nos dias secos e 0 nos chuvosos, em ordem.
function secos(ano) {
  return dias(ano).map(function (im) { return im.lt(LIMIAR_MM).toInt16(); })
    .toArray()                 // [dias, 1]
    .arrayProject([0]);        // [dias]
}

// Dias secos seguidos até cada dia (zera no dia chuvoso) e se já houve dia chuvoso até cada dia.
function sequencias(seco) {
  var acum = seco.arrayAccum(0, ee.Reducer.sum());
  var chuvoso = seco.multiply(-1).add(1);
  var noUltimoChuvoso = acum.multiply(chuvoso).arrayAccum(0, ee.Reducer.max());
  return {
    seq: acum.subtract(noUltimoChuvoso),
    jaChoveu: chuvoso.arrayAccum(0, ee.Reducer.max())
  };
}

// CDD do ano: a sequência seca que vem de 31/12 do ano anterior continua contando.
function cddAno(ano) {
  var s = sequencias(secos(ano));
  var seq = s.seq;
  if (ano > PRIMEIRO_ANO) {
    var ant = sequencias(secos(ano - 1));
    var herdada = ant.seq.arraySlice(0, -1).arrayGet([0]);          // sequência seca em 31/12
    seq = seq.add(s.jaChoveu.multiply(-1).add(1).multiply(herdada)); // soma só até a 1ª chuva do ano
  }
  var ref = ee.Image(dias(ano).first());
  return seq.arrayReduce(ee.Reducer.max(), [0]).arrayGet([0]).rename('cdd').toInt16()
    .updateMask(ref.mask())
    .setDefaultProjection(ref.projection())
    .set({
      year: ano,
      'system:time_start': ee.Date.fromYMD(ano, 1, 1).millis(),
      limiar_mm: LIMIAR_MM,
      fonte: PR
    });
}

// --- Teste em pontos de climas bem diferentes ---------------------------------------------------------
var pontos = ee.FeatureCollection([
  ee.Feature(ee.Geometry.Point([-40.50, -9.39]), {nome: 'Petrolina (semiárido)'}),
  ee.Feature(ee.Geometry.Point([-60.02, -3.10]), {nome: 'Manaus (Amazônia úmida)'}),
  ee.Feature(ee.Geometry.Point([-56.10, -15.60]), {nome: 'Cuiabá (savana, seca no inverno)'}),
  ee.Feature(ee.Geometry.Point([-49.27, -25.43]), {nome: 'Curitiba (sem estação seca)'}),
  ee.Feature(ee.Geometry.Point([-60.67, 2.82]), {nome: 'Boa Vista (seca dez-mar)'})
]);
var dia = ee.Image(chuvaDiaria.filterDate('2010-01-15', '2010-01-16').first());
print('Chuva de 15/01/2010, mín e máx no Brasil (mm):',
      dia.reduceRegion(ee.Reducer.minMax(), dia.geometry(), 50000, null, null, true));
[2010, 2012].forEach(function (ano) {
  print('CDD ' + ano + ' nos pontos de teste:',
        cddAno(ano).reduceRegions(pontos, ee.Reducer.first(), 11132).aggregate_array('first'),
        pontos.aggregate_array('nome'));
});

// --- Mapa -------------------------------------------------------------------------------------------
var vis = {min: 0, max: 150, palette: ['#ffffff', '#ffffb2', '#fecc5c', '#fd8d3c', '#e31a1c', '#800026']};
Map.setOptions('HYBRID');
Map.setCenter(-52, -14, 4);
Map.addLayer(cddAno(ANO_MAPA), vis, 'CDD ' + ANO_MAPA + ' (calculado agora)');
Map.addLayer(ee.ImageCollection(COL_ANUAL).filter(ee.Filter.eq('year', ANO_MAPA)).first(), vis,
             'CDD ' + ANO_MAPA + ' (asset)', false);
Map.addLayer(pontos, {color: 'blue'}, 'Pontos de teste');

// --- Exportação: uma tarefa por ano, na grade nativa do BR-DWGD (0,1°) ---------------------------------
if (EXPORTAR) {
  var ref = ee.Image(chuvaDiaria.first());
  ref.projection().evaluate(function (proj) {
    for (var ano = ANOS_EXPORTAR[0]; ano <= ANOS_EXPORTAR[1]; ano++) {
      Export.image.toAsset({
        image: cddAno(ano),
        description: 'cdd_anual_' + ano,
        assetId: COL_ANUAL + '/' + ano,
        crs: proj.crs,
        crsTransform: proj.transform,
        region: ref.geometry(),
        maxPixels: 1e9
      });
    }
  });
}
