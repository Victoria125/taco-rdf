"""Executable regression contracts for TACO's QUDT-native -> OM/NICE-Food export.

These tests intentionally leave the production model unchanged. They cross-check all
21,150 source measurements against the exported graph (including nonnumeric statuses),
the unit dictionary, and SHACL. They do not prove nutritional equivalence of datasets.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from pyshacl import validate as shacl_validate
from rdflib import Graph, Literal
from rdflib.namespace import DCAT, PROV, RDF, SKOS, XSD

from taco_rdf import nice_food
from taco_rdf.namespaces import FIO, ID, NEVONUT, OBO, OM, QUDT, ROOT, TACO, UNIT

EXPECTED_UNITS = {
    UNIT.GM: (OM.gramPerHectogram, "g"),
    UNIT.PERCENT: (OM.gramPerHectogram, "g"),
    UNIT.MilliGM: (OM.milligramPerHectogram, "mg"),
    UNIT.MicroGM: (None, "µg"),
    UNIT.KiloCAL: (OM.kilocaloriePerHectogram, "kcal"),
    UNIT.KiloJ: (OM.kilojoulePerHectogram, "kJ"),
}


@pytest.fixture(scope="module")
def exported_graph(graph):
    output, counts = nice_food.export(graph, nice_food.nevo_codes(nice_food.NUTRIENTS))
    return output, counts


def check_units(mapping):
    """Explicit contract independent of the implementation's own UNITS table."""
    assert mapping == EXPECTED_UNITS


def test_mapping_exact_and_a_wrong_mapping_is_rejected():
    check_units(nice_food.UNITS)
    wrong = dict(nice_food.UNITS)
    wrong[UNIT.MilliGM] = (OM.gramPerHectogram, "g")
    with pytest.raises(AssertionError):
        check_units(wrong)


def test_unit_mapping_is_not_reversible_and_micrograms_only_have_a_string():
    assert UNIT.GM != UNIT.PERCENT
    assert nice_food.UNITS[UNIT.GM] == nice_food.UNITS[UNIT.PERCENT]
    # Reverse mapping cannot decide whether the input was g or %.
    assert len(set(nice_food.UNITS.values())) < len(nice_food.UNITS)
    assert nice_food.UNITS[UNIT.MicroGM] == (None, "µg")


def test_all_actual_taco_measurements_preserve_exact_numeric_values_and_statuses(graph, exported_graph):
    out, counts = exported_graph
    measured = 0
    without_number = 0
    units_seen = set()
    native_numeric = set(graph.triples((None, QUDT.numericValue, None)))
    native_units = set(graph.triples((None, QUDT.unit, None)))
    before = len(graph)

    for m in graph.subjects(RDF.type, TACO.NutrientMeasurement):
        number = graph.value(m, QUDT.numericValue)
        unit = graph.value(m, QUDT.unit)
        status = graph.value(m, TACO.valueStatus)
        assert (m, RDF.type, FIO.NutritionalValue) in out

        if number is None:
            without_number += 1
            assert status in {TACO.Trace, TACO.NotApplicable, TACO.UnderReevaluation}
            assert unit is None
            assert out.value(m, OM.hasValue) is None
            assert out.value(m, TACO.valueStatus) == status
            continue

        measured += 1
        units_seen.add(unit)
        assert status == TACO.Measured
        assert unit in EXPECTED_UNITS
        measure = out.value(m, OM.hasValue)
        assert measure is not None
        assert (measure, RDF.type, OM.Measure) in out
        assert out.value(measure, OM.hasNumericalValue) == number
        iri, label = EXPECTED_UNITS[unit]
        expected = {Literal(label, datatype=XSD.string)}
        if iri is not None:
            expected.add(iri)
        assert set(out.objects(measure, OM.hasUnit)) == expected

    assert measured == 17564
    assert without_number == 3586
    assert measured + without_number == 21150
    assert units_seen == set(EXPECTED_UNITS)
    assert counts["values"] == 21150
    assert len(set(out.subjects(RDF.type, FIO.NutritionalValue))) == 21720
    assert len(set(out.subjects(RDF.type, OM.Measure))) == 18134

    # The adapter is non-destructive: source QUDT triples remain in the native graph.
    assert len(graph) == before
    assert set(graph.triples((None, QUDT.numericValue, None))) == native_numeric
    assert set(graph.triples((None, QUDT.unit, None))) == native_units
    assert not any(out.triples((None, QUDT.numericValue, None)))
    assert not any(out.triples((None, QUDT.unit, None)))


def test_interoperability_requires_foodon_fio_om_cdno_not_qudt_prov_or_dcat(exported_graph):
    out, _ = exported_graph
    foods = set(out.subjects(RDF.type, FIO.FoodItem))
    assert len(foods) == 597
    assert all(any(str(t).startswith("http://purl.obolibrary.org/obo/FOODON_")
                   for t in out.objects(food, RDF.type)) for food in foods)
    assert any(str(c).startswith("http://purl.obolibrary.org/obo/CDNO_")
               for m in out.subjects(RDF.type, FIO.NutritionalValue)
               for c in out.objects(m, RDF.type))

    # Metadata/provenance are extra useful information, not the join path used by NICE-Food.
    assert (nice_food.DATASET, RDF.type, DCAT.Dataset) in out
    assert len(list(out.triples((None, PROV.wasDerivedFrom, None)))) == 1140

    # SKOS still provides multilingual labels, not SKOS links from foods to FoodOn.
    assert any(out.objects(next(iter(foods)), SKOS.prefLabel))
    for food in foods:
        for p in (SKOS.exactMatch, SKOS.closeMatch, SKOS.relatedMatch):
            assert not any(out.objects(food, p))


def test_small_om_measure_passes_shacl_and_missing_number_fails(exported_graph):
    out, _ = exported_graph
    measure = next(out.subjects(RDF.type, OM.Measure))
    sample = Graph()
    for predicate, obj in out.predicate_objects(measure):
        sample.add((measure, predicate, obj))
    shapes = Graph().parse(ROOT / "verification" / "om_measure_shapes.ttl", format="turtle")
    conforms, _, report = shacl_validate(sample, shacl_graph=shapes, inference="none", abort_on_first=True)
    assert conforms, str(report)
    num = sample.value(measure, OM.hasNumericalValue)
    sample.remove((measure, OM.hasNumericalValue, num))
    conforms, _, _ = shacl_validate(sample, shacl_graph=shapes, inference="none", abort_on_first=True)
    assert not conforms


def test_nice_food_om_is_a_per_100g_representation_not_a_simple_uri_rename(graph, exported_graph):
    out, _ = exported_graph
    basis = next(graph.subjects(RDF.type, TACO.ReferenceBasis))
    assert graph.value(basis, QUDT.numericValue) == Literal(Decimal("100.0"), datatype=XSD.decimal)
    assert graph.value(basis, QUDT.unit) == UNIT.GM
    # The source may have 'g' or '%' at the measurement, but its basis is 100 g.
    # NICE-Food's OM unit encodes that denominator directly.
    assert nice_food.UNITS[UNIT.GM][0] == OM.gramPerHectogram
    assert nice_food.UNITS[UNIT.PERCENT][0] == OM.gramPerHectogram
    assert len(list(out.subjects(RDF.type, OM.Measure))) > 0


def test_sparql_portability_depends_on_fio_cdno_and_om_not_dataset_metadata(exported_graph):
    """Remove optional metadata without changing the nutrient query; break core predicates and it fails."""
    out, _ = exported_graph
    food = ID["food/1"]
    value = ID["measurement/1/protein"]
    measure = out.value(value, OM.hasValue)
    assert measure is not None
    assert (value, RDF.type, OBO.CDNO_0200040) in out
    assert (value, FIO.hasNutrient, NEVONUT.PROT) in out

    small = Graph()
    for subject in (food, value, measure, nice_food.DATASET):
        for p, obj in out.predicate_objects(subject):
            small.add((subject, p, obj))
    # The query deliberately uses the shared semantic class rather than a table-specific nutrient code.
    query = f"""
        PREFIX fio: <http://www.foodvoc.org/resource/fio#>
        PREFIX om: <http://www.ontology-of-units-of-measure.org/resource/om-2/>
        PREFIX obo: <http://purl.obolibrary.org/obo/>
        SELECT ?n WHERE {{
          <{food}> a fio:FoodItem ; fio:hasNutritionalValue <{value}> .
          <{value}> a obo:CDNO_0200040 ; om:hasValue ?m .
          ?m om:hasNumericalValue ?n .
        }}
    """
    expected = [r[0] for r in small.query(query)]
    assert len(expected) == 1
    assert expected[0].toPython() > 0
    no_metadata = Graph()
    for subject, pred, obj in small:
        if subject != nice_food.DATASET and pred != PROV.wasDerivedFrom:
            no_metadata.add((subject, pred, obj))
    assert [r[0] for r in no_metadata.query(query)] == expected

    # Negative metamorphic tests identify what the query *actually* requires.
    no_measure = Graph()
    no_measure += no_metadata
    no_measure.remove((value, OM.hasValue, measure))
    assert list(no_measure.query(query)) == []
    no_cdno = Graph()
    no_cdno += no_metadata
    no_cdno.remove((value, RDF.type, OBO.CDNO_0200040))
    assert list(no_cdno.query(query)) == []
