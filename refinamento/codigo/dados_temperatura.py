"""Prepara observações de Tmax/Tmin para normais mensais de 1991–2020.

Não preenche falhas nem corrige séries curtas com uma grade de referência.
A temperatura é (Tmax + Tmin)/2 calculada apenas em dias com os dois extremos
válidos; não equivale à média das 24 horas. Saltos, constância e coordenadas
duplicadas são sinais para revisão, não causas automáticas de exclusão.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import io
import json
import math
from pathlib import Path
import pickle
import zipfile

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
NORMAL_START = "1991-01-01"
NORMAL_END = "2020-12-31"
N_YEARS = 30
STATION_COLUMNS = ["station_id", "latitude", "longitude", "elevation_m"]


def safe_path(path: str | Path) -> Path:
    """Resolve caminhos relativos a refinamento e recusa saídas da pasta."""
    path = Path(path)
    resolved = (path if path.is_absolute() else ROOT / path).resolve()
    if not resolved.is_relative_to(ROOT.resolve()):
        raise ValueError(f"Caminho fora de refinamento: {path}")
    return resolved


@dataclass
class Observations:
    data: np.ndarray
    stations: pd.DataFrame
    dates: pd.DatetimeIndex


@dataclass
class Prepared:
    monthly: pd.DataFrame
    normals: pd.DataFrame
    stations: pd.DataFrame
    qc: pd.DataFrame
    sensitivity: pd.DataFrame
    unpaired_stations: pd.DataFrame


class _NumpyIDUnpickler(pickle.Unpickler):
    """Compatibilidade restrita para IDs legados, sem globals arbitrários."""

    def find_class(self, module: str, name: str):
        allowed = {
            ("numpy", "ndarray"): np.ndarray,
            ("numpy", "dtype"): np.dtype,
            ("numpy._core.multiarray", "_reconstruct"): np._core.multiarray._reconstruct,
            ("numpy.core.multiarray", "_reconstruct"): np._core.multiarray._reconstruct,
        }
        if (module, name) not in allowed:
            raise ValueError(f"ID legado contém global proibido: {module}.{name}")
        return allowed[module, name]

    def persistent_load(self, pid):
        raise ValueError("ID legado contém referência persistente proibida.")


def _load_legacy_ids(path: Path) -> np.ndarray:
    """Lê somente ID.npy object legado com construtores NumPy autorizados.

    Nunca habilita allow_pickle=True. Não admite código/classe do fornecedor,
    arrays multidimensionais, IDs compostos ou outros objetos nos elementos.
    """
    with zipfile.ZipFile(path) as archive:
        info = archive.getinfo("ID.npy")
        if info.file_size > 2 * 1024 * 1024:
            raise ValueError("ID.npy legado excede o limite de 2 MiB.")
        stream = io.BytesIO(archive.read(info))
    version = np.lib.format.read_magic(stream)
    if version == (1, 0):
        shape, _, dtype = np.lib.format.read_array_header_1_0(stream)
    elif version == (2, 0):
        shape, _, dtype = np.lib.format.read_array_header_2_0(stream)
    else:
        raise ValueError(f"Versão NPY não suportada para ID legado: {version}")
    if len(shape) != 1 or dtype != np.dtype("O"):
        raise ValueError("ID legado deve ser vetor simples de dtype object.")
    try:
        ids = _NumpyIDUnpickler(stream).load()
    except (pickle.UnpicklingError, EOFError, TypeError, AttributeError) as exc:
        raise ValueError("ID legado possui serialização inválida ou não suportada.") from exc
    if (
        type(ids) is not np.ndarray or ids.shape != shape or ids.dtype != np.dtype("O")
        or any(type(value) not in (str, int) for value in ids)
    ):
        raise ValueError("ID legado deve conter apenas strings ou inteiros simples.")
    return ids.astype(str)


def load_observations(
    path: str | Path,
    source_start: str = "1961-01-01",
    source_end: str = "2025-12-31",
) -> Observations:
    """Lê NPZ sem pickle e confere o calendário declarado pelo fornecedor."""
    path = safe_path(path)
    dates = pd.date_range(source_start, source_end, freq="D")
    if dates.empty:
        raise ValueError("O início do calendário deve anteceder seu fim.")
    with np.load(path, allow_pickle=False) as archive:
        missing = {"data", "lat_lon_alt", "ID"} - set(archive.files)
        if missing:
            raise ValueError(f"{path.name}: campos ausentes: {sorted(missing)}")
        try:
            ids = archive["ID"]
        except ValueError as exc:
            if "Object arrays cannot be loaded" not in str(exc):
                raise
            ids = _load_legacy_ids(path)
        if ids.ndim != 1 or ids.dtype.kind not in "USiu":
            raise ValueError(f"{path.name}: ID deve ser vetor de texto ou inteiros.")
        station_ids = [
            (value.decode("utf-8") if isinstance(value, bytes) else str(value)).strip()
            for value in ids
        ]
        if any(not value for value in station_ids) or len(set(station_ids)) != len(ids):
            raise ValueError(f"{path.name}: ID vazio ou duplicado.")
        raw_data = archive["data"]
        raw_coords = archive["lat_lon_alt"]
        if raw_data.dtype.kind not in "fiu" or raw_coords.dtype.kind not in "fiu":
            raise ValueError(f"{path.name}: data e lat_lon_alt devem ser numéricos reais.")
        data = np.asarray(raw_data, dtype=np.float64)
        coords = np.asarray(raw_coords, dtype=np.float64)
    if not len(station_ids):
        raise ValueError(f"{path.name}: nenhuma estação.")
    if data.shape != (len(dates), len(station_ids)):
        raise ValueError(
            f"{path.name}: data tem forma {data.shape}; esperado "
            f"({len(dates)}, {len(station_ids)}) para {source_start} a {source_end}. "
            "Confirme as datas com o fornecedor; não infira o início pelo comprimento."
        )
    if coords.shape != (len(station_ids), 3):
        raise ValueError(f"{path.name}: lat_lon_alt deve ter forma (estações, 3).")
    if (
        not np.isfinite(coords[:, :2]).all()
        or (np.abs(coords[:, 0]) > 90).any()
        or (np.abs(coords[:, 1]) > 180).any()
        or np.isinf(coords[:, 2]).any()
    ):
        raise ValueError(f"{path.name}: coordenadas inválidas ou altitude infinita.")
    stations = pd.DataFrame(coords, columns=STATION_COLUMNS[1:])
    stations.insert(0, "station_id", station_ids)
    return Observations(data, stations, dates)


def align_observations(tmax: Observations, tmin: Observations) -> tuple[np.ndarray, np.ndarray, pd.DataFrame]:
    """Índices da interseção por ID e auditoria das estações sem o outro extremo."""
    if not tmax.dates.equals(tmin.dates):
        raise ValueError("Tmax e Tmin têm calendários diferentes.")
    maximum = tmax.stations.set_index("station_id")
    minimum = tmin.stations.set_index("station_id")
    common = maximum.index.intersection(minimum.index, sort=False)
    if common.empty:
        raise ValueError("Tmax e Tmin não têm IDs em comum.")
    maximum_order = maximum.index.get_indexer(common)
    order = minimum.index.get_indexer(common)
    left = maximum.iloc[maximum_order][STATION_COLUMNS[1:]].to_numpy()
    right = minimum.iloc[order][STATION_COLUMNS[1:]].to_numpy()
    equal = np.isclose(left, right, rtol=0, atol=[1e-6, 1e-6, 0.01], equal_nan=True)
    if not equal.all():
        bad_ids = common[~equal.all(axis=1)].tolist()
        raise ValueError(f"Coordenadas/altitude divergentes entre Tmax e Tmin: {bad_ids[:10]}")
    unpaired = pd.concat([
        tmax.stations.loc[~tmax.stations.station_id.isin(common)].assign(available_variable="tmax"),
        tmin.stations.loc[~tmin.stations.station_id.isin(common)].assign(available_variable="tmin"),
    ], ignore_index=True)
    return maximum_order, order, unpaired


def _audit_series(values: np.ndarray, jump_c: float) -> tuple[np.ndarray, np.ndarray]:
    """Máximo de dias consecutivos idênticos e saltos em dias consecutivos."""
    finite = np.isfinite(values)
    longest = np.zeros(values.shape[1], dtype=int)
    current = np.zeros(values.shape[1], dtype=int)
    for day in range(len(values)):
        same = (
            finite[day] & finite[day - 1] & (values[day] == values[day - 1])
            if day else np.zeros(values.shape[1], dtype=bool)
        )
        current = np.where(finite[day], np.where(same, current + 1, 1), 0)
        longest = np.maximum(longest, current)
    jumps = (finite[1:] & finite[:-1] & (np.abs(np.diff(values, axis=0)) > jump_c)).sum(axis=0)
    return longest, jumps


def _fraction(value: float, name: str) -> None:
    if not np.isfinite(value) or not 0 < value <= 1:
        raise ValueError(f"{name} deve estar no intervalo (0, 1].")


def _normal_tables(
    monthly: pd.DataFrame, stations: pd.DataFrame, minimum_year_fraction: float,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    normal = monthly.groupby(["station_id", "month"], sort=False)["temperature_c"].agg(
        temperature_c="mean", n_years="count",
    ).reset_index()
    normal["coverage"] = normal["n_years"] / N_YEARS
    sensitivity_rows = []
    for fraction in sorted({0.7, 0.8, 0.9, minimum_year_fraction}):
        required_years = math.ceil(N_YEARS * fraction)
        supported = normal["n_years"] >= required_years
        by_station = normal.assign(supported=supported).groupby("station_id")["supported"].sum()
        for month in range(1, 13):
            sensitivity_rows.append({
                "minimum_year_fraction": fraction, "required_years": required_years,
                "month": month, "stations_eligible": int((supported & (normal["month"] == month)).sum()),
                "stations_total": len(stations),
            })
        sensitivity_rows.append({
            "minimum_year_fraction": fraction, "required_years": required_years,
            "month": 0, "stations_eligible": int((by_station == 12).sum()),
            "stations_total": len(stations),
        })
    normal.loc[normal["n_years"] < math.ceil(N_YEARS * minimum_year_fraction), "temperature_c"] = np.nan

    # A normal anual combina as 12 normais mensais; não combina somente os anos
    # completos. n_years e coverage anuais são os mínimos entre os 12 meses.
    dates = pd.date_range(NORMAL_START, NORMAL_END, freq="D")
    weights = pd.Series(1, index=dates).groupby(dates.month).sum() / N_YEARS
    complete = normal.groupby("station_id")["temperature_c"].count().eq(12)
    annual_source = normal.loc[normal["station_id"].isin(complete[complete].index)].copy()
    annual_source["weighted_temperature"] = annual_source["temperature_c"] * annual_source["month"].map(weights)
    annual = annual_source.groupby("station_id", as_index=False).agg(
        temperature_c=("weighted_temperature", "sum"),
        n_years=("n_years", "min"), coverage=("coverage", "min"),
    )
    annual["temperature_c"] /= weights.sum()
    annual["month"] = 0
    normal = pd.concat([normal, annual], ignore_index=True)
    normal = stations.merge(normal, on="station_id", validate="one_to_many")
    normal = normal[STATION_COLUMNS + ["month", "temperature_c", "n_years", "coverage"]]
    return normal.sort_values(["station_id", "month"]).reset_index(drop=True), pd.DataFrame(sensitivity_rows)


def prepare_temperature(
    tmax: Observations,
    tmin: Observations,
    minimum_day_fraction: float = 0.8,
    minimum_year_fraction: float = 0.8,
    constant_run_days: int = 7,
    jump_c: float = 20.0,
) -> Prepared:
    """Aplica QC no período normal, agrega meses e calcula normais auditáveis."""
    _fraction(minimum_day_fraction, "minimum_day_fraction")
    _fraction(minimum_year_fraction, "minimum_year_fraction")
    if constant_run_days < 2 or not np.isfinite(jump_c) or jump_c <= 0:
        raise ValueError("Constância exige pelo menos 2 dias; salto deve ser positivo.")
    maximum_order, minimum_order, unpaired = align_observations(tmax, tmin)
    normal_dates = pd.date_range(NORMAL_START, NORMAL_END, freq="D")
    period = (tmax.dates >= NORMAL_START) & (tmax.dates <= NORMAL_END)
    if not tmax.dates[period].equals(normal_dates):
        raise ValueError("O calendário de origem deve conter todos os dias de 1991–2020.")
    maximum = tmax.data[np.ix_(period, maximum_order)]
    minimum = tmin.data[np.ix_(period, minimum_order)]
    valid_max = np.isfinite(maximum) & (maximum > -30) & (maximum < 50)
    valid_min = np.isfinite(minimum) & (minimum > -30) & (minimum < 50)
    inverted = valid_max & valid_min & (minimum > maximum)
    valid_pair = valid_max & valid_min & ~inverted
    audit = tmax.stations.iloc[maximum_order].reset_index(drop=True).copy()
    for name, values, valid in [("tmax", maximum, valid_max), ("tmin", minimum, valid_min)]:
        audit[f"{name}_missing_days"] = np.isnan(values).sum(axis=0)
        audit[f"{name}_invalid_days"] = (~valid & ~np.isnan(values)).sum(axis=0)
        cleaned = np.where(valid & ~inverted, values, np.nan)
        longest, jumps = _audit_series(cleaned, jump_c)
        audit[f"{name}_longest_constant_run"] = longest
        audit[f"{name}_constant_flag"] = longest >= constant_run_days
        audit[f"{name}_jump_count"] = jumps
    audit["inverted_days"] = inverted.sum(axis=0)
    audit["paired_valid_days"] = valid_pair.sum(axis=0)
    audit["duplicate_coordinates"] = audit[["latitude", "longitude"]].round(6).duplicated(keep=False)
    audit["missing_elevation"] = audit["elevation_m"].isna()

    # Filtrar antes da soma também evita overflow com sentinelas extremas.
    paired = (np.where(valid_pair, maximum, np.nan) + np.where(valid_pair, minimum, np.nan)) / 2
    daily = pd.DataFrame(paired, index=normal_dates, columns=audit["station_id"])
    monthly_mean = daily.resample("MS").mean()
    monthly_count = daily.resample("MS").count()
    expected = monthly_mean.index.days_in_month.to_numpy()
    accepted = monthly_count.to_numpy() >= np.ceil(expected * minimum_day_fraction)[:, None]
    monthly_mean = monthly_mean.where(accepted)
    station_count = len(audit)
    monthly = pd.DataFrame({
        "station_id": np.tile(audit["station_id"].to_numpy(), len(monthly_mean)),
        "year": np.repeat(monthly_mean.index.year, station_count),
        "month": np.repeat(monthly_mean.index.month, station_count),
        "temperature_c": monthly_mean.to_numpy().ravel(),
        "valid_days": monthly_count.to_numpy().ravel(),
        "expected_days": np.repeat(expected, station_count),
        "accepted": accepted.ravel(),
    })
    monthly["coverage"] = monthly["valid_days"] / monthly["expected_days"]
    audit["accepted_months"] = accepted.sum(axis=0)
    normals, sensitivity = _normal_tables(monthly, audit[STATION_COLUMNS], minimum_year_fraction)
    annual_ids = set(normals.loc[normals["month"] == 0, "station_id"])
    audit["annual_normal_eligible"] = audit["station_id"].isin(annual_ids)
    qc_values = {
        "stations_tmax_input": len(tmax.stations),
        "stations_tmin_input": len(tmin.stations),
        "stations_paired_input": station_count,
        "stations_without_tmax": int((unpaired.available_variable == "tmin").sum()),
        "stations_without_tmin": int((unpaired.available_variable == "tmax").sum()),
        "days_in_normal_period": len(normal_dates),
        "station_days_total": len(normal_dates) * station_count,
        "paired_valid_station_days": int(valid_pair.sum()),
        "inverted_station_days": int(inverted.sum()),
        "accepted_station_months": int(accepted.sum()),
        "rejected_station_months": int((~accepted).sum()),
        "stations_with_annual_normal": len(annual_ids),
        "stations_without_annual_normal": station_count - len(annual_ids),
        "stations_duplicate_coordinates_flag": int(audit["duplicate_coordinates"].sum()),
        "stations_missing_elevation": int(audit["missing_elevation"].sum()),
    }
    for name in ("tmax", "tmin"):
        for key in ("missing_days", "invalid_days", "jump_count", "constant_flag"):
            qc_values[f"{name}_{key}"] = int(audit[f"{name}_{key}"].sum())
    qc = pd.DataFrame(qc_values.items(), columns=["metric", "value"])
    return Prepared(monthly, normals, audit, qc, sensitivity, unpaired)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tmax", default="dados/brutos/Tmax.npz", help="Caminho relativo a refinamento ou absoluto dentro dela.")
    parser.add_argument("--tmin", default="dados/brutos/Tmin.npz", help="Caminho relativo a refinamento ou absoluto dentro dela.")
    parser.add_argument("--source-start", default="1961-01-01", help="Primeiro dia confirmado pelo fornecedor, ISO AAAA-MM-DD.")
    parser.add_argument("--source-end", default="2025-12-31", help="Último dia confirmado pelo fornecedor, ISO AAAA-MM-DD.")
    parser.add_argument("--minimum-day-fraction", type=float, default=0.8)
    parser.add_argument("--minimum-year-fraction", type=float, default=0.8)
    parser.add_argument("--constant-run-days", type=int, default=7)
    parser.add_argument("--jump-c", type=float, default=20.0)
    args = parser.parse_args(argv)
    try:
        paths = [safe_path(args.tmax), safe_path(args.tmin)]
        sources = [load_observations(path, args.source_start, args.source_end) for path in paths]
        result = prepare_temperature(
            *sources, minimum_day_fraction=args.minimum_day_fraction,
            minimum_year_fraction=args.minimum_year_fraction,
            constant_run_days=args.constant_run_days, jump_c=args.jump_c,
        )
        outputs = {
            "dados/processados/temperatura_mensal.csv": result.monthly,
            "dados/processados/normais_temperatura.csv": result.normals,
            "dados/processados/estacoes_auditadas.csv": result.stations,
            "dados/processados/estacoes_sem_par.csv": result.unpaired_stations,
            "resultados/tabelas/controle_qualidade_temperatura.csv": result.qc,
            "resultados/tabelas/sensibilidade_cobertura_temperatura.csv": result.sensitivity,
        }
        # Validar todos os destinos antes da primeira escrita, inclusive links.
        destinations = {name: safe_path(name) for name in outputs}
        manifest_path = safe_path("dados/processados/manifesto_temperatura.json")
        manifest = {
            "created_utc": datetime.now(timezone.utc).isoformat(),
            "source_calendar": [args.source_start, args.source_end],
            "normal_period": [NORMAL_START, NORMAL_END],
            "temperature_definition": "Média de (Tmax+Tmin)/2 somente nos dias pareados válidos.",
            "parameters": vars(args),
            "inputs": [{"path": str(path.relative_to(ROOT)), "sha256": _sha256(path)} for path in paths],
            "numpy_version": np.__version__, "pandas_version": pd.__version__,
            "limitations": [
                "Constância, saltos e locais duplicados são apenas sinalizados; exigem revisão.",
                "Usa apenas interseção de IDs Tmax/Tmin; estações sem par são listadas separadamente.",
                "ID object legado usa Unpickler restrito aos três construtores NumPy e valida elementos str/int; np.load mantém allow_pickle=False.",
                "QC físico exige -30 < Tmax,Tmin < 50 °C e Tmin <= Tmax; limites são operacionais.",
                "Altitude não conferida com MDE; homogeneidade e mudanças de estação não avaliadas.",
                "Não há preenchimento, ajuste de normal reduzida ou comparação com média de 24 h.",
                "Cobertura calculada separadamente para cada mês; testar 70%, 80% e 90% não seleciona um limiar ótimo.",
                "Normal anual exige 12 normais mensais e pesa dias médios de 1991–2020; n_years e coverage anuais são mínimos mensais, não anos completos comuns.",
                "Normal mensal abaixo da cobertura é NaN; ausência de normal anual significa 12 meses não aprovados.",
            ],
        }
        for name, frame in outputs.items():
            destinations[name].parent.mkdir(parents=True, exist_ok=True)
            frame.to_csv(destinations[name], index=False, encoding="utf-8", float_format="%.8f")
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    except (ValueError, OSError, KeyError) as exc:
        parser.exit(2, f"Erro: {exc}\n")
    print(f"Processadas {len(result.stations)} estações; {int(result.stations['annual_normal_eligible'].sum())} com normal anual elegível.")
    print("CSV de observações em refinamento/dados/processados; resumos em refinamento/resultados/tabelas.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
