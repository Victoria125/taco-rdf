"""Convert TBCA, as scripts/fetch_tbca.py downloads it, into RDF in the NICE-Food pattern.

NICE-Food models NEVO's foods as fio:FoodItem with fio:NutritionalValue nodes, each naming a nutrient and an
om:Measure with a number and an OM unit, and types each value with a CDNO class. This script writes TBCA's
foods the same way, so the queries over NEVO's foods read TBCA's too. data/alignment/tbca_components.csv says
which CDNO class types each TBCA component, and why; components without a class there are left out. TBCA's
trace values ("tr") keep TACO's taco:Trace status and no number; values TBCA does not give ("NA", "-") are
left out, without asserting why they are missing. Each food is marked as a version of TBCA
(dcterms:isVersionOf), as NICE-Food marks NEVO's.

The foods get no FoodOn type here: that needs a reviewed mapping. With --candidates, the unreviewed
candidates of scripts/tbca_foodon_candidates.py are added as tbca:foodOnCandidate, never as rdf:type, so
queries can compare TBCA provisionally without taking a candidate for a type; candidates that are classes of
whole organisms are left out. The output goes to build/, which git ignores, because TBCA's values may not be
redistributed without its coordinators' written permission.
"""

from __future__ import annotations

import argparse
import csv
import datetime
import re
import sys
import unicodedata
from decimal import Decimal, InvalidOperation
from pathlib import Path

from rdflib import DCTERMS, RDF, RDFS, SKOS, XSD, Graph, Literal, Namespace, URIRef

from taco_rdf.namespaces import BUILD_DIR, FIO, OBO, OM, ROOT, TACO

DCAT = Namespace("http://www.w3.org/ns/dcat#")
TBCA = Namespace("https://w3id.org/taco-rdf/tbca#")
TBCA_ID = Namespace("https://w3id.org/taco-rdf/id/tbca/")
TBCA_SITE = URIRef("https://www.tbca.net.br/")
SOURCE = ROOT / "data" / "external" / "tbca"
COMPONENTS = ROOT / "data" / "alignment" / "tbca_components.csv"
OUT = BUILD_DIR / "tbca.ttl"
UNITS = {"g": OM.gramPerHectogram, "mg": OM.milligramPerHectogram}


def slug(text: str) -> str:
    ascii_text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "_", ascii_text.lower()).strip("_")


def number(text: str) -> Decimal | None:
    """TBCA's value with a decimal comma as a number; None for a trace or anything else."""
    try:
        return Decimal(text.replace(".", "").replace(",", "."))
    except InvalidOperation:
        return None


def read(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def convert(foods: list[dict[str, str]], values: list[dict[str, str]],
            components: list[dict[str, str]], retrieved: str) -> tuple[Graph, dict[str, int]]:
    """The TBCA graph and counts of what was converted and left out."""
    g = Graph()
    for prefix, ns in (("fio", FIO), ("om", OM), ("dcat", DCAT), ("tbca", TBCA), ("tbcaid", TBCA_ID),
                       ("obo", OBO), ("taco", TACO), ("skos", SKOS), ("dcterms", DCTERMS)):
        g.bind(prefix, ns)
    classes = {(c["component"], c["unit"]): c["cdno"] for c in components if c["cdno"]}
    dataset = TBCA_ID["dataset"]
    g.add((dataset, RDF.type, DCAT.Dataset))
    title = "TBCA, Tabela Brasileira de Composição de Alimentos (BD-AIN)"
    rights = ("Used with the permission of TBCA's coordination; TBCA's terms of use forbid reproduction or "
              "alteration without it.")
    g.add((dataset, DCTERMS.title, Literal(title, lang="pt")))
    g.add((dataset, DCTERMS.source, TBCA_SITE))
    g.add((dataset, DCTERMS.date, Literal(retrieved, datatype=XSD.date)))
    g.add((dataset, DCTERMS.rights, Literal(rights, lang="en")))
    for food in foods:
        f = TBCA_ID[f"food/{food['code']}"]
        g.add((f, RDF.type, FIO.FoodItem))
        g.add((f, DCTERMS.isVersionOf, TBCA_SITE))
        g.add((f, DCTERMS.identifier, Literal(food["code"])))
        g.add((f, SKOS.prefLabel, Literal(food["name_pt"], lang="pt")))
        if food["name_en"]:
            g.add((f, SKOS.prefLabel, Literal(food["name_en"], lang="en")))
        for prop, key in ((TBCA.group, "group"), (TBCA.foodType, "food_type"),
                          (TBCA.scientificName, "scientific_name")):
            if food[key]:
                g.add((f, prop, Literal(food[key])))
    counts = {"values": 0, "traces": 0, "not given (NA or -)": 0, "without CDNO class": 0}
    for v in values:
        cdno = classes.get((v["component"], v["unit"]))
        raw = v["value_per_100g"].strip().lower()
        amount = number(raw)
        if not cdno:
            counts["without CDNO class"] += 1
            continue
        if raw != "tr" and amount is None:
            counts["not given (NA or -)"] += 1
            continue
        food, key = v["code"], slug(v["component"])
        node = TBCA_ID[f"value/{food}/{key}"]
        nutrient = TBCA_ID[f"nutrient/{key}"]
        g.add((TBCA_ID[f"food/{food}"], FIO.hasNutritionalValue, node))
        g.add((node, RDF.type, FIO.NutritionalValue))
        g.add((node, RDF.type, OBO[cdno]))
        g.add((node, FIO.hasNutrient, nutrient))
        g.add((nutrient, RDF.type, FIO.Nutrient))
        g.add((nutrient, RDFS.label, Literal(v["component"], lang="pt")))
        if amount is None:
            g.add((node, TACO.valueStatus, TACO.Trace))
            counts["traces"] += 1
        else:
            measure = TBCA_ID[f"value/{food}/{key}/measure"]
            g.add((node, OM.hasValue, measure))
            g.add((measure, RDF.type, OM.Measure))
            g.add((measure, OM.hasNumericalValue, Literal(amount, datatype=XSD.decimal)))
            g.add((measure, OM.hasUnit, UNITS[v["unit"]]))
            counts["values"] += 1
    return g, counts


def add_candidates(g: Graph, candidates: list[dict[str, str]]) -> int:
    """Add each non-organism FoodOn candidate as tbca:foodOnCandidate; return how many were added."""
    added = 0
    for c in candidates:
        if c["foodon"] and c.get("organism_class") != "True":
            food = TBCA_ID[f"food/{c['code']}"]
            g.add((food, TBCA.foodOnCandidate, OBO[c["foodon"]]))
            g.add((food, TBCA.foodOnCandidateRule, Literal(c["rule"])))
            added += 1
    return added


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source", type=Path, default=SOURCE, help=f"folder of fetch_tbca.py's CSVs ({SOURCE})")
    p.add_argument("-o", "--output", type=Path, default=OUT, help=f"Turtle file to write (default {OUT})")
    p.add_argument("--candidates", type=Path, nargs="?", const=SOURCE / "foodon_candidates.csv",
                   help="add the unreviewed FoodOn candidates of tbca_foodon_candidates.py as "
                        "tbca:foodOnCandidate")
    args = p.parse_args()
    paths = [args.source / "foods.csv", args.source / "values.csv"]
    if not all(path.is_file() for path in paths):
        print(f"missing {args.source}/foods.csv or values.csv; run scripts/fetch_tbca.py first",
              file=sys.stderr)
        return 1
    retrieved = datetime.date.fromtimestamp(paths[1].stat().st_mtime).isoformat()
    g, counts = convert(read(paths[0]), read(paths[1]), read(COMPONENTS), retrieved)
    if args.candidates:
        counts["FoodOn candidates"] = add_candidates(g, read(args.candidates))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    g.serialize(args.output, format="turtle")
    foods = len(set(g.subjects(RDF.type, FIO.FoodItem)))
    summary = ", ".join(f"{n} {k}" for k, n in counts.items())
    print(f"wrote {args.output}: {len(g)} triples, {foods} foods; {summary}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
