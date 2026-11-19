#!/bin/bash
# Retoma a predição dos mapas de 1 km (koppen_ipef + sem_clima, 1985-2024) e, ao fim, gera os GeoTIFFs.
# Retomável: pula anos já preditos e mapas já gerados; o ano interrompido é refeito do início.
# Uso: bash climas/mapas_1km/codigo/retomar.sh   (roda em segundo plano; log em climas/dados_mapas_1km/prever.log)
cd "$(dirname "$0")" || exit 1
PY=../../chelsa_climas_brasil/.venv/bin/python
LOG=../../dados_mapas_1km/prever.log
nohup caffeinate -i -s bash -c "
  echo \"=== retomada \$(date) ===\"
  Rscript prever_1km.R koppen_ipef,sem_clima 1985 2024
  for c in koppen_ipef sem_clima; do $PY rasterizar.py \$c 1985 2024; done
  echo \"=== fim \$(date) ===\"
" >> "$LOG" 2>&1 &
echo "rodando (pid $!); acompanhar: tail -f climas/dados_mapas_1km/prever.log"
