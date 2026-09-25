"""Métricas de validação no formato do MapBiomas Solo (error_statistics, 00_helper_functions.r):

    ME    = média(previsto − observado)                  viés
    MAE   = média(|previsto − observado|)
    RMSE  = raiz(média((previsto − observado)²))
    MEC   = 1 − MSE / variância(observado)               = o R² fora da amostra usado aqui
    slope = inclinação de lm(observado ~ previsto)       1 é o ideal; > 1 = predições "achatadas"

SOC também com a correção de Duan (smearing) do viés da retransformação do log.

Calculadas a partir das predições fora da amostra (1ª repetição da validação em blocos de 2°) salvas pela
fase 1. Textura em % (as três camadas de 0-30 cm juntas e por camada); SOC em t/ha (estoque 0-30 cm,
exp da predição em log; 1 g/m² = 0,01 t/ha), como o MapBiomas reporta.

Saída: resultados/tabelas/metricas_mapbiomas{,_semC2}.csv
"""
import numpy as np
import pandas as pd

import config as cfg


def error_statistics(obs, prev):
    obs, prev = np.asarray(obs, float), np.asarray(prev, float)
    erro = prev - obs
    mse = np.mean(erro ** 2)
    return {'n': len(obs), 'me': erro.mean(), 'mae': np.abs(erro).mean(), 'rmse': np.sqrt(mse),
            'mec': 1 - mse / np.mean((obs.mean() - obs) ** 2), 'slope': np.polyfit(prev, obs, 1)[0]}


def main():
    for suf in ('', '_semC2'):
        linhas = []
        tex = pd.read_parquet(cfg.PONTOS / f'textura_oof{suf}.parquet')
        for (cen, camada), g in list(tex.groupby(['cenario', 'camada'])) + [((c, '000_030cm'), g) for c, g in tex.groupby('cenario')]:
            for fr in ('areia', 'silte', 'argila'):
                linhas.append({'variavel': fr, 'cenario': cen, 'camada': camada,
                               **error_statistics(g[f'{fr}_obs'], g[f'{fr}_prev'])})
        soc = pd.read_parquet(cfg.PONTOS / f'soc_oof{suf}.parquet')
        for cen, g in soc.groupby('cenario'):
            obs, prev = np.exp(g.log_soc_obs) * 0.01, np.exp(g.log_soc_prev) * 0.01
            linhas.append({'variavel': 'soc_t_ha', 'cenario': cen, 'camada': '000_030cm',
                           **error_statistics(obs, prev)})
            # Voltar do log com exp() estima ~a mediana e subestima a média (SOC é assimétrico); a correção de
            # Duan (smearing) multiplica pela média de exp(resíduo). Fator global, calculado nas predições
            # fora da amostra.
            fator = np.mean(np.exp(g.log_soc_obs - g.log_soc_prev))
            linhas.append({'variavel': 'soc_t_ha_smearing', 'cenario': cen, 'camada': '000_030cm',
                           **error_statistics(obs, prev * fator), 'fator_smearing': fator})
        pd.DataFrame(linhas).to_csv(cfg.TABELAS / f'metricas_mapbiomas{suf}.csv', index=False)


if __name__ == '__main__':
    main()
