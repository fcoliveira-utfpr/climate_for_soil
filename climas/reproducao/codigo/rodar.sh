#!/usr/bin/env bash
# Roda as etapas da reprodução em sequência. Uso: ./rodar.sh [etapa ...]
#   etapas: textura soc mapas_textura mapas_soc (padrão: todas)
# Variante sem a textura da coleção 2: REPRODUCAO_SEM_C2=1 ./rodar.sh
# Logs em climas/dados_reproducao/<etapa>[_semC2].log
set -euo pipefail
cd "$(dirname "$0")"
PY=../../chelsa_climas_brasil/.venv/bin/python
LOGS=../../dados_reproducao
SUF=""; [[ "${REPRODUCAO_SEM_C2:-}" == "1" ]] && SUF="_semC2"
ETAPAS=("${@:-textura soc mapas_textura mapas_soc}")
for e in ${ETAPAS[@]}; do
  case $e in
    textura)       cmd="fase1_textura.py" ;;
    soc)           cmd="fase1_soc.py" ;;
    mapas_textura) cmd="mapas_textura.py mapas" ;;
    mapas_soc)     cmd="mapas_soc.py mapas" ;;
    *) echo "etapa desconhecida: $e"; exit 1 ;;
  esac
  echo "$(date '+%H:%M') início: $e$SUF"
  $PY -u $cmd > "$LOGS/$e$SUF.log" 2>&1
  echo "$(date '+%H:%M') fim: $e$SUF"
done
