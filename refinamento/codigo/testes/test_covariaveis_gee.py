"""Validação local: seleção independente de erros e associação por chave."""
from pathlib import Path
import sys

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from codigo.covariaveis_gee import juntar_covariaveis, selecionar_mensais, utm_crs


def monthly():
    return pd.DataFrame({"station_id": "A", "latitude": -25, "longitude": -49,
        "elevation_m": 900, "month": range(13), "temperature_c": np.arange(13) + 10.0})


def test_selecao_exclui_anual_e_estacao_sem_12_meses():
    first = monthly()
    second = first.assign(station_id="B")
    second.loc[second.month == 12, "temperature_c"] = np.nan
    selected = selecionar_mensais(pd.concat([first, second]))
    assert len(selected) == 12
    assert set(selected.station_id) == {"A"}
    assert set(selected.month) == set(range(1, 13))


def test_coordenada_inconsistente_ou_chave_duplicada_falha():
    data = monthly()
    data.loc[data.month == 4, "latitude"] = -20
    with pytest.raises(ValueError, match="varia"):
        selecionar_mensais(data)
    with pytest.raises(ValueError, match="duplicada"):
        selecionar_mensais(pd.concat([monthly(), monthly()]))


def test_utm_e_associacao_de_bandas():
    assert utm_crs(-25, -49) == "EPSG:32722"
    assert utm_crs(3, -60) == "EPSG:32621"
    values = {"station_id": "A", "dem_elevation_m": 901, "coarse_elevation_m": 890, "slope_deg": 3}
    values.update({f"b{i}": 20 + i / 10 for i in range(1, 13)})
    merged = juntar_covariaveis(selecionar_mensais(monthly()), [values])
    assert merged.loc[merged.month == 10, "chelsa_c"].iloc[0] == 21
    assert len(merged) == 12
    values["b4"] = None
    with pytest.raises(ValueError, match="ausências"):
        juntar_covariaveis(selecionar_mensais(monthly()), [values])
