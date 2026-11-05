/**
 * Módulo: conjunto curto de clima decenal para o modelo de SOC do MapBiomas Solo (Xavier BR-DWGD v3.2.4).
 *
 * Nove variáveis em média móvel dos 10 anos anteriores ao ano, 1985-2026, na grade de 0,1°. Todas as funções
 * devolvem o clima com interpolação BILINEAR, a forma validada: use as mesmas funções no treino (amostrar) e no
 * mapa (climaDoAno / empilhar), para que o modelo veja os mesmos valores nos dois.
 *
 * Uso: salve este arquivo como script num repositório do Code Editor e chame com require, por exemplo
 *   var clima = require('users/SEU_USUARIO/SEU_REPOSITORIO:clima_curto');
 *
 * Autor: Fabrício Correia de Oliveira (UTFPR). Código: github.com/fcoliveira-utfpr/climate_for_soil (C4/gee).
 */
var COLECAO = 'projects/fcoliveira/assets/Climas2/xavier_conjunto_curto_decenal';
var BANDAS = ['cd_t_media', 'cd_tmax_media', 'cd_tmin_media', 'cd_t_mes_quente', 'cd_t_mes_frio',
              'cd_amplitude', 'cd_biotemp', 'cd_cdd', 'cd_arm_csolo'];
var ANO_MIN = 1985;
var ANO_MAX = 2026;

exports.BANDAS = BANDAS;
exports.colecao = ee.ImageCollection(COLECAO);

/** As 9 variáveis do ano (1985-2026), com interpolação bilinear. Anos fora da faixa usam o extremo mais próximo. */
exports.climaDoAno = function (ano) {
  var a = ee.Number(ano).max(ANO_MIN).min(ANO_MAX);
  return ee.Image(ee.ImageCollection(COLECAO).filter(ee.Filter.eq('year', a)).first())
    .select(BANDAS)
    .resample('bilinear');
};

/** Acrescenta o clima do ano a uma imagem de covariáveis (para o mapa do ano). */
exports.empilhar = function (covariaveis, ano) {
  return ee.Image(covariaveis).addBands(exports.climaDoAno(ano));
};

/**
 * Clima de cada amostra no ano dela (para o treino). `campoAno` é o nome da propriedade com o ano
 * (padrão 'year'); `escala` é a escala da amostragem em metros (padrão 30).
 */
exports.amostrar = function (amostras, campoAno, escala) {
  campoAno = campoAno || 'year';
  escala = escala || 30;
  amostras = ee.FeatureCollection(amostras);
  var anos = amostras.aggregate_array(campoAno).distinct();
  return ee.FeatureCollection(anos.map(function (a) {
    return exports.climaDoAno(a).sampleRegions({
      collection: amostras.filter(ee.Filter.eq(campoAno, a)),
      scale: escala,
      geometries: true
    });
  })).flatten();
};
