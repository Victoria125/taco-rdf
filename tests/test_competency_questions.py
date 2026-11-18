"""The competency questions find each table's foods of a kind by FoodOn's hierarchy, richest first."""

from __future__ import annotations

import importlib.util
from decimal import Decimal

from rdflib import RDF, RDFS, SKOS, Graph, Literal, Namespace, URIRef

from taco_rdf.namespaces import ROOT

spec = importlib.util.spec_from_file_location("competency_questions",
                                              ROOT / "scripts" / "competency_questions.py")
assert spec is not None and spec.loader is not None
cq = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cq)

OBO = Namespace("http://purl.obolibrary.org/obo/")
FIO = Namespace("http://www.foodvoc.org/resource/fio#")
OM = Namespace("http://www.ontology-of-units-of-measure.org/resource/om-2/")
DCTERMS = Namespace("http://purl.org/dc/terms/")
EX = Namespace("urn:example:")


def food(g: Graph, name: str, source: str, cls: URIRef, *amounts: str) -> None:
    f = EX[name.replace(" ", "_").replace(",", "")]
    g.add((f, RDF.type, FIO.FoodItem))
    g.add((f, RDF.type, cls))
    g.add((f, DCTERMS.isVersionOf, URIRef(source)))
    g.add((f, SKOS.prefLabel, Literal(name, lang="en")))
    for i, amount in enumerate(amounts):
        v, m = EX[f"{f.split(':')[-1]}_v{i}"], EX[f"{f.split(':')[-1]}_m{i}"]
        g.add((f, FIO.hasNutritionalValue, v))
        g.add((v, RDF.type, OBO.CDNO_0200570))
        g.add((v, OM.hasValue, m))
        g.add((m, OM.hasNumericalValue, Literal(Decimal(amount))))
        g.add((m, OM.hasUnit, Literal("mg")))


def graph() -> Graph:
    g = Graph()
    g.add((OBO.FOODON_1, RDFS.subClassOf, OBO.FOODON_00001172))
    g.add((OBO.FOODON_1, RDFS.label, Literal("Brazil nut")))
    food(g, "Brazil nut, raw", cq.TACO, OBO.FOODON_1, "365")
    food(g, "Cashew nut, roasted", cq.TACO, OBO.FOODON_00001172, "236")
    food(g, "Brazil nuts salted", cq.NEVO, OBO.FOODON_1, "100", "350")
    food(g, "Apple raw", cq.NEVO, OBO.FOODON_00001057, "5")
    return g


def test_the_richest_foods_of_a_kind_come_first_for_each_table():
    rows = graph().query(cq.richest("FOODON_00001172", "CDNO_0200570"))
    found = [(str(r.source), str(r.name), float(r.amount)) for r in rows]
    assert found == [(cq.TACO, "Brazil nut, raw", 365.0), (cq.TACO, "Cashew nut, roasted", 236.0),
                     (cq.NEVO, "Brazil nuts salted", 350.0)]


def test_shared_food_types_count_foods_of_both_tables():
    rows = list(graph().query(cq.SHARED))
    assert [(str(r.label), int(r.taco), int(r.nevo)) for r in rows] == [("Brazil nut", 1, 1)]


def test_amounts_are_rounded_for_reading():
    assert [cq.amount(v) for v in ("941.369667", "18.5817", "7.98667", "0.46")] == ["941", "19", "8.0", "0.5"]


def test_top_keeps_one_table_in_order():
    rows = [{"source": "a", "name": "1"}, {"source": "b", "name": "2"}, {"source": "a", "name": "3"}]
    assert [r["name"] for r in cq.top(rows, "a", 5)] == ["1", "3"]
