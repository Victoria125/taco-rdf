"""Round 2 of the alignment review: the sample, the forms and the scoring of FoodOn type decisions."""

from __future__ import annotations

import csv
import importlib.util
import json
import shutil

import pytest

from taco_rdf.namespaces import ROOT

ROUND_2 = ROOT / "data" / "alignment" / "review" / "round-2"


def load(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


prepare = load("prepare_type_review")
score = load("score_type_review")


def test_seats_follow_group_sizes_with_largest_remainders():
    assert prepare.allocate({"a": 50, "b": 30, "c": 20}, 10) == {"a": 5, "b": 3, "c": 2}
    assert prepare.allocate({"a": 2, "b": 1}, 2) == {"a": 1, "b": 1}
    assert prepare.allocate({"a": 1, "b": 1, "c": 1}, 2) == {"a": 1, "b": 1, "c": 0}


def test_the_sample_is_drawn_again_from_the_same_seed():
    groups = {"a": list(range(1, 21)), "b": list(range(21, 31))}
    first = prepare.draw(groups, 9, seed=7)
    assert first == prepare.draw(groups, 9, seed=7)
    assert len(first) == 9 and len(first & set(groups["a"])) == 6


def test_candidates_carry_labels_and_sources_not_food_names():
    row = {"usable_classes": "FOODON_1; FOODON_2", "name_class": "FOODON_1", "ols1_class": "FOODON_1",
           "nevo_neighbour1_class": "FOODON_2; FOODON_3", "nevo_neighbour1_food": "Some NEVO food"}
    text = prepare.candidates(row, {"FOODON_1": "rice (cooked)", "FOODON_2": "rice"})
    assert text == "FOODON_1 rice (cooked) [OLS, name] | FOODON_2 rice [NEVO neighbour]"
    assert "Some NEVO food" not in text


def test_decisions_are_normalised_and_checked():
    assert score.normal(" FOODON:03301449 ") == "FOODON_03301449"
    assert score.normal("http://purl.obolibrary.org/obo/FOODON_03301449") == "FOODON_03301449"
    assert score.normal("None") == "none"
    form = {1: {"decision": "FOODON_1"}, 2: {"decision": "FOODON_9"}, 3: {"decision": "FOODON_2"},
            4: {"decision": "none", "searched_terms": ""}, 5: {"decision": ""}}
    assert score.problems(form, {"FOODON_1", "FOODON_2"}, {"FOODON_2"}) == [
        "2: FOODON_9 is not a class of the pinned FoodOn release",
        "3: FOODON_2 has a whole organism or plant among its ancestors",
        "4: none without searched_terms"]


def test_agreement():
    assert score.agreement(["a", "b", "none"], ["a", "c", "none"]) == 2 / 3
    assert score.agreement([], []) is None


needs_round_2 = pytest.mark.skipif(not (ROUND_2 / "manifest.json").is_file(), reason="round 2 not prepared")


@needs_round_2
def test_round_2_matches_its_recorded_inputs():
    manifest = json.loads((ROUND_2 / "manifest.json").read_text(encoding="utf-8"))
    context = score.validate(ROUND_2, manifest)
    assert len(context) == manifest["foods"]
    with (ROUND_2 / "items.csv").open(encoding="utf-8") as fh:
        assert sum(r["in_sample"] == "True" for r in csv.DictReader(fh)) == manifest["sample_size"]


@needs_round_2
def test_round_2_refuses_a_changed_form(tmp_path):
    folder = tmp_path / "round-2"
    shutil.copytree(ROUND_2, folder)
    manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
    form = folder / "reviewer-2.csv"
    with form.open(encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    rows[0]["candidates"] = "FOODON_1 something else [name]"
    with form.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]), lineterminator="\r\n")
        w.writeheader()
        w.writerows(rows)
    with pytest.raises(ValueError, match=r"differs from context\.csv"):
        score.validate(folder, manifest)
