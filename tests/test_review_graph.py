"""A scored review round, applied to the alignments, and the graph that records it."""

from __future__ import annotations

import csv
import json
import subprocess
import sys

import pytest

from taco_rdf import evaluation as ev
from taco_rdf import graph as graphmod
from taco_rdf.namespaces import (
    ALIGNMENTS_CSV,
    DCTERMS,
    ID,
    OBO,
    PROV,
    RAW_XLS,
    ROOT,
    SHAPES_DIR,
    SKOS,
    TACO,
)
from taco_rdf.validate import validate

DAY = "2026-09-24"


def scored_round(folder, mappings, reviewers="Reviewer One; Reviewer Two"):
    """A round folder as score_alignment_review.py leaves it, as far as the build reads it."""
    release = ev.foodon_index().release
    folder.mkdir(parents=True)
    (folder / "manifest.json").write_text(json.dumps({"protocol_sha256": "0" * 64, "foodon_release": release}),
                                          encoding="utf-8")
    rows = [{"subject_id": f"tacoid:food/{food}", "subject_label": "", "predicate_id": predicate,
             "object_id": target, "object_label": "", "mapping_justification": "semapv:ManualMappingCuration",
             "author_label": reviewers, "mapping_date": DAY, "object_source_version": release, "comment": "{}"}
            for food, predicate, target in mappings]
    ev.write_sssom(folder / "reviewed.sssom.tsv", rows, folder.name)
    return folder


def assertion(graph, food):
    records = [r for r in graph.objects(ID[f"food/{food}"], TACO.alignment)]
    assert len(records) == 1
    return records[0]


def test_a_confirmed_mapping_is_recorded_as_reviewed_and_conforms(tmp_path, table, alignments, food_names_en):
    folder = scored_round(tmp_path / "round-1", [(1, "rdf:type", "FOODON:00004678"),
                                                 (280, "skos:relatedMatch", "FOODON:03411423"),
                                                 (540, "skos:closeMatch", "sssom:NoTermFound")])
    reviewed = graphmod.load_reviewed_mappings(tmp_path)
    graph = graphmod.build_graph(table, alignments, source_file=RAW_XLS, food_names_en=food_names_en,
                                 reviewed=reviewed)
    release = ev.foodon_index().release
    for food in (1, 280):
        record = assertion(graph, food)
        assert graph.value(record, TACO.reviewStatus) == TACO.Reviewed
        assert graph.value(record, TACO.ontologyVersionStatus) == TACO.Recorded
        assert str(graph.value(record, TACO.ontologyVersion)) == release
        assert {str(r) for r in graph.objects(record, TACO.reviewer)} == {"Reviewer One", "Reviewer Two"}
        assert str(graph.value(record, DCTERMS.date)) == DAY
        assert (record, PROV.wasDerivedFrom, ID["review/round-1"]) in graph
        assert (record, PROV.wasDerivedFrom, ID["alignment-set"]) in graph
    assert graph.value(assertion(graph, 273), TACO.reviewStatus) == TACO.Unreviewed
    assert str(graph.value(ID["review/round-1"], TACO.sha256)) == graphmod.sha256_of(folder / "reviewed.sssom.tsv")
    note = str(graph.value(ID["alignment-set"], SKOS.editorialNote))
    assert f"2 of the {len(alignments)} assertions have since been independently reviewed" in note
    report = validate(graph, SHAPES_DIR)
    assert report.conforms_strict, report.details()


@pytest.mark.parametrize("mapping", [
    (1, "skos:closeMatch", "FOODON:00004678"),
    (1, "rdf:type", "FOODON:00004677"),
    (273, "skos:closeMatch", "sssom:NoTermFound"),
    (540, "skos:relatedMatch", "FOODON:03000089"),
])
def test_the_build_refuses_a_mapping_its_review_changed(tmp_path, table, alignments, mapping):
    scored_round(tmp_path / "round-1", [mapping])
    with pytest.raises(ValueError, match=rf"reviewed mapping of foods {mapping[0]} \(round-1\)"):
        graphmod.build_graph(table, alignments, source_file=RAW_XLS,
                             reviewed=graphmod.load_reviewed_mappings(tmp_path))


def test_a_later_round_supersedes_an_earlier_one(tmp_path):
    scored_round(tmp_path / "round-1", [(1, "rdf:type", "FOODON:00004678")])
    scored_round(tmp_path / "round-2", [(1, "skos:closeMatch", "FOODON:00004677")], reviewers="Reviewer Three")
    scored_round(tmp_path / "round-10", [(2, "skos:closeMatch", "sssom:NoTermFound")])
    reviewed = graphmod.load_reviewed_mappings(tmp_path)
    assert (reviewed[1].round.name, reviewed[1].predicate) == ("round-2", "closeMatch")
    assert reviewed[1].reviewers == ("Reviewer Three",)
    assert reviewed[2].target_iri == ""


def test_applying_a_round_brings_the_alignments_into_line_with_it(tmp_path, table, food_names_en):
    folder = scored_round(tmp_path / "review" / "round-1", [
        (1, "rdf:type", "FOODON:00004678"),
        (280, "skos:broadMatch", "FOODON:03411423"),
        (562, "skos:closeMatch", "FOODON:00001248"),
        (273, "skos:closeMatch", "sssom:NoTermFound"),
        (540, "skos:relatedMatch", "FOODON:03000089"),
    ])
    target = tmp_path / "alignments.csv"
    target.write_bytes(ALIGNMENTS_CSV.read_bytes())
    run = [sys.executable, str(ROOT / "scripts" / "apply_alignment_review.py"), str(folder),
           "--alignments", str(target)]
    done = subprocess.run(run, check=True, capture_output=True, text=True)
    assert "1 added, 1 class changed, 1 relation changed, 1 removed, 1 unchanged" in done.stdout

    with open(target, newline="", encoding="utf-8") as fh:
        rows = {(r["source_type"], r["source_key"]): r for r in csv.DictReader(fh)}
    assert ("food", "273") not in rows
    assert rows[("food", "280")]["predicate"] == "broadMatch"
    assert rows[("food", "562")]["target_label"] == "fish food product"
    assert rows[("food", "540")]["note"] == "Revised by review round-1."
    assert rows[("food", "1")]["note"] == ""
    applied = graphmod.load_alignments(target)
    graph = graphmod.build_graph(table, applied, source_file=RAW_XLS, food_names_en=food_names_en,
                                 reviewed=graphmod.load_reviewed_mappings(tmp_path / "review"))
    for food in (1, 280, 562, 540):
        assert graph.value(assertion(graph, food), TACO.reviewStatus) == TACO.Reviewed
    assert (ID["food/540"], SKOS.relatedMatch, OBO.FOODON_03000089) in graph
    assert not list(graph.objects(ID["food/273"], TACO.alignment))

    again = subprocess.run(run, check=True, capture_output=True, text=True)
    assert again.stdout.strip() == "round-1: 5 unchanged"
