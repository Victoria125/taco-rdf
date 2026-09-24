from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import replace

import pytest
from rdflib import OWL, RDF, Graph

from taco_rdf import evaluation as ev
from taco_rdf.namespaces import FOODON_MODULE_TTL, ROOT


def completed(rows, reviewer):
    return [row | {"decision": "accept", "certainty": "certain", "justification": "Checked the source",
                   "reviewer": reviewer, "reviewed_on": "2026-09-24"} for row in rows]


def score(folder):
    return subprocess.run([sys.executable, str(ROOT / "scripts/score_alignment_review.py"), str(folder)],
                          capture_output=True, text=True)


@pytest.fixture
def context(table, alignments, food_names_en):
    return ev.form_rows([ev.Item(1, "sample")], table, alignments, food_names_en,
                        ev.foodon_index().release)


@pytest.fixture
def prepared_round(tmp_path):
    folder = tmp_path / "round"
    subprocess.run([sys.executable, str(ROOT / "scripts/prepare_alignment_review.py"),
                    "--output", str(folder), "--offline", "--per-stratum", "1"],
                   check=True, capture_output=True, text=True)
    return folder


def test_review_index_uses_class_declarations_from_the_pinned_module():
    graph = Graph().parse(FOODON_MODULE_TTL, format="turtle")
    declared = {str(term).rsplit("/", 1)[-1] for term in graph.subjects(RDF.type, OWL.Class)
                if str(term).startswith("http://purl.obolibrary.org/obo/FOODON_")}
    index = ev.foodon_index()
    assert set(index.labels) == declared
    assert index.release in {str(version) for version in graph.objects(None, OWL.versionIRI)}
    assert "FOODON_99999999" not in index.labels


@pytest.mark.parametrize("changes", [
    {"decision": "class", "relation": "close", "class": "FOODON_99999999"},
    {"decision": "accept", "current_class": "FOODON_99999999"},
    {"decision": "relation", "relation": "related", "current_class": "FOODON_99999999"},
])
def test_review_rejects_undeclared_foodon_targets(tmp_path, context, changes):
    path = tmp_path / "answers.csv"
    rows = completed(context, "Reviewer")
    rows[0].update(changes)
    ev.write_rows(path, rows, ev.CONTEXT + ev.ANSWER)
    with pytest.raises(ValueError, match="FOODON_99999999"):
        ev.read_answers(path)


def test_review_rejects_a_release_that_differs_from_the_local_module(tmp_path, context):
    rows = completed(context, "Reviewer")
    rows[0]["foodon_release"] = "http://example.org/foodon/another-release"
    path = tmp_path / "answers.csv"
    ev.write_rows(path, rows, ev.CONTEXT + ev.ANSWER)
    with pytest.raises(ValueError, match="release"):
        ev.read_answers(path)


def test_proposed_class_exports_its_label_from_the_pinned_module(tmp_path, context, table, alignments):
    index = ev.foodon_index()
    target = next(term for term, label in index.labels.items()
                  if label and term != context[0]["current_class"])
    rows = completed(context, "Reviewer")
    rows[0].update(decision="class", relation="close", **{"class": target})
    path = tmp_path / "answers.csv"
    ev.write_rows(path, rows, ev.CONTEXT + ev.ANSWER)
    exported = ev.sssom_rows(ev.read_answers(path), table, alignments)
    assert exported[0]["object_id"] == target.replace("FOODON_", "FOODON:")
    assert exported[0]["object_label"] == index.labels[target]
    assert exported[0]["object_source_version"] == index.release


@pytest.mark.parametrize("changes,expected", [
    ({"decision": "class", "relation": "close", "target": "FOODON_99999999"}, "FOODON_99999999"),
    ({"foodon_release": "http://example.org/foodon/another-release"}, "release"),
])
def test_export_revalidates_targets_and_release(tmp_path, context, table, alignments, changes, expected):
    path = tmp_path / "answers.csv"
    ev.write_rows(path, completed(context, "Reviewer"), ev.CONTEXT + ev.ANSWER)
    answer = replace(ev.read_answers(path)[1], **changes)
    with pytest.raises(ValueError, match=expected):
        ev.sssom_rows({1: answer}, table, alignments)


@pytest.mark.parametrize("stage", ["reviewer", "adjudicator"])
def test_scorer_blocks_nonexistent_targets_before_export(prepared_round, stage):
    rows = ev.read_rows(prepared_round / "context.csv")
    food = next(row["food_number"] for row in rows if row["current_class"])
    for who in ("a", "b"):
        answers = completed(rows, who)
        selected = next(row for row in answers if row["food_number"] == food)
        if who == "a":
            if stage == "reviewer":
                selected.update(decision="class", relation="close", **{"class": "FOODON_99999999"})
            else:
                selected["decision"] = "none"
        ev.write_rows(prepared_round / f"reviewer-{who}.csv", answers, ev.CONTEXT + ev.ANSWER)
    if stage == "adjudicator":
        done = score(prepared_round)
        assert done.returncode == 0, done.stdout + done.stderr
        path = prepared_round / "adjudication.csv"
        answers = completed(ev.read_rows(path), "Adjudicator")
        answers[0].update(decision="class", relation="close", **{"class": "FOODON_99999999"})
        ev.write_rows(path, answers, ev.ADJUDICATION)
    done = score(prepared_round)
    assert done.returncode != 0
    assert "FOODON_99999999" in done.stdout
    assert not (prepared_round / "results.csv").exists()
    assert not (prepared_round / "reviewed.sssom.tsv").exists()


def test_matching_manifest_and_context_cannot_claim_another_module_release(prepared_round):
    release = "http://example.org/foodon/another-release"
    context_path = prepared_round / "context.csv"
    rows = [row | {"foodon_release": release} for row in ev.read_rows(context_path)]
    ev.write_rows(context_path, rows, ev.CONTEXT)
    for who in ("a", "b"):
        ev.write_rows(prepared_round / f"reviewer-{who}.csv", completed(rows, who), ev.CONTEXT + ev.ANSWER)
    manifest_path = prepared_round / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest.update(foodon_release=release, context_sha256=ev.review_hash(context_path))
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    done = score(prepared_round)
    assert done.returncode != 0
    assert "release" in done.stdout
    assert not (prepared_round / "adjudication.csv").exists()
    assert not (prepared_round / "results.csv").exists()
    assert not (prepared_round / "reviewed.sssom.tsv").exists()
