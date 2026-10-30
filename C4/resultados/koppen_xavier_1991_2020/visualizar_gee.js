// projects/fcoliveira/assets/Climas2/koppen_xavier_1991_2020
var koppen = ee.Image('projects/fcoliveira/assets/Climas2/koppen_xavier_1991_2020').select('koppen');
var ids = [1, 2, 3, 4, 5, 7, 9, 10, 15, 16];
var cores = ['#0000FF', '#0078FF', '#46A0FF', '#96C8FF', '#F5A623', '#FF0000', '#C8FF50', '#64FF50', '#C8FFC8', '#96FF96'];
var nomes = ['Af - tropical úmido, sem estação seca', 'Am - tropical de monção', 'As - tropical com verão seco', 'Aw - tropical com inverno seco (savana)', 'BSh - semiárido quente', 'BWh - desértico quente', 'Cfa - subtropical úmido, verão quente', 'Cfb - temperado úmido, verão ameno', 'Cwa - subtropical com inverno seco, verão quente', 'Cwb - subtropical de altitude, inverno seco, verão ameno'];

// renumera as classes presentes (1..n) para usar a paleta na ordem
var vis = koppen.remap(ids, ee.List.sequence(1, ids.length));
Map.setCenter(-52, -14, 4);
Map.addLayer(vis, {min: 1, max: ids.length, palette: cores}, 'Köppen Xavier 1991-2020');

// legenda
var legenda = ui.Panel({style: {position: 'bottom-left', padding: '8px'}});
legenda.add(ui.Label('Köppen-Geiger 1991-2020 (Xavier)', {fontWeight: 'bold'}));
for (var i = 0; i < ids.length; i++) {
  legenda.add(ui.Panel([
    ui.Label('', {backgroundColor: cores[i], padding: '8px', margin: '0 6px 4px 0'}),
    ui.Label(nomes[i], {margin: '0 0 4px 0'})
  ], ui.Panel.Layout.Flow('horizontal')));
}
Map.add(legenda);

// área de cada classe (km²) no Brasil
var area = ee.Image.pixelArea().divide(1e6).addBands(koppen).reduceRegion({
  reducer: ee.Reducer.sum().group(1, 'classe'), geometry: koppen.geometry(), scale: 11132, maxPixels: 1e9});
print('área por classe (km²)', area);
