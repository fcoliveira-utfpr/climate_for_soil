import numpy as np
import pytest

from codigo.falhas_artificiais import estimate_normal, scenarios


def test_difference_corrects_known_trend_and_hidden_observations_cannot_leak():
    reference = np.linspace(10, 20, 30)
    observed = reference + 3
    retained = np.arange(30) >= 20
    estimates = estimate_normal(observed, reference, retained)
    assert estimates["difference"] == pytest.approx(observed.mean())
    assert estimates["regression_fill"] == pytest.approx(observed.mean())
    assert estimates["available_years"] > observed.mean()
    changed = observed.copy()
    changed[~retained] = np.nan
    assert estimate_normal(changed, reference, retained) == estimates


def test_regression_recovers_a_nonunit_anomaly_slope():
    reference = np.linspace(10, 20, 30)
    observed = 2 * reference - 5
    retained = np.arange(30) >= 10
    estimates = estimate_normal(observed, reference, retained)
    assert estimates["regression_fill"] == pytest.approx(observed.mean())
    assert abs(estimates["difference"] - observed.mean()) > 1


@pytest.mark.parametrize("case", ["too_short", "no_missing", "missing_reference", "constant_reference", "int_mask"])
def test_invalid_gap_experiments_are_rejected(case):
    reference = np.arange(30, dtype=float)
    observed = reference + 2
    mask = np.arange(30) >= 10
    if case == "too_short":
        mask = np.arange(30) >= 28
    elif case == "no_missing":
        mask[:] = True
    elif case == "missing_reference":
        reference[0] = np.nan
    elif case == "constant_reference":
        reference[:] = 10
    else:
        mask = mask.astype(int)
    with pytest.raises(ValueError):
        estimate_normal(observed, reference, mask)


def test_scenarios_have_reproducible_coverage_and_explicit_recent_periods():
    first = list(scenarios(np.random.default_rng(42)))
    second = list(scenarios(np.random.default_rng(42)))
    assert len(first) == 93
    for (name, repeat, mask), (other, repeat2, mask2) in zip(first, second):
        assert (name, repeat) == (other, repeat2)
        np.testing.assert_array_equal(mask, mask2)
        assert mask.sum() == int(name.rsplit("_", 1)[1])
        if name == "recent_10":
            assert np.flatnonzero(mask).tolist() == list(range(20, 30))
