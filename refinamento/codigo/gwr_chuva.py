"""C3 da chuva: M3, regressão geograficamente ponderada (GWR), nas mesmas dobras dos outros modelos.

Mesma formulação da correção de modelos_chuva.py: resposta log1p(chuva) − log1p(CHELSA), covariáveis
padronizadas (latitude, longitude, altitude e declividade de 30 m, harmônicos do mês e
log1p(CHELSA)), kernel gaussiano geodésico com bandwidth de 250 ou 750 km escolhido em 3 dobras
internas, ridge numérico de 1e-6 (como o M3 da temperatura) e retransformação por smearing dos
resíduos do treino. Os 12 meses de um mesmo local têm os mesmos pesos, então os coeficientes
locais são calculados uma vez por local.

Uso, de dentro de refinamento/:  python -B -m codigo.gwr_chuva --block-size 2
"""
import argparse
import json

import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, RegressorMixin
from sklearn.model_selection import GridSearchCV, GroupKFold
from sklearn.preprocessing import StandardScaler

from codigo import modelos, modelos_chuva
from codigo.dados_temperatura import safe_path
from codigo.grade_brasil import digest

FEATURES = ["latitude", "longitude", "elevation_30", "slope_30", "month_sin", "month_cos", "chelsa_mm"]
EARTH_KM = 6371.0088


class RainGWR(RegressorMixin, BaseEstimator):
    def __init__(self, bandwidth_km=750):
        self.bandwidth_km = bandwidth_km

    def _design(self, X):
        frame = X[FEATURES].copy()
        frame["chelsa_mm"] = np.log1p(frame.chelsa_mm)
        return frame

    def _local(self, X):
        design = np.column_stack([np.ones(len(X)), self.scaler_.transform(self._design(X))])
        coords = np.deg2rad(X[["latitude", "longitude"]].to_numpy(float))
        keys, inverse = np.unique(np.round(coords, 9), axis=0, return_inverse=True)
        penalty = np.eye(design.shape[1]) * 1e-6
        penalty[0, 0] = 0
        result = np.empty(len(X))
        for k, (lat, lon) in enumerate(keys):
            a = (np.sin((self.coords_[:, 0] - lat) / 2) ** 2
                 + np.cos(lat) * np.cos(self.coords_[:, 0]) * np.sin((self.coords_[:, 1] - lon) / 2) ** 2)
            distance = EARTH_KM * 2 * np.arcsin(np.sqrt(np.clip(a, 0, 1)))
            logw = -0.5 * (distance / self.bandwidth_km) ** 2
            weights = np.exp(logw - logw.max())
            weighted = self.design_.T * weights
            beta = np.linalg.solve(weighted @ self.design_ + penalty, weighted @ self.target_)
            rows = np.flatnonzero(inverse.ravel() == k)
            result[rows] = design[rows] @ beta
        return result

    def fit(self, X, y):
        y = np.asarray(y, float)
        self.scaler_ = StandardScaler().fit(self._design(X))
        self.design_ = np.column_stack([np.ones(len(X)), self.scaler_.transform(self._design(X))])
        self.coords_ = np.deg2rad(X[["latitude", "longitude"]].to_numpy(float))
        self.target_ = np.log1p(y) - np.log1p(X.chelsa_mm.to_numpy(float))
        residual = self.target_ - self._local(X)
        self.smearing_ = float(np.exp(residual).mean())
        return self

    def predict(self, X):
        log_prediction = self._local(X) + np.log1p(X.chelsa_mm.to_numpy(float))
        return np.maximum(0, np.exp(log_prediction) * self.smearing_ - 1)


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--block-size", type=int, choices=[1, 2], default=2)
    args = parser.parse_args()
    data, coverage = modelos_chuva.prepare()
    development = data.loc[~data.reserved].reset_index(drop=True)
    groups = modelos.spatial_blocks(development, args.block_size)
    stored = pd.read_csv(safe_path(f"dados/chuva/predicoes_M5_{args.block_size}graus_30m_base.csv"), dtype={"station_id": str})
    stored = stored[stored.method.isin(["M0_chelsa", "M0_chirps", "M5_correction"])]
    records, settings = [], []
    for repeat in range(3):
        outer = GroupKFold(n_splits=5, shuffle=True, random_state=42 + repeat)
        for fold, (a, b) in enumerate(outer.split(development, groups=groups)):
            train, test = development.iloc[a], development.iloc[b]
            search = GridSearchCV(RainGWR(), {"bandwidth_km": [250, 750]}, cv=GroupKFold(n_splits=3),
                                  scoring="neg_root_mean_squared_error", n_jobs=1, error_score="raise")
            search.fit(train, train.precipitation_mm, groups=groups[a])
            base = test[["station_id", "month", "precipitation_mm"]].copy()
            base["block"], base["repeat"], base["fold"] = groups[b], repeat, fold
            records.append(base.assign(method="M3_correction", prediction=search.predict(test)))
            settings.append({"repeat": repeat, "fold": fold, **search.best_params_})
            print(f"GWR chuva: bloco {args.block_size}, repetição {repeat + 1}, dobra {fold + 1}, {search.best_params_}", flush=True)
    output = pd.concat([stored] + records, ignore_index=True)
    suffix = f"M3_{args.block_size}graus_30m_base"
    path = safe_path(f"dados/chuva/predicoes_{suffix}.csv")
    output.to_csv(path, index=False)
    modelos_chuva.summary(output).to_csv(safe_path(f"resultados/tabelas/chuva_{suffix}.csv"), index=False)
    paired = output.rename(columns={"precipitation_mm": "temperature_c"})
    diffs = pd.concat([modelos.paired_intervals(paired, reference_method=ref) for ref in ("M0_chelsa", "M5_correction")])
    diffs.rename(columns={"delta_rmse_c": "delta_rmse_mm"}).to_csv(safe_path(f"resultados/tabelas/chuva_diferencas_{suffix}.csv"), index=False)
    report = {**coverage, "configuration": vars(args), "holdout_scored": False, "settings": settings,
              "script_sha256": digest(__file__), "output_sha256": digest(path)}
    safe_path(f"resultados/tabelas/chuva_auditoria_{suffix}.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    summary = modelos_chuva.summary(output)
    print(summary.groupby(["method", "scope"]).rmse.mean().unstack().round(3).to_string())
    print(diffs.round(3).to_string(index=False))


if __name__ == "__main__":
    main()
