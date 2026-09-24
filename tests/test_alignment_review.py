from __future__ import annotations

import csv
import json
import subprocess
import sys
from collections import Counter

import pytest

from taco_rdf import evaluation as ev
from taco_rdf.namespaces import ROOT

PROBLEM_CASES = ROOT / "data" / "alignment" / "review" / "problem_cases.csv"
DAY = "2026-09-24"


def fill(rows, answers, reviewer):
    filled = []
    for row in rows:
        base = {"certainty": "certain", "justification": "checked against the TACO name",
                "reviewer": reviewer, "reviewed_on": DAY}
        filled.append(row | base | answers[int(row["food_number"])])
    return filled


@pytest.fixture(scope="module")
def items(table, alignments):
    return ev.review_items(table, alignments, ev.load_problem_cases(PROBLEM_CASES), seed="test",
                           per_stratum=2)


def test_the_round_has_the_sample_the_problem_cases_and_every_prepared_dish(table, items):
    numbers = [i.food_number for i in items]
    assert len(numbers) == len(set(numbers))
    assert set(ev.load_problem_cases(PROBLEM_CASES)) <= set(numbers)
    prepared = table.groups.index("Alimentos preparados") + 1
    assert {f.id for f in table.foods.values() if f.group_id == prepared} <= set(numbers)
    for item in items:
        if item.part == "sample":
            assert item.sample_size == min(2, item.stratum_size)
            assert 0 < item.inclusion_probability <= 1
        else:
            assert item.inclusion_probability is None


def test_the_sample_is_reproducible(table, alignments, items):
    again = ev.review_items(table, alignments, ev.load_problem_cases(PROBLEM_CASES), seed="test",
                            per_stratum=2)
    assert again == items
    other = ev.review_items(table, alignments, {}, seed="another seed", per_stratum=2)
    assert {i.food_number for i in other if i.part == "sample"} != {
        i.food_number for i in items if i.part == "sample"}


def test_cohen_kappa_on_a_small_example():
    assert ev.cohen_kappa(["accept", "accept", "none", "none"], ["accept", "none", "none", "none"]) == 0.5
    assert ev.cohen_kappa(["accept", "none"], ["accept", "none"]) == 1.0


def test_kappa_is_not_estimable_for_empty_or_constant_decisions():
    assert ev.cohen_kappa([], []) is None
    assert ev.cohen_kappa(["accept"] * 5, ["accept"] * 5) is None
    assert ev.Agreement([1], [], None).share == 1.0
    assert ev.Agreement([1], [], None).kappa_text == "not estimable"
    with pytest.raises(ValueError, match="equally sized"):
        ev.cohen_kappa(["accept"], [])


def form(table, alignments, food_names_en, numbers):
    items = [ev.Item(n, "sample", "x/y", 4, 2) for n in numbers]
    return ev.form_rows(items, table, alignments, food_names_en, ev.foodon_index().release)


def test_an_incomplete_or_inconsistent_form_is_refused(tmp_path, table, alignments, food_names_en):
    rows = fill(form(table, alignments, food_names_en, [1, 279]),
                {1: {"decision": "accept", "justification": ""},
                 279: {"decision": "class", "relation": "close", "class": "codfish"}}, "reviewer one")
    path = tmp_path / "form.csv"
    ev.write_rows(path, rows, ev.CONTEXT + ev.ANSWER)
    with pytest.raises(ValueError) as problems:
        ev.read_answers(path)
    assert "food 1: justification is empty" in str(problems.value)
    assert "food 279: class must be a FoodOn identifier" in str(problems.value)


def test_accepting_and_saying_no_class_agree_for_an_unmapped_food(tmp_path, table, alignments, food_names_en):
    rows = form(table, alignments, food_names_en, [540])
    for who, decision in (("a", "accept"), ("b", "none")):
        ev.write_rows(tmp_path / f"{who}.csv", fill(rows, {540: {"decision": decision}}, who),
                      ev.CONTEXT + ev.ANSWER)
    agreement = ev.compare(ev.read_answers(tmp_path / "a.csv"), ev.read_answers(tmp_path / "b.csv"))
    assert agreement.agreed == [540]


def test_a_round_from_forms_to_results(tmp_path, table, alignments, food_names_en):
    items = [ev.Item(1, "sample", "1/type", 10, 2), ev.Item(562, "problem case", flag="carioca"),
             ev.Item(279, "problem case", flag="salted cod"), ev.Item(540, "prepared dish")]
    rows = ev.form_rows(items, table, alignments, food_names_en, ev.foodon_index().release)
    shared = {562: {"decision": "relation", "relation": "related"},
              279: {"decision": "class", "relation": "broad", "class": "FOODON_00001248"},
              540: {"decision": "none"}}
    a = fill(rows, shared | {1: {"decision": "accept"}}, "reviewer one")
    b = fill(rows, shared | {1: {"decision": "class", "relation": "close", "class": "FOODON_00004677"}},
             "reviewer two")
    for name, filled in (("a", a), ("b", b)):
        ev.write_rows(tmp_path / f"{name}.csv", filled, ev.CONTEXT + ev.ANSWER)
    answers_a, answers_b = ev.read_answers(tmp_path / "a.csv"), ev.read_answers(tmp_path / "b.csv")
    agreement = ev.compare(answers_a, answers_b)
    assert agreement.disagreed == [1] and agreement.agreed == [279, 540, 562]
    with pytest.raises(ValueError, match="without an adjudicated decision"):
        ev.final_answers(answers_a, answers_b, agreement, {})

    adjudication = ev.adjudication_rows(rows, answers_a, answers_b, agreement.disagreed)
    decided = fill(adjudication, {1: {"decision": "accept"}}, "both reviewers")
    ev.write_rows(tmp_path / "adjudication.csv", decided, ev.ADJUDICATION)
    final = ev.final_answers(answers_a, answers_b, agreement, ev.read_answers(tmp_path / "adjudication.csv"))

    summary = ev.summarise(items, final)
    assert summary["parts"]["sample"] == Counter({"correct": 1})
    assert summary["parts"]["problem case"] == Counter({"wrong relation": 1, "class missed": 1})
    assert summary["parts"]["prepared dish"] == Counter({"correctly unmapped": 1})
    assert [e.food_number for e in summary["errors"]] == [562, 279]
    mapped = ev.sssom_rows(final, table, alignments)
    sssom = {r["subject_id"]: (r["predicate_id"], r["object_id"]) for r in mapped}
    assert sssom == {"tacoid:food/1": ("rdf:type", "FOODON:00004678"),
                     "tacoid:food/279": ("skos:broadMatch", "FOODON:00001248"),
                     "tacoid:food/540": ("skos:closeMatch", "sssom:NoTermFound"),
                     "tacoid:food/562": ("skos:relatedMatch", "FOODON:03000089")}


@pytest.mark.parametrize("food,decision,target", [
    (279, "class", "FOODON_00001248"), (280, "relation", ""),
])
def test_reviewers_can_propose_foodon_class_membership(tmp_path, table, alignments, food_names_en,
                                                    food, decision, target):
    rows = form(table, alignments, food_names_en, [food])
    answers = {food: {"decision": decision, "relation": "type", "class": target}}
    path = tmp_path / "typed.csv"
    ev.write_rows(path, fill(rows, answers, "reviewer"), ev.CONTEXT + ev.ANSWER)
    result = ev.sssom_rows(ev.read_answers(path), table, alignments)
    assert result[0]["predicate_id"] == "rdf:type"
    assert result[0]["object_id"] == (target or rows[0]["current_class"]).replace("FOODON_", "FOODON:")


def test_accepting_a_skos_mapping_preserves_the_relation(tmp_path, table, alignments, food_names_en):
    rows = form(table, alignments, food_names_en, [273, 280])
    path = tmp_path / "skos.csv"
    ev.write_rows(path, fill(rows, {273: {"decision": "accept"}, 280: {"decision": "accept"}}, "reviewer"),
                  ev.CONTEXT + ev.ANSWER)
    result = ev.sssom_rows(ev.read_answers(path), table, alignments)
    assert [row["predicate_id"] for row in result] == ["skos:closeMatch", "skos:relatedMatch"]


def test_the_scripts_prepare_a_round_and_report_it(tmp_path):
    folder = tmp_path / "round-test"
    run = [sys.executable, str(ROOT / "scripts" / "prepare_alignment_review.py"), "--output", str(folder),
           "--offline", "--per-stratum", "1"]
    subprocess.run(run, check=True, capture_output=True, text=True)
    manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["items"] == sum(manifest["parts"].values())
    assert "2026-09-20" in manifest["foodon_release"]
    with open(folder / "reviewer-a.csv", newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    assert "part" not in rows[0] and "flag" not in rows[0]
    accept = {int(r["food_number"]): {"decision": "accept"} for r in rows}
    for who in ("a", "b"):
        ev.write_rows(folder / f"reviewer-{who}.csv", fill(rows, accept, f"reviewer {who}"),
                      ev.CONTEXT + ev.ANSWER)
    score = [sys.executable, str(ROOT / "scripts" / "score_alignment_review.py"), str(folder)]
    done = subprocess.run(score, check=True, capture_output=True, text=True)
    assert "0 disagreements" in done.stdout
    report = (folder / "results.md").read_text(encoding="utf-8")
    assert "kappa on the decision is not estimable" in report
    assert "100%" in report
    assert "## Estimated precision" in report
    assert "| all links |" in report
    assert "It says nothing about whether the links are right" in report
    assert (folder / "reviewed.sssom.tsv").read_text(encoding="utf-8").startswith("# curie_map:")
    assert "#   rdf: http://www.w3.org/1999/02/22-rdf-syntax-ns#" in (
        folder / "reviewed.sssom.tsv").read_text(encoding="utf-8")
    with pytest.raises(subprocess.CalledProcessError):
        subprocess.run(run, check=True, capture_output=True, text=True)


def judged(food, decision, mapped=True):
    return ev.Answer(food, "FOODON_00004678" if mapped else "", "type" if mapped else "none", decision, "", "",
                     "certain", "checked", "", "reviewer", DAY, "release", ())


def test_precision_is_estimated_by_weighting_each_stratum_by_its_size():
    items = [ev.Item(1, "sample", "1/type", 10, 2), ev.Item(2, "sample", "1/type", 10, 2),
             ev.Item(3, "sample", "2/type", 30, 2), ev.Item(4, "sample", "2/type", 30, 2),
             ev.Item(5, "sample", "3/none", 50, 1), ev.Item(6, "problem case")]
    final = {1: judged(1, "accept"), 2: judged(2, "accept"), 3: judged(3, "accept"), 4: judged(4, "class"),
             5: judged(5, "class", mapped=False), 6: judged(6, "none")}
    estimate = ev.precision_estimate(items, final)
    assert estimate.share == pytest.approx((10 * 1 + 30 * 0.5) / 40)
    assert (estimate.links, estimate.covered, estimate.judged) == (40, 40, 4)
    assert 0 < estimate.low < estimate.share < estimate.high < 1
    assert ev.precision_estimate(items, final, relation="relatedMatch").text() == "not estimable"


def test_right_class_counts_a_link_whose_relation_alone_was_wrong():
    items = [ev.Item(1, "sample", "1/relatedMatch", 4, 2), ev.Item(2, "sample", "1/relatedMatch", 4, 2)]
    final = {1: judged(1, "accept"), 2: judged(2, "relation")}
    assert ev.precision_estimate(items, final).share == 0.5
    assert ev.precision_estimate(items, final, right=("correct", "wrong relation")).share == 1.0


def test_unsure_answers_leave_the_estimate_and_can_leave_a_stratum_uncovered():
    items = [ev.Item(1, "sample", "1/type", 10, 2), ev.Item(2, "sample", "1/type", 10, 2),
             ev.Item(3, "sample", "2/type", 30, 1)]
    final = {1: judged(1, "accept"), 2: judged(2, "unsure"), 3: judged(3, "unsure")}
    estimate = ev.precision_estimate(items, final)
    assert (estimate.share, estimate.links, estimate.covered, estimate.judged) == (1.0, 40, 10, 1)
    assert estimate.low < 1.0


def test_a_fully_reviewed_stratum_adds_no_sampling_variance():
    items = [ev.Item(1, "sample", "1/type", 2, 2), ev.Item(2, "sample", "1/type", 2, 2)]
    final = {1: judged(1, "accept"), 2: judged(2, "class")}
    estimate = ev.precision_estimate(items, final)
    assert estimate.share == 0.5
    assert estimate.low == pytest.approx(ev.wilson(0.5, 2)[0])
