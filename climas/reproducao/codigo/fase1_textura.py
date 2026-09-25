"""Fase 1a: modelos de textura do MapBiomas (GBM por camada sobre as razões log) com cada clima.

Para cada camada de 0-30 cm (centros 5, 15, 25 cm; horizontes a até 5 cm do centro), cada cenário de
clima e cada dobra espacial: dois GBM (ln areia/argila e ln silte/argila) -> % de areia, silte e argila.
Covariáveis: todas as da matriz de textura (com profundidade e textura da coleção 2) + o clima do cenário.

Saída: resultados/tabelas/textura_repeticoes.csv (R² e RMSE por repetição, cenário, camada e fração) e
dados_reproducao/pontos/textura_oof.parquet (predições fora da amostra, restritas, para os gráficos).
"""
import time

import numpy as np
import pandas as pd

import config as cfg
import dados
import modelagem as m


def main():
    cfg.TABELAS.mkdir(parents=True, exist_ok=True)
    tex, soc = dados.carregar()
    cov_base = m.base(tex)
    cats = {c: m.categorias(c, tex, soc) for c in cfg.CENARIOS}
    chaves_tex = m.chave_bloco(tex)
    todas_chaves = pd.concat([chaves_tex, m.chave_bloco(soc)])
    rng = np.random.default_rng(cfg.SEMENTE)
    print(f'textura: {len(tex)} horizontes, {len(cov_base)} covariáveis-base', flush=True)

    linhas, oof = [], []
    for rep in range(cfg.N_REPETICOES):
        dobra_de = m.sortear_dobras(todas_chaves, rng)
        dobra = chaves_tex.map(dobra_de).to_numpy()
        for camada, centro in cfg.CAMADAS.items():
            sel = tex.profundidade.between(centro - cfg.MEIA_JANELA, centro + cfg.MEIA_JANELA).to_numpy()
            d = tex[sel].reset_index(drop=True)
            dob = dobra[sel]
            obs = d[['areia', 'silte', 'argila']].to_numpy() / 10.0          # g/kg -> %
            for cen in cfg.CENARIOS:
                t0 = time.time()
                x = pd.concat([d[cov_base], m.clima(d, cen, cats[cen])], axis=1).to_numpy(float)
                pred = np.empty((len(d), 2))
                for f in range(cfg.N_DOBRAS):
                    te, tr = dob == f, dob != f
                    for j, alvo in enumerate(cfg.ALVOS_TEXTURA):
                        mod = m.gbm(cfg.SEMENTE + rep).fit(x[tr], d[alvo].to_numpy()[tr])
                        pred[te, j] = mod.predict(x[te])
                pct = np.column_stack(m.razoes_para_pct(pred[:, 0], pred[:, 1]))
                for k, frac in enumerate(('areia', 'silte', 'argila')):
                    linhas.append({'rep': rep, 'camada': camada, 'cenario': cen, 'fracao': frac,
                                   'n': len(d), 'r2': m.r2(obs[:, k], pct[:, k]),
                                   'rmse': m.rmse(obs[:, k], pct[:, k])})
                if rep == 0:
                    oof.append(pd.DataFrame({'ponto_id': d.ponto_id, 'camada': camada, 'cenario': cen,
                                             'longitude': d.longitude, 'latitude': d.latitude,
                                             'areia_obs': obs[:, 0], 'silte_obs': obs[:, 1], 'argila_obs': obs[:, 2],
                                             'areia_prev': pct[:, 0], 'silte_prev': pct[:, 1],
                                             'argila_prev': pct[:, 2]}))
                print(f'  rep {rep + 1} {camada} {cen:15s} {time.time() - t0:5.0f}s', flush=True)
        pd.DataFrame(linhas).to_csv(cfg.TABELAS / f'textura_repeticoes{cfg.SUFIXO}.csv', index=False)   # parcial
    pd.concat(oof).to_parquet(cfg.PONTOS / f'textura_oof{cfg.SUFIXO}.parquet', index=False)


if __name__ == '__main__':
    main()
