"""TACO foods FoodOn has no class for: untyped foods without a usable candidate, organisms matched by name."""

from __future__ import annotations

import csv
import importlib.util

from taco_rdf.namespaces import ROOT

spec = importlib.util.spec_from_file_location("foodon_term_requests",
                                              ROOT / "scripts" / "foodon_term_requests.py")
assert spec is not None and spec.loader is not None
terms = importlib.util.module_from_spec(spec)
spec.loader.exec_module(terms)


def test_an_organism_counts_only_when_its_label_shares_a_word_with_the_food():
    labels = {"FOODON_1": "pequi plant", "FOODON_2": "pequin pepper plant", "FOODON_3": "catfish"}
    row = {"name_en": "Pequi, raw", "blocked_classes": "FOODON_1; FOODON_2"}
    assert terms.organisms(row, labels) == ["FOODON_1 pequi plant"]
    assert terms.organisms({"name_en": "Pintado (spotted sorubim catfish), baked",
                            "blocked_classes": "FOODON_3"}, labels) == ["FOODON_3 catfish"]


def test_only_foods_without_a_usable_candidate_are_requests():
    sheet = [{"food_number": "1", "name_pt": "Umbu, cru", "name_en": "Umbu, raw",
              "group": "Frutas e derivados", "usable_classes": "", "blocked_classes": ""},
             {"food_number": "2", "name_pt": "Banana, prata, crua", "name_en": "Banana, prata, raw",
              "group": "Frutas e derivados", "usable_classes": "FOODON_00004184", "blocked_classes": ""}]
    assert [r["food_number"] for r in terms.requests_from(sheet, {})] == ["1"]


def test_the_list_holds_untyped_foods_and_taco_names_only():
    with (ROOT / "analysis" / "data" / "foodon_term_requests.csv").open(encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        assert reader.fieldnames == ["food_number", "name_pt", "name_en", "group", "foodon_has_the_organism"]
        rows = list(reader)
    with (ROOT / "analysis" / "data" / "foodon_typing_gaps.csv").open(encoding="utf-8") as fh:
        untyped = {r["food_number"]: r["name_pt"] for r in csv.DictReader(fh)}
    assert all(untyped.get(r["food_number"]) == r["name_pt"] for r in rows)
    if not untyped:
        assert rows == []
