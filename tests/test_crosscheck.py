"""Cross-check the parser against an independent transcription of the workbook (taco-api)."""

from __future__ import annotations

import csv
import re
from decimal import Decimal

import pytest

from taco_rdf.namespaces import ROOT
from taco_rdf.parse import Status

RAW = ROOT / "data" / "raw"

NUTRIENT_COLUMNS = {
    "moisture": "moisture", "kcal": "energy_kcal", "kJ": "energy_kj", "protein": "protein",
    "lipids": "lipids", "cholesterol": "cholesterol", "carbohydrates": "carbohydrate",
    "dietaryFiber": "dietary_fiber", "ash": "ash", "calcium": "calcium", "magnesium": "magnesium",
    "manganese": "manganese", "phosphorus": "phosphorus", "iron": "iron", "sodium": "sodium",
    "potassium": "potassium", "copper": "copper", "zinc": "zinc", "retinol": "retinol", "re": "re",
    "rae": "rae", "thiamin": "thiamin", "riboflavin": "riboflavin", "pyridoxine": "pyridoxine",
    "niacin": "niacin", "vitaminC": "vitamin_c",
}
FATTY_COLUMNS = {
    "saturated": "sfa", "monounsaturated": "mufa", "polyunsaturated": "pufa",
    "12:0": "fa_12_0", "14:0": "fa_14_0", "16:0": "fa_16_0", "18:0": "fa_18_0", "20:0": "fa_20_0",
    "22:0": "fa_22_0", "24:0": "fa_24_0", "14:1": "fa_14_1", "16:1": "fa_16_1", "18:1": "fa_18_1",
    "20:1": "fa_20_1", "18:2n6": "fa_18_2_n6", "18:3n3": "fa_18_3_n3", "20:4": "fa_20_4",
    "20:5": "fa_20_5", "22:5": "fa_22_5", "22:6": "fa_22_6", "18:1t": "fa_18_1t", "18:2t": "fa_18_2t",
}
AMINO_COLUMNS = {
    k: k for k in "tryptophan threonine isoleucine leucine lysine methionine cystine phenylalanine "
                  "tyrosine valine arginine histidine alanine".split()
} | {"asparticAcid": "aspartic_acid", "glutamicAcid": "glutamic_acid", "glycine": "glycine",
     "proline": "proline", "serine": "serine"}


def _rows(name):
    with open(RAW / name, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def _squash(text: str) -> str:
    return re.sub(r"\s+", "", text).casefold()


def _compare(rows, columns, value_of, id_map=None):
    """Return a list of disagreements between the CSV rows and the parsed observations."""
    problems = []
    for row in rows:
        csv_id = int(row["foodId"])
        fid = (id_map or {}).get(csv_id, csv_id)
        for col, key in columns.items():
            raw = row[col].strip()
            obs = value_of.get((fid, key))
            if raw == "":
                if obs is not None and obs.status is Status.MEASURED:
                    problems.append((fid, key, "csv blank, parsed measured", obs.value))
                continue
            decimals = len(raw.split(".")[1]) if "." in raw else 0
            tol = Decimal(5) / Decimal(10) ** (decimals + 1)
            csv_val = Decimal(raw)
            if obs is None:
                problems.append((fid, key, "csv has value, parsed none", raw))
            elif obs.status is Status.TRACE:
                if csv_val != 0:
                    problems.append((fid, key, "parsed trace, csv non-zero", raw))
            elif obs.status is Status.MEASURED:
                if abs(obs.value - csv_val) > tol:
                    problems.append((fid, key, f"differ (tol {tol})", (obs.value, raw)))
            else:
                problems.append((fid, key, f"parsed {obs.status.value}, csv has value", raw))
    return problems


def test_food_ids_names_and_groups_agree(table):
    rows = _rows("food.csv")
    assert len(rows) == 597
    for r in rows:
        food = table.foods[int(r["id"])]
        assert food.group_id == int(r["categoryId"])
        csv_name = re.sub(r" [12]$", "", r["name"])
        assert _squash(food.name) == _squash(csv_name)
    assert [g for g in table.groups] == [r["name"] for r in _rows("categories.csv")]


def test_composition_values_agree_with_the_independent_transcription(value_of):
    problems = _compare(_rows("nutrients.csv"), NUTRIENT_COLUMNS, value_of)
    assert problems == []


def test_fatty_acid_values_agree(value_of):
    assert _compare(_rows("fatty-acids.csv"), FATTY_COLUMNS, value_of) == []


def test_amino_acid_values_agree_except_for_the_documented_food_number_defect(value_of):
    """taco-api keeps the workbook's wrong food number 468 for 'Maria mole'; we reassign it to 504."""
    rows = _rows("amino-acids.csv")
    assert {int(r["foodId"]) for r in rows} - {468} == {
        fid for (fid, key) in value_of if key == "tryptophan"
    } - {504}
    assert _compare(rows, AMINO_COLUMNS, value_of, id_map={468: 504}) == []
    assert value_of[(468, "protein")].value > Decimal("9")
    assert value_of[(504, "protein")].value < Decimal("4")
    total_aa = sum(
        value_of[(504, k)].value for k in AMINO_COLUMNS.values() if (504, k) in value_of
    )
    assert abs(total_aa - value_of[(504, "protein")].value) < Decimal("0.5")


@pytest.mark.parametrize("fid, key, csv_expected", [
    (1, "fa_14_0", "0.00"),
])
def test_trace_versus_zero_is_the_information_we_keep(value_of, fid, key, csv_expected):
    fa = {r["foodId"]: r for r in _rows("fatty-acids.csv")}
    column = next(c for c, k in FATTY_COLUMNS.items() if k == key)
    assert fa[str(fid)][column] == csv_expected
    assert value_of[(fid, key)].status is Status.TRACE


def test_the_crosscheck_can_actually_fail(value_of):
    """Guard against a vacuous comparison: corrupt one value and one status, expect findings."""
    from dataclasses import replace

    tampered = dict(value_of)
    tampered[(1, "protein")] = replace(value_of[(1, "protein")], value=Decimal("9.9"))
    tampered[(2, "iron")] = replace(value_of[(2, "iron")], status=Status.NOT_APPLICABLE, value=None)
    problems = _compare(_rows("nutrients.csv"), NUTRIENT_COLUMNS, tampered)
    assert {(p[0], p[1]) for p in problems} == {(1, "protein"), (2, "iron")}
