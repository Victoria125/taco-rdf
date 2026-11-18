"""Properties of the FoodOn candidate rules, tried on many generated cases with Hypothesis.

The rules come from scripts/nevo_foodon_candidates.py and scripts/taco_foodon_candidates.py; the names are
generated from a small vocabulary of NEVO- and TACO-style words, with no NEVO name used.

    $env:PYTHONPATH = "src;<folder with hypothesis>"
    python -m pytest verification/test_candidate_properties.py
"""

from __future__ import annotations

import importlib.util

from hypothesis import given, settings
from hypothesis import strategies as st

from taco_rdf.namespaces import ROOT


def load(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


step1 = load("taco_foodon_candidates")
nevo = step1.nevo
WORDS = ["rice", "beans", "pear", "bread", "w", "wo", "excl", "without", "raw", "boiled", "fresh", "prep",
         "tinned", "av", "brown", "skin", "Crème", "fraîche", "10-<20%", "salt", "milk", "and", ",", "(raw)"]
CLASSES = st.sets(st.sampled_from([f"FOODON_{i}" for i in range(12)]))
names = st.lists(st.sampled_from(WORDS), min_size=1, max_size=8).map(" ".join)


@settings(max_examples=2000)
@given(CLASSES, CLASSES, CLASSES)
def test_usable_is_exactly_pinned_minus_blocked(found, pinned, blocked):
    usable = step1.usable(found, pinned, blocked)
    assert set(usable) == (found & pinned) - blocked
    assert not set(usable) & blocked
    assert usable == sorted(usable)


@settings(max_examples=2000)
@given(names)
def test_nothing_after_without_or_excluding_says_what_the_food_is(name):
    ws = nevo.words(name)
    cut = next((i for i, w in enumerate(ws) if w in nevo.NOT), len(ws))
    what = nevo.what(ws)
    assert all(w in ws[:cut] for w in what)
    assert not any(w in nevo.STATES or any(ch.isdigit() for ch in w) for w in what)


@settings(max_examples=2000)
@given(names)
def test_folding_twice_changes_nothing(name):
    assert nevo.fold(nevo.fold(name)) == nevo.fold(name)


@settings(max_examples=1000)
@given(names, st.lists(names, max_size=12), st.integers(min_value=1, max_value=3))
def test_neighbours_share_the_first_word_and_come_best_first(name, others, n):
    typed = [{"name_en": o, "classes": [("FOODON_1", "x")]} for o in others]
    found = nevo.neighbours(name, typed, n=n)
    assert len(found) <= n
    scores = [s for s, _ in found]
    assert scores == sorted(scores, reverse=True)
    assert all(0 < s <= 1 or s == 0 for s in scores)
    head = step1.tbca.singular(nevo.words(name)[0]) if nevo.words(name) else ""
    assert all(head in nevo.content(food["name_en"]) for _, food in found)


COLUMNS = st.sampled_from(["history_class", "name_class", "ols1_class", "name_label", "note"])
VALUES = st.lists(st.sampled_from([f"FOODON_{i}" for i in range(6)]), max_size=3).map("; ".join)


@settings(max_examples=1000)
@given(st.dictionaries(COLUMNS, VALUES))
def test_classes_come_from_class_columns_only(row):
    expected = {c for k, v in row.items() if k.endswith("_class") for c in v.split("; ") if c}
    assert step1.classes_in(row) == expected
