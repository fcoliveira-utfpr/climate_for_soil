# Qual clima usar como base para estimar SOC e textura do solo

Comparação de classificações climáticas CHELSA (Köppen, Holdridge, Thornthwaite) como base para estimar
carbono orgânico (SOC) e textura (areia, silte, argila) do solo em 0-30 cm, com o Köppen IPEF das
matrizes do MapBiomas Solo C3 como referência. Métrica: R² fora da amostra com validação em blocos
espaciais.

- **[comparacao_climas.ipynb](comparacao_climas.ipynb):** qual classificação climática sozinha explica melhor
  SOC e textura (método, resultados e interpretação).
- **[experimento_clima_modelos.ipynb](experimento_clima_modelos.ipynb):** o que pôr no lugar do Köppen nos
  modelos do MapBiomas Solo (clima contínuo, zonas climáticas homogêneas, estratificação).
- `codigo/`: `preparar_dados.py` (GEE), `comparar_climas.py` (métricas), `legendas.py`, testes;
  `experimento_dados.py`, `zonas_clima.py`, `experimento_modelos.py` (experimento dos modelos).
- `resultados/tabelas/`: resultados agregados. Os dados por ponto são restritos e ficam em `.local/`
  (fora do git).
- `docs/memoria_fabricio.md`: registro do que foi feito e decidido.

```bash
python -m pip install -r requirements.txt
python codigo/preparar_dados.py     # exige a conta GEE com acesso às matrizes do MapBiomas
python codigo/comparar_climas.py
python codigo/experimento_dados.py && (cd codigo && python -c "import zonas_clima as z; z.main(ks=(10, 15))")
python codigo/experimento_modelos.py   # ~75 min
python -m pytest codigo
```

## Assets utilizados

Todos são assets do Google Earth Engine. Os do MapBiomas têm acesso restrito (liberado para a conta
`fcoliveira`); os do projeto `fcoliveira` são gerados em `climas/chelsa_climas_brasil/`.

**Dados de solo (MapBiomas Solo, coleção 3):**

| Asset | O que é |
|---|---|
| `projects/mapbiomas-workspace/SOLOS/AMOSTRAS/MATRIZES/collection3/matriz-collection3_carbon_datac2v2` | Matriz de treino do modelo de carbono: estoque de SOC por ponto e ano, com as covariáveis do MapBiomas e o Köppen IPEF em dummies (a referência) |
| `projects/mapbiomas-workspace/SOLOS/AMOSTRAS/MATRIZES/collection3/c03_psd_v2025_11_18` | Matriz de treino do modelo de textura: areia, silte e argila (g/kg) por ponto e profundidade, com as mesmas covariáveis e o Köppen IPEF |

**Clima CHELSA V2.1, normal 1991-2020 (~1 km):**

| Asset | O que é |
|---|---|
| `projects/fcoliveira/assets/chelsa_brasil_tas_normal_1991_2020` | Temperatura média mensal (12 bandas, °C) |
| `projects/fcoliveira/assets/chelsa_brasil_pr_normal_1991_2020` | Precipitação mensal (12 bandas, mm) |
| `projects/fcoliveira/assets/chelsa_brasil_pet_normal_1991_2020` | ETP de Penman-Monteith mensal (12 bandas, mm) |
| `projects/fcoliveira/assets/Koppen_CHELSA_BR_1991_2020` | Köppen-Geiger (Alvares et al. 2013; sazonalidade C por Kottek et al. 2006), id da classe 1-31 |
| `projects/fcoliveira/assets/Holdridge_CHELSA_BR_1991_2020_ETPM` | Zonas de vida de Holdridge (38 zonas, numeração de Jungkunst et al. 2021), razão ETP/P com a ETP de Penman-Monteith |
| `projects/fcoliveira/assets/Holdridge_CHELSA_BR_1991_2020_ETH` | Idem, com a ETP de Holdridge (58,93 × biotemperatura) |
| `projects/fcoliveira/assets/Thornthwaite_CHELSA_BR_1991_2020_CAD100` | Thornthwaite (1948) com balanço hídrico de CAD 100 mm; 10 bandas: umidade, subtipo, térmica, concentração, ETP, DEF, EXC, Ih, Ia, Im |
| `projects/fcoliveira/assets/Thornthwaite_CHELSA_BR_1991_2020_CADsolo` | Idem, com CAD do solo (AWC × 1000 × 1 m) |

**Usado indiretamente** (na geração do Thornthwaite CAD do solo, não pelo código daqui):
`projects/fcoliveira/assets/AWC_br` — polígonos de solo com a água disponível (AWC, m³/m³).

**Arquivos locais** (não são assets; ficam em `climas/dados_chelsa/`, fora do git): as mesmas normais
CHELSA e o Thornthwaite CAD 100 mm em GeoTIFF, lidos por `zonas_clima.py` para ajustar e mapear as zonas
climáticas homogêneas (`zonas/zonas_climaticas_k10.tif`, que pode virar asset).
