"""C11 em vários anos: estabilidade da diferença entre as definições de temperatura média.

Repete a comparação de definicoes_temperatura_inmet.py (mesmo dia UTC, 24 registros válidos,
mesma fórmula da compensada) nos arquivos oficiais do INMET de 2008, 2012, 2016, 2020 e 2024.
Pergunta: a diferença (Tmax + Tmin)/2 − média de 24 h é estável entre anos e entre regiões?
Se for, ela pode ser tratada como um deslocamento conhecido; se variar, não.

Também mede a estabilidade por estação: para estações presentes em vários anos, compara a
diferença média anual de cada estação entre os anos (desvio padrão entre anos).

Uso, de dentro de refinamento/:  python -B -m codigo.definicoes_multianual
"""
import io
import json
import unicodedata
import zipfile

import numpy as np
import pandas as pd
import requests

from codigo.dados_temperatura import safe_path
from codigo.definicoes_temperatura_inmet import daily_means
from codigo.grade_brasil import digest
from codigo.metricas import metricas

YEARS = [2008, 2012, 2016, 2020, 2024]
URL = "https://portal.inmet.gov.br/uploads/dadoshistoricos/{year}.zip"


def _normal(text):
    return "".join(c for c in unicodedata.normalize("NFKD", text.strip().upper()) if not unicodedata.combining(c))


def read_station(content):
    """Lê os dois formatos do INMET: 2020/01/01 e 0000 UTC, ou 2008-01-01 e 00:00."""
    text = content.decode("latin1")
    lines = text.splitlines()
    metadata = {_normal(line.split(";")[0]).strip(":"): line.split(";")[1] for line in lines[:8]}
    frame = pd.read_csv(io.StringIO(text), sep=";", skiprows=8, decimal=",", na_values=["-9999", "-9999.0", "-9999,0"])
    columns = {_normal(c): c for c in frame}

    def column(prefix):
        return next(v for k, v in columns.items() if k.startswith(prefix))

    dates = pd.to_datetime(frame.iloc[:, 0].astype(str).str.replace("/", "-"), format="%Y-%m-%d")
    hours = frame.iloc[:, 1].astype(str).str.extract(r"^(\d{2})")[0].astype(int)
    times = dates + pd.to_timedelta(hours, unit="h")
    values = pd.DataFrame({name: pd.to_numeric(frame[column(prefix)], errors="coerce").to_numpy() for name, prefix in
                           [("air", "TEMPERATURA DO AR"), ("maximum", "TEMPERATURA MAXIMA NA HORA"),
                            ("minimum", "TEMPERATURA MINIMA NA HORA")]}, index=pd.DatetimeIndex(times))
    return metadata, values


def download(year):
    path = safe_path(f"dados/brutos/inmet_{year}.zip")
    if not path.exists():
        partial = path.with_suffix(".part")
        with requests.get(URL.format(year=year), stream=True, timeout=(15, 300)) as response:
            response.raise_for_status()
            with partial.open("wb") as handle:
                for chunk in response.iter_content(1024 * 1024):
                    handle.write(chunk)
        partial.replace(path)
    return path


def monthly_for_year(year):
    cache = safe_path(f"dados/inmet/c11_meses_{year}.csv")
    if cache.exists():
        return pd.read_csv(cache, dtype={"station_id": str}).assign(year=year), None
    path = download(year)
    days = []
    with zipfile.ZipFile(path) as archive:
        files = sorted(n for n in archive.namelist() if n.lower().endswith(".csv"))
        for index, name in enumerate(files):
            try:
                metadata, frame = read_station(archive.read(name))
            except (StopIteration, ValueError, KeyError):
                continue
            frame = frame[~frame.index.duplicated(keep="first")]
            daily = daily_means(frame)
            daily = daily.loc[daily.date.dt.year.eq(year)].copy()
            daily["station_id"], daily["region"] = metadata.get("CODIGO (WMO)", name), metadata.get("REGIAO", "")
            days.append(daily)
            if (index + 1) % 100 == 0:
                print(f"C11 {year}: {index + 1}/{len(files)} estações", flush=True)
    daily = pd.concat(days, ignore_index=True)
    daily["month"] = daily.date.dt.month
    monthly = daily.groupby(["station_id", "region", "month"]).agg(
        n_days=("date", "size"), mean_24h=("mean_24h", "mean"), mean_extremes=("mean_extremes", "mean"),
        mean_compensated=("mean_compensated", "mean")).reset_index()
    required = {m: int(np.ceil(pd.Period(f"{year}-{m:02d}").days_in_month * 0.8)) for m in range(1, 13)}
    monthly = monthly[monthly.n_days >= monthly.month.map(required)].assign(year=year)
    cache.parent.mkdir(parents=True, exist_ok=True)
    monthly.to_csv(cache, index=False)
    return monthly, {"year": year, "source": URL.format(year=year), "source_sha256": digest(path), "files": len(files)}


def main():
    frames, sources = [], []
    for year in YEARS:
        monthly, source = monthly_for_year(year)
        frames.append(monthly)
        if source:
            sources.append(source)
    data = pd.concat(frames, ignore_index=True)
    data["diff_extremes"] = data.mean_extremes - data.mean_24h
    data["diff_compensated"] = data.mean_compensated - data.mean_24h
    rows = []
    for year, frame in data.groupby("year"):
        for method in ("mean_extremes", "mean_compensated"):
            rows.append({"scope": "year", "year": year, "group": "all", "method": method,
                         "n_stations": frame.station_id.nunique(), **metricas(frame.mean_24h, frame[method])})
        for region, part in frame.groupby("region"):
            if part.station_id.nunique() >= 5:
                rows.append({"scope": "region", "year": year, "group": region, "method": "mean_extremes",
                             "n_stations": part.station_id.nunique(), **metricas(part.mean_24h, part.mean_extremes)})
    by_year = pd.DataFrame(rows)
    by_month = (data.groupby(["year", "month"]).diff_extremes.mean().unstack("year").round(3)
                .reset_index().rename(columns=lambda c: f"vies_{c}" if isinstance(c, (int, np.integer)) else c))
    station_year = data.groupby(["station_id", "year"]).diff_extremes.mean().unstack("year")
    repeated = station_year.dropna(thresh=3)
    stability = pd.DataFrame([{
        "stations_in_3plus_years": int(len(repeated)),
        "median_between_year_sd_c": float(repeated.std(axis=1, ddof=1).median()),
        "p90_between_year_sd_c": float(repeated.std(axis=1, ddof=1).quantile(0.9)),
        "between_station_sd_c": float(repeated.mean(axis=1).std(ddof=1)),
        "station_mean_offset_min_c": float(repeated.mean(axis=1).min()),
        "station_mean_offset_max_c": float(repeated.mean(axis=1).max()),
    }])
    by_year.to_csv(safe_path("resultados/tabelas/c11_definicoes_multianual.csv"), index=False)
    by_month.to_csv(safe_path("resultados/tabelas/c11_vies_mensal_multianual.csv"), index=False)
    stability.to_csv(safe_path("resultados/tabelas/c11_estabilidade_estacoes.csv"), index=False)
    report = {"years": YEARS, "sources": sources, "script_sha256": digest(__file__), "station_months": len(data),
              "rule": "same as definicoes_temperatura_inmet.py; months with at least 80% of complete days"}
    safe_path("resultados/tabelas/c11_definicoes_multianual.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(by_year[by_year.scope.eq("year")][["year", "method", "n_stations", "bias", "rmse"]].round(3).to_string(index=False))
    print(stability.round(3).to_string(index=False))


if __name__ == "__main__":
    main()
