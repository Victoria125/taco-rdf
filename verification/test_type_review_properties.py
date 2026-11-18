"""Properties of round 2's sample and scoring, tried on many generated cases with Hypothesis.

The kappa of taco_rdf.evaluation is compared with a second implementation in exact fractions.

    $env:PYTHONPATH = "src;<folder with hypothesis>"
    python -m pytest verification/test_type_review_properties.py
"""

from __future__ import annotations

import importlib.util
import math
from collections import Counter
from fractions import Fraction

from hypothesis import given, settings
from hypothesis import strategies as st

from taco_rdf.evaluation import cohen_kappa
from taco_rdf.namespaces import ROOT

spec = importlib.util.spec_from_file_location("prepare_type_review",
                                              ROOT / "scripts" / "prepare_type_review.py")
assert spec is not None and spec.loader is not None
prepare = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prepare)

sizes = st.dictionaries(st.sampled_from("abcdefghij"), st.integers(min_value=1, max_value=60), min_size=1)
decisions = st.lists(st.sampled_from(["FOODON_1", "FOODON_2", "FOODON_3", "none"]), min_size=1, max_size=60)


def exact_kappa(a: list[str], b: list[str]) -> Fraction | None:
    n = len(a)
    observed = Fraction(sum(x == y for x, y in zip(a, b, strict=True)), n)
    ca, cb = Counter(a), Counter(b)
    expected = Fraction(sum(ca[k] * cb[k] for k in ca), n * n)
    return None if expected == 1 else (observed - expected) / (1 - expected)


@settings(max_examples=2000)
@given(sizes, st.data())
def test_seats_add_up_and_stay_within_one_of_the_exact_quota(groups, data):
    total = sum(groups.values())
    n = data.draw(st.integers(min_value=0, max_value=total))
    seats = prepare.allocate(groups, n)
    assert sum(seats.values()) == n
    for g, size in groups.items():
        quota = Fraction(n * size, total)
        assert math.floor(quota) <= seats[g] <= math.ceil(quota) <= size


@settings(max_examples=500)
@given(sizes, st.integers(min_value=0, max_value=2**32), st.data())
def test_the_sample_is_a_subset_of_the_right_size_and_reproducible(groups, seed, data):
    foods, start = {}, 0
    for g, size in groups.items():
        foods[g] = list(range(start, start + size))
        start += size
    n = data.draw(st.integers(min_value=0, max_value=start))
    sample = prepare.draw(foods, n, seed)
    assert len(sample) == n and sample <= set(range(start))
    assert sample == prepare.draw(foods, n, seed)
    seats = prepare.allocate({g: len(f) for g, f in foods.items()}, n)
    assert all(len(sample & set(f)) == seats[g] for g, f in foods.items())


@settings(max_examples=3000)
@given(decisions, st.data())
def test_kappa_matches_exact_fractions_and_is_symmetric(a, data):
    b = data.draw(st.lists(st.sampled_from(["FOODON_1", "FOODON_2", "FOODON_3", "none"]),
                           min_size=len(a), max_size=len(a)))
    k, exact = cohen_kappa(a, b), exact_kappa(a, b)
    assert (k is None) == (exact is None)
    if k is not None:
        assert abs(k - float(exact)) < 1e-12
        assert k <= 1 + 1e-12
        assert abs(k - cohen_kappa(b, a)) < 1e-12


@settings(max_examples=1000)
@given(decisions)
def test_identical_decisions_give_kappa_one(a):
    k = cohen_kappa(a, list(a))
    assert k is None if len(set(a)) == 1 else abs(k - 1) < 1e-12
