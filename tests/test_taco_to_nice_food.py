"""TACO's graph becomes a NICE-Food subgraph that keeps every value and names nutrients by NEVO's codes."""

from __future__ import annotations

import csv
import importlib.util
from decimal import Decimal

from rdflib import DCTERMS, PROV, RDF, RDFS, SKOS, Graph, Literal, URIRef

from taco_rdf.namespaces import ID, OBO, QUDT, ROOT, TACO, UNIT
from taco_rdf.nutrients import BY_KEY

spec = importlib.util.spec_from_file_location("taco_to_nice_food", ROOT / "scripts" / "taco_to_nice_food.py")
assert spec is not None and spec.loader is not None
nice = importlib.util.module_from_spec(spec)
spec.loader.exec_module(nice)

FOOD = ID["food/1"]


def taco_graph(*measurements: tuple[str, str | None, URIRef | None, URIRef, URIRef | None]) -> Graph:
    """A TACO food with measurements given as (nutrient, number, unit, status, CDNO class)."""
    g = Graph()
    g.add((FOOD, RDF.type, TACO.Food))
    g.add((FOOD, RDF.type, OBO.FOODON_03301449))
    g.add((FOOD, TACO.foodNumber, Literal(1)))
    g.add((FOOD, SKOS.prefLabel, Literal("Arroz, integral, cozido", lang="pt")))
    g.add((FOOD, SKOS.prefLabel, Literal("Rice, brown, cooked", lang="en")))
    for nutrient, number, unit, status, cdno in measurements:
        m = ID[f"measurement/1/{nutrient}"]
        g.add((m, RDF.type, TACO.NutrientMeasurement))
        g.add((m, TACO.ofFood, FOOD))
        g.add((m, TACO.ofNutrient, ID[f"nutrient/{nutrient}"]))
        g.add((m, TACO.valueStatus, status))
        if cdno is not None:
            g.add((m, RDF.type, cdno))
        if number is not None:
            g.add((m, QUDT.numericValue, Literal(Decimal(number))))
            g.add((m, QUDT.unit, unit))
    return g


def exported(*measurements):
    with nice.NUTRIENTS.open(encoding="utf-8", newline="") as fh:
        codes = {r["taco_nutrient"]: r["nevo_code"] for r in csv.DictReader(fh) if r["nevo_code"]}
    return nice.export(taco_graph(*measurements), codes)


def value_of(g: Graph, nutrient: URIRef) -> URIRef:
    values = g.objects(FOOD, nice.FIO.hasNutritionalValue)
    return next(v for v in values if (v, nice.FIO.hasNutrient, nutrient) in g)


def number_of(g: Graph, node: URIRef):
    return g.value(g.value(node, nice.OM.hasValue), nice.OM.hasNumericalValue).toPython()


def units_of(g: Graph, node: URIRef) -> set:
    return set(g.objects(g.value(node, nice.OM.hasValue), nice.OM.hasUnit))


def test_the_alignment_file_lists_every_taco_nutrient_once():
    with nice.NUTRIENTS.open(encoding="utf-8", newline="") as fh:
        keys = [r["taco_nutrient"] for r in csv.DictReader(fh)]
    assert sorted(keys) == sorted(BY_KEY)


def test_a_food_is_a_food_item_marked_as_a_version_of_taco_with_its_foodon_class_and_names():
    g, counts = exported()
    assert (FOOD, RDF.type, nice.FIO.FoodItem) in g
    assert (FOOD, RDF.type, OBO.FOODON_03301449) in g
    assert (FOOD, DCTERMS.isVersionOf, nice.TACO_SOURCE) in g
    assert list(g.objects(FOOD, DCTERMS.hasVersion)) == [nice.TACO_VERSION]
    assert nice.TACO_VERSION.language == "pt"  # the table's language, as NEVO's version is in Dutch
    assert len(set(g.objects(FOOD, SKOS.prefLabel))) == 2
    assert counts["foods with a FoodOn class"] == 1


def test_protein_is_named_by_nevo_s_code_with_its_cdno_class_and_an_om_unit_and_a_string():
    g, _ = exported(("protein", "2.6", UNIT.GM, TACO.Measured, OBO.CDNO_0200040))
    node = value_of(g, nice.NEVONUT.PROT)
    assert (node, RDF.type, OBO.CDNO_0200040) in g
    assert number_of(g, node) == Decimal("2.6")
    assert units_of(g, node) == {nice.OM.gramPerHectogram, Literal("g", datatype=nice.XSD.string)}


def test_a_trace_and_a_value_without_a_cdno_class_are_kept():
    g, counts = exported(("iron", None, None, TACO.Trace, OBO.CDNO_0200651),
                         ("energy_kcal", "124", UNIT.KiloCAL, TACO.Measured, None))
    trace = value_of(g, nice.NEVONUT.FE)
    assert g.value(trace, TACO.valueStatus) == TACO.Trace
    assert g.value(trace, nice.OM.hasValue) is None
    energy = value_of(g, nice.NEVONUT.ENERCC)
    assert nice.OM.kilocaloriePerHectogram in units_of(g, energy)
    assert counts["values"] == 2


def test_total_carbohydrate_keeps_taco_s_nutrient_and_available_carbohydrate_is_carbohydrate_minus_fibre():
    carbohydrate = ("carbohydrate", "25.8", UNIT.GM, TACO.Measured, OBO.CDNO_0200005)
    g, counts = exported(carbohydrate, ("dietary_fiber", "2.7", UNIT.GM, TACO.Measured, OBO.CDNO_0200035))
    total = value_of(g, ID["nutrient/carbohydrate"])
    assert (total, RDF.type, OBO.CDNO_0200005) in g
    available = value_of(g, nice.NEVONUT.CHO)
    assert (available, RDF.type, OBO.CDNO_0200033) in g
    assert number_of(g, available) == Decimal("23.1")
    assert set(g.objects(available, PROV.wasDerivedFrom)) == {ID["measurement/1/carbohydrate"],
                                                             ID["measurement/1/dietary_fiber"]}
    assert counts["available carbohydrate: carbohydrate minus fibre"] == 1


def foods_found(query_file: str, codes: dict[str, str]) -> set[str]:
    """Foods NICE-Food's query finds in TACO's subgraph, with a lentil food under FoodOn's legume class."""
    taco = taco_graph(("protein", "23.2", UNIT.GM, TACO.Measured, OBO.CDNO_0200040))
    taco.add((ID["nutrient/protein"], SKOS.prefLabel, Literal("Protein", lang="en")))
    g, _ = nice.export(taco, codes)
    g.add((OBO.FOODON_03301449, RDFS.subClassOf, OBO.FOODON_00001264))
    g.add((nice.NEVONUT.PROT, RDF.type, nice.FIO.Nutrient))
    g.add((nice.NEVONUT.PROT, RDFS.label, Literal("Protein total", lang="en")))
    query = (ROOT / "queries" / "nice-food" / query_file).read_text(encoding="utf-8")
    return {str(r.foodname) for r in g.query(query)}


def test_nice_food_s_query_finds_taco_foods_by_nevo_s_code_and_its_cdno_variant_without_it():
    assert foods_found("protein_groups.rq", {"protein": "PROT"}) == {"Rice, brown, cooked"}
    assert foods_found("protein_groups.rq", {}) == set()
    assert foods_found("protein_groups_cdno.rq", {}) == {"Rice, brown, cooked"}


def test_available_carbohydrate_is_total_carbohydrate_without_fibre_and_zero_below_zero():
    g, _ = exported(("carbohydrate", "-0.045", UNIT.GM, TACO.Measured, OBO.CDNO_0200005),
                    ("dietary_fiber", None, None, TACO.NotApplicable, OBO.CDNO_0200035))
    available = value_of(g, nice.NEVONUT.CHO)
    assert number_of(g, available) == 0
    assert "not applicable" in str(g.value(available, DCTERMS.description))
    assert number_of(g, value_of(g, ID["nutrient/carbohydrate"])) == Decimal("-0.045")
