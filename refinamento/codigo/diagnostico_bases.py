"""C1 exploratório: quatro grades nos mesmos pares estação/mês de 2010–2019.

Não estima a normal 1991–2020 nem seleciona modelos. A definição física de
Tmed_media permanece pendente: média horária, compensada ou de extremos.
Métricas são descritivas, sem independência demonstrada das estações em
relação aos dados usados para produzir as grades.

Execução a partir de refinamento/: python -B codigo/diagnostico_bases.py
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

try:
    from .metricas import metricas
except ImportError:
    from metricas import metricas

RAIZ = Path(__file__).resolve().parents[1]
CHAVE = ["codigo", "ano", "mes"]
BASES = {
    "chelsa": "dados_chelsa.csv",
    "xavier": "dados_xavier_estacoes_1991_2020.csv",
    "era5": "dados_era5.csv",
    "terraclimate": "dados_terraclimate.csv",
}
COBERTURAS = (0.7, 0.8, 0.9)
COLUNAS_RESULTADO = ["periodo", "cobertura_min", "escopo", "grupo", "base", "n_estacoes",
                     "bias", "rmse", "mae", "r", "nse", "pbias", "d", "kge", "n"]


def _chaves_validas(tabela: pd.DataFrame, nome: str) -> None:
    if tabela[CHAVE].isna().any().any() or tabela["codigo"].eq("").any():
        raise ValueError(f"{nome}: chave ausente.")
    if tabela.duplicated(CHAVE).any():
        raise ValueError(f"{nome}: chave estação/ano/mês duplicada.")
    if not tabela["mes"].between(1, 12).all():
        raise ValueError(f"{nome}: mês inválido.")


def carregar_painel(fontes: Path) -> pd.DataFrame:
    """Lê CSV sem modificar as fontes; mantém ausências para auditoria."""
    obs = pd.read_csv(fontes / "mensal_todas_estacoes.csv", dtype={"codigo": "string"})
    obs["codigo"] = obs["codigo"].str.strip().str.upper()
    datas = pd.to_datetime(obs["ano_mes"], format="%Y-%m", errors="raise")
    obs["ano"], obs["mes"] = datas.dt.year, datas.dt.month
    _chaves_validas(obs, "observações")
    obs = obs.loc[obs["ano"].between(2010, 2019)].copy()
    obs = obs.rename(columns={"uf": "UF", "Tmed_media": "observado"})
    for coluna in ("observado", "T_dias_validos", "dias_no_mes"):
        obs[coluna] = pd.to_numeric(obs[coluna], errors="raise")
    dias_calendario = pd.to_datetime(dict(year=obs.ano, month=obs.mes, day=1)).dt.days_in_month
    if not obs["dias_no_mes"].eq(dias_calendario).all():
        raise ValueError("dias_no_mes difere do calendário.")
    dias = obs["T_dias_validos"]
    if (dias.isna() | (dias < 0) | (dias > obs["dias_no_mes"]) | (dias % 1 != 0)).any():
        raise ValueError("Contagem inválida de dias observados.")
    obs["fracao_dias_validos"] = dias / obs["dias_no_mes"]
    painel = obs[CHAVE + ["UF", "observado", "T_dias_validos", "dias_no_mes", "fracao_dias_validos"]]
    for base, arquivo in BASES.items():
        grade = pd.read_csv(fontes / arquivo, dtype={"Codigo": "string"}).rename(columns={"Codigo": "codigo", "tmed": base})
        grade["codigo"] = grade["codigo"].str.strip().str.upper()
        for coluna in ("ano", "mes"):
            valores = pd.to_numeric(grade[coluna], errors="raise")
            if valores.isna().any() or (valores % 1 != 0).any():
                raise ValueError(f"{base}: {coluna} deve ser inteiro.")
            grade[coluna] = valores.astype(int)
        _chaves_validas(grade, base)
        grade[base] = pd.to_numeric(grade[base], errors="raise")
        colunas = CHAVE + [base]
        if base == "chelsa":
            colunas += ["Latitude", "Longitude", "Altitude"]
        painel = painel.merge(grade[colunas], on=CHAVE, how="left", validate="one_to_one")
    return painel.sort_values(CHAVE).reset_index(drop=True)


def _grupos(painel: pd.DataFrame):
    yield "global", "todos", painel
    for mes in range(1, 13):
        yield "mes", f"{mes:02d}", painel.loc[painel.mes.eq(mes)]
    for uf, grupo in painel.groupby("UF", dropna=False, sort=True):
        yield "uf", str(uf), grupo


def diagnosticar(painel: pd.DataFrame, coberturas=COBERTURAS, minimo_estacoes=5):
    """Retorna métricas e auditoria; todos os métodos usam os mesmos pares."""
    if minimo_estacoes < 5:
        raise ValueError("Resultados públicos exigem no mínimo cinco estações.")
    resultados, auditoria = [], []
    for cobertura in coberturas:
        if not 0 <= cobertura <= 1:
            raise ValueError("Cobertura deve estar entre zero e um.")
        for escopo, grupo, dados in _grupos(painel):
            obs_valida = np.isfinite(dados["observado"])
            qc = obs_valida & dados["fracao_dias_validos"].ge(cobertura)
            grades_validas = np.isfinite(dados[list(BASES)]).all(axis=1)
            comuns = dados.loc[qc & grades_validas]
            n_estacoes = comuns["codigo"].nunique()
            publicado = n_estacoes >= minimo_estacoes
            identificacao = {"periodo": "2010-2019", "cobertura_min": cobertura, "escopo": escopo, "grupo": grupo}
            auditoria.append({**identificacao, "n_linhas": len(dados),
                "n_obs_validas": int(obs_valida.sum()), "n_apos_cobertura": int(qc.sum()),
                "n_excluidas_cobertura": int((obs_valida & ~qc).sum()),
                "n_excluidas_grades": int((qc & ~grades_validas).sum()),
                "n_pares_comuns": len(comuns), "n_estacoes": n_estacoes,
                "metricas_publicadas": publicado,
                "motivo": "ok" if publicado else "menos_de_5_estacoes"})
            if publicado:
                for base in BASES:
                    resultados.append({**identificacao, "base": base, "n_estacoes": n_estacoes,
                                       **metricas(comuns["observado"], comuns[base])})
    return pd.DataFrame(resultados, columns=COLUNAS_RESULTADO), pd.DataFrame(auditoria)


def destino_local(caminho: Path) -> Path:
    """Impede escrita fora de refinamento/, inclusive por links simbólicos."""
    resolvido = caminho.resolve()
    if not resolvido.is_relative_to(RAIZ):
        raise ValueError("As saídas devem ficar dentro de refinamento/.")
    return resolvido


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fontes", type=Path, default=RAIZ.parent / "validacao")
    parser.add_argument("--saida", type=Path, default=RAIZ / "resultados" / "tabelas")
    parser.add_argument("--salvar-painel", action="store_true", help="Salva painel privado em dados/processados.")
    args = parser.parse_args()
    saida = destino_local(args.saida)
    painel = carregar_painel(args.fontes)
    resultados, auditoria = diagnosticar(painel)
    saida.mkdir(parents=True, exist_ok=True)
    arquivo_resultados = destino_local(saida / "c1_piloto_2010_2019.csv")
    arquivo_auditoria = destino_local(saida / "c1_cobertura.csv")
    resultados.to_csv(arquivo_resultados, index=False, na_rep="NaN", float_format="%.9g")
    auditoria.to_csv(arquivo_auditoria, index=False)
    if args.salvar_painel:
        privado = destino_local(RAIZ / "dados" / "processados" / "c1_painel.csv")
        privado.parent.mkdir(parents=True, exist_ok=True)
        painel.to_csv(privado, index=False, na_rep="NaN")
    resumo = resultados.loc[(resultados.escopo == "global") & (resultados.cobertura_min == 0.8)]
    print(resumo[["base", "n", "n_estacoes", "rmse", "bias"]].to_string(index=False))
    print("Piloto 2010–2019; definição de temperatura média pendente; sem validação independente das grades.")


if __name__ == "__main__":
    main()
