"""Etapa 6c: métricas das validações (error_statistics do MapBiomas, em t/ha) e ganhos pareados.

Lê climas/dados_espaco_tempo/oof/*.parquet (validacao.R, ranger) ou oof_gee/ (validacao_gee.py, modelo do
mapa). Métricas por cenário, esquema, resposta e repetição, em todas as profundidades, em 0-30 cm (linhas com
profundidade = 30) e em 0-30 cm só com amostras reais (sem réplicas trep e sem pseudoamostras); também por
período e por bioma em 0-30 cm. Ganho pareado: métrica do cenário menos a do Köppen IPEF na mesma repetição (mesmas
dobras).

Saídas: resultados/tabelas/validacao_metricas{,_gee}.csv, validacao_ganhos{,_gee}.csv,
validacao_periodo_bioma{,_gee}.csv

Uso: python metricas.py [ranger|gee]
"""
import sys

import numpy as np
import pandas as pd

import config as cfg

BIOMAS = ['Amazonia', 'Caatinga', 'Cerrado', 'Mata_Atlantica', 'Pampa', 'Pantanal']
REFERENCIA = 'koppen_ipef'


def error_statistics(obs, pred):
    """00_helper_functions.r do MapBiomas."""
    err = pred - obs
    mse = np.mean(err ** 2)
    slope = np.polyfit(pred, obs, 1)[0] if np.std(pred) > 0 else np.nan
    return {'n': len(obs), 'me': err.mean(), 'mae': np.abs(err).mean(), 'mse': mse, 'rmse': np.sqrt(mse),
            'mec': 1 - mse / np.mean((obs.mean() - obs) ** 2), 'slope': slope}


def carregar(pasta='oof'):
    m = pd.read_parquet(cfg.DADOS / 'matriz_cenarios.parquet',
                        columns=['id', 'carbono_gm2_qmap', 'profundidade', 'periodo', 'PSEUDOROCK_index',
                                 'PSEUDOSAND_index'] + BIOMAS)
    m['bioma'] = m[BIOMAS].idxmax(axis=1)
    m['real'] = ~m.id.str.startswith('trep') & (m.PSEUDOROCK_index == 0) & (m.PSEUDOSAND_index == 0)
    m = m.drop(columns=['id', 'PSEUDOROCK_index', 'PSEUDOSAND_index'])
    partes = []
    for arq in sorted((cfg.DADOS / pasta).glob('*.parquet')):
        cen, esq, resp = arq.stem.rsplit('_', 2)
        o = pd.read_parquet(arq)
        o['cenario'], o['esquema'], o['resposta'] = cen, esq, resp
        partes.append(o)
    oof = pd.concat(partes, ignore_index=True)
    oof['linha'] -= 1                                  # R conta a partir de 1
    oof = oof.join(m, on='linha')
    oof['obs'] = oof.carbono_gm2_qmap / 100           # t/ha
    oof['pred'] = oof.pred / 100
    return oof


def _metricas(df, chaves):
    linhas = []
    for k, g in df.groupby(chaves):
        linhas.append(dict(zip(chaves, k), **error_statistics(g.obs.to_numpy(), g.pred.to_numpy())))
    return pd.DataFrame(linhas)


def main(modelo='ranger'):
    suf = '' if modelo == 'ranger' else '_gee'
    oof = carregar('oof' if modelo == 'ranger' else 'oof_gee')
    oof['camadas'] = 'todas'
    o30 = oof[oof.profundidade == 30].assign(camadas='0-30 cm')
    r30 = o30[o30.real].assign(camadas='0-30 cm, amostras reais')
    ambos = pd.concat([oof, o30, r30])
    chaves = ['cenario', 'esquema', 'resposta', 'camadas', 'rep']
    met = _metricas(ambos, chaves)
    cfg.TABELAS.mkdir(parents=True, exist_ok=True)
    met.to_csv(cfg.TABELAS / f'validacao_metricas{suf}.csv', index=False, float_format='%.4g')

    ref = met[met.cenario == REFERENCIA].set_index(['esquema', 'resposta', 'camadas', 'rep'])
    g = met.join(ref[['mec', 'rmse', 'me']], on=['esquema', 'resposta', 'camadas', 'rep'], rsuffix='_ref')
    g['ganho_mec'] = g.mec - g.mec_ref
    g['ganho_rmse'] = g.rmse_ref - g.rmse                   # positivo = melhor que o Köppen
    ganhos = (g.groupby(['cenario', 'esquema', 'resposta', 'camadas'])
              .agg(mec=('mec', 'mean'), rmse=('rmse', 'mean'), me=('me', 'mean'),
                   ganho_mec=('ganho_mec', 'mean'), ganho_mec_min=('ganho_mec', 'min'),
                   ganho_mec_max=('ganho_mec', 'max'), ganho_rmse=('ganho_rmse', 'mean'), reps=('rep', 'size'))
              .reset_index())
    ganhos.to_csv(cfg.TABELAS / f'validacao_ganhos{suf}.csv', index=False, float_format='%.4g')

    pb = pd.concat([_metricas(o30.assign(grupo='periodo_' + o30.periodo.astype(str)),
                              ['cenario', 'esquema', 'resposta', 'grupo']),
                    _metricas(o30.assign(grupo=o30.bioma), ['cenario', 'esquema', 'resposta', 'grupo'])])
    pb.to_csv(cfg.TABELAS / f'validacao_periodo_bioma{suf}.csv', index=False, float_format='%.4g')

    pd.set_option('display.width', 200)
    print(ganhos.sort_values(['esquema', 'resposta', 'camadas', 'mec'], ascending=[True, True, True, False])
          .round(4).to_string(index=False))


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else 'ranger')
