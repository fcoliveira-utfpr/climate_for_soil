# Reprodução dos modelos do MapBiomas Solo C3 com os climas CHELSA

Pergunta: trocando o Köppen IPEF por cada um dos nossos climas, as estimativas de **textura** e de **SOC**
do MapBiomas Solo (coleção 3) melhoram? E como ficam os mapas?

- **[reproducao_resultados.ipynb](reproducao_resultados.ipynb):** resultados, gráficos e mapas.
- `codigo/`: `config.py` (caminhos, cenários, parâmetros), `dados.py`, `modelagem.py`, `fase1_textura.py`,
  `fase1_soc.py`, `covariaveis_gee.py` (covariáveis do MapBiomas portadas para Python), `mapas_textura.py`,
  `mapas_soc.py`.
- `resultados/`: tabelas agregadas e figuras (versionadas).
- **`../dados_reproducao/`** (fora do git): dados por ponto (restritos), pilhas de covariáveis e os mapas
  gerados (GeoTIFF), que podem virar assets no GEE.

## Como o modelo do MapBiomas foi reproduzido

| | MapBiomas C3 | Aqui |
|---|---|---|
| Textura | GBM por alvo e por camada de 10 cm (horizontes a ±5 cm do centro), sobre ln((x+1)/(argila+1)); profundidade e textura da coleção 2 como covariáveis | igual, nas camadas de 0-30 cm (centros 5, 15, 25 cm); GBM do scikit-learn (400 iterações, taxa 0,01, 25 folhas) |
| SOC | random forest com a textura de 0-30 cm da coleção atual como covariável; estoque acumulado com a profundidade como covariável | igual; a textura vem do modelo de textura do mesmo cenário de clima; avaliação e mapas em 0-30 cm |
| Matriz de SOC | `c03_soc_v2025_11_26_trep` (pontos + covariáveis; sem acesso de leitura para esta conta) | os pontos da C3 (`ORIGINAIS/collection3/2025_11_26_soildata_soc_trep`, = SoilData doi 10.60502/SoilData/IUZOAK), `carbono_gm2_qmap`, sem pseudoamostras e sem as réplicas `trep`; covariáveis extraídas no GEE no ano de coleta (lista em `codigo/covariaveis_soc.txt`) |
| Clima | Köppen IPEF em dummies L1-L3 | 9 cenários (abaixo) |

Cenários: Köppen IPEF (referência), sem clima, Köppen CHELSA, Holdridge ETPM, Holdridge ETH, Thornthwaite CAD
100 mm, Thornthwaite CAD do solo, clima contínuo (12 variáveis CHELSA + BHC) e zonas climáticas k10.

**Fase 1** — validação cruzada em blocos espaciais de 2° (5 dobras × 3 repetições; mesmas dobras na textura e
no SOC; no SOC, a textura dos locais de teste vem de modelos que não viram os blocos de teste).
**Fase 2** — mapas de 0-30 cm numa grade de 0,05° (~5 km) alinhada ao CHELSA, com as covariáveis do centro de
cada pixel (as do MapBiomas, portadas em `covariaveis_gee.py`, conferidas contra a matriz) e o clima de 1 km.
SOC para 2023.

```bash
cd codigo
python dados.py            # GEE: matriz de textura, pontos de SOC C3 + covariáveis (horas; cache por ano), climas
python fase1_textura.py    # ~45 min
python fase1_soc.py        # ~1,5 h
python mapas_textura.py    # baixa as covariáveis (GEE) e gera os 9 mapas de textura
python mapas_soc.py        # idem para o SOC (2023)
```

Depende dos dados da análise solo-clima (`corelacao/codigo`, `corelacao/.local/`) e dos rasters CHELSA locais
(`climas/dados_chelsa/`).
