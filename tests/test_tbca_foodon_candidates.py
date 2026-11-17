"""TBCA's English food names are rewritten into FoodOn-style labels to propose candidates for review."""

from __future__ import annotations

import importlib.util

from taco_rdf.namespaces import ROOT

spec = importlib.util.spec_from_file_location("tbca_foodon_candidates",
                                              ROOT / "scripts" / "tbca_foodon_candidates.py")
assert spec is not None and spec.loader is not None
candidates = importlib.util.module_from_spec(spec)
spec.loader.exec_module(candidates)

LABELS = {label.lower(): (f"FOODON_{i:08d}", label) for i, label in enumerate(
    ["white rice (raw)", "white rice", "ham (cooked)", "ham", "pork (cooked)", "shrimp (cooked)",
     "crustacean", "cashew nut", "nut (roasted)", "chickpea", "canned", "cowpea (raw)"])}


def label_for(name_en: str) -> tuple[str, str]:
    _, label, rule = candidates.candidate(name_en, LABELS)
    return label, rule


def test_the_most_specific_label_wins_qualifier_name_and_state_before_name():
    assert label_for("Rice, white, raw, Brazil (average of several cultivars)") == (
        "white rice (raw)", "qualifier, name and state")


def test_a_qualifier_is_tried_as_the_name_only_after_a_category():
    assert label_for("Crustacean, shrimp, unshelled, cooked, Brazil") == (
        "shrimp (cooked)", "qualifier as name, and state")
    assert label_for("Ham, pork, cooked, Brazil") == ("ham (cooked)", "name and state")
    assert label_for("Chickpea, canned, drained, Brazil") == ("chickpea", "name")


def test_a_plural_qualifier_and_a_name_in_brackets_are_tried_in_the_singular():
    assert label_for("Cashew, nuts, toasted, with salt, Brazil") == ("cashew nut", "name and qualifier")
    assert label_for("Beans, black eyed (cowpeas), raw, Brazil") == (
        "cowpea (raw)", "name in brackets and state")


def test_a_state_followed_by_details_still_counts():
    assert candidates.state_of("cooked (50% beans, 50% water)") == "cooked"
    assert candidates.state_of("cookedish") is None


def test_a_name_without_any_label_gets_no_candidate():
    assert label_for("Brazilian sweets (coconut and sugar)") == ("", "")
