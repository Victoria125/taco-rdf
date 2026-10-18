from __future__ import annotations

import importlib.util
from decimal import Decimal

from rdflib import RDFS, Graph, Literal, Namespace, URIRef
from rdflib.graph import ReadOnlyGraphAggregate

from taco_rdf.namespaces import OBO, QUERIES_DIR, RDF, ROOT, SKOS
from taco_rdf.queries import run_query

spec = importlib.util.spec_from_file_location("compare_taco_nevo", ROOT / "scripts" / "compare_taco_nevo.py")
assert spec is not None and spec.loader is not None
compare = importlib.util.module_from_spec(spec)
spec.loader.exec_module(compare)

FIO = Namespace("http://www.foodvoc.org/resource/fio#")
OM = Namespace("http://www.ontology-of-units-of-measure.org/resource/om-2/")
NEVONUT = Namespace("https://data.rivm.nl/data/nvip/bigfood/nevo/nutrient#")
NEVO = Namespace("https://example.org/nevo/")
SAME_CLASS = QUERIES_DIR / "nevo" / "taco_nevo_same_foodon_class.rq"
CARBOHYDRATE = QUERIES_DIR / "nevo" / "taco_nevo_available_carbohydrate.rq"
PROTEIN, CARBOHYDRATE_CLASS, WATER = OBO.CDNO_0200040, OBO.CDNO_0200005, OBO.CDNO_0200002


def nevo_food(g: Graph, code: str, foodon: URIRef,
              values: list[tuple[str, URIRef, float, URIRef]]) -> None:
    """A NEVO food as NICE-Food models it: typed with FoodOn, values typed with CDNO."""
    food = NEVO[code]
    g.add((food, RDF.type, FIO.FoodItem))
    g.add((food, RDF.type, foodon))
    g.add((food, SKOS.prefLabel, Literal(f"NEVO food {code}", lang="en")))
    for i, (nutrient, cdno, number, unit) in enumerate(values):
        nv, measure = NEVO[f"{code}/value/{i}"], NEVO[f"{code}/measure/{i}"]
        g.add((food, FIO.hasNutritionalValue, nv))
        g.add((nv, RDF.type, FIO.NutritionalValue))
        g.add((nv, RDF.type, cdno))
        g.add((nv, FIO.hasNutrient, NEVONUT[nutrient]))
        g.add((NEVONUT[nutrient], RDFS.label, Literal(f"NEVO {nutrient}", lang="en")))
        g.add((nv, OM.hasValue, measure))
        g.add((measure, OM.hasNumericalValue, Literal(number)))
        g.add((measure, OM.hasUnit, unit))


def potatoes(graph: Graph) -> ReadOnlyGraphAggregate:
    nevo = Graph()
    nevo_food(nevo, "1", OBO.FOODON_03301449, [("PROT", PROTEIN, 2.0, OM.gramPerHectogram),
                                              ("PROT", PROTEIN, 2000.0, OM.milligramPerHectogram),
                                              ("CHO", CARBOHYDRATE_CLASS, 15.0, OM.gramPerHectogram),
                                              ("WATER", WATER, 80.0, OM.gramPerHectogram)])
    nevo_food(nevo, "2", OBO.FOODON_00002403, [("PROT", PROTEIN, 9.0, OM.gramPerHectogram)])
    return ReadOnlyGraphAggregate([graph, nevo])


def found(graph, query, **bindings) -> list[dict]:
    header, rows = run_query(graph, query, bindings)
    return [dict(zip(header, row, strict=True)) for row in rows]


def test_taco_and_nevo_foods_of_one_foodon_class_compare_by_cdno_class_and_unit(graph, value_of):
    rows = found(potatoes(graph), SAME_CLASS, **{"class": f"<{PROTEIN}>"})
    # food 92 is typed potato (raw), as NEVO 1 is; NEVO 2 has another class; mg is not compared with g
    pairs = [(int(r["taco_food"]), str(r["nevo_food"]), float(r["nevo_value"]), str(r["unit"])) for r in rows]
    assert pairs == [(92, str(NEVO["1"]), 2.0, "g")]
    assert Decimal(str(rows[0]["taco_value"])) == value_of[(92, "protein")].value
    assert (str(rows[0]["taco_nutrient"]), str(rows[0]["nevo_nutrient"])) == ("Protein", "NEVO PROT")
    assert str(rows[0]["foodon_label"]) == "potato (raw)"


def test_moisture_in_percent_compares_with_water_in_grams_per_100_g(graph, value_of):
    rows = found(potatoes(graph), SAME_CLASS, **{"class": f"<{WATER}>"})
    assert [(int(r["taco_food"]), float(r["nevo_value"]), str(r["unit"])) for r in rows] == [(92, 80.0, "g")]
    assert Decimal(str(rows[0]["taco_value"])) == value_of[(92, "moisture")].value


def test_nevo_available_carbohydrate_is_not_paired_with_taco_total_carbohydrate(graph):
    # NICE-Food types it with CDNO's carbohydrate class, the class of TACO's carbohydrate by difference
    assert found(potatoes(graph), SAME_CLASS, **{"class": f"<{CARBOHYDRATE_CLASS}>"}) == []


def test_available_carbohydrate_compares_taco_carbohydrate_minus_fibre(graph, value_of):
    rows = found(potatoes(graph), CARBOHYDRATE)
    assert [(int(r["taco_food"]), float(r["nevo_value"])) for r in rows] == [(92, 15.0)]
    carbohydrate, fibre = value_of[(92, "carbohydrate")].value, value_of[(92, "dietary_fiber")].value
    assert Decimal(str(rows[0]["taco_value"])) == carbohydrate - fibre


def test_the_queries_find_nothing_in_the_taco_graph_alone(graph):
    assert found(graph, SAME_CLASS, **{"class": f"<{PROTEIN}>"}) == []
    assert found(graph, CARBOHYDRATE) == []


def test_eu_tolerance_for_protein_is_2_g_below_10_g_20_percent_up_to_40_g_and_8_g_above():
    def within(taco: float, nevo: float) -> bool | None:
        return compare.within_eu_tolerance(str(PROTEIN), "g", taco, nevo)

    assert within(5.0, 6.9) and not within(5.0, 7.1)
    assert within(20.0, 23.9) and not within(20.0, 24.1)
    assert within(50.0, 42.0) and not within(50.0, 41.9)


def test_eu_tolerance_for_minerals_and_vitamins_is_minus_35_percent_plus_45_or_50():
    calcium, vitamin_c = str(OBO.CDNO_0200544), str(OBO.CDNO_0200192)
    assert compare.within_eu_tolerance(calcium, "mg", 100.0, 145.0)
    assert not compare.within_eu_tolerance(calcium, "mg", 100.0, 146.0)
    assert compare.within_eu_tolerance(vitamin_c, "mg", 100.0, 150.0)
    assert compare.within_eu_tolerance(vitamin_c, "mg", 100.0, 65.0)
    assert not compare.within_eu_tolerance(vitamin_c, "mg", 100.0, 64.0)


def test_no_eu_tolerance_applies_to_water():
    assert compare.within_eu_tolerance(str(WATER), "g", 80.0, 80.0) is None
