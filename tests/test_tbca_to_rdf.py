"""TBCA's foods become RDF in the NICE-Food pattern, values typed by data/alignment/tbca_components.csv."""

from __future__ import annotations

import csv
import importlib.util
from decimal import Decimal

from rdflib import DCTERMS, RDF, SKOS, URIRef

from taco_rdf.namespaces import OBO, ROOT, TACO

spec = importlib.util.spec_from_file_location("tbca_to_rdf", ROOT / "scripts" / "tbca_to_rdf.py")
assert spec is not None and spec.loader is not None
tbca = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tbca)

FOOD = {"code": "BRC9999X", "group": "C - Frutas e derivados", "food_type": "A - Alimento in natura",
        "scientific_name": "", "name_pt": "Fruta, crua, Brasil", "name_en": "Fruit, raw, Brazil",
        "name_es": ""}


def components() -> list[dict[str, str]]:
    with (ROOT / "data" / "alignment" / "tbca_components.csv").open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def value(component: str, unit: str, text: str) -> dict[str, str]:
    return {"code": FOOD["code"], "component": component, "unit": unit, "value_per_100g": text}


def converted(*values: dict[str, str]):
    g, counts = tbca.convert([FOOD], list(values), components(), "2026-11-05")
    return g, counts, tbca.TBCA_ID[f"food/{FOOD['code']}"]


def test_a_food_is_a_fio_food_item_marked_as_a_version_of_tbca_with_both_names():
    g, _, food = converted()
    assert (food, RDF.type, tbca.FIO.FoodItem) in g
    assert (food, DCTERMS.isVersionOf, URIRef("https://www.tbca.net.br/")) in g
    assert {(str(n), n.language) for n in g.objects(food, SKOS.prefLabel)} == {
        ("Fruta, crua, Brasil", "pt"), ("Fruit, raw, Brazil", "en")}


def test_a_value_with_a_decimal_comma_is_typed_with_its_cdno_class_in_om_units():
    g, counts, food = converted(value("Proteína", "g", "1,15"))
    node = g.value(food, tbca.FIO.hasNutritionalValue)
    assert (node, RDF.type, OBO.CDNO_0200040) in g
    measure = g.value(node, tbca.OM.hasValue)
    assert g.value(measure, tbca.OM.hasNumericalValue).toPython() == Decimal("1.15")
    assert g.value(measure, tbca.OM.hasUnit) == tbca.OM.gramPerHectogram
    assert counts["values"] == 1


def test_available_carbohydrate_gets_cdno_s_available_carbohydrate_class_and_total_the_general_one():
    g, _, food = converted(value("Carboidrato disponível", "g", "1,81"),
                           value("Carboidrato total", "g", "5,84"))
    classes = {c for node in g.objects(food, tbca.FIO.hasNutritionalValue) for c in g.objects(node, RDF.type)}
    assert {OBO.CDNO_0200033, OBO.CDNO_0200005} <= classes


def test_a_trace_keeps_taco_s_trace_status_and_no_number():
    g, counts, food = converted(value("Ferro", "mg", "tr"))
    node = g.value(food, tbca.FIO.hasNutritionalValue)
    assert g.value(node, TACO.valueStatus) == TACO.Trace
    assert g.value(node, tbca.OM.hasValue) is None
    assert counts["traces"] == 1


def test_values_not_given_and_components_without_a_cdno_class_are_left_out():
    g, counts, food = converted(value("Manganês", "mg", "NA"), value("Selênio", "mcg", "1,2"))
    assert g.value(food, tbca.FIO.hasNutritionalValue) is None
    assert counts["not given (NA or -)"] == 1
    assert counts["without CDNO class"] == 1
