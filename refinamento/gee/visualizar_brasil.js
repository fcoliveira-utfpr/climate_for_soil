// ===== Refinamento a 30 m | Brasil inteiro | Visualizador =====
// Usa a biblioteca brasil_30m (o modelo rodando no GEE). Prévia experimental; ver refinamento/mapa.md.
var r = require('users/vitorkenor/refinamento_30m:brasil_30m');
var temperatura = r.temperatura, chuva = r.chuva;
var MESES = ['01', '02', '03', '04', '05', '06', '07', '08', '09', '10', '11', '12'];
var ROTULOS = ['Janeiro', 'Fevereiro', 'Março', 'Abril', 'Maio', 'Junho', 'Julho', 'Agosto',
               'Setembro', 'Outubro', 'Novembro', 'Dezembro', 'Anual'];

var VIS = {
'Temperatura (°C)': {img: temperatura, mensal: [10, 30], anual: [14, 28], inc: [0, 2],
  paleta: ['313695', '4575b4', '74add1', 'abd9e9', 'ffffbf', 'fdae61', 'f46d43', 'd73027', 'a50026']},
'Chuva (mm)': {img: chuva, mensal: [0, 400], anual: [500, 3500], inc: [0, 150],
  paleta: ['f7fbff', 'deebf7', 'c6dbef', '9ecae1', '6baed6', '4292c6', '2171b5', '08519c', '08306b']}
};
var estado = {v: 'Temperatura (°C)', camada: 'media', p: 'anual'};
var legenda = ui.Panel({style: {position: 'bottom-left', padding: '6px 10px'}});
function desenhar() {
var v = VIS[estado.v], ehInc = estado.camada === 'inc90';
var f = ehInc ? v.inc : (estado.p === 'anual' ? v.anual : v.mensal);
var vis = {min: f[0], max: f[1], palette: ehInc ? ['fff5eb', 'fdae6b', 'e6550d', '7f2704'] : v.paleta};
Map.layers().reset([ui.Map.Layer(v.img.select(estado.camada + '_' + estado.p), vis, estado.v)]);
legenda.clear();
legenda.add(ui.Label(estado.v + (ehInc ? ' | incerteza (±, 90%)' : '') + ' | ' +
  ROTULOS[estado.p === 'anual' ? 12 : MESES.indexOf(estado.p)], {fontWeight: 'bold'}));
legenda.add(ui.Label(f[0] + ' a ' + f[1]));
}
var painel = ui.Panel({widgets: [
ui.Label('Refinamento a 30 m | Brasil', {fontWeight: 'bold', fontSize: '15px'}),
ui.Label('Calculado no GEE com o modelo validado no Paraná. Prévia experimental; ver refinamento/mapa.md.',
         {fontSize: '12px'}),
ui.Select({items: Object.keys(VIS), value: estado.v, onChange: function (x) { estado.v = x; desenhar(); }}),
ui.Select({items: [{label: 'Valor', value: 'media'}, {label: 'Incerteza (±90%)', value: 'inc90'}], value: 'media',
           onChange: function (x) { estado.camada = x; desenhar(); }}),
ui.Select({items: MESES.concat(['anual']).map(function (p, i) { return {label: ROTULOS[i], value: p}; }),
           value: 'anual', onChange: function (x) { estado.p = x; desenhar(); }}),
ui.Label('Clique no mapa para ver os valores no ponto (a 30 m).', {fontSize: '12px'})
], style: {width: '300px'}});
var ponto = ui.Label('');
painel.add(ponto);
ui.root.insert(0, painel);
Map.add(legenda);
Map.setCenter(-53, -15, 5);
desenhar();
Map.onClick(function (c) {
  ponto.setValue('Consultando...');
  temperatura.select('media_anual').rename('t').addBands(chuva.select('media_anual').rename('p'))
    .reduceRegion(ee.Reducer.first(), ee.Geometry.Point([c.lon, c.lat]), 30)
    .evaluate(function (v) {
      ponto.setValue(v && v.t !== null ? 'Temperatura anual ' + v.t.toFixed(2) + ' °C | chuva anual ' +
        Math.round(v.p) + ' mm' : 'Sem dado no ponto.');
    });
});
