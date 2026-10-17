"""Measurements typed with CDNO classes, as NICE-Food types each NEVO nutritional value."""

from __future__ import annotations

import pytest
from pyshacl import validate
from rdflib import Graph

from taco_rdf import graph as graphmod
from taco_rdf.namespaces import ID, OBO, RDF, SH, SHAPES_DIR, SKOS, TACO

CDNO = "http://purl.obolibrary.org/obo/CDNO_"


def cdno_types(graph, measurement):
    return {t for t in graph.objects(measurement, RDF.type) if str(t).startswith(CDNO)}


def test_measurements_of_close_cdno_nutrients_carry_the_cdno_class(graph, table, alignments):
    types = graphmod.cdno_measurement_types(alignments)
    assert len(types) == 53
    typed = 0
    for obs in table.observations:
        expected = {types[obs.nutrient]} if obs.nutrient in types else set()
        assert cdno_types(graph, graphmod.measurement_iri(obs.food_id, obs.nutrient)) == expected, obs
        typed += bool(expected)
    in_graph = {m for m in graph.subjects(RDF.type, TACO.NutrientMeasurement) if cdno_types(graph, m)}
    assert len(in_graph) == typed > 0


@pytest.mark.parametrize("nutrient", ["re", "rae", "cystine", "fa_18_1", "energy_kcal"])
def test_related_or_unmapped_nutrients_type_no_measurement(graph, table, nutrient):
    measurements = [graphmod.measurement_iri(o.food_id, o.nutrient)
                    for o in table.observations if o.nutrient == nutrient]
    assert measurements
    assert all(not cdno_types(graph, m) for m in measurements)


def test_value_status_does_not_change_the_cdno_class(graph, table):
    # Cholesterol is not applicable to brown rice; the measurement is still about that concentration.
    m = graphmod.measurement_iri(1, "cholesterol")
    assert graph.value(m, TACO.valueStatus) == TACO.NotApplicable
    assert cdno_types(graph, m) == {OBO.CDNO_0200123}


def test_nice_food_style_query_reads_values_by_cdno_class(graph, table):
    rows = graph.query("""
        PREFIX qudt: <http://qudt.org/schema/qudt/>
        PREFIX taco: <https://w3id.org/taco-rdf/vocab#>
        SELECT ?food ?value WHERE {
            ?m a <http://purl.obolibrary.org/obo/CDNO_0200040> ; taco:ofFood ?food ;
               qudt:numericValue ?value .
        }""")
    measured = [o for o in table.observations if o.nutrient == "protein" and o.value is not None]
    assert len(rows) == len(measured)
    assert {(str(r.food), float(r.value)) for r in rows} == {
        (str(graphmod.food_iri(o.food_id)), float(o.value)) for o in measured}


def test_two_close_cdno_classes_for_one_nutrient_are_refused():
    rows = [graphmod.Alignment("nutrient", "protein", predicate, CDNO + suffix, "x", "CDNO", "")
            for predicate, suffix in (("closeMatch", "0200040"), ("exactMatch", "0200041"))]
    with pytest.raises(ValueError, match="more than one close CDNO class"):
        graphmod.cdno_measurement_types(rows)


def test_chebi_and_related_cdno_mappings_type_nothing():
    rows = [
        graphmod.Alignment("nutrient", "protein", "closeMatch", "http://purl.obolibrary.org/obo/CHEBI_36080",
                           "protein", "ChEBI", ""),
        graphmod.Alignment("nutrient", "cystine", "relatedMatch", CDNO + "0200051", "cysteine", "CDNO", ""),
        graphmod.Alignment("food", "1", "closeMatch", CDNO + "0200040", "x", "CDNO", ""),
    ]
    assert graphmod.cdno_measurement_types(rows) == {}


@pytest.fixture(scope="module")
def alignment_shapes():
    return Graph().parse(SHAPES_DIR / "taco-alignment-shapes.ttl")


def nutrient_graph(measurement_type):
    graph = Graph()
    nutrient, m = ID["nutrient/protein"], ID["measurement/1/protein"]
    graph.add((nutrient, RDF.type, TACO.Nutrient))
    graph.add((nutrient, SKOS.closeMatch, OBO.CDNO_0200040))
    graph.add((m, RDF.type, TACO.NutrientMeasurement))
    graph.add((m, TACO.ofNutrient, nutrient))
    if measurement_type is not None:
        graph.add((m, RDF.type, measurement_type))
    return graph


@pytest.mark.parametrize(("measurement_type", "message"), [
    (OBO.CDNO_0200040, None),
    (OBO.CDNO_0200068, "does not closeMatch or exactMatch"),
    (None, "lacks the CDNO class"),
])
def test_shacl_ties_measurement_cdno_types_to_the_nutrient_mapping(alignment_shapes, measurement_type,
                                                                    message):
    conforms, report, text = validate(nutrient_graph(measurement_type), shacl_graph=alignment_shapes)
    if message is None:
        assert conforms, text
    else:
        assert not conforms
        assert any(message in str(m) for m in report.objects(None, SH.resultMessage)), text
