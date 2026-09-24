from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import replace

import pytest

from taco_rdf import evaluation as ev
from taco_rdf.namespaces import FOOD_NAMES_EN, ROOT


def completed(rows, reviewer):
    return [row | {"decision": "accept", "certainty": "certain", "justification": "Checked the source",
                   "reviewer": reviewer, "reviewed_on": "2026-09-24"} for row in rows]


@pytest.fixture
def context(table, alignments, food_names_en):
    return ev.form_rows([ev.Item(1, "sample", "1/type", 10, 1)], table, alignments, food_names_en,
                        ev.foodon_index().release)


@pytest.fixture
def prepared_round(tmp_path):
    folder = tmp_path / "round"
    subprocess.run([sys.executable, str(ROOT / "scripts/prepare_alignment_review.py"),
                    "--output", str(folder), "--offline", "--per-stratum", "1"],
                   check=True, capture_output=True, text=True)
    return folder


def score(folder):
    return subprocess.run([sys.executable, str(ROOT / "scripts/score_alignment_review.py"), str(folder)],
                          capture_output=True, text=True)


@pytest.mark.parametrize("field,value", [
    ("current_class", "FOODON_00004679"), ("current_relation", "relatedMatch"),
    ("foodon_release", "http://example.org/another-release"), ("name_en", "A different food"),
    ("current_definition", "A different definition"), ("candidates", "A different candidate"),
])
def test_agreement_refuses_different_contexts(tmp_path, context, field, value):
    a, b = tmp_path / "a.csv", tmp_path / "b.csv"
    ev.write_rows(a, completed(context, "A"), ev.CONTEXT + ev.ANSWER)
    altered = [context[0] | {field: value}]
    ev.write_rows(b, completed(altered, "B"), ev.CONTEXT + ev.ANSWER)
    with pytest.raises(ValueError, match=r"different contexts|foodon_release differs"):
        ev.compare(ev.read_answers(a), ev.read_answers(b))
    with pytest.raises(ValueError, match="reference context"):
        ev.read_answers(b, context)


def test_duplicate_answers_are_refused(tmp_path, context):
    rows = completed(context, "A")
    path = tmp_path / "duplicates.csv"
    ev.write_rows(path, [*rows, rows[0] | {"decision": "none"}], ev.CONTEXT + ev.ANSWER)
    with pytest.raises(ValueError, match="duplicate food_number"):
        ev.read_answers(path)


def test_export_refuses_an_alignment_changed_after_review(tmp_path, context, table, alignments):
    path = tmp_path / "answers.csv"
    ev.write_rows(path, completed(context, "A"), ev.CONTEXT + ev.ANSWER)
    changed = [replace(link, predicate="relatedMatch") if link.source_type == "food"
               and link.source_key == "1" else link for link in alignments]
    with pytest.raises(ValueError, match="alignment differs"):
        ev.sssom_rows(ev.read_answers(path), table, changed)


@pytest.mark.parametrize("key", [
    "alignments_sha256", "workbook_sha256", "names_sha256", "problem_cases_sha256",
    "foodon_module_sha256", "correction_cells_sha256", "correction_ids_sha256", "protocol_sha256",
    "context_sha256", "items_sha256",
])
def test_manifest_rejects_changed_or_unrecorded_inputs(prepared_round, key):
    manifest = json.loads((prepared_round / "manifest.json").read_text(encoding="utf-8"))
    ev.validate_round(prepared_round, manifest)
    manifest[key] = "0" * 64
    with pytest.raises(ValueError, match=key):
        ev.validate_round(prepared_round, manifest)
    del manifest[key]
    with pytest.raises(ValueError, match=key):
        ev.validate_round(prepared_round, manifest)


def test_both_reviewers_cannot_replace_the_reference_context(prepared_round):
    rows = ev.read_rows(prepared_round / "context.csv")
    rows[0]["name_en"] = "A translation absent from the reference context"
    for reviewer in ("a", "b"):
        ev.write_rows(prepared_round / f"reviewer-{reviewer}.csv", completed(rows, reviewer),
                      ev.CONTEXT + ev.ANSWER)
    done = score(prepared_round)
    assert done.returncode != 0
    assert "reference context" in done.stdout
    assert not (prepared_round / "adjudication.csv").exists()
    assert not (prepared_round / "results.csv").exists()


def test_scorer_checks_input_hashes_before_producing_results(prepared_round):
    rows = ev.read_rows(prepared_round / "context.csv")
    for reviewer in ("a", "b"):
        ev.write_rows(prepared_round / f"reviewer-{reviewer}.csv", completed(rows, reviewer),
                      ev.CONTEXT + ev.ANSWER)
    path = prepared_round / "manifest.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    manifest["names_sha256"] = "0" * 64
    path.write_text(json.dumps(manifest), encoding="utf-8")
    done = score(prepared_round)
    assert done.returncode != 0
    assert "names_sha256" in done.stdout
    assert not (prepared_round / "adjudication.csv").exists()
    assert not (prepared_round / "reviewed.sssom.tsv").exists()


def test_adjudication_cannot_reuse_a_decision_after_the_reviews_change(prepared_round):
    rows = ev.read_rows(prepared_round / "context.csv")
    a, b = completed(rows, "A"), completed(rows, "B")
    a[0].update(decision="class", relation="close", **{"class": "FOODON_00004678"})
    ev.write_rows(prepared_round / "reviewer-a.csv", a, ev.CONTEXT + ev.ANSWER)
    ev.write_rows(prepared_round / "reviewer-b.csv", b, ev.CONTEXT + ev.ANSWER)
    assert score(prepared_round).returncode == 0
    path = prepared_round / "adjudication.csv"
    adjudication = completed(ev.read_rows(path), "Adjudicator")
    ev.write_rows(path, adjudication, ev.ADJUDICATION)
    a[0]["class"] = "FOODON_00004679"
    ev.write_rows(prepared_round / "reviewer-a.csv", a, ev.CONTEXT + ev.ANSWER)
    done = score(prepared_round)
    assert done.returncode != 0
    assert "a_class" in done.stdout
    assert not (prepared_round / "results.csv").exists()


def test_context_and_items_are_recorded_in_the_manifest(prepared_round):
    manifest = json.loads((prepared_round / "manifest.json").read_text(encoding="utf-8"))
    for name in ("context", "items"):
        assert manifest[f"{name}_sha256"] == ev.review_hash(prepared_round / f"{name}.csv")
    context = ev.validate_round(prepared_round, manifest)
    for reviewer in ("a", "b"):
        rows = ev.read_rows(prepared_round / f"reviewer-{reviewer}.csv")
        ev.check_context(rows, context, reviewer)
        assert all(not row[field] for row in rows for field in ev.ANSWER)


def test_text_hashes_and_context_survive_checkout_line_endings(prepared_round):
    manifest = json.loads((prepared_round / "manifest.json").read_text(encoding="utf-8"))
    baseline = ev.validate_round(prepared_round, manifest)
    for name in ("context", "items", "reviewer-a"):
        path = prepared_round / f"{name}.csv"
        path.write_bytes(path.read_bytes().replace(b"\n", b"\r\n"))
    assert ev.validate_round(prepared_round, manifest) == baseline
    ev.check_context(ev.read_rows(prepared_round / "reviewer-a.csv"), baseline, "reviewer-a")


def test_the_checked_in_round_uses_current_english_names():
    folder = ROOT / "data/alignment/review/round-1"
    manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
    context = ev.validate_round(folder, manifest)
    names = ev.indexed_rows(ev.read_rows(FOOD_NAMES_EN), "English names")
    for row in context:
        assert row["name_en"] == names[int(row["food_number"])]["name_en"]
    for reviewer in ("a", "b"):
        ev.check_context(ev.read_rows(folder / f"reviewer-{reviewer}.csv"), context, reviewer)
