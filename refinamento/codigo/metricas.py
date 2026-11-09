"""Métricas pareadas; viés positivo significa previsão maior que observação.

KGE original (Gupta et al., 2009): correlação, razão de desvios padrão e
razão de médias. PBIAS adota explicitamente previsto menos observado.
Razões com denominador zero e correlações constantes retornam NaN.
"""
from __future__ import annotations

import numpy as np


def metricas(obs, pred) -> dict[str, float | int]:
    """Calcula n, bias, rmse, mae, r, nse, pbias, d e kge em pares finitos."""
    observado, previsto = np.asarray(obs, dtype=float), np.asarray(pred, dtype=float)
    if observado.ndim != 1 or previsto.shape != observado.shape:
        raise ValueError("Observações e previsões devem ser vetores de mesmo tamanho.")
    valido = np.isfinite(observado) & np.isfinite(previsto)
    observado, previsto = observado[valido], previsto[valido]
    n = len(observado)
    resultado = dict.fromkeys(("bias", "rmse", "mae", "r", "nse", "pbias", "d", "kge"), float("nan"))
    resultado["n"] = n
    if not n:
        return resultado
    erro = previsto - observado
    media_obs, media_pred = observado.mean(), previsto.mean()
    soma_quadrados = np.sum(erro ** 2)
    variacao_obs = np.sum((observado - media_obs) ** 2)
    denominador_d = np.sum((np.abs(previsto - media_obs) + np.abs(observado - media_obs)) ** 2)
    resultado.update(bias=float(erro.mean()), rmse=float(np.sqrt(np.mean(erro ** 2))),
                     mae=float(np.mean(np.abs(erro))))
    if variacao_obs > 0:
        resultado["nse"] = float(1 - soma_quadrados / variacao_obs)
    if observado.sum() != 0:
        resultado["pbias"] = float(100 * erro.sum() / observado.sum())
    if denominador_d > 0:
        resultado["d"] = float(1 - soma_quadrados / denominador_d)
    desvio_obs, desvio_pred = observado.std(), previsto.std()
    if n >= 2 and desvio_obs > 0 and desvio_pred > 0:
        r = float(np.clip(np.corrcoef(observado, previsto)[0, 1], -1, 1))
        resultado["r"] = r
        if media_obs != 0:
            resultado["kge"] = float(1 - np.sqrt((r - 1) ** 2
                + (desvio_pred / desvio_obs - 1) ** 2 + (media_pred / media_obs - 1) ** 2))
    return resultado
