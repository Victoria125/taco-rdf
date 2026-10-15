"""Published class coverage must not silently count historical SKOS candidates."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest
from rdflib import OWL, RDF, RDFS, SKOS, Graph, Literal, URIRef

from taco_rdf.graph import Alignment, ReviewedMapping, ReviewRound, food_iri
from taco_rdf.namespaces import ROOT
from taco_rdf.parse import Food, Table

spec = importlib.util.spec_from_file_location(
    "audit_foodon_typing", ROOT / "scripts" / "audit_foodon_typing.py")
assert spec is not None and spec.loader is not None
audit_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit_module)
FOODON = "http://purl.obolibrary.org/obo/FOODON_"


def alignment(food, predicate="type", suffix="00001248"):
    return Alignment("food", str(food), predicate, FOODON + suffix, "fish food product", "FoodOn", "Evidence")


def table_with(*numbers):
    return Table(groups=["Pescados"], foods={number: Food(number, f"Food {number}", 1) for number in numbers})


def test_counts_actual_graph_types_and_keeps_unpublished_candidate_evidence():
    table = table_with(3, 2, 1)
    graph = Graph()
    target = URIRef(FOODON + "00001248")
    graph.add((food_iri(1), RDF.type, target))
    graph.add((target, RDFS.label, Literal("fish food product", lang="en")))
    # Merely listing a type or SKOS candidate in curation inputs never publishes it.
    inputs = [alignment(1), alignment(2), alignment(3, "relatedMatch")]
    typed, gaps = audit_module.audit(graph, table, inputs, {})
    assert [row["food_number"] for row in typed] == [1]
    assert typed[0]["predicate"] == "rdf:type"
    assert typed[0]["target_label"] == "fish food product"
    assert [row["food_number"] for row in gaps] == [2, 3]
    assert gaps[1]["candidate_predicate"] == "relatedMatch"
    assert gaps[1]["candidate_note"] == "Evidence"
    assert all(row["review_status"] == "pending_review" for row in typed + gaps)


def test_scored_non_type_and_no_term_decisions_remain_distinct():
    review = ReviewRound("round-2", Path("reviewed.sssom.tsv"), "digest", "pinned-release")
    reviewed = {
        2: ReviewedMapping(2, "relatedMatch", FOODON + "00001248", ("A", "B"), "2026-10-08", review),
        3: ReviewedMapping(3, "", "", ("A", "B"), "2026-10-08", review),
    }
    _, gaps = audit_module.audit(Graph(), table_with(1, 2, 3), [alignment(2, "relatedMatch")], reviewed)
    expected = ["pending_review", "reviewed_no_type", "reviewed_no_term"]
    assert [row["review_status"] for row in gaps] == expected
    assert gaps[1]["review_round"] == "round-2"
    assert gaps[1]["reviewers"] == "A; B"
    assert gaps[2]["candidate_iri"] == ""
    assert gaps[2]["foodon_release"] == "pinned-release"


def test_multiple_types_count_once_in_coverage_and_output_order_is_stable():
    graph = Graph()
    for suffix in ("00001293", "00001248"):
        graph.add((food_iri(1), RDF.type, URIRef(FOODON + suffix)))
    table = table_with(2, 1)
    typed, gaps = audit_module.audit(graph, table, [], {})
    assert [row["target_iri"] for row in typed] == [FOODON + "00001248", FOODON + "00001293"]
    text = audit_module.report(table, typed, gaps)
    assert "1 of 2 TACO foods" in text
    assert "Published type assertions: 2. Foods without a FoodOn type: 1." in text
    assert "| pending_review | 1 | 1 |" in text
    assert "| Pescados | 2 | 1 | 1 |" in text
    assert "does not prove" in text


@pytest.mark.parametrize("predicate", audit_module.SKOS_MATCHES)
def test_rejects_published_food_skos_mappings(predicate):
    graph = Graph()
    graph.add((food_iri(1), predicate, URIRef(FOODON + "00001248")))
    with pytest.raises(ValueError, match="published SKOS mapping"):
        audit_module.audit(graph, table_with(1), [alignment(1, "relatedMatch")], {})


def test_foodon_axiom_conflicts_are_reported_apart_from_organism_candidates():
    obo = "http://purl.obolibrary.org/obo/"
    pod, fish = URIRef(FOODON + "00004236"), URIRef(FOODON + "03413876")
    graph = Graph()
    for cls, label, parents in (
        (pod, "green bean pod (raw)", ("FOODON_00002403", "PO_0000003")),  # food material and whole plant
        (fish, "pollock", ("COB_0000022",)),
    ):
        graph.add((cls, RDF.type, OWL.Class))
        graph.add((cls, RDFS.label, Literal(label, lang="en")))
        for parent in parents:
            graph.add((cls, RDFS.subClassOf, URIRef(obo + parent)))
    inputs = [alignment(1, "closeMatch", "00004236"), alignment(2, "closeMatch", "03413876")]
    _, gaps = audit_module.audit(graph, table_with(1, 2, 3), inputs, {})
    assert [row["candidate_obstacle"] for row in gaps] == ["foodon_axiom_conflict", "organism_class", ""]
    text = audit_module.report(table_with(1, 2, 3), [], gaps)
    assert "FoodOn axiom conflicts: 1 untyped foods (1)" in text
    assert "Organism classes only: 1 untyped foods" in text
    assert "These are not ontology gaps" in text


def test_ignores_group_skos_and_non_foodon_types():
    graph = Graph()
    graph.add((URIRef("https://example.org/group/1"), SKOS.closeMatch, URIRef(FOODON + "00001248")))
    graph.add((food_iri(1), RDF.type, URIRef("https://example.org/Food")))
    typed, gaps = audit_module.audit(graph, table_with(1), [], {})
    assert typed == []
    assert gaps[0]["candidate_iri"] == ""
