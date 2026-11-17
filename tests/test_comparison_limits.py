"""Values lying exactly on a comparison limit are read as exact arithmetic reads them, not as floats do.

Found by verification/differential.py, which runs these rules against their Lean model
(verification/lean/TacoRules.lean): with plain floats, 1.45 * 20 is 28.999999999999996 and the median of 0.6
and 0.7 is 0.6499999999999999, which moved one iron value of the TACO x NEVO comparison outside its EU
tolerance.
"""

from __future__ import annotations

import importlib.util
import statistics

from taco_rdf.namespaces import ROOT


def load(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


compare = load("compare_taco_nevo")
pairs = load("check_food_pairs")
IRON, CALCIUM, PROTEIN, SODIUM = (compare.CDNO + c for c in ("0200651", "0200544", "0200040", "0200599"))


def test_a_median_exactly_on_the_lower_mineral_limit_is_within_the_tolerance():
    median = statistics.median([0.6, 0.7])  # 0.6499999999999999 as a float
    assert compare.within_eu_tolerance(IRON, "mg", 1.0, median) is True


def test_a_value_exactly_on_the_upper_mineral_limit_is_within_the_tolerance():
    assert compare.within_eu_tolerance(CALCIUM, "mg", 20.0, 29.0) is True  # 1.45 * 20 = 29
    assert compare.within_eu_tolerance(CALCIUM, "mg", 20.0, 29.000001) is False


def test_macronutrient_and_sodium_limits_are_exact():
    assert compare.within_eu_tolerance(PROTEIN, "g", 9.999999, 7.999999) is True  # exactly 2 g apart
    assert compare.within_eu_tolerance(PROTEIN, "g", 9.999999, 7.999998) is False
    assert compare.within_eu_tolerance(SODIUM, "mg", 500.0, 600.0) is True  # exactly 20 %


def test_twenty_percent_is_exact():
    assert compare.within_20_percent(91.249300, 72.999440) is True  # exactly 20 % of the larger
    assert compare.within_20_percent(91.249300, 72.999439) is False


def test_water_exactly_fifteen_grams_apart_does_not_disagree():
    assert pairs.disagreeing({pairs.WATER: (35.9712, 20.9712, "g")}) == []
    assert pairs.disagreeing({pairs.WATER: (35.971201, 20.9712, "g")}) == ["water"]


def test_a_mineral_exactly_three_times_higher_disagrees():
    copper = "0200642"
    assert pairs.disagreeing({copper: (0.1, 0.3, "mg")}) == ["copper"]  # 0.3 / 0.1 is 2.9999999999999996
    assert pairs.disagreeing({copper: (0.1, 0.299999, "mg")}) == []
