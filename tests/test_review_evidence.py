from __future__ import annotations

import csv
import json
import subprocess
import sys

import pytest

from taco_rdf import evaluation as ev
from taco_rdf.namespaces import ROOT


def completed(rows, reviewer, evidence):
    return [row | {"decision": "accept", "certainty": "certain", "justification": "Checked the source",
                   "evidence": evidence, "reviewer": reviewer, "reviewed_on": "2026-09-24"}
            for row in rows]


def score(folder):
    return subprocess.run([sys.executable, str(ROOT / "scripts/score_alignment_review.py"), str(folder)],
                          capture_output=True, text=True)


def sssom_file(path):
    with path.open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader((line for line in stream if not line.startswith("#")), delimiter="\t"))


@pytest.fixture
def prepared_round(tmp_path):
    folder = tmp_path / "round"
    subprocess.run([sys.executable, str(ROOT / "scripts/prepare_alignment_review.py"),
                    "--output", str(folder), "--offline", "--per-stratum", "1"],
                   check=True, capture_output=True, text=True)
    return folder


@pytest.mark.parametrize("first,second,merged", [
    ("  TACO p. 122 | corn\nFoodOn: café  ", "Second source | p. 7\nDefinition",
     "  TACO p. 122 | corn\nFoodOn: café  \nSecond source | p. 7\nDefinition"),
    ("Same evidence", "Same evidence", "Same evidence"),
    ("", "Recorded source", "Recorded source"),
    ("", "", ""),
])
def test_agreement_preserves_both_evidence_records(tmp_path, table, alignments, food_names_en,
                                                  first, second, merged):
    rows = ev.form_rows([ev.Item(1, "sample")], table, alignments, food_names_en,
                        ev.foodon_index().release)
    answers = {}
    for who, evidence in (("a", first), ("b", second)):
        path = tmp_path / f"{who}.csv"
        ev.write_rows(path, completed(rows, who, evidence), ev.CONTEXT + ev.ANSWER)
        answers[who] = ev.read_answers(path)
        assert answers[who][1].evidence == evidence
    final = ev.final_answers(answers["a"], answers["b"], ev.compare(answers["a"], answers["b"]), {})
    assert final[1].evidence == merged
    assert final[1].a_evidence == first
    assert final[1].b_evidence == second
    exported = ev.sssom_rows(final, table, alignments)
    comment = json.loads(exported[0]["comment"])
    assert comment == {"justification": final[1].justification, "certainty": "certain",
                       "evidence": merged, "a_evidence": first, "b_evidence": second}


def test_scorer_preserves_agreed_evidence_in_csv_and_sssom(prepared_round):
    rows = ev.read_rows(prepared_round / "context.csv")
    first, second = "Source A | café\nPage 122", "Source B | maize\nDefinition"
    for who, evidence in (("a", first), ("b", second)):
        ev.write_rows(prepared_round / f"reviewer-{who}.csv", completed(rows, who, evidence),
                      ev.CONTEXT + ev.ANSWER)
    done = score(prepared_round)
    assert done.returncode == 0, done.stdout + done.stderr
    results = ev.read_rows(prepared_round / "results.csv")
    assert len(results) == len(rows)
    for row in results:
        assert row["evidence"] == first + "\n" + second
        assert row["a_evidence"] == first
        assert row["b_evidence"] == second
    exported = sssom_file(prepared_round / "reviewed.sssom.tsv")
    assert len(exported) == len(rows)
    for row in exported:
        comment = json.loads(row["comment"])
        assert comment["evidence"] == first + "\n" + second
        assert comment["a_evidence"] == first
        assert comment["b_evidence"] == second


def prepare_disagreement(folder):
    rows = ev.read_rows(folder / "context.csv")
    selected = next(row for row in rows if row["current_class"])
    first, second = "Reviewer A | source\nDefinition", "Reviewer B | source\nScope"
    for who, evidence in (("a", first), ("b", second)):
        answers = completed(rows, who, evidence)
        if who == "a":
            next(row for row in answers if row["food_number"] == selected["food_number"])["decision"] = "none"
        ev.write_rows(folder / f"reviewer-{who}.csv", answers, ev.CONTEXT + ev.ANSWER)
    done = score(folder)
    assert done.returncode == 0, done.stdout + done.stderr
    return selected["food_number"], first, second


def test_adjudication_preserves_evidence_and_its_reviewer_provenance(prepared_round):
    food, first, second = prepare_disagreement(prepared_round)
    path = prepared_round / "adjudication.csv"
    adjudication = ev.read_rows(path)
    assert len(adjudication) == 1
    row = adjudication[0]
    assert row["food_number"] == food
    assert row["a_evidence"] == first
    assert row["b_evidence"] == second
    assert (row["a_reviewer"], row["b_reviewer"]) == ("a", "b")
    assert (row["a_reviewed_on"], row["b_reviewed_on"]) == ("2026-09-24", "2026-09-24")
    evidence = "Adjudicator | independent source\nCafé, page 2"
    ev.write_rows(path, completed(adjudication, "Adjudicator", evidence), ev.ADJUDICATION)
    done = score(prepared_round)
    assert done.returncode == 0, done.stdout + done.stderr
    result = next(row for row in ev.read_rows(prepared_round / "results.csv") if row["food_number"] == food)
    assert result["evidence"] == evidence
    assert result["a_evidence"] == first
    assert result["b_evidence"] == second
    assert result["reviewer"] == "Adjudicator"
    exported = next(row for row in sssom_file(prepared_round / "reviewed.sssom.tsv")
                    if row["subject_id"] == f"tacoid:food/{food}")
    comment = json.loads(exported["comment"])
    assert comment["evidence"] == evidence
    assert comment["a_evidence"] == first
    assert comment["b_evidence"] == second


def test_adjudication_is_stale_when_only_reviewer_evidence_changes(prepared_round):
    food, first, _second = prepare_disagreement(prepared_round)
    path = prepared_round / "adjudication.csv"
    ev.write_rows(path, completed(ev.read_rows(path), "Adjudicator", "Decision source"), ev.ADJUDICATION)
    reviewer = prepared_round / "reviewer-a.csv"
    answers = ev.read_rows(reviewer)
    next(row for row in answers if row["food_number"] == food)["evidence"] = first + "\nCorrected source"
    ev.write_rows(reviewer, answers, ev.CONTEXT + ev.ANSWER)
    done = score(prepared_round)
    assert done.returncode != 0
    assert "a_evidence" in done.stdout
    assert not (prepared_round / "results.csv").exists()
    assert not (prepared_round / "reviewed.sssom.tsv").exists()
