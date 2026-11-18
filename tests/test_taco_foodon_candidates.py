"""TACO FoodOn candidates: names become FoodOn labels; only classes the build could publish are usable."""

from __future__ import annotations

import importlib.util

from taco_rdf.namespaces import ROOT

spec = importlib.util.spec_from_file_location("taco_foodon_candidates",
                                              ROOT / "scripts" / "taco_foodon_candidates.py")
assert spec is not None and spec.loader is not None
step1 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(step1)


def test_comma_names_meet_foodon_labels():
    labels = {"brown rice (cooked)": ("FOODON_1", "brown rice (cooked)")}
    assert step1.name_candidate("Rice, brown, cooked", labels, {}) == (
        "FOODON_1", "brown rice (cooked)", "qualifier, name and state")


def test_accents_fall_back_to_the_folded_word_rules():
    folded = {"creme (raw)": ("FOODON_2", "crème (raw)")}
    assert step1.name_candidate("Crème, fresh", {}, folded) == ("FOODON_2", "crème (raw)", "name and state")
    assert step1.name_candidate("Kibbeh, baked", {}, folded) == ("", "", "")


def test_classes_come_only_from_class_columns():
    row = {"history_class": "FOODON_1; FOODON_2", "name_class": "", "ols1_class": "FOODON_3",
           "nevo_neighbour1_class": "FOODON_4 | FOODON_5", "name_label": "FOODON_9", "note": "FOODON_8"}
    assert step1.classes_in(row) == {"FOODON_1", "FOODON_2", "FOODON_3", "FOODON_4", "FOODON_5"}


def test_usable_means_pinned_and_without_organism_ancestor():
    assert step1.usable({"FOODON_1", "FOODON_2", "FOODON_3"}, {"FOODON_1", "FOODON_2"}, {"FOODON_2"}) == [
        "FOODON_1"]
    assert step1.usable(set(), {"FOODON_1"}, set()) == []
