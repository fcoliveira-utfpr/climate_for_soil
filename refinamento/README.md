# Downscaling do CHELSA (~1 km) para 30 m

Objetivo: gerar temperatura, chuva e ETP em 30 m a partir do CHELSA (que já temos), sem
depender de interpolação simples. Baseado em Xavier et al. (2016, joc.4518 — IDW/ADW são os
melhores interpoladores pro Brasil) e Xavier et al. (2022, joc.7731 — melhoraram Tmax/Tmin
incorporando elevação + lapse rate).

## Temperatura — [temperatura_gee.py](temperatura_gee.py)

Correção por elevação (lapse rate), sem depender de estação:

```
T_30m = T_CHELSA(reamostrada bilinear p/ 30m) + lapse_rate x (elev_efetiva_do_CHELSA − elev_real_30m)
```

`elev_efetiva_do_CHELSA` é o DEM de 30 m (NASADEM) agregado por média na grade nativa do CHELSA — a
altitude que a temperatura de ~1 km já reflete implicitamente. A correção só entra na diferença entre
essa elevação e a elevação real de cada pixel fino.

**Validado contra as 25 estações de `validacao/`** (script em `validacao_temperatura.csv`, gerado
comparando `tmed` observado 2010-2019 vs. CHELSA bilinear puro vs. CHELSA + correção):

- Funciona muito bem no caso que mais importa: **Pico do Couto (A610, 1777 m)** — RMSE caiu de
  1,37 °C para 0,21 °C. É exatamente o cenário do downscaling: pico isolado onde a célula de ~1 km
  mistura terreno mais baixo ao redor.
- No conjunto das 25 estações, ganho pequeno (RMSE 0,943→0,929 °C; MAE 0,765→0,740 °C) e o viés
  piorou (0,21→0,31 °C, mais quente).
- Calibrei o lapse rate com as próprias 25 estações (regressão sem intercepto): deu **−4,4 °C/km**
  em vez do padrão −6,5, mas quase não mudou o resultado agregado (RMSE 0,925). Correlação entre
  diferença de elevação e erro do CHELSA é fraca (0,31) — na maioria das estações o erro do CHELSA
  não vem principalmente de má representação de elevação (pode ser viés do modelo, microclima,
  período diferente da observação etc.).

**Conclusão inicial (25 estações)**: o método está correto e vale a pena em relevo forte/pontos
isolados, mas 25 estações não bastam pra calibrar o lapse rate com confiança.

### Dados observados do próprio Xavier (`dados_observados_xavier/`, fora do git)

O usuário achou os dados brutos de estação que o Xavier et al. (2022) usaram pra montar a grade
melhorada — direto do autor (Google Drive, ver README_Observed_Data.txt): `Tmax.npz`, `Tmin.npz`,
`RH.npz`, `Rs.npz`, `u2.npz` (1194 estações) e `pr.npz` (**14.170 pluviômetros**, altitude até
2450 m), diário, 1961-2025. Formato: `data` (dias x estações), `lat_lon_alt`, `ID` (mesmos códigos
INMET tipo A001, e também códigos numéricos OMM de estações convencionais).

**Refiz a validação de temperatura com 255 estações** (as com boa cobertura no período 1991-2020:
`climatologia_temp_estacoes.csv`, `estacoes_temp_metadata.csv`,
`validacao_temperatura_255estacoes.csv`):

- RMSE 0,831→0,817 °C, MAE 0,696→0,682 °C, viés −0,491→−0,466 °C — melhora pequena mas consistente
  (diferente do teste com 25, onde o viés piorava).
- Correlação entre diferença de elevação e erro do CHELSA: **0,05 — praticamente nula.**
  Testei se era bug no `reduceResolution` (`maxPixels` baixo demais pra cobrir os ~1111 sub-pixels
  de 30 m numa célula de 1 km); corrigi pra 4096, resultado **idêntico** — não era isso.
- Conclusão que se mantém: a correção ajuda muito em pontos extremos isolados (tipo Pico do Couto),
  mas no grosso da distribuição a elevação não explica o erro do CHELSA — deve ser viés do modelo,
  microclima, período diferente etc. O ganho agregado de RMSE vem dos poucos pontos extremos, não
  de uma relação geral.

**Próximo passo em aberto**: com 255 estações e correlação ~0, não acho que vale a pena investir
mais em calibrar o lapse rate por enquanto — o retorno é baixo fora dos casos extremos. Se quiser
retomar, o caminho seria regionalizar (lapse rate por bioma/região, não um valor único pro Brasil)
ou aceitar a limitação e focar esforço em chuva, que tem uma base de dados muito mais rica agora.

## Chuva

Depende de estação (não tem atalho de terreno confiável tipo lapse rate). Agora com
**14.170 pluviômetros** (`pr.npz`) em vez de precisar buscar no INMET — base excelente.

Plano: razão estação/CHELSA por mês, interpolada por IDW ou ADW (os dois validados pelo Xavier et
al. 2016 como melhores pro Brasil), aplicada como correção multiplicativa sobre o CHELSA em 30 m.
Ainda não iniciado.

## ETP — não iniciado

Recalcular via Penman-Monteith a partir da temperatura já corrigida + demais variáveis do CHELSA.

## Escala

Uma grade nacional em 30 m é ~1400x mais pixels que a de 1 km do CHELSA — inviável baixar local
como fizemos com Holdridge/Köppen/Thornthwaite. Validação usa só os pontos das estações (barato).
Se/quando o produto final for gerado pro Brasil inteiro, deve ir direto como asset no GEE
(`Export.image.toAsset`), não como GeoTIFF local.
