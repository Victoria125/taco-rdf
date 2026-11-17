"""Write the TACO graph as a NICE-Food subgraph, shaped like NICE-Food's nevo21_graph.ttl.

NICE-Food (rivm-syso/nicekg_processing) gives each dataset a subgraph: food items (fio:FoodItem) typed
with a FoodOn class, each with fio:NutritionalValue nodes, typed with a CDNO class where there is one,
naming a nutrient and an om:Measure whose unit is an OM unit and a string. Its analysis queries name
nutrients by NEVO's codes, e.g. fio:hasNutrient nevonut:PROT in protein_groups.rq. This script writes TACO
the same way, so the subgraph can be loaded next to NEVO's and NICE-Food's queries read Brazilian foods
unchanged. Every TACO value is written:

- foods keep their TACO IRIs, FoodOn types and names, and are marked as a version of TACO
  (dcterms:isVersionOf), as NICE-Food marks NEVO's;
- every measurement becomes a nutritional value with its CDNO class, if it has one; a number gets a
  measure, and a trace, not-applicable or under-re-evaluation cell keeps TACO's taco:valueStatus instead,
  since it has no number and a trace is not zero;
- the nutrient is NEVO's code where data/alignment/taco_nevo_nutrients.csv gives one (protein is
  nevonut:PROT), TACO's own nutrient otherwise;
- TACO's carbohydrate is total carbohydrate, which NEVO has no code for. Each food also gets its available
  carbohydrate, carbohydrate minus dietary fibre, as NEVO's CHO, saying which values it was derived from.

TACO's conditions allow reproduction with the source cited, so this subgraph can be shared; it goes to
build/.
"""

from __future__ import annotations

import argparse
import csv
import sys
from collections import Counter
from decimal import Decimal
from pathlib import Path

from rdflib import DCTERMS, PROV, RDF, RDFS, SKOS, XSD, Graph, Literal, Namespace, URIRef

from taco_rdf.namespaces import BUILD_DIR, FIO, OBO, QUDT, ROOT, TACO, UNIT

OM = Namespace("http://www.ontology-of-units-of-measure.org/resource/om-2/")
NEVONUT = Namespace("https://data.rivm.nl/data/nvip/bigfood/nevo/nutrient#")
DCAT = Namespace("http://www.w3.org/ns/dcat#")
TACO_SOURCE = URIRef("https://nepa.unicamp.br/tabela-brasileira-de-composicao-de-alimentos-4a-edicao/")
DATASET = URIRef("https://w3id.org/taco-rdf/nice-food")
NUTRIENTS = ROOT / "data" / "alignment" / "taco_nevo_nutrients.csv"
OUT = BUILD_DIR / "taco_nice_food.ttl"
# TACO's QUDT units as NICE-Food writes NEVO's: an OM unit per 100 g and a string. NICE-Food gives
# micrograms the string only, and so does this export.
UNITS = {UNIT.GM: (OM.gramPerHectogram, "g"), UNIT.PERCENT: (OM.gramPerHectogram, "g"),
         UNIT.MilliGM: (OM.milligramPerHectogram, "mg"), UNIT.MicroGM: (None, "µg"),
         UNIT.KiloCAL: (OM.kilocaloriePerHectogram, "kcal"), UNIT.KiloJ: (OM.kilojoulePerHectogram, "kJ")}
CDNO = str(OBO) + "CDNO_"
FOODON = str(OBO) + "FOODON_"
AVAILABLE_CARBOHYDRATE = OBO.CDNO_0200033
# Fibre statuses under which available carbohydrate is total carbohydrate: TACO marks dietary fibre not
# applicable where a food has none, as in meat, and a trace is too small to subtract.
NO_FIBRE = {TACO.NotApplicable: "not applicable", TACO.Trace: "a trace"}


def nevo_codes(path: Path) -> dict[str, str]:
    """TACO nutrient key to NEVO code, for the nutrients the alignment file gives a code."""
    with path.open(encoding="utf-8", newline="") as fh:
        return {r["taco_nutrient"]: r["nevo_code"] for r in csv.DictReader(fh) if r["nevo_code"]}


def add_measure(g: Graph, value_node: URIRef, number: Decimal | Literal, unit: URIRef) -> None:
    measure = URIRef(f"{value_node}/measure")
    g.add((value_node, OM.hasValue, measure))
    g.add((measure, RDF.type, OM.Measure))
    g.add((measure, OM.hasNumericalValue, number if isinstance(number, Literal) else Literal(number)))
    om_unit, text = UNITS[unit]
    if om_unit is not None:
        g.add((measure, OM.hasUnit, om_unit))
    g.add((measure, OM.hasUnit, Literal(text, datatype=XSD.string)))


def available_carbohydrate(g: Graph, taco: Graph, food: URIRef, carbohydrate: URIRef | None,
                           fibre: URIRef | None) -> str:
    """Write a food's available carbohydrate as NEVO's CHO, and say how it was found or why it was not."""
    if carbohydrate is None or taco.value(carbohydrate, QUDT.numericValue) is None:
        return "no number for carbohydrate"
    total = taco.value(carbohydrate, QUDT.numericValue).toPython()
    fibre_number = taco.value(fibre, QUDT.numericValue) if fibre is not None else None
    fibre_status = taco.value(fibre, TACO.valueStatus) if fibre is not None else None
    if fibre_number is not None:
        value = Decimal(str(total)) - Decimal(str(fibre_number.toPython()))
        how = "TACO's carbohydrate minus its dietary fibre"
        sources = [carbohydrate, fibre]
        outcome = "carbohydrate minus fibre"
    elif fibre_status in NO_FIBRE:
        value = Decimal(str(total))
        how = f"TACO's carbohydrate, its dietary fibre being {NO_FIBRE[fibre_status]}"
        sources = [carbohydrate, fibre]
        outcome = f"fibre {NO_FIBRE[fibre_status]}"
    else:
        return "no number for dietary fibre"
    if value < 0:
        value, how, outcome = Decimal(0), how + ", less than zero and so zero", "below zero, written as zero"
    node = URIRef(str(carbohydrate).rsplit("/", 1)[0] + "/available_carbohydrate")
    g.add((food, FIO.hasNutritionalValue, node))
    g.add((node, RDF.type, FIO.NutritionalValue))
    g.add((node, RDF.type, AVAILABLE_CARBOHYDRATE))
    g.add((node, FIO.hasNutrient, NEVONUT.CHO))
    g.add((node, DCTERMS.description, Literal(f"Available carbohydrate by difference: {how}.", lang="en")))
    for source in sources:
        g.add((node, PROV.wasDerivedFrom, source))
    add_measure(g, node, value, UNIT.GM)
    return outcome


def export(taco: Graph, codes: dict[str, str]) -> tuple[Graph, Counter]:
    """The NICE-Food subgraph of TACO, and counts of what it holds."""
    g = Graph()
    for prefix, ns in (("fio", FIO), ("om", OM), ("nevonut", NEVONUT), ("obo", OBO), ("skos", SKOS),
                       ("dcterms", DCTERMS), ("dcat", DCAT), ("prov", PROV), ("taco", TACO)):
        g.bind(prefix, ns)
    g.add((DATASET, RDF.type, DCAT.Dataset))
    g.add((DATASET, DCTERMS.title, Literal("TACO as a NICE-Food subgraph", lang="en")))
    g.add((DATASET, DCTERMS.source, TACO_SOURCE))
    g.add((DATASET, DCTERMS.rights, Literal("TACO, NEPA-UNICAMP 2011: reproduction allowed with the source "
                                            "cited.", lang="en")))
    counts: Counter = Counter()
    for food in taco.subjects(RDF.type, TACO.Food):
        counts["foods"] += 1
        g.add((food, RDF.type, FIO.FoodItem))
        g.add((food, DCTERMS.isVersionOf, TACO_SOURCE))
        g.add((food, DCTERMS.identifier, Literal(str(taco.value(food, TACO.foodNumber)))))
        foodon = [c for c in taco.objects(food, RDF.type) if str(c).startswith(FOODON)]
        counts["foods with a FoodOn class"] += bool(foodon)
        for c in foodon:
            g.add((food, RDF.type, c))
        for label in taco.objects(food, SKOS.prefLabel):
            g.add((food, SKOS.prefLabel, label))
    by_food: dict[URIRef, dict[str, URIRef]] = {}
    for m in taco.subjects(RDF.type, TACO.NutrientMeasurement):
        food, nutrient = taco.value(m, TACO.ofFood), taco.value(m, TACO.ofNutrient)
        key = str(nutrient).rsplit("/", 1)[-1]
        by_food.setdefault(food, {})[key] = m
        g.add((food, FIO.hasNutritionalValue, m))
        g.add((m, RDF.type, FIO.NutritionalValue))
        classes = [c for c in taco.objects(m, RDF.type) if str(c).startswith(CDNO)]
        for c in classes:
            g.add((m, RDF.type, c))
        counts["values"] += 1
        counts["values with a CDNO class"] += bool(classes)
        if key in codes:
            g.add((m, FIO.hasNutrient, NEVONUT[codes[key]]))
            counts["values with a NEVO code"] += 1
        else:
            g.add((m, FIO.hasNutrient, nutrient))
            g.add((nutrient, RDF.type, FIO.Nutrient))
            for label in taco.objects(nutrient, SKOS.prefLabel):
                g.add((nutrient, RDFS.label, label))
        number, unit = taco.value(m, QUDT.numericValue), taco.value(m, QUDT.unit)
        if number is not None and unit in UNITS:
            add_measure(g, m, number, unit)
            counts["values with a number"] += 1
        else:
            status = taco.value(m, TACO.valueStatus)
            g.add((m, TACO.valueStatus, status))
            counts[f"values without a number ({str(status).rsplit('#', 1)[-1]})"] += 1
    for food, measurements in by_food.items():
        outcome = available_carbohydrate(g, taco, food, measurements.get("carbohydrate"),
                                         measurements.get("dietary_fiber"))
        counts[f"available carbohydrate: {outcome}"] += 1
    return g, counts


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--graph", type=Path, default=BUILD_DIR / "taco.ttl",
                   help="TACO Turtle snapshot to export (default build/taco.ttl)")
    p.add_argument("-o", "--output", type=Path, default=OUT, help=f"Turtle file to write (default {OUT})")
    args = p.parse_args()
    if not args.graph.is_file():
        print(f"{args.graph} is missing; build the graph first", file=sys.stderr)
        return 1
    g, counts = export(Graph().parse(args.graph, format="turtle"), nevo_codes(NUTRIENTS))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    g.serialize(args.output, format="turtle")
    print(f"wrote {args.output}: {len(g)} triples")
    for name, n in sorted(counts.items()):
        print(f"  {n:6d}  {name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
