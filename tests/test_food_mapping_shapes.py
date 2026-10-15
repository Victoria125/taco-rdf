"""SHACL keeps candidate food-to-FoodOn links out of official triples and alignment assertions."""

from __future__ import annotations

import pytest
from pyshacl import validate
from rdflib import Graph, Literal, URIRef

from taco_rdf.namespaces import ID, OBO, PROV, RDF, SH, SHAPES_DIR, SKOS, TACO, XSD

SKOS_MAPPINGS = (
    SKOS.exactMatch, SKOS.closeMatch, SKOS.broadMatch,
    SKOS.narrowMatch, SKOS.relatedMatch, SKOS.mappingRelation,
)
# NICE-Food links LCA items to NEVO codes with skos:closeMatch; this is such a code.
NEVO_ITEM = URIRef("https://data.rivm.nl/data/nvip/bigfood/nevo23/nevocode#1")


@pytest.fixture(scope="module")
def alignment_shapes():
    return Graph().parse(SHAPES_DIR / "taco-alignment-shapes.ttl")


def assertion_graph(source_class, relation, target=OBO.FOODON_00004678, ontology="FoodOn"):
    graph = Graph()
    subject, assertion, source = ID["test/subject"], ID["test/assertion"], ID["test/source"]
    for triple in (
        (subject, RDF.type, source_class),
        (subject, relation, target),
        (subject, TACO.alignment, assertion),
        (assertion, RDF.type, TACO.AlignmentAssertion),
        (assertion, RDF.subject, subject),
        (assertion, RDF.predicate, relation),
        (assertion, RDF.object, target),
        (assertion, PROV.wasDerivedFrom, source),
        (assertion, TACO.targetOntology, Literal(ontology, datatype=XSD.string)),
        (assertion, TACO.ontologyVersionStatus, TACO.NotRecorded),
        (assertion, TACO.reviewStatus, TACO.Unreviewed),
        (source, RDF.type, PROV.Entity),
    ):
        graph.add(triple)
    return graph


def test_official_food_type_assertion_is_allowed(alignment_shapes):
    conforms, _, report = validate(assertion_graph(TACO.Food, RDF.type), shacl_graph=alignment_shapes)
    assert conforms, report


def test_food_can_remain_without_a_foodon_type(alignment_shapes):
    graph = Graph()
    graph.add((ID["food/1"], RDF.type, TACO.Food))
    conforms, _, report = validate(graph, shacl_graph=alignment_shapes)
    assert conforms, report


@pytest.mark.parametrize("relation", SKOS_MAPPINGS)
def test_skos_mapping_triple_on_a_food_is_rejected(alignment_shapes, relation):
    graph = Graph()
    graph.add((ID["food/1"], RDF.type, TACO.Food))
    graph.add((ID["food/1"], relation, OBO.FOODON_00004678))
    conforms, report, _ = validate(graph, shacl_graph=alignment_shapes)
    assert not conforms
    messages = report.objects(None, SH.resultMessage)
    assert any("only by rdf:type" in str(message) for message in messages)


@pytest.mark.parametrize("relation", SKOS_MAPPINGS)
def test_reified_skos_food_assertion_is_rejected_even_without_a_mapping_triple(alignment_shapes, relation):
    graph = assertion_graph(TACO.Food, relation)
    graph.remove((ID["test/subject"], relation, OBO.FOODON_00004678))
    conforms, report, _ = validate(graph, shacl_graph=alignment_shapes)
    assert not conforms
    assert any("must use rdf:type" in str(message) for message in report.objects(None, SH.resultMessage))


@pytest.mark.parametrize("relation", SKOS_MAPPINGS[:-1])
def test_skos_link_from_a_food_to_another_dataset_is_allowed(alignment_shapes, relation):
    # Only food-to-FoodOn links are restricted to rdf:type, as in NICE-Food.
    conforms, _, report = validate(assertion_graph(TACO.Food, relation, NEVO_ITEM, "NEVO"),
                                   shacl_graph=alignment_shapes)
    assert conforms, report


@pytest.mark.parametrize("source_class", [TACO.FoodGroup, TACO.Nutrient])
@pytest.mark.parametrize("relation", SKOS_MAPPINGS[:-1])
def test_skos_group_and_nutrient_assertions_remain_allowed(alignment_shapes, source_class, relation):
    conforms, _, report = validate(assertion_graph(source_class, relation), shacl_graph=alignment_shapes)
    assert conforms, report
