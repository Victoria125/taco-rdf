"""The rules of scripts/nutrient_definitions.py: when a shared nutrient code is the same quantity."""

from __future__ import annotations

import importlib.util

from taco_rdf.namespaces import ROOT

SCRIPT = ROOT / "scripts" / "nutrient_definitions.py"
spec = importlib.util.spec_from_file_location("nutrient_definitions", SCRIPT)
assert spec is not None and spec.loader is not None
nd = importlib.util.module_from_spec(spec)
spec.loader.exec_module(nd)

SAME, ELEMENT, UNIT, CALCULATED, OTHER_CODE, CONFIRM = nd.VERDICTS


def test_the_verdict_checks_nevo_s_values_then_the_unit_then_the_data_then_the_definition():
    assert nd.verdict("sodium", 0, {"mg"}, set(), None) == OTHER_CODE
    assert nd.verdict("tryptophan", 26, {"g"}, {"mg"}, "same") == UNIT
    assert nd.verdict("energy_kcal", 1673, {"kcal"}, {"kcal"}, "differs") == CALCULATED
    assert nd.verdict("re", 592, {"µg"}, {"µg"}, "same") == SAME
    assert nd.verdict("calcium", 1673, {"mg"}, {"mg"}, None) == ELEMENT
    assert nd.verdict("thiamin", 1673, {"mg"}, {"mg"}, None) == CONFIRM


def test_a_test_holds_for_95_percent_fails_below_half_and_is_unclear_between():
    assert nd.holds((95, 100)) is True
    assert nd.holds((49, 100)) is False
    assert nd.holds((70, 100)) is None
    assert nd.holds((0, 0)) is None


def test_nevo_s_carbohydrate_as_a_sum_makes_taco_s_by_difference_another_calculation():
    results = {"carbohydrate: sum": {"NEVO": (98, 100), "TACO": (0, 582)}}
    assert nd.test_says("carbohydrate", results, 0) == "differs"
    results = {"carbohydrate: sum": {"NEVO": (10, 100), "TACO": (0, 582)}}
    assert nd.test_says("carbohydrate", results, 0) == "same"


def test_energy_differs_when_nevo_follows_the_eu_factors_and_taco_does_not():
    results = {"energy kcal: EU": {"NEVO": (99, 100), "TACO": (36, 100)}}
    assert nd.test_says("energy kcal", results, 0) == "differs"
    results = {"energy kcal: EU": {"NEVO": (99, 100), "TACO": (99, 100)}}
    assert nd.test_says("energy kcal", results, 0) == "same"


def test_protein_is_the_same_kind_when_nevo_uses_a_factor_per_food():
    results = {"protein: 6.25": {"NEVO": (18, 347), "TACO": (0, 0)}}
    assert nd.test_says("protein", results, 132) == "same"
    assert nd.test_says("protein", results, 1) == "differs"


def test_the_nutrients_that_could_take_a_nevo_code_are_taco_s_own_and_every_tagname_is_a_taco_nutrient():
    mapping = {r["taco_nutrient"]: r["nevo_code"] for r in nd.mapping()}
    assert all(key in mapping and not mapping[key] for key in nd.COULD_TAKE)
    assert set(nd.TAGNAMES) <= set(mapping)
    assert set(nd.TEST_OF) | nd.BY_DEFINITION <= {k for k, code in mapping.items() if code}
