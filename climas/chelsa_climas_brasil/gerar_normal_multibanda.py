# -*- coding: utf-8 -*-
"""Calcula a normal climatológica 1991-2020 (média mensal, tolerante a anos faltantes)
para tas, pet e pr, e monta uma única imagem GeoTIFF multibanda (36 bandas: 3 variáveis x 12 meses).

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
SAIDA_PATH = SAIDA_DIR / "chelsa_brasil_normal_1991_2020.tif"


def caminho_local(var: str, ano: int, mes: int) -> Path:
    return RECORTADO_DIR / var / str(ano) / f"CHELSA_{var}_{mes:02d}_{ano}_brasil.tif"


def media_mensal(var: str, mes: int, perfil_referencia: dict):
    """Média (ignorando ausências) de um mês, através dos anos 1991-2020, para uma variável."""
    pilha = []
    for ano in range(ANO_INICIO, ANO_FIM + 1):
        caminho = caminho_local(var, ano, mes)
        if not caminho.exists():
            continue
        with rasterio.open(caminho) as src:
            if perfil_referencia["shape"] is None:
                perfil_referencia["shape"] = src.shape
                perfil_referencia["transform"] = src.transform
                perfil_referencia["crs"] = src.crs
            pilha.append(src.read(1))

    if not pilha:
        print(f"  AVISO: nenhum arquivo para {var} mês {mes:02d} em {ANO_INICIO}-{ANO_FIM}; banda ficará toda NaN.")
        return None, 0, None

    empilhado = np.stack(pilha, axis=0)
    n_validos = np.sum(~np.isnan(empilhado), axis=0)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", category=RuntimeWarning)  # pixels sem nenhum ano válido -> NaN
        media = np.nanmean(empilhado, axis=0)
    return media.astype("float32"), len(pilha), n_validos


def main():
    perfil_referencia = {"shape": None, "transform": None, "crs": None}
    bandas = []
    nomes_bandas = []
    resumo_anos = []

    for var in VARIAVEIS:
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
        raise RuntimeError("Nenhum recorte mensal encontrado em dados_chelsa/mensal_recortado. "
                            "Rode baixar_recortar.py primeiro.")

    bandas = [
        np.full(perfil_referencia["shape"], np.nan, dtype="float32") if b is None else b
        for b in bandas
    ]

    SAIDA_DIR.mkdir(parents=True, exist_ok=True)
    altura, largura = perfil_referencia["shape"]
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
    with rasterio.open(SAIDA_PATH, "w", **perfil) as dst:
        for i, (banda, nome) in enumerate(zip(bandas, nomes_bandas), start=1):
            dst.write(banda, i)
            dst.set_band_description(i, nome)

    print(f"\nImagem multibanda salva em: {SAIDA_PATH}")
    print(f"Total de bandas: {len(bandas)}")
    print("\nAnos usados por banda (min esperado: 30, pet pode ter menos):")
    for nome, n_anos in resumo_anos:
        marcador = "" if n_anos == (ANO_FIM - ANO_INICIO + 1) else "  <-- menos que 30 anos"
        print(f"  {nome}: {n_anos} anos{marcador}")

    print("\nUpload manual para o GEE (referência, não executado por este script):")
    print("  earthengine upload image --asset_id=projects/SEU_PROJETO/assets/chelsa_brasil_normal_1991_2020 "
          "gs://SEU_BUCKET/chelsa_brasil_normal_1991_2020.tif")


if __name__ == "__main__":
    main()
