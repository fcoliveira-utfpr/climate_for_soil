# -*- coding: utf-8 -*-
"""Atualiza dados_chelsa.csv a partir dos recortes mensais do CHELSA em
climas/dados_chelsa/mensal_recortado, amostrando tas/pet/pr nas coordenadas das
estacoes ja presentes no arquivo (mesmas estacoes e mesmo periodo; so os valores
climaticos sao recalculados a partir dos dados baixados mais recentes).
"""
from pathlib import Path

import numpy as np
import pandas as pd
import rasterio

RAIZ = Path(__file__).resolve().parent
ARQUIVO_SAIDA = RAIZ / "dados_chelsa.csv"
RECORTADO_DIR = RAIZ.parent / "climas" / "dados_chelsa" / "mensal_recortado"

COLS_SAIDA = ["Nome", "UF", "Latitude", "Longitude", "Altitude", "Codigo",
              "ano", "mes", "tmed", "pr_mes", "etp_mes"]
VARIAVEIS = {"tas": "tmed", "pr": "pr_mes", "pet": "etp_mes"}
ANO_INICIO, ANO_FIM = 2010, 2019


def caminho_raster(var: str, ano: int, mes: int) -> Path:
    return RECORTADO_DIR / var / str(ano) / f"CHELSA_{var}_{mes:02d}_{ano}_brasil.tif"


def carregar_estacoes() -> pd.DataFrame:
    """Reaproveita a lista de estacoes (Codigo/Nome/UF/Lat/Lon/Altitude) do
    dados_chelsa.csv atual -- so os valores climaticos sao recalculados."""
    atual = pd.read_csv(ARQUIVO_SAIDA)
    return atual.drop_duplicates("Codigo")[
        ["Codigo", "Nome", "UF", "Latitude", "Longitude", "Altitude"]
    ].reset_index(drop=True)


def amostrar_variavel(var: str, estacoes: pd.DataFrame, ano: int, mes: int) -> np.ndarray:
    caminho = caminho_raster(var, ano, mes)
    if not caminho.exists():
        return np.full(len(estacoes), np.nan, dtype="float32")
    with rasterio.open(caminho) as src:
        pontos = list(zip(estacoes["Longitude"], estacoes["Latitude"]))
        return np.array([v[0] for v in src.sample(pontos)], dtype="float32")


def main():
    estacoes = carregar_estacoes()
    blocos = []
    for ano in range(ANO_INICIO, ANO_FIM + 1):
        for mes in range(1, 13):
            bloco = estacoes.copy()
            bloco["ano"] = ano
            bloco["mes"] = mes
            for var, col in VARIAVEIS.items():
                bloco[col] = amostrar_variavel(var, estacoes, ano, mes)
            blocos.append(bloco)

    resultado = pd.concat(blocos, ignore_index=True).reindex(columns=COLS_SAIDA)

    faltando = resultado["etp_mes"].isna().sum()
    if faltando:
        print(f"Aviso: {faltando} linhas sem etp_mes (pet tem meses faltantes "
              f"conhecidos na fonte CHELSA nesse periodo).")

    resultado.to_csv(ARQUIVO_SAIDA, index=False)
    print(f"Atualizado: {ARQUIVO_SAIDA} ({len(resultado)} linhas, "
          f"{estacoes.shape[0]} estacoes, {ANO_INICIO}-{ANO_FIM}).")


if __name__ == "__main__":
    main()
