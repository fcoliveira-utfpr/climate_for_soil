"""Etapa 7h: trajetórias de cada cenário com o modelo do mapa oficial (random forest do GEE emulado,
maxNodes 40) e o pós-processamento do mapa (fidelidade_gee.pos_processar). Mostra como cada clima mudaria o
produto publicado. cont_sel: seleção (pares |r| > 0,9) com a matriz inteira.

Saída (restrita): climas/dados_espaco_tempo/painel_predicoes_gee.parquet (ponto_id, year, uma coluna por
cenário, t/ha, já pós-processada; os 3 locais da provável máscara de areia ficam fora).

Uso: python prever_painel_gee.py
"""
import json
import time

import numpy as np
import pandas as pd

import config as cfg
from fidelidade_gee import modelo_gee, pos_processar
from validacao_gee import selecionar


def main():
    meta = json.loads((cfg.PASTA / 'codigo' / 'cenarios.json').read_text(encoding='utf-8'))
    m = pd.read_parquet(cfg.DADOS / 'matriz_cenarios.parquet')
    p = pd.read_parquet(cfg.DADOS / 'painel_cenarios.parquet')
    masc = pd.read_parquet(cfg.DADOS / 'mascaras_mapa.parquet')
    oficial = pd.read_parquet(cfg.DADOS / 'soc_oficial_c3.parquet')
    areia = oficial.groupby('ponto_id').soc_oficial_t_ha.apply(lambda s: (s == 10).any())
    p = p[~p.ponto_id.map(areia).astype(bool)].merge(masc, on=['ponto_id', 'year'])
    p = p.sort_values(['ponto_id', 'year']).reset_index(drop=True)
    out = p[['ponto_id', 'year']].copy()
    y = m.carbono_gm2_qmap.to_numpy()
    tudo = np.ones(len(m), bool)
    for cen, clima in meta['cenarios'].items():
        t0 = time.time()
        if cen == 'cont_sel':
            clima = selecionar(m, meta['base'], clima, tudo, 2021)
            (cfg.TABELAS / 'selecao_continuas_final_gee.txt').write_text('\n'.join(clima) + '\n', encoding='utf-8')
        cols = meta['base'] + clima
        rf = modelo_gee().fit(m[cols].to_numpy(np.float32), y)
        X = p[cols].to_numpy(np.float32)
        p['_pred'] = np.concatenate([rf.predict(X[i:i + 50000]) for i in range(0, len(X), 50000)]) / 100
        out[cen] = pos_processar(p, '_pred').to_numpy()
        print(f'{cen}: {time.time() - t0:.0f} s, média {out[cen].mean():.2f} t/ha', flush=True)
    out.to_parquet(cfg.DADOS / 'painel_predicoes_gee.parquet', index=False)


if __name__ == '__main__':
    main()
