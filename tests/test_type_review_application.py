"""Application preserves independent evidence and refuses corrupted or unsafe review data."""

from __future__ import annotations

import importlib.util
import json

import pytest
from rdflib import OWL, RDF, RDFS, Graph

from taco_rdf import graph as graphmod
from taco_rdf import type_review as tr
from taco_rdf.namespaces import OBO, ROOT

spec = importlib.util.spec_from_file_location("apply_review", ROOT / "scripts/apply_alignment_review.py")
assert spec is not None and spec.loader is not None
applymod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(applymod)

A, B, C = "FOODON_00000001", "FOODON_00000002", "FOODON_00000003"


def write(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(tr.csv_bytes(rows, list(rows[0]), "\r\n"))


def seal(folder):
    receipt = json.loads((folder / "adjudication-receipt.json").read_text(encoding="utf-8"))
    receipt["outputs_sha256"] = {
        str(folder / name): tr.digest(folder / name, normalized=False)
        for name in (
            "reviewed-types.csv",
            "adjudication-all.csv",
            "adjudication.csv",
            "adjudication-additional.csv",
        )
    }
    (folder / "adjudication-receipt.json").write_text(json.dumps(receipt), encoding="utf-8")


@pytest.fixture
def review(tmp_path):
    root, folder = tmp_path / "repo", tmp_path / "repo/data/alignment/review/round-1"
    folder.mkdir(parents=True)
    owl = root / "foodon.owl"
    graph = Graph()
    for term in (A, B, C):
        graph.add((OBO[term], RDF.type, OWL.Class))
    graph.add((OBO[B], RDFS.subClassOf, OBO[A]))
    graph.serialize(owl, format="xml")
    classes = root / "ontology/imports/foodon-classes.tsv"
    classes.parent.mkdir(parents=True)
    classes.write_text(
        f"# release: https://example.org/releases/2026-09-20/foodon.owl\n"
        f"# sha256: {tr.digest(owl, normalized=False)}\nclass\tlabel\n"
        f"{A}\tfood A\n{B}\tfood B\n{C}\tfood C\n",
        encoding="utf-8",
    )
    protocol = root / "docs/alignment-review-v3.md"
    protocol.parent.mkdir(parents=True)
    protocol.write_text("Protocol 3 fixture\n", encoding="utf-8")
    baseline = [
        {"food_number": "1", "target_iri": str(OBO[A])},
        {"food_number": "3", "target_iri": str(OBO[A])},
    ]
    write(root / "analysis/data/foodon_types.csv", baseline)
    write(root / "analysis/data/foodon_typing_gaps.csv", [{"food_number": "2"}])
    context = [
        {
            "food_number": str(i),
            "name_pt": f"Food {i}",
            "name_en": f"Food {i}",
            "group": "group",
            "candidates": "",
        }
        for i in (1, 2, 3)
    ]
    write(folder / "context.csv", context)
    write(folder / "items.csv", [{"food_number": str(i), "in_sample": "True"} for i in (1, 2, 3)])
    forms = []
    for number in (1, 2):
        decisions = (A, A if number == 1 else B, C)
        form = [
            r
            | {
                "decision": d,
                "justification": f"Reason {number}/{r['food_number']}",
                "searched_terms": "",
                "unsure": "",
            }
            for r, d in zip(context, decisions, strict=True)
        ]
        write(folder / f"reviewer-{number}.csv", form)
        forms.append(form)
    adj = [
        {
            "food_number": str(n),
            "name_pt": f"Food {n}",
            "source_sheet": "adjudication",
            "adjudicated": d,
            "justification": f"Adjudicator reason {n}",
        }
        for n, d in ((2, B), (3, C))
    ]
    write(folder / "adjudication-all.csv", adj)
    write(folder / "adjudication-additional.csv", [adj[1]])
    write(
        folder / "adjudication.csv",
        [
            {
                "food_number": "2",
                "name_pt": "Food 2",
                "reviewer_1": A,
                "reviewer_2": B,
                "adjudicated": B,
                "justification": adj[0]["justification"],
            }
        ],
    )
    final = []
    for n, (a, b) in enumerate(zip(*forms, strict=True), 1):
        adjudicated = adj[n - 2] if n > 1 else None
        decision = adjudicated["adjudicated"] if adjudicated else a["decision"]
        row = {k: a[k] for k in ("food_number", "name_pt", "name_en", "group")}
        row.update(
            decision=decision,
            decision_label=f"food {chr(64 + int(decision[-1]))}",
            decision_source="adjudication" if adjudicated else "reviewer_agreement",
            adjudicator="Third Reviewer" if adjudicated else "",
            adjudication_sheet="adjudication" if adjudicated else "",
            adjudication_justification=adjudicated["justification"] if adjudicated else "",
        )
        for number, answer in enumerate((a, b), 1):
            row.update({f"reviewer_{number}_{key}": answer[key] for key in tr.ANSWERS})
        final.append(row)
    write(folder / "reviewed-types.csv", final)
    receipt = {
        "human_confirmed_by_user": True,
        "adjudicator": "Third Reviewer",
        "processed_on": "2026-11-19",
        "foods": 3,
        "adjudicated": 2,
        "original_agreements_retained": 1,
        "with_class": 3,
        "none": 0,
        "unique_classes": 3,
    }
    (folder / "adjudication-receipt.json").write_text(json.dumps(receipt), encoding="utf-8")
    seal(folder)
    inputs = (
        "analysis/data/foodon_types.csv",
        "analysis/data/foodon_typing_gaps.csv",
        "ontology/imports/foodon-classes.tsv",
        "docs/alignment-review-v3.md",
    )
    manifest = {
        "protocol_version": 3,
        "protocol": "docs/alignment-review-v3.md",
        "hash_format": "sha256-lf-v1",
        "foodon_release": "2026-09-20",
        "foods": 3,
        "sample_size": 3,
        "inputs": {path: tr.digest(root / path) for path in inputs},
        "context_sha256": tr.digest(folder / "context.csv"),
        "items_sha256": tr.digest(folder / "items.csv"),
    }
    (folder / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    for relative in tr.AUDITS:
        snapshot = folder / "baseline" / relative
        snapshot.parent.mkdir(parents=True, exist_ok=True)
        snapshot.write_bytes((root / relative).read_bytes())
    alignments = root / "alignments.csv"
    rows = [
        {
            "source_type": "food",
            "source_key": str(n),
            "predicate": "type",
            "target_iri": str(OBO[A]),
            "target_label": "food A",
            "target_ontology": "FoodOn",
            "note": "original",
        }
        for n in (1, 3)
    ]
    rows += [
        {
            "source_type": "food",
            "source_key": "3",
            "predicate": "closeMatch",
            "target_iri": "https://example.org/nevo/3",
            "target_label": "NEVO 3",
            "target_ontology": "NEVO",
            "note": "other dataset",
        },
        {
            "source_type": "nutrient",
            "source_key": "protein",
            "predicate": "closeMatch",
            "target_iri": "https://example.org/protein",
            "target_label": "protein",
            "target_ontology": "CDNO",
            "note": "nutrient untouched",
        },
    ]
    write(alignments, rows)
    return root, folder, owl, alignments


def apply(review):
    root, folder, owl, alignments = review
    return applymod.apply_type_review(
        folder,
        alignments,
        owl,
        root=root,
        applied_on="2026-11-22",
        reviewer_1="Reviewer One",
        reviewer_2="Reviewer Two",
    )


def test_apply_activates_exact_decisions_and_preserves_unrelated_rows(review, monkeypatch):
    root, folder, _, alignments = review
    before = tr.read_rows(alignments)
    assert apply(review) == {"unchanged": 1, "added": 1, "class changed": 1}
    rows = tr.read_rows(alignments)
    assert [r for r in rows if r["target_ontology"] != "FoodOn"] == before[2:]
    assert {int(r["source_key"]): r["target_iri"] for r in rows if r["target_ontology"] == "FoodOn"} == {
        1: str(OBO[A]),
        2: str(OBO[B]),
        3: str(OBO[C]),
    }
    saved = alignments.read_bytes(), (folder / "application.json").read_bytes()
    assert apply(review) == {"unchanged": 3}
    assert (alignments.read_bytes(), (folder / "application.json").read_bytes()) == saved
    validate = tr.validate
    monkeypatch.setattr(tr, "validate", lambda folder, **kwargs: validate(folder, root=root, **kwargs))
    mappings = graphmod.read_review_round(folder)
    assert mappings[0].reviewers == ("Reviewer One", "Reviewer Two")
    assert mappings[1].reviewers == ("Reviewer One", "Reviewer Two", "Third Reviewer")
    assert mappings[0].round.sssom == folder / "reviewed-types.csv"
    assert mappings[0].round.protocol == "docs/alignment-review-v3.md"


def test_a_completed_csv_without_activation_does_not_enter_the_build(review):
    _, folder, _, _ = review
    assert graphmod.load_reviewed_mappings(folder.parent) == {}


def test_regenerated_audits_do_not_change_the_frozen_review(review):
    root, folder, _, _ = review
    (root / "analysis/data/foodon_types.csv").write_text("regenerated\n", encoding="utf-8")
    assert len(tr.validate(folder, root=root).rows) == 3
    (folder / "baseline/analysis/data/foodon_types.csv").write_text("corrupted\n", encoding="utf-8")
    with pytest.raises(ValueError, match="inputs differ"):
        tr.validate(folder, root=root)


@pytest.mark.parametrize("mutation", ["decision", "reason", "source", "missing", "duplicate", "unapproved"])
def test_bad_consolidation_is_rejected_without_touching_alignments(review, mutation):
    _, folder, _, alignments = review
    before = alignments.read_bytes()
    rows = tr.read_rows(folder / "reviewed-types.csv")
    if mutation == "decision":
        rows[1]["decision"] = A
    elif mutation == "reason":
        rows[1]["adjudication_justification"] = "invented reason"
    elif mutation == "source":
        rows[1]["decision_source"] = "reviewer_agreement"
    elif mutation == "missing":
        rows.pop()
    elif mutation == "duplicate":
        rows.append(rows[0])
    else:
        path = folder / "adjudication-receipt.json"
        receipt = json.loads(path.read_text(encoding="utf-8"))
        receipt["human_confirmed_by_user"] = False
        path.write_text(json.dumps(receipt), encoding="utf-8")
    write(folder / "reviewed-types.csv", rows)
    seal(folder)  # Hashes alone must not make inconsistent decisions acceptable.
    with pytest.raises(ValueError):
        apply(review)
    assert alignments.read_bytes() == before
    assert not (folder / "application.json").exists()


def test_changing_an_existing_agreed_type_still_requires_adjudication(review):
    root, folder, _, _ = review
    adj = tr.read_rows(folder / "adjudication-all.csv")[:1]
    write(folder / "adjudication-all.csv", adj)
    path = folder / "adjudication-additional.csv"
    path.write_text(",".join(adj[0]) + "\n", encoding="utf-8")
    rows = tr.read_rows(folder / "reviewed-types.csv")
    rows[2].update(
        decision_source="reviewer_agreement",
        adjudicator="",
        adjudication_sheet="",
        adjudication_justification="",
    )
    write(folder / "reviewed-types.csv", rows)
    seal(folder)
    with pytest.raises(ValueError, match="requires adjudication"):
        tr.validate(folder, root=root)


def test_wrong_owl_file_and_blocked_class_cannot_be_applied(review):
    root, folder, owl, alignments = review
    before = alignments.read_bytes()
    graph = Graph().parse(owl, format="xml")
    graph.add((OBO[C], RDFS.subClassOf, OBO.PO_0000003))
    graph.serialize(owl, format="xml")
    with pytest.raises(ValueError, match="SHA-256"):
        apply(review)
    assert alignments.read_bytes() == before
    checked = tr.validate(folder, root=root)
    # A synthetic pinned release that itself contains a forbidden selected class.
    checked.foodon["sha256"] = tr.digest(owl, normalized=False)
    with pytest.raises(ValueError, match="organism/plant"):
        tr.check_hierarchy(checked, owl)


def test_activation_detects_evidence_changed_even_when_the_receipt_is_resealed(review):
    root, folder, _, _ = review
    apply(review)
    rows = tr.read_rows(folder / "reviewer-1.csv")
    rows[0]["justification"] = "changed after application"
    write(folder / "reviewer-1.csv", rows)
    final = tr.read_rows(folder / "reviewed-types.csv")
    final[0]["reviewer_1_justification"] = rows[0]["justification"]
    write(folder / "reviewed-types.csv", final)
    seal(folder)
    with pytest.raises(ValueError, match="changed since application"):
        tr.validate(folder, root=root, require_application=True)


def test_duplicate_prior_foodon_rows_are_replaced_once(review):
    _, _, _, alignments = review
    rows = tr.read_rows(alignments)
    rows.insert(1, rows[0].copy())
    write(alignments, rows)
    assert apply(review)["deduplicated"] == 1
    rows = tr.read_rows(alignments)
    assert sum(r["source_key"] == "1" and r["target_ontology"] == "FoodOn" for r in rows) == 1


def test_marker_failure_rolls_back_alignment_mutation(review, monkeypatch):
    _, _, _, alignments = review
    before = alignments.read_bytes()
    replace = applymod.replace_bytes

    def fail_marker(path, data):
        if path.name == "application.json":
            raise OSError("simulated marker write failure")
        replace(path, data)

    monkeypatch.setattr(applymod, "replace_bytes", fail_marker)
    with pytest.raises(OSError, match="simulated"):
        apply(review)
    assert alignments.read_bytes() == before


def test_scoring_cannot_overwrite_human_adjudication(review, monkeypatch):
    _, folder, _, _ = review
    spec = importlib.util.spec_from_file_location("score_guard", ROOT / "scripts/score_type_review.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    before = (folder / "adjudication.csv").read_bytes()
    monkeypatch.setattr("sys.argv", ["score_type_review.py", "--round", str(folder)])
    assert module.main() == 1
    assert (folder / "adjudication.csv").read_bytes() == before


def test_git_csv_newline_conversion_preserves_receipt_verification(review):
    root, folder, _, _ = review
    path = folder / "reviewed-types.csv"
    path.write_bytes(path.read_bytes().replace(b"\r\n", b"\n"))
    assert len(tr.validate(folder, root=root).rows) == 3
