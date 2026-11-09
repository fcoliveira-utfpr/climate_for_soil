"""Regressões para métricas, pareamento comum, cobertura e proteção de saída."""
from pathlib import Path
import sys

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from codigo.diagnostico_bases import BASES, carregar_painel, destino_local, diagnosticar
from codigo.metricas import metricas


def test_metricas_contra_calculo_manual():
    resultado = metricas([1, 2, 3], [2, 3, 4])
    esperado = dict(n=3, bias=1, mae=1, rmse=1, r=1, nse=-0.5, pbias=50, d=8/11, kge=0.5)
    assert resultado == pytest.approx(esperado)


def test_metricas_removem_nao_finitos_pareados_e_preservam_indefinidos():
    resultado = metricas([1, 2, np.nan, 4], [1, 2, 3, np.inf])
    assert resultado["n"] == 2
    assert resultado["rmse"] == 0
    constante = metricas([0, 0], [0, 0])
    assert constante["rmse"] == 0
    for nome in ("r", "nse", "pbias", "d", "kge"):
        assert np.isnan(constante[nome])
    assert metricas([], [])["n"] == 0
    with pytest.raises(ValueError):
        metricas([1, 2], [1])


def _painel():
    tabela = pd.DataFrame({"codigo": [f"A{i}" for i in range(6)], "ano": 2010,
        "mes": 1, "UF": "XX", "observado": np.arange(6) + 20,
        "fracao_dias_validos": [0.7, 0.8, 0.9, 1, 1, 1]})
    for base in BASES:
        tabela[base] = tabela.observado + 1
    return tabela


def test_cobertura_inclusiva_e_supressao_grupos_pequenos():
    resultados, auditoria = diagnosticar(_painel())
    globais = resultados.loc[resultados.escopo == "global"]
    assert set(globais.cobertura_min) == {0.7, 0.8}
    assert set(globais.loc[globais.cobertura_min == 0.8, "n"]) == {5}
    omitido = auditoria.loc[(auditoria.escopo == "global") & (auditoria.cobertura_min == 0.9)].iloc[0]
    assert omitido.n_estacoes == 4
    assert not omitido.metricas_publicadas


def test_ausencia_em_uma_grade_remove_o_par_de_todas():
    painel = _painel()
    painel.loc[0, "xavier"] = np.nan
    resultados, auditoria = diagnosticar(painel, coberturas=(0.7,))
    assert set(resultados.n) == {5}
    assert set(resultados.rmse) == {1}
    assert auditoria.loc[auditoria.escopo == "global", "n_excluidas_grades"].iloc[0] == 1


def test_todos_os_grupos_pequenos_geram_apenas_auditoria():
    resultados, auditoria = diagnosticar(_painel().iloc[:3])
    assert resultados.empty
    assert "rmse" in resultados.columns
    assert not auditoria.metricas_publicadas.any()


def test_saida_fora_da_pasta_rejeitada():
    with pytest.raises(ValueError, match="refinamento"):
        destino_local(Path(__file__).resolve().parents[3] / "saida_invalida")


def test_leitura_chaves_e_rejeicao_duplicata(tmp_path):
    obs = pd.DataFrame({"ano_mes": ["2010-01", "2010-02"], "codigo": [" a1 ", "A1"],
        "uf": "XX", "Tmed_media": [20, 21], "T_dias_validos": [31, 28], "dias_no_mes": [31, 28]})
    obs.to_csv(tmp_path / "mensal_todas_estacoes.csv", index=False)
    grade = pd.DataFrame({"Codigo": ["A1", "A1"], "ano": [2010.0, 2010.0],
        "mes": [2.0, 1.0], "tmed": [22, 21], "Latitude": -23, "Longitude": -45, "Altitude": 10})
    for arquivo in BASES.values():
        grade.to_csv(tmp_path / arquivo, index=False)
    painel = carregar_painel(tmp_path)
    assert list(painel.chelsa) == [21, 22]
    assert list(painel.codigo) == ["A1", "A1"]
    pd.concat([grade, grade.iloc[:1]]).to_csv(tmp_path / BASES["xavier"], index=False)
    with pytest.raises(ValueError, match="duplicada"):
        carregar_painel(tmp_path)
