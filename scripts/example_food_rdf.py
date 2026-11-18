"""Write one TACO food of the NICE-Food export as a short Turtle file, to read how the data is semantified.

The food is an instance typed with fio:FoodItem and its FoodOn class. Each nutritional value is an instance of
its own, typed with fio:NutritionalValue and a CDNO class, linked to NEVO's nutrient code and to a measure.
The measure is an instance of om:Measure whose number is a literal and whose unit is an OM unit. By default
the file holds food 574, raw red beans, the food of docs/taco-in-nice-food/images/2_one_food_red_beans.svg,
with five of its values, protein (22.17 g per 100 g) among them.

    $env:PYTHONPATH = "src"; python scripts/example_food_rdf.py
"""

from __future__ import annotations

import argparse
import sys

from rdflib import Graph, Namespace, URIRef

from taco_rdf.namespaces import BUILD_DIR, ROOT

SOURCE = BUILD_DIR / "taco_nice_food.ttl"
OUT_DIR = ROOT / "docs" / "taco-in-nice-food" / "files" / "knowledge-graph"
FIO = Namespace("http://www.foodvoc.org/resource/fio#")
OM = Namespace("http://www.ontology-of-units-of-measure.org/resource/om-2/")
VALUES = ("protein", "lipids", "energy_kcal", "magnesium", "available_carbohydrate")
PREFIXES = {"tacoid": "https://w3id.org/taco-rdf/id/", "obo": "http://purl.obolibrary.org/obo/",
            "fio": str(FIO), "om": str(OM), "nevonut": "https://data.rivm.nl/data/nvip/bigfood/nevo/nutrient#",
            "dcterms": "http://purl.org/dc/terms/", "skos": "http://www.w3.org/2004/02/skos/core#",
            "prov": "http://www.w3.org/ns/prov#", "taco": "https://w3id.org/taco-rdf/ontology#"}


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


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--food", type=int, default=574, help="TACO food number (default 574, raw red beans)")
    p.add_argument("--all", action="store_true", help="every value of the food, not five")
    args = p.parse_args()
    if not SOURCE.is_file():
        print(f"{SOURCE} is missing; run scripts/taco_to_nice_food.py first", file=sys.stderr)
        return 1
    source = Graph().parse(SOURCE, format="turtle")
    food = URIRef(f"https://w3id.org/taco-rdf/id/food/{args.food}")
    g = example(source, food, None if args.all else VALUES)
    out = OUT_DIR / f"example_food_{args.food}.ttl"
    out.parent.mkdir(parents=True, exist_ok=True)
    g.serialize(out, format="turtle", encoding="utf-8")
    print(f"wrote {out} ({len(g)} triples)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
