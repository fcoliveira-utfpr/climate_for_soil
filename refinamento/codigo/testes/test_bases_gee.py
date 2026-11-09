import numpy as np
import pytest

from codigo.bases_gee import MONTHS, decode_batch, validate_calendar


def test_calendar_accepts_month_start_and_month_end_but_not_duplicate_or_missing():
    times = [int(p.start_time.tz_localize("UTC").timestamp() * 1000) for p in MONTHS]
    end_times = [int(p.end_time.normalize().tz_localize("UTC").timestamp() * 1000) for p in MONTHS]
    assert validate_calendar(times) == validate_calendar(end_times)
    for damaged in (times[:-1], [times[1], *times[1:]], times[::-1]):
        with pytest.raises(ValueError, match="360 meses"):
            validate_calendar(damaged)


def test_decode_preserves_masked_pixels_and_zero_without_changing_station_ids():
    bands = [f"m{p.year}_{p.month:02d}" for p in MONTHS]
    props = {"station_id": "0001", **{b: 20.0 for b in bands}}
    props[bands[0]], props[bands[1]] = 0, None
    del props[bands[2]]
    result = decode_batch([{"properties": props}], ["0001"], bands, "era5")
    assert len(result) == 360
    assert result.station_id.eq("0001").all()
    assert result.grid_c.iloc[0] == 0
    assert result.grid_c.isna().sum() == 2
    assert result.iloc[-1][["year", "month"]].tolist() == [2020, 12]


@pytest.mark.parametrize("value", [280, np.inf, -100])
def test_decode_rejects_wrong_units_or_nonfinite_values(value):
    bands = [f"m{p.year}_{p.month:02d}" for p in MONTHS]
    props = {"station_id": "S1", bands[0]: value}
    with pytest.raises(ValueError, match="escala/offset"):
        decode_batch([{"properties": props}], ["S1"], bands, "era5")


@pytest.mark.parametrize("ids", [[], ["S2"], ["S1", "S1"]])
def test_decode_rejects_changed_station_set(ids):
    bands = [f"m{p.year}_{p.month:02d}" for p in MONTHS]
    with pytest.raises(ValueError, match="estações"):
        decode_batch([{"properties": {"station_id": s}} for s in ids], ["S1"], bands, "era5")
