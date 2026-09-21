# Assets utilizados

## Earth Engine — consultados diretamente pelo código

| Asset | O que é |
| --- | --- |
| `projects/mapbiomas-workspace/SOLOS/AMOSTRAS/MATRIZES/collection3/matriz-collection3_carbon_datac2v2` | Estoque de carbono orgânico do solo (`soc_stock_g_m2`) por ponto, com Köppen L1/L2/L3 já em dummy |
| `projects/mapbiomas-workspace/SOLOS/AMOSTRAS/MATRIZES/collection3/c03_psd_v2025_11_18` | Areia/silte/argila medidas em laboratório (g/kg) por ponto, com Köppen L1/L2/L3 já em dummy |
| `projects/mapbiomas-brazil/assets/SOIL/COVARIATES/holdridge_lifezones_chelsa-v2026` | Holdridge (HLZ_L1/L2), banda `zone38_id`, legenda documentada na própria descrição do asset (CHELSA V2.1) — amostrado nas coordenadas de cada ponto das duas matrizes acima |

## De onde vem o Köppen

As duas matrizes de treino já trazem Köppen L1/L2/L3 embutido como dummy — o código só decodifica
essas colunas (`codigo/preparar_dados.py:decodificar_koppen`), sem consultar nenhum asset de Köppen à
parte. A fonte original dessas dummies, segundo o próprio nome das colunas, é
`IPEF_2013_KOPPEN_100M_2025`.

## Acesso

As duas matrizes de treino são assets privados do MapBiomas — acesso liberado para a conta usada aqui,
não é acesso público. `holdridge_lifezones_chelsa-v2026` é acessível à mesma conta.
