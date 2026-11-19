"""Show how TACO's NICE-Food export semantifies its data: one food as Turtle, or the whole graph in numbers.

The food is an instance typed with fio:FoodItem and its FoodOn class. Each nutritional value is an instance of
its own, typed with fio:NutritionalValue and a CDNO class, linked to NEVO's nutrient code and to a measure.
The measure is an instance of om:Measure whose number is a literal and whose unit is an OM unit.

The food is read from Fuseki's nicefood dataset, where the export is loaded (triplestore/README.md), or with
--file from the export itself (docs/taco-in-nice-food/files/knowledge-graph/taco_nice_food.ttl). Without
--print the Turtle goes to example_food_<n>.ttl beside the export; food 574, raw red beans, is the food of
docs/taco-in-nice-food/images/2_one_food_red_beans.svg. --summary counts the whole graph instead.

    $env:PYTHONPATH = "src"; python scripts/example_food_rdf.py --food 574 --print
"""

from __future__ import annotations

import argparse
import sys

from rdflib import Graph, URIRef

from taco_rdf import sparql
from taco_rdf.namespaces import FIO, NEVONUT, OM, ROOT, TACO_SOURCE
from taco_rdf.namespaces import TACO as TACO_ONTOLOGY

ENDPOINT = sparql.endpoint()
KG_DIR = ROOT / "docs" / "taco-in-nice-food" / "files" / "knowledge-graph"
EXPORT = KG_DIR / "taco_nice_food.ttl"
TACO = str(TACO_SOURCE)
VALUES = ("protein", "lipids", "energy_kcal", "magnesium", "available_carbohydrate")
PREFIXES = {"obo": "http://purl.obolibrary.org/obo/", "fio": str(FIO), "om": str(OM), "nevonut": str(NEVONUT),
            "dcterms": "http://purl.org/dc/terms/", "skos": "http://www.w3.org/2004/02/skos/core#",
            "prov": "http://www.w3.org/ns/prov#", "taco": str(TACO_ONTOLOGY)}
SPARQL_PREFIXES = "".join(f"PREFIX {p}: <{ns}> " for p, ns in PREFIXES.items())


def example(source: Graph, food: URIRef, values: tuple[str, ...] | None) -> Graph:
    """The food's own triples, and those of its chosen values and their measures."""
    g = Graph()
    for prefix, ns in PREFIXES.items():
        g.bind(prefix, ns)
    for p, o in source.predicate_objects(food):
        if p != FIO.hasNutritionalValue:
            g.add((food, p, o))
    for v in source.objects(food, FIO.hasNutritionalValue):
        if values is None or str(v).rsplit("/", 1)[-1] in values:
            g.add((food, FIO.hasNutritionalValue, v))
            g += source.triples((v, None, None))
            for m in source.objects(v, OM.hasValue):
                g += source.triples((m, None, None))
    return g


def from_fuseki(endpoint: str, food: URIRef) -> Graph:
    """The food, its values and their measures, as loaded in Fuseki."""
    g = Graph()
    for query in (f"CONSTRUCT {{ <{food}> ?p ?o }} WHERE {{ <{food}> ?p ?o }}",
                  SPARQL_PREFIXES + f"CONSTRUCT {{ ?v ?vp ?vo . ?m ?mp ?mo }} WHERE {{ "
                  f"<{food}> fio:hasNutritionalValue ?v . ?v ?vp ?vo . "
                  "OPTIONAL { ?v om:hasValue ?m . ?m ?mp ?mo } }"):
        g += sparql.construct(query, endpoint, timeout=300)
    return g


def summary(endpoint: str) -> list[tuple[str, str]]:
    """The whole TACO graph in Fuseki, counted."""
    q = SPARQL_PREFIXES + f"""SELECT (COUNT(DISTINCT ?f) AS ?foods) (COUNT(DISTINCT ?typed) AS ?typedfoods)
      (COUNT(DISTINCT ?v) AS ?values) (COUNT(DISTINCT ?food_class) AS ?foodon)
      (COUNT(DISTINCT ?value_class) AS ?cdno) WHERE {{
      ?f dcterms:isVersionOf <{TACO}> ; fio:hasNutritionalValue ?v .
      OPTIONAL {{ ?f a ?food_class . FILTER STRSTARTS(STR(?food_class), "http://purl.obolibrary.org/obo/FOODON_")
                  BIND (?f AS ?typed) }}
      OPTIONAL {{ ?v a ?value_class .
                  FILTER STRSTARTS(STR(?value_class), "http://purl.obolibrary.org/obo/CDNO_") }}
    }}"""
    b = sparql.select(q, endpoint, timeout=300)[0]
    triples = sum(1 for _ in open(EXPORT, encoding="utf-8")) if EXPORT.is_file() else 0
    size = f"{EXPORT.stat().st_size / 1e6:.1f} MB, {triples:,} lines" if triples else "missing"
    return [("TACO foods", b["foods"]), ("with a FoodOn type", b["typedfoods"]),
            ("nutritional values", b["values"]), ("FoodOn classes used", b["foodon"]),
            ("CDNO classes used", b["cdno"]),
            ("file on GitHub", f"docs/taco-in-nice-food/files/knowledge-graph/taco_nice_food.ttl ({size})")]


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--food", type=int, default=574, help="TACO food number (default 574, raw red beans)")
    p.add_argument("--all", action="store_true", help="every value of the food, not five")
    p.add_argument("--file", action="store_true", help="read the export file instead of Fuseki")
    p.add_argument("--print", action="store_true", help="print the Turtle instead of writing a file")
    p.add_argument("--summary", action="store_true", help="count the whole graph instead")
    p.add_argument("--endpoint", default=ENDPOINT)
    args = p.parse_args()
    if args.summary:
        for what, n in summary(args.endpoint):
            print(f"  {what:22} {n}")
        return 0
    food = URIRef(f"https://w3id.org/taco-rdf/id/food/{args.food}")
    source = Graph().parse(EXPORT, format="turtle") if args.file else from_fuseki(args.endpoint, food)
    g = example(source, food, None if args.all else VALUES)
    if not len(g):
        print(f"TACO food {args.food} is not in the graph", file=sys.stderr)
        return 1
    if args.print:
        print(g.serialize(format="turtle"))
        return 0
    out = KG_DIR / f"example_food_{args.food}.ttl"
    g.serialize(out, format="turtle", encoding="utf-8")
    print(f"wrote {out} ({len(g)} triples)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
