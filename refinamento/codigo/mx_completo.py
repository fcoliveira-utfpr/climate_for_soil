"""C15: método do Xavier reproduzido com mais fidelidade, nas mesmas dobras dos modelos.

Temperatura: IDW (p = 2) das 5 estações de treino mais próximas, com cada normal levada à
altitude do alvo por um gradiente recalibrado em cada dobra, com pares de estações de treino
a até 90 km (regressão da diferença de temperatura contra a diferença de altitude pela origem,
como no artigo). Variantes: gradiente fixo de −0,006 °C/m, recalibrado global e recalibrado
por mês. Para normais mensais com os mesmos vizinhos, a média do IDW diário é igual ao IDW
das médias, então a referência mensal equivale ao método diário quando não há falhas.

Chuva: IDW (p = 2) e ADW (New et al., 2000; Hofstra et al., 2008) das 5 estações de treino
mais próximas. No ADW, peso = exp(−d/CDD)^4 × (1 + termo angular), com a distância de
decaimento da correlação (CDD) estimada em cada dobra só com pares de estações de treino,
a partir das anomalias mensais padronizadas de 1991-2020.

As predições de MX são comparadas com as predições já gravadas dos modelos, depois de
conferir que estações, blocos e dobras são idênticos. O teste reservado não é usado.

Uso, de dentro de refinamento/:  python -B -m codigo.mx_completo --block-size 2
"""
import argparse
import json

import numpy as np
import pandas as pd
from sklearn.model_selection import GroupKFold
from sklearn.neighbors import BallTree

from codigo import modelos, modelos_chuva
from codigo.dados_temperatura import safe_path
from codigo.grade_brasil import digest
from codigo.metricas import metricas

EARTH_KM = 6371.0088
NEIGHBORS = 5
PAIR_KM = 90
CDD_PAIR_KM = 500
ADW_M = 4
DAYS = np.array([31, 28.25, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31])


def haversine_tree(frame):
    return BallTree(np.deg2rad(frame[["latitude", "longitude"]].to_numpy()), metric="haversine")


def bearing(lat1, lon1, lat2, lon2):
    """Azimute (rad) do ponto 1 para o ponto 2, em graus decimais de entrada."""
    p1, p2, dl = np.deg2rad(lat1), np.deg2rad(lat2), np.deg2rad(lon2 - lon1)
    return np.arctan2(np.sin(dl) * np.cos(p2), np.cos(p1) * np.sin(p2) - np.sin(p1) * np.cos(p2) * np.cos(dl))


def folds(development, block_size, repeat):
    groups = modelos.spatial_blocks(development, block_size)
    outer = GroupKFold(n_splits=5, shuffle=True, random_state=42 + repeat)
    return groups, list(outer.split(development, groups=groups))


# ---------------------------------------------------------------- temperatura
def station_table(frame, value):
    stations = frame.groupby("station_id")[["latitude", "longitude", "elevation_m"]].first()
    normals = frame.pivot(index="station_id", columns="month", values=value).loc[stations.index]
    return stations, normals


def auxiliary_pairs():
    """Pares de estações a até 90 km entre todas as estações de Tmax/Tmin (como no artigo).

    Para cada par, a diferença de temperatura de cada mês do calendário é a média das
    diferenças nos meses aceitos em comum (pelo menos 2 por mês do calendário).
    """
    monthly = pd.read_csv(safe_path("dados/processados/temperatura_mensal.csv"), dtype={"station_id": str})
    monthly = monthly[monthly.accepted.astype(str).eq("True") & monthly.temperature_c.notna()]
    stations = pd.read_csv(safe_path("dados/processados/estacoes_auditadas.csv"), dtype={"station_id": str})
    stations = stations[~stations.missing_elevation.astype(str).eq("True") & stations.elevation_m.notna()]
    stations = stations[stations.station_id.isin(monthly.station_id)].set_index("station_id")
    monthly = monthly[monthly.station_id.isin(stations.index)]
    time = (monthly.year - 1991) * 12 + monthly.month - 1
    table = (monthly.assign(time=time).pivot(index="station_id", columns="time", values="temperature_c")
             .reindex(index=stations.index, columns=range(360)))
    values = table.to_numpy(float)
    calendar = np.arange(360) % 12
    tree = haversine_tree(stations)
    neighbors = tree.query_radius(np.deg2rad(stations[["latitude", "longitude"]].to_numpy()), r=PAIR_KM / EARTH_KM)
    records = []
    for i, found in enumerate(neighbors):
        for j in found:
            if j <= i:
                continue
            both = np.isfinite(values[i]) & np.isfinite(values[j])
            diff = values[i] - values[j]
            by_month = np.array([diff[both & (calendar == m)].mean() if np.sum(both & (calendar == m)) >= 2 else np.nan
                                 for m in range(12)])
            if np.isfinite(by_month).all():
                records.append((stations.index[i], stations.index[j],
                                stations.elevation_m.iloc[i] - stations.elevation_m.iloc[j], *by_month))
    pairs = pd.DataFrame(records, columns=["first", "second", "dz"] + [f"dt_{m:02d}" for m in range(1, 13)])
    return pairs, stations[["latitude", "longitude"]]


def gamma_from_pairs(pairs, excluded):
    """Gradiente (°C/m) global e por mês, só com pares fora das estações excluídas."""
    use = pairs[~pairs["first"].isin(excluded) & ~pairs["second"].isin(excluded)]
    if len(use) < 30:
        raise ValueError("Poucos pares de estações a até 90 km para recalibrar o gradiente.")
    dz = use.dz.to_numpy()
    dt = use[[f"dt_{m:02d}" for m in range(1, 13)]].to_numpy()
    monthly = (dt * dz[:, None]).sum(axis=0) / np.sum(dz ** 2)
    pooled = float((dt * dz[:, None]).sum() / (12 * np.sum(dz ** 2)))
    return pooled, monthly, len(use)


def mx_temperature(train, test, gamma_by_month):
    prediction = np.empty(len(test))
    for month in range(1, 13):
        source = train[train.month == month]
        positions = np.flatnonzero(test.month.to_numpy() == month)
        target = test.iloc[positions]
        tree = haversine_tree(source)
        distances, indices = tree.query(np.deg2rad(target[["latitude", "longitude"]].to_numpy()), k=NEIGHBORS)
        gamma = gamma_by_month[month - 1]
        adjusted = (source.temperature_c.to_numpy()[indices]
                    + gamma * (target.elevation_m.to_numpy()[:, None] - source.elevation_m.to_numpy()[indices]))
        weights = np.maximum(distances, 1e-12) ** -2
        prediction[positions] = (adjusted * weights).sum(axis=1) / weights.sum(axis=1)
    return prediction


def run_temperature(block_size):
    data = modelos.prepare(pd.read_csv(safe_path("dados/processados/normais_covariaveis.csv"), dtype={"station_id": str}))
    held = modelos.reserve_test(data)
    development = data.loc[~held].reset_index(drop=True)
    stored = pd.read_csv(safe_path(f"dados/modelagem/predicoes_{block_size}graus_grade_correction.csv"), dtype={"station_id": str})
    keep = ["M0_chelsa", "MX_mensal_referencia", "M4_random_forest", "M5_lightgbm"]
    stored = stored[stored.method.isin(keep)]
    pairs, auxiliary = auxiliary_pairs()
    reserved_blocks = set(modelos.spatial_blocks(data.loc[held], 2))
    auxiliary_reserved = set(auxiliary.index[np.isin(modelos.spatial_blocks(auxiliary, 2), list(reserved_blocks))])
    auxiliary_reserved |= set(data.loc[held, "station_id"])
    auxiliary_blocks = modelos.spatial_blocks(auxiliary, block_size)
    rows, gammas, checks = [], [], []
    for repeat in range(3):
        groups, splits = folds(development, block_size, repeat)
        for fold, (train_index, test_index) in enumerate(splits):
            train, test = development.iloc[train_index], development.iloc[test_index]
            reference = stored[(stored.repeat == repeat) & (stored.fold == fold) & (stored.method == "M5_lightgbm")]
            same = set(reference.station_id) == set(test.station_id) and len(reference) == len(test)
            checks.append(bool(same))
            test_blocks = set(groups[test_index])
            excluded = (auxiliary_reserved | set(test.station_id)
                        | set(auxiliary.index[np.isin(auxiliary_blocks, list(test_blocks))]))
            pooled, monthly, n_pairs = gamma_from_pairs(pairs, excluded)
            gammas.append({"repeat": repeat, "fold": fold, "n_pairs": n_pairs, "gamma_global_c_por_km": 1000 * pooled,
                           **{f"gamma_{m:02d}_c_por_km": 1000 * monthly[m - 1] for m in range(1, 13)}})
            base = test[["station_id", "month", "temperature_c", "elevation_m"]].copy()
            base["block"], base["repeat"], base["fold"] = groups[test_index], repeat, fold
            for name, gamma in (("MX_gamma_global", np.full(12, pooled)), ("MX_gamma_mensal", monthly)):
                rows.append(base.assign(method=name, prediction=mx_temperature(train, test, gamma)))
    if not all(checks):
        raise ValueError("Dobras diferentes das predições gravadas; comparação não seria pareada.")
    predictions = pd.concat([stored] + rows, ignore_index=True)[
        ["station_id", "month", "temperature_c", "elevation_m", "block", "prediction", "method", "repeat", "fold"]]
    summary = modelos.summarize(predictions)
    weights = DAYS / DAYS.sum()
    annual = (predictions.assign(w=lambda x: weights[x.month - 1])
              .assign(obs=lambda x: x.temperature_c * x.w, pred=lambda x: x.prediction * x.w)
              .groupby(["method", "repeat", "station_id"])[["obs", "pred"]].sum().reset_index())
    for (method, repeat), frame in annual.groupby(["method", "repeat"]):
        summary.loc[len(summary)] = {"method": method, "repeat": repeat, "scope": "annual", "group": "all",
                                     "n_stations": frame.station_id.nunique(), **metricas(frame.obs, frame.pred)}
    differences = modelos.paired_intervals(predictions, reference_method="MX_gamma_global")
    return summary, differences, pd.DataFrame(gammas), {"temperature_folds_identical": all(checks),
                                                         "temperature_development_stations": int(development.station_id.nunique())}


# --------------------------------------------------------------------- chuva
def anomaly_correlations(station_ids):
    """Correlação aproximada (pares completos) das anomalias mensais padronizadas, 1991-2020."""
    monthly = pd.read_csv(safe_path("dados/processados/precipitacao_mensal.csv"), dtype={"station_id": str},
                          usecols=["station_id", "year", "month", "precipitation_mm"])
    monthly = monthly[monthly.station_id.isin(station_ids)]
    grouped = monthly.groupby(["station_id", "month"]).precipitation_mm
    standardized = (monthly.precipitation_mm - grouped.transform("mean")) / grouped.transform("std")
    monthly = monthly.assign(anomaly=standardized, time=(monthly.year - 1991) * 12 + monthly.month - 1)
    table = monthly.pivot(index="station_id", columns="time", values="anomaly").reindex(station_ids)
    values = table.to_numpy(float)
    mask = np.isfinite(values).astype(float)
    filled = np.nan_to_num(values)
    numerator = filled @ filled.T
    squares = filled ** 2
    denominator = np.sqrt((squares @ mask.T) * (mask @ squares.T))
    overlap = mask @ mask.T
    with np.errstate(invalid="ignore", divide="ignore"):
        correlation = numerator / denominator
    correlation[overlap < 60] = np.nan
    return correlation


def cdd_from_pairs(stations, correlation):
    tree = haversine_tree(stations)
    coordinates = np.deg2rad(stations[["latitude", "longitude"]].to_numpy())
    neighbors, distances = tree.query_radius(coordinates, r=CDD_PAIR_KM / EARTH_KM, return_distance=True)
    xs, rs = [], []
    for i, (found, dist) in enumerate(zip(neighbors, distances)):
        for j, d in zip(found, dist):
            if j > i:
                xs.append(d * EARTH_KM)
                rs.append(correlation[i, j])
    xs, rs = np.array(xs), np.array(rs)
    good = np.isfinite(rs) & (rs > 0.05) & (xs > 0)
    inverse = -np.sum(xs[good] * np.log(np.minimum(rs[good], 1))) / np.sum(xs[good] ** 2)
    return float(1 / inverse), int(good.sum())


def mx_rain(train, test, cdd):
    idw = np.empty(len(test))
    adw = np.empty(len(test))
    for month in range(1, 13):
        source = train[train.month == month]
        positions = np.flatnonzero(test.month.to_numpy() == month)
        target = test.iloc[positions]
        tree = haversine_tree(source)
        distances, indices = tree.query(np.deg2rad(target[["latitude", "longitude"]].to_numpy()), k=NEIGHBORS)
        km = np.maximum(distances * EARTH_KM, 1e-6)
        values = source.precipitation_mm.to_numpy()[indices]
        weights = km ** -2
        idw[positions] = (values * weights).sum(axis=1) / weights.sum(axis=1)
        theta = bearing(target.latitude.to_numpy()[:, None], target.longitude.to_numpy()[:, None],
                        source.latitude.to_numpy()[indices], source.longitude.to_numpy()[indices])
        base = np.exp(-km / cdd) ** ADW_M
        angular = np.zeros_like(base)
        for k in range(NEIGHBORS):
            others = [l for l in range(NEIGHBORS) if l != k]
            angular[:, k] = ((base[:, others] * (1 - np.cos(theta[:, others] - theta[:, [k]]))).sum(axis=1)
                             / np.maximum(base[:, others].sum(axis=1), 1e-300))
        final = base * (1 + angular)
        degenerate = final.sum(axis=1) <= 1e-300
        final[degenerate] = weights[degenerate]
        adw[positions] = (values * final).sum(axis=1) / final.sum(axis=1)
    return idw, adw


def run_rain(block_size):
    data, _ = modelos_chuva.prepare()
    development = data.loc[~data.reserved].reset_index(drop=True)
    stations = development.groupby("station_id")[["latitude", "longitude"]].first()
    correlation = anomaly_correlations(list(stations.index))
    position = {sid: i for i, sid in enumerate(stations.index)}
    stored = pd.read_csv(safe_path(f"dados/chuva/predicoes_M5_{block_size}graus_30m_base.csv"), dtype={"station_id": str})
    stored = stored[stored.method.isin(["M0_chelsa", "M0_chirps", "M0_era5", "M5_correction"])]
    rows, cdds, checks = [], [], []
    for repeat in range(3):
        groups, splits = folds(development, block_size, repeat)
        for fold, (train_index, test_index) in enumerate(splits):
            train, test = development.iloc[train_index], development.iloc[test_index]
            reference = stored[(stored.repeat == repeat) & (stored.fold == fold) & (stored.method == "M5_correction")]
            checks.append(set(reference.station_id) == set(test.station_id) and len(reference) == len(test))
            train_stations = train.groupby("station_id")[["latitude", "longitude"]].first()
            index = [position[s] for s in train_stations.index]
            cdd, n_pairs = cdd_from_pairs(train_stations, correlation[np.ix_(index, index)])
            cdds.append({"repeat": repeat, "fold": fold, "cdd_km": cdd, "n_pairs": n_pairs})
            idw, adw = mx_rain(train, test, cdd)
            base = test[["station_id", "month", "precipitation_mm"]].copy()
            base["block"], base["repeat"], base["fold"] = groups[test_index], repeat, fold
            rows.append(base.assign(method="MX_idw", prediction=idw))
            rows.append(base.assign(method="MX_adw", prediction=adw))
    if not all(checks):
        raise ValueError("Dobras diferentes das predições gravadas de chuva.")
    predictions = pd.concat([stored] + rows, ignore_index=True)
    summary = modelos_chuva.summary(predictions)
    paired = predictions.rename(columns={"precipitation_mm": "temperature_c"})
    differences = modelos.paired_intervals(paired, reference_method="MX_adw").rename(columns={"delta_rmse_c": "delta_rmse_mm"})
    return summary, differences, pd.DataFrame(cdds), {"rain_folds_identical": all(checks),
                                                      "rain_development_stations": int(development.station_id.nunique())}


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--block-size", type=int, choices=[1, 2], default=2)
    args = parser.parse_args()
    b = args.block_size
    t_summary, t_diff, gammas, t_audit = run_temperature(b)
    t_summary.to_csv(safe_path(f"resultados/tabelas/c15_mx_temperatura_{b}graus.csv"), index=False)
    t_diff.to_csv(safe_path(f"resultados/tabelas/c15_diferencas_temperatura_{b}graus.csv"), index=False)
    gammas.to_csv(safe_path(f"resultados/tabelas/c15_gradientes_{b}graus.csv"), index=False)
    r_summary, r_diff, cdds, r_audit = run_rain(b)
    r_summary.to_csv(safe_path(f"resultados/tabelas/c15_mx_chuva_{b}graus.csv"), index=False)
    r_diff.to_csv(safe_path(f"resultados/tabelas/c15_diferencas_chuva_{b}graus.csv"), index=False)
    cdds.to_csv(safe_path(f"resultados/tabelas/c15_cdd_chuva_{b}graus.csv"), index=False)
    audit = {**t_audit, **r_audit, "block_size": b, "neighbors": NEIGHBORS, "pair_km": PAIR_KM,
             "cdd_pair_km": CDD_PAIR_KM, "adw_exponent": ADW_M, "holdout_scored": False,
             "script_sha256": digest(__file__)}
    safe_path(f"resultados/tabelas/c15_auditoria_{b}graus.json").write_text(json.dumps(audit, indent=2), encoding="utf-8")
    view = t_summary[t_summary.scope.isin(["global", "annual"])].groupby(["method", "scope"]).rmse.mean().unstack()
    print("Temperatura (RMSE °C):\n", view.round(3).to_string())
    print(t_diff[["method", "delta_rmse_c", "ci025", "ci975"]].round(3).to_string(index=False))
    print("Gradiente global (°C/km): media", round(gammas.gamma_global_c_por_km.mean(), 2),
          "faixa", round(gammas.gamma_global_c_por_km.min(), 2), round(gammas.gamma_global_c_por_km.max(), 2))
    view = r_summary.groupby(["method", "scope"]).rmse.mean().unstack()
    print("Chuva (RMSE mm):\n", view.round(3).to_string())
    print(r_diff[["method", "delta_rmse_mm", "ci025", "ci975"]].round(3).to_string(index=False))
    print("CDD (km): media", round(cdds.cdd_km.mean(), 1), "faixa", round(cdds.cdd_km.min(), 1), round(cdds.cdd_km.max(), 1))


if __name__ == "__main__":
    main()
