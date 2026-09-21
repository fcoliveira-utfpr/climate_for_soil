# -*- coding: utf-8 -*-
"""Baixa e recorta para o Brasil os arquivos mensais do CHELSA V2.1 (tas, pet, pr),
para o período 1991-2020, sem baixar os GeoTIFFs globais inteiros.

Lê apenas a janela de pixels correspondente ao bbox do Brasil (via /vsicurl/, aproveitando
o tiling COG dos arquivos remotos), aplica nodata e escala/offset embutidos em cada arquivo,
converte tas para Celsius, e grava GeoTIFFs float32 recortados localmente.

Também grava um manifesto (dados_chelsa/manifesto_arquivos.csv) com o status de cada
combinação variável/ano/mês, já que pet tem meses faltantes na fonte.
"""
import csv
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import numpy as np
import rasterio
import requests
from rasterio.windows import from_bounds
from tqdm import tqdm

VARIAVEIS = ["tas", "pet", "pr"]
ANO_INICIO, ANO_FIM = 1991, 2020
BASE_URL = "https://os.unil.cloud.switch.ch/chelsa02/chelsa/global/monthly/{var}/{ano}/CHELSA_{var}_{mes:02d}_{ano}_V.2.1.tif"

# Bbox do Brasil (WGS84, graus decimais) - retangular, com pequena margem
BRASIL_OESTE, BRASIL_SUL, BRASIL_LESTE, BRASIL_NORTE = -74.0, -34.0, -28.5, 5.5

DADOS_DIR = Path(__file__).resolve().parent.parent / "dados_chelsa"
RECORTADO_DIR = DADOS_DIR / "mensal_recortado"
MANIFESTO_PATH = DADOS_DIR / "manifesto_arquivos.csv"

MAX_TENTATIVAS = 3
N_THREADS = 6


def url_remota(var: str, ano: int, mes: int) -> str:
    return BASE_URL.format(var=var, ano=ano, mes=mes)


def caminho_local(var: str, ano: int, mes: int) -> Path:
    return RECORTADO_DIR / var / str(ano) / f"CHELSA_{var}_{mes:02d}_{ano}_brasil.tif"


def arquivo_existe_remoto(url: str) -> bool:
    for tentativa in range(MAX_TENTATIVAS + 2):
        try:
            r = requests.head(url, timeout=20)
            if r.status_code == 200:
                return True
            if r.status_code == 404:
                return False
        except requests.RequestException:
            pass
        time.sleep(2 * (tentativa + 1))
    raise RuntimeError(f"Não foi possível verificar {url} (erros temporários repetidos)")


def recortar_arquivo(var: str, ano: int, mes: int, url: str) -> str:
    """Baixa apenas a janela do Brasil e grava o GeoTIFF recortado localmente.

    Retorna 'ok', 'ja_existe' ou 'erro:<msg>'.
    """
    destino = caminho_local(var, ano, mes)
    if destino.exists():
        return "ja_existe"

    vsicurl_url = "/vsicurl/" + url
    for tentativa in range(MAX_TENTATIVAS):
        try:
            with rasterio.open(vsicurl_url) as src:
                window = from_bounds(
                    BRASIL_OESTE, BRASIL_SUL, BRASIL_LESTE, BRASIL_NORTE, transform=src.transform
                )
                dados_brutos = src.read(1, window=window)
                transform_janela = src.window_transform(window)
                nodata = src.nodata
                scale = src.scales[0]
                offset = src.offsets[0]

            dados = dados_brutos.astype("float32")
            mascara = dados_brutos == nodata
            dados = dados * scale + offset
            if var == "tas":
                dados = dados - 273.15  # Kelvin -> Celsius
            dados[mascara] = np.nan

            destino.parent.mkdir(parents=True, exist_ok=True)
            perfil = {
                "driver": "GTiff",
                "height": dados.shape[0],
                "width": dados.shape[1],
                "count": 1,
                "dtype": "float32",
                "crs": "EPSG:4326",
                "transform": transform_janela,
                "nodata": np.nan,
                "compress": "deflate",
            }
            with rasterio.open(destino, "w", **perfil) as dst:
                dst.write(dados, 1)
                dst.set_band_description(1, f"{var}_{mes:02d}_{ano}")

            return "ok"
        except Exception as exc:  # noqa: BLE001 - queremos registrar qualquer falha e seguir
            if tentativa == MAX_TENTATIVAS - 1:
                return f"erro:{exc}"
            time.sleep(1 + tentativa)
    return "erro:tentativas_esgotadas"


def montar_lista_tarefas():
    tarefas = []
    for var in VARIAVEIS:
        for ano in range(ANO_INICIO, ANO_FIM + 1):
            for mes in range(1, 13):
                tarefas.append((var, ano, mes, url_remota(var, ano, mes)))
    return tarefas


def main():
    tarefas = montar_lista_tarefas()
    print(f"Verificando disponibilidade remota de {len(tarefas)} arquivos...")

    linhas_manifesto = []
    tarefas_disponiveis = []
    with ThreadPoolExecutor(max_workers=N_THREADS) as executor:
        futuros = {
            executor.submit(arquivo_existe_remoto, url): (var, ano, mes, url)
            for var, ano, mes, url in tarefas
        }
        for futuro in tqdm(as_completed(futuros), total=len(futuros), desc="Checando URLs"):
            var, ano, mes, url = futuros[futuro]
            existe = futuro.result()
            linhas_manifesto.append(
                {"variavel": var, "ano": ano, "mes": mes, "encontrado": existe, "url": url}
            )
            if existe:
                tarefas_disponiveis.append((var, ano, mes, url))

    DADOS_DIR.mkdir(parents=True, exist_ok=True)
    linhas_manifesto.sort(key=lambda r: (r["variavel"], r["ano"], r["mes"]))
    with open(MANIFESTO_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["variavel", "ano", "mes", "encontrado", "url"])
        writer.writeheader()
        writer.writerows(linhas_manifesto)

    print(f"\nManifesto salvo em {MANIFESTO_PATH}")
    for var in VARIAVEIS:
        total = sum(1 for r in linhas_manifesto if r["variavel"] == var)
        encontrados = sum(1 for r in linhas_manifesto if r["variavel"] == var and r["encontrado"])
        print(f"  {var}: {encontrados}/{total} arquivos encontrados na fonte")

    print(f"\nRecortando {len(tarefas_disponiveis)} arquivos para o Brasil...")
    resultados = {"ok": 0, "ja_existe": 0, "erro": 0}
    erros = []
    with ThreadPoolExecutor(max_workers=N_THREADS) as executor:
        futuros = {
            executor.submit(recortar_arquivo, var, ano, mes, url): (var, ano, mes)
            for var, ano, mes, url in tarefas_disponiveis
        }
        for futuro in tqdm(as_completed(futuros), total=len(futuros), desc="Recortando"):
            var, ano, mes = futuros[futuro]
            status = futuro.result()
            if status.startswith("erro"):
                resultados["erro"] += 1
                erros.append((var, ano, mes, status))
            else:
                resultados[status] += 1

    print(f"\nConcluído: {resultados['ok']} baixados, {resultados['ja_existe']} já existiam, "
          f"{resultados['erro']} com erro.")
    if erros:
        print("Arquivos com erro:")
        for var, ano, mes, status in erros:
            print(f"  {var} {ano}-{mes:02d}: {status}")


if __name__ == "__main__":
    main()
