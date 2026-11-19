"""FAT/TRP regression checks based on the actual NEVO CDNO proposal code.

Synthetic NEVO observations are used because NEVO measurements are not redistributed
in the TACO repository. The source TACO graph fixture is real, however. These tests
show the structural benefit and two concrete hazards; they do NOT certify that all
3,360 proposed NEVO records are semantically correct.
"""

from __future__ import annotations

import csv
import importlib.util
from decimal import Decimal

import pytest
from rdflib import Graph, Literal
from rdflib.namespace import DCTERMS, RDF, SKOS, XSD

from taco_rdf import nice_food
from taco_rdf.namespaces import FIO, ID, NEVO_SOURCE, NEVONUT, OBO, OM, ROOT, TACO, TACO_SOURCE
from taco_rdf.nice_food_queries import richest

SCRIPT = ROOT / "scripts" / "nevo_cdno_completion.py"
spec = importlib.util.spec_from_file_location("nevo_cdno_completion", SCRIPT)
assert spec is not None and spec.loader is not None
completion = importlib.util.module_from_spec(spec)
spec.loader.exec_module(completion)

TARGET = {"FAT": OBO.CDNO_0200068, "TRP": OBO.CDNO_0200065}
# The four sample values below are deliberately synthetic; do not attribute
# them to real NEVO foods.
SAMPLES = (
    ("taco", "FAT", "8.25", "g"),
    ("nevo", "FAT", "7.80", "g"),
    ("taco", "TRP", "0.12", "g"),
    ("nevo", "TRP", "120", "mg"),
)


def proposal():
    with (ROOT / "data" / "alignment" / "nevo_cdno_completion.csv").open(
        newline="", encoding="utf-8"
    ) as fh:
        return list(csv.DictReader(fh))


def fixture_graph():
    graph = Graph()
    for country, code, num, unit in SAMPLES:
        food = ID[f"test-fat-trp/food/{country}/{code}"]
        value = ID[f"test-fat-trp/value/{country}/{code}"]
        measure = ID[f"test-fat-trp/measure/{country}/{code}"]
        source = TACO_SOURCE if country == "taco" else NEVO_SOURCE
        graph.add((food, RDF.type, FIO.FoodItem))
        graph.add((food, RDF.type, OBO.FOODON_00001256))
        graph.add((food, DCTERMS.isVersionOf, source))
        graph.add((food, SKOS.prefLabel, Literal(f"{country.upper()} {code} example", lang="en")))
        graph.add((food, FIO.hasNutritionalValue, value))
        graph.add((value, RDF.type, FIO.NutritionalValue))
        graph.add((value, FIO.hasNutrient, NEVONUT[code]))
        graph.add((value, OM.hasValue, measure))
        graph.add((measure, RDF.type, OM.Measure))
        graph.add((measure, OM.hasNumericalValue, Literal(Decimal(num), datatype=XSD.decimal)))
        graph.add((measure, OM.hasUnit, Literal(unit, datatype=XSD.string)))
        if country == "taco":
            graph.add((value, RDF.type, TARGET[code]))
    return graph


def overlay(graph, monkeypatch):
    def select_local(query, _endpoint):
        result = graph.query(query)
        assert result.graph is not None
        return result.graph

    monkeypatch.setattr(completion.store, "construct", select_local)
    return completion.additions("local-fixture", proposal(), str(NEVONUT))


def test_proposed_classes_and_3360_counts_are_explicit_in_saved_candidate_csv():
    rows = proposal()
    assert [(r["nevo_code"], r["cdno_class"], int(r["nevo_values"])) for r in rows] == [
        ("FAT", "CDNO_0200068", 3346),
        ("TRP", "CDNO_0200065", 14),
    ]
    assert sum(int(r["nevo_values"]) for r in rows) == 3360
    ontology = Graph().parse(ROOT / "ontology/imports/cdno-module.ttl", format="turtle")
    for cls in TARGET.values():
        assert (cls, RDF.type, None) in ontology


def test_actual_taco_source_uses_these_cdno_classes_and_codes(graph):
    codes = nice_food.nevo_codes(nice_food.NUTRIENTS)
    assert codes["lipids"] == "FAT"
    assert codes["tryptophan"] == "TRP"
    for key, code in (("lipids", "FAT"), ("tryptophan", "TRP")):
        measured = [m for m in graph.subjects(TACO.ofNutrient, ID[f"nutrient/{key}"])
                    if (m, RDF.type, TARGET[code]) in graph]
        assert len(measured) > 0
    exported, _ = nice_food.export(graph, codes)
    for code, cls in TARGET.items():
        vals = list(exported.subjects(FIO.hasNutrient, NEVONUT[code]))
        assert vals
        assert all((v, RDF.type, cls) in exported for v in vals)


def test_real_completion_function_maps_only_unique_taco_classes():
    without = [
        {"n": str(NEVONUT.FAT), "label": "Fat total", "values": "3346"},
        {"n": str(NEVONUT.TRP), "label": "Tryptophan", "values": "14"},
        {"n": str(NEVONUT.CHO), "label": "Carbohydrate", "values": "3314"},
    ]
    taco = [
        {"n": str(NEVONUT.FAT), "c": str(TARGET["FAT"]), "label": "lipid"},
        {"n": str(NEVONUT.TRP), "c": str(TARGET["TRP"]), "label": "tryptophan"},
        {"n": str(NEVONUT.CHO), "c": str(OBO.CDNO_0200005), "label": "carbohydrate"},
        {"n": str(NEVONUT.CHO), "c": str(OBO.CDNO_0200033), "label": "available carbohydrate"},
    ]
    result = completion.completion(without, taco)
    assert [(r["nevo_code"], r["cdno_class"]) for r in result] == [
        ("FAT", "CDNO_0200068"), ("TRP", "CDNO_0200065")
    ]


def test_actual_overlay_adds_only_types_and_expands_cdno_queries(monkeypatch):
    before = fixture_graph()
    original = set(before)
    proposed = overlay(before, monkeypatch)
    expected = {
        (ID[f"test-fat-trp/value/nevo/{code}"], RDF.type, TARGET[code])
        for code in TARGET
    }
    assert set(proposed) == expected
    after = before + proposed
    assert original.issubset(set(after))
    assert len(after) == len(before) + 2
    assert len(after + proposed) == len(after)  # idempotent when loaded again
    for code, cls in (("FAT", "CDNO_0200068"), ("TRP", "CDNO_0200065")):
        q = richest("FOODON_00001256", cls)
        previous = list(before.query(q))
        current = list(after.query(q))
        assert len(previous) == 1
        assert len(current) == 2
    assert list(before.triples((None, OM.hasNumericalValue, None))) == list(
        after.triples((None, OM.hasNumericalValue, None))
    )


def test_trp_numbers_require_unit_conversion_before_cross_country_ranking(monkeypatch):
    before = fixture_graph()
    after = before + overlay(before, monkeypatch)
    vals = {str(row.source): (Decimal(str(row.amount)), str(row.unit))
            for row in after.query(richest("FOODON_00001256", "CDNO_0200065"))}
    assert vals[str(TACO_SOURCE)] == (Decimal("0.12"), "g")
    assert vals[str(NEVO_SOURCE)] == (Decimal("120"), "mg")
    normalized = {source: number * (1000 if unit == "g" else 1)
                  for source, (number, unit) in vals.items()}
    assert normalized[str(TACO_SOURCE)] == normalized[str(NEVO_SOURCE)] == Decimal("120")


def test_current_overlay_needs_conflict_guard_when_nevo_already_has_another_cdno(monkeypatch):
    """Counterexample: current additions() does not check whether a CDNO class already exists."""
    graph = fixture_graph()
    node = ID["test-fat-trp/value/nevo/FAT"]
    graph.add((node, RDF.type, OBO.CDNO_0200005))
    proposed = overlay(graph, monkeypatch)
    assert (node, RDF.type, TARGET["FAT"]) in proposed
    classes = {c for c in (graph + proposed).objects(node, RDF.type)
               if str(c).startswith(str(OBO) + "CDNO_")}
    assert classes == {OBO.CDNO_0200005, OBO.CDNO_0200068}
    # This is intentionally a passing *counterexample*, not a claim of safe
    # production application. Existing CDNO annotations must be checked first.


def test_proposal_is_not_a_nevo_numeric_data_patch():
    """Proposed CSV contains source codes/counts/classes, not any copyrighted food observations."""
    data = proposal()
    assert all(set(row) == {
        "nevo_code", "nevo_label", "cdno_class", "cdno_label", "nevo_values", "evidence"
    } for row in data)
