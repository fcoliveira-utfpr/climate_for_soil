# -*- coding: utf-8 -*-
"""Calcula a normal climatológica 1991-2020 (média mensal, tolerante a anos faltantes)
para tas, pet e pr, e monta uma imagem GeoTIFF multibanda (12 bandas, uma por mês) para
cada variável -- um asset por variável no GEE, em vez de um único asset combinado.

Lê os recortes mensais do Brasil já gerados por baixar_recortar.py.
"""
import warnings
from pathlib import Path

import numpy as np
import rasterio

VARIAVEIS = ["tas", "pet", "pr"]
ANO_INICIO, ANO_FIM = 1991, 2020

DADOS_DIR = Path(__file__).resolve().parent.parent / "dados_chelsa"
RECORTADO_DIR = DADOS_DIR / "mensal_recortado"
SAIDA_DIR = DADOS_DIR / "normal_1991_2020"


def saida_path(var: str) -> Path:
    return SAIDA_DIR / f"chelsa_brasil_{var}_normal_1991_2020.tif"


def caminho_local(var: str, ano: int, mes: int) -> Path:
    return RECORTADO_DIR / var / str(ano) / f"CHELSA_{var}_{mes:02d}_{ano}_brasil.tif"


def media_mensal(var: str, mes: int, perfil_referencia: dict):
    """Média (ignorando ausências) de um mês, através dos anos 1991-2020, para uma variável.

    Acumula soma e contagem incrementalmente em vez de empilhar os 30 anos em memória
    (equivalente a nanmean, mas com pico de memória de ~1 grade em vez de 30 -- empilhar
    a grade inteira do Brasil por 30 anos passa de 2,8 GB e estourava em máquinas com
    menos RAM livre).
    """
    soma = None
    contagem = None
    n_anos = 0
    for ano in range(ANO_INICIO, ANO_FIM + 1):
        caminho = caminho_local(var, ano, mes)
        if not caminho.exists():
            continue
        with rasterio.open(caminho) as src:
            if perfil_referencia["shape"] is None:
                perfil_referencia["shape"] = src.shape
                perfil_referencia["transform"] = src.transform
                perfil_referencia["crs"] = src.crs
            dados = src.read(1)
        if soma is None:
            soma = np.zeros(dados.shape, dtype="float64")
            contagem = np.zeros(dados.shape, dtype="int32")
        valido = ~np.isnan(dados)
        soma[valido] += dados[valido]
        contagem += valido
        n_anos += 1

    if soma is None:
        print(f"  AVISO: nenhum arquivo para {var} mês {mes:02d} em {ANO_INICIO}-{ANO_FIM}; banda ficará toda NaN.")
        return None, 0, None

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", category=RuntimeWarning)  # pixels sem nenhum ano válido -> NaN
        media = np.where(contagem > 0, soma / contagem, np.nan)
    return media.astype("float32"), n_anos, contagem


def gerar_variavel(var: str):
    """Constrói e grava a imagem de 12 bandas (uma por mês) de uma única variável."""
    perfil_referencia = {"shape": None, "transform": None, "crs": None}
    bandas = []
    nomes_bandas = []
    resumo_anos = []

    for mes in range(1, 13):
        media, n_anos, n_validos = media_mensal(var, mes, perfil_referencia)
        bandas.append(media)
        nome_banda = f"{var}_{mes:02d}"
        nomes_bandas.append(nome_banda)
        resumo_anos.append((nome_banda, n_anos))
        if n_validos is not None:
            print(f"  {nome_banda}: média de {n_anos} anos "
                  f"(pixels com anos válidos: mín. {int(n_validos.min())}, máx. {int(n_validos.max())})")

    if perfil_referencia["shape"] is None:
        print(f"  AVISO: nenhum recorte mensal encontrado para '{var}' em dados_chelsa/mensal_recortado. "
              "Pulando esta variável.")
        return None

    bandas = [
        np.full(perfil_referencia["shape"], np.nan, dtype="float32") if b is None else b
        for b in bandas
    ]

    SAIDA_DIR.mkdir(parents=True, exist_ok=True)
    altura, largura = perfil_referencia["shape"]
    caminho = saida_path(var)
    perfil = {
        "driver": "GTiff",
        "height": altura,
        "width": largura,
        "count": len(bandas),
        "dtype": "float32",
        "crs": perfil_referencia["crs"],
        "transform": perfil_referencia["transform"],
        "nodata": np.nan,
        "compress": "deflate",
    }
    with rasterio.open(caminho, "w", **perfil) as dst:
        for i, (banda, nome) in enumerate(zip(bandas, nomes_bandas), start=1):
            dst.write(banda, i)
            dst.set_band_description(i, nome)

    print(f"  Imagem de '{var}' salva em: {caminho} ({len(bandas)} bandas)")
    return caminho, resumo_anos


def main():
    resultados = {}
    for var in VARIAVEIS:
        print(f"\n=== Variável: {var} ===")
        resultado = gerar_variavel(var)
        if resultado is not None:
            resultados[var] = resultado

    if not resultados:
        raise RuntimeError("Nenhum recorte mensal encontrado em dados_chelsa/mensal_recortado. "
                            "Rode baixar_recortar.py primeiro.")

    print("\nAnos usados por banda (min esperado: 30, pet pode ter menos):")
    for var, (_, resumo_anos) in resultados.items():
        for nome, n_anos in resumo_anos:
            marcador = "" if n_anos == (ANO_FIM - ANO_INICIO + 1) else "  <-- menos que 30 anos"
            print(f"  {nome}: {n_anos} anos{marcador}")

    print("\nUpload manual para o GEE, um asset por variável (referência, não executado por este script):")
    for var in resultados:
        print(f"  earthengine upload image "
              f"--asset_id=projects/SEU_PROJETO/assets/chelsa_brasil_{var}_normal_1991_2020 "
              f"gs://SEU_BUCKET/chelsa_brasil_{var}_normal_1991_2020.tif")


if __name__ == "__main__":
    main()
