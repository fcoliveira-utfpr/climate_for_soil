"""Fase 1b: modelo de SOC do MapBiomas (random forest) com a textura prevista no mesmo cenário de clima.

No MapBiomas, o SOC usa como covariável a textura de 0-30 cm prevista pela coleção atual. Aqui, em cada
cenário de clima e em cada dobra espacial:
  1. treina os GBM de textura (3 camadas x 2 razões log) só com os horizontes dos blocos de treino;
  2. prevê a textura de 0-30 cm (média das 3 camadas) em todos os locais de SOC;
  3. treina o RF de log(SOC) com as covariáveis da matriz de SOC + o clima do cenário + essa textura.
Assim a melhora (ou piora) do clima passa da textura para o SOC, como no pipeline real, sem vazamento:
a textura dos locais de teste vem de modelos que nunca viram os blocos de teste.

O modelo de textura desta etapa usa só as covariáveis que existem nas duas matrizes (os locais de SOC
não têm as combinações geologia x solo da matriz de textura); a profundidade entra como o centro da camada.

Os dados de SOC têm uma linha por local e profundidade (estoque acumulado até ela); a profundidade é
covariável do RF, que é treinado com todas as linhas. O R² é calculado só nas linhas de 0-30 cm (o estoque
que o MapBiomas mapeia); as outras profundidades do mesmo local ficam sempre na mesma dobra (mesmo bloco).

Saída: resultados/tabelas/soc_repeticoes.csv e dados_reproducao/pontos/soc_oof.parquet (restrito).
"""
import time

import numpy as np
import pandas as pd

import config as cfg
import dados
import modelagem as m


def main():
    tex, soc = dados.carregar()
    cats = {c: m.categorias(c, tex, soc) for c in cfg.CENARIOS}
    comuns = sorted(set(m.base(tex)) & set(m.base(soc)) - {'profundidade'})   # textura da cadeia
    cov_tex = comuns + ['profundidade']
    cov_soc = [c for c in m.base(soc) if c not in cfg.TEXTURA_C2]         # a textura vem da cadeia
    chaves_tex, chaves_soc = m.chave_bloco(tex), m.chave_bloco(soc)
    todas_chaves = pd.concat([chaves_tex, chaves_soc])
    y = np.log(soc.soc_g_m2.to_numpy(float))
    aval = soc.profundidade.eq(cfg.PROF_SOC).to_numpy()                 # estoque de 0-30 cm
    rng = np.random.default_rng(cfg.SEMENTE)          # mesma sequência da fase 1a -> mesmas dobras
    print(f'SOC: {len(soc)} linhas, {soc.ponto_id.nunique()} locais, {aval.sum()} avaliadas (0-30 cm) | '
          f'covariáveis SOC {len(cov_soc)} | textura da cadeia {len(cov_tex)}',
          flush=True)

    linhas, oof = [], []
    for rep in range(cfg.N_REPETICOES):
        dobra_de = m.sortear_dobras(todas_chaves, rng)
        dob_tex, dob_soc = chaves_tex.map(dobra_de).to_numpy(), chaves_soc.map(dobra_de).to_numpy()
        for cen in cfg.CENARIOS:
            t0 = time.time()
            clima_soc = m.clima(soc, cen, cats[cen])
            pred = np.empty(len(soc))
            for f in range(cfg.N_DOBRAS):
                # 1-2. textura de 0-30 cm prevista nos locais de SOC, com modelos sem os blocos de teste
                camadas = []
                for camada, centro in cfg.CAMADAS.items():
                    sel = tex.profundidade.between(centro - cfg.MEIA_JANELA, centro + cfg.MEIA_JANELA).to_numpy()
                    tr = sel & (dob_tex != f)
                    d = tex[tr]
                    x_tr = pd.concat([d[cov_tex], m.clima(d, cen, cats[cen])], axis=1).to_numpy(float)
                    x_soc = pd.concat([soc[comuns].assign(profundidade=float(centro)), clima_soc],
                                      axis=1).to_numpy(float)
                    razoes = [m.gbm(cfg.SEMENTE + rep).fit(x_tr, d[a].to_numpy()).predict(x_soc)
                              for a in cfg.ALVOS_TEXTURA]
                    camadas.append(np.column_stack(m.razoes_para_pct(*razoes)))
                textura = pd.DataFrame(np.mean(camadas, axis=0), columns=['areia_prev', 'silte_prev', 'argila_prev'],
                                       index=soc.index)
                # 3. RF de log(SOC)
                x = pd.concat([soc[cov_soc], clima_soc, textura], axis=1)
                te, tr = dob_soc == f, dob_soc != f
                med = x[tr].median()
                mod = m.rf(cfg.SEMENTE + rep).fit(x[tr].fillna(med).to_numpy(float), y[tr])
                pred[te] = mod.predict(x[te].fillna(med).to_numpy(float))
            linhas.append({'rep': rep, 'cenario': cen, 'n': int(aval.sum()), 'r2': m.r2(y[aval], pred[aval]),
                           'rmse': m.rmse(y[aval], pred[aval])})
            if rep == 0:
                s = soc[aval]
                oof.append(pd.DataFrame({'ponto_id': s.ponto_id, 'cenario': cen, 'longitude': s.longitude,
                                         'latitude': s.latitude, 'log_soc_obs': y[aval], 'log_soc_prev': pred[aval]}))
            print(f'  rep {rep + 1} {cen:15s} R² {linhas[-1]["r2"]:.3f}  {time.time() - t0:5.0f}s', flush=True)
        pd.DataFrame(linhas).to_csv(cfg.TABELAS / f'soc_repeticoes{cfg.SUFIXO}.csv', index=False)          # parcial
    pd.concat(oof).to_parquet(cfg.PONTOS / f'soc_oof{cfg.SUFIXO}.parquet', index=False)


if __name__ == '__main__':
    main()
