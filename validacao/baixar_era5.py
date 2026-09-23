# -*- coding: utf-8 -*-
"""Baixa temperatura media (2m) e precipitacao mensal do ERA5-Land direto do
Earth Engine, nas coordenadas das estacoes, e grava dados_era5.csv no mesmo
formato das outras bases de referencia (Nome/UF/Lat/Lon/Altitude/Codigo/ano/mes/
tmed/pr_mes). Sem etp_mes: essa comparacao usa so temperatura e precipitacao.
"""
from pathlib import Path

import ee
import pandas as pd

RAIZ = Path(__file__).resolve().parent
ARQUIVO_ESTACOES = RAIZ / "dados_chelsa.csv"  # so para reaproveitar a lista de estacoes
ARQUIVO_SAIDA = RAIZ / "dados_era5.csv"

PROJETO = "fcoliveira"
ANO_INICIO, ANO_FIM = 2010, 2019
COLECAO = "ECMWF/ERA5_LAND/MONTHLY_AGGR"
ESCALA_M = 11132  # resolucao nativa do ERA5-Land (~0.1 grau)


def carregar_estacoes() -> pd.DataFrame:
    df = pd.read_csv(ARQUIVO_ESTACOES)
    return df.drop_duplicates("Codigo")[
        ["Codigo", "Nome", "UF", "Latitude", "Longitude", "Altitude"]
    ].reset_index(drop=True)


def main():
    ee.Initialize(project=PROJETO)
    estacoes = carregar_estacoes()
    pontos = ee.FeatureCollection([
        ee.Feature(ee.Geometry.Point([lon, lat]), {"Codigo": cod})
        for cod, lat, lon in zip(estacoes["Codigo"], estacoes["Latitude"], estacoes["Longitude"])
    ])

    col = ee.ImageCollection(COLECAO).select(["temperature_2m", "total_precipitation_sum"])

    linhas = []
    for ano in range(ANO_INICIO, ANO_FIM + 1):
        for mes in range(1, 13):
            ini = ee.Date.fromYMD(ano, mes, 1)
            img = col.filterDate(ini, ini.advance(1, "month")).first()
            amostras = img.sampleRegions(collection=pontos, scale=ESCALA_M).getInfo()
            for f in amostras["features"]:
                p = f["properties"]
                linhas.append({
                    "Codigo": p["Codigo"],
                    "ano": ano,
                    "mes": mes,
                    "tmed": p["temperature_2m"] - 273.15,
                    "pr_mes": p["total_precipitation_sum"] * 1000,
                })
            print(f"  {ano}-{mes:02d} ok")

    dados = pd.DataFrame(linhas).merge(estacoes, on="Codigo")
    dados = dados.reindex(columns=["Nome", "UF", "Latitude", "Longitude", "Altitude",
                                    "Codigo", "ano", "mes", "tmed", "pr_mes"])
    dados.to_csv(ARQUIVO_SAIDA, index=False)
    print(f"\nSalvo: {ARQUIVO_SAIDA} ({len(dados)} linhas, {estacoes.shape[0]} estacoes, "
          f"{ANO_INICIO}-{ANO_FIM}).")


if __name__ == "__main__":
    main()
