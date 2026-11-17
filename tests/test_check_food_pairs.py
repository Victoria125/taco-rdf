"""The composition check flags TACO and NEVO food pairs that disagree in several components."""

from __future__ import annotations

import importlib.util

from taco_rdf.namespaces import OBO, ROOT

spec = importlib.util.spec_from_file_location("check_food_pairs", ROOT / "scripts" / "check_food_pairs.py")
assert spec is not None and spec.loader is not None
check = importlib.util.module_from_spec(spec)
spec.loader.exec_module(check)

WATER, PROTEIN, CARBOHYDRATE, IRON = "0200002", "0200040", "0200033", "0200651"


def row(taco: str, nevo: str, code: str, taco_value: float, nevo_value: float, unit: str) -> dict[str, str]:
    return {"taco_food": taco, "taco_name": f"TACO {taco}", "nevo_food": f"https://example.org/nevocode#{nevo}",
            "nevo_name": f"NEVO {nevo}", "foodon": str(OBO.FOODON_03301449), "foodon_label": "potato (raw)",
            "class": f"{OBO}CDNO_{code}", "taco_value": str(taco_value), "nevo_value": str(nevo_value),
            "unit": unit}


def test_a_dry_food_against_a_prepared_one_disagrees_in_water_protein_and_carbohydrate():
    values = {WATER: (10.0, 70.0, "g"), PROTEIN: (9.0, 3.0, "g"), CARBOHYDRATE: (70.0, 20.0, "g")}
    assert check.disagreeing(values) == ["water", "protein", "available carbohydrate"]


def test_protein_within_the_eu_tolerance_does_not_disagree():
    # below 10 g the tolerance is 2 g either way, TACO's value taken as the declared one
    assert check.disagreeing({PROTEIN: (5.0, 6.9, "g")}) == []
    assert check.disagreeing({PROTEIN: (5.0, 7.1, "g")}) == ["protein"]


def test_a_mineral_counts_from_three_times_higher_and_only_above_a_trace_amount():
    assert check.disagreeing({IRON: (1.0, 2.9, "mg")}) == []
    assert check.disagreeing({IRON: (1.0, 3.0, "mg")}) == ["iron"]
    assert check.disagreeing({IRON: (0.1, 0.4, "mg")}) == []  # four times higher, but a trace of iron


def test_a_pair_is_flagged_from_three_strongly_disagreeing_components():
    rows = [row("92", "1", WATER, 80.0, 79.0, "g"), row("92", "1", PROTEIN, 1.8, 2.0, "g"),
            row("39", "3228", WATER, 10.0, 70.0, "g"), row("39", "3228", PROTEIN, 9.0, 3.0, "g"),
            row("39", "3228", CARBOHYDRATE, 70.0, 20.0, "g")]
    checked = {(r["taco_food"], r["nevo_code"]): r for r in check.check(rows)}
    assert checked["39", "3228"]["flagged"] == "True"
    assert checked["39", "3228"]["found_by_hand"] == "True"
    assert checked["92", "1"] | {"disagreeing": "", "flagged": "False"} == checked["92", "1"]


def test_the_report_names_no_nevo_food():
    rows = [row("39", "3228", WATER, 10.0, 70.0, "g"), row("39", "3228", PROTEIN, 9.0, 3.0, "g"),
            row("39", "3228", CARBOHYDRATE, 70.0, 20.0, "g")]
    text = check.report(check.check(rows), "pairs.csv", "2026-11-05")
    assert "NEVO 3228" not in text and "| 39 | TACO 39 |" in text
