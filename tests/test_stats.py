import math
from socrix import stats as S


def test_wilson_known_value():            # 9/11 -> 0.523 (published worked example)
    assert round(S.wilson_lower(9, 11), 3) == 0.523


def test_wilson_edges():
    assert math.isnan(S.wilson_lower(0, 0))
    assert S.wilson_lower(0, 10) == 0.0
    assert 0 < S.wilson_lower(10, 10) < 1


def test_modified_z_orientation_and_floor():
    m, med, mad = S.modified_z(10, [1, 2, 3, 4, 5], higher_is_worse=True)
    assert med == 3 and mad == 1 and round(m, 3) == round(0.6745 * 7, 3)
    m2, *_ = S.modified_z(10, [1, 2, 3, 4, 5], higher_is_worse=False)
    assert m2 == -m
    m3, _, mad3 = S.modified_z(0.1, [0, 0, 0, 0, 0], mad_floor=0.05)   # all-equal peers must not divide by zero
    assert mad3 == 0.05 and math.isfinite(m3)


def test_concern_mapping():
    assert S.concern_from_modz(3.5) == 50.0
    assert S.concern_from_modz(7) == 100.0 and S.concern_from_modz(20) == 100.0
    assert S.concern_from_modz(-3) == 0.0


def test_power_mean_limits_dilution_and_skips_nan():
    assert round(S.power_mean([100, 0, 0, 0], p=1), 6) == 25.0
    assert S.power_mean([100, 0, 0, 0], p=3) > 60
    assert S.power_mean([50, float("nan")], p=3) == 50.0
    assert S.power_mean([0, 0, 0, 0], p=3) == 0.0          # no 8e-16 float noise in displayed areas
    assert math.isnan(S.power_mean([float("nan")]))


def test_binomial_helpers():
    assert abs(S.binomial_sf(0, 40, 0.1) - 1) < 1e-12
    assert abs(S.binomial_sf(1, 40, 0.0032) - (1 - (1 - 0.0032) ** 40)) < 1e-12
    assert S.binomial_se(0.0, 20) > 0            # p=0 still has sampling noise (continuity guard)
