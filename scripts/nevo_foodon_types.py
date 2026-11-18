"""Turn the reviewed NEVO to FoodOn sheet into rdf:type triples, as NICE-Food types its other NEVO foods.

scripts/nevo_foodon_candidates.py writes build/nevo/foodon_pilot/candidates.csv. A reviewer fills its decision
column with the candidate chosen (name, neighbour1, neighbour2, taco_neighbour, ols1, ols2, ols3), with other
and the class in
chosen_class, or with none when no FoodOn class fits. This script checks each decision (one class, in the
pinned FoodOn release, not a class of whole organisms or plants) and writes one triple per typed food:

    <https://data.rivm.nl/data/nvip/bigfood/nevo21/nevocode#...> a obo:FOODON_... .

rdf:type only, no SKOS, as in the rest of NICE-Food's graph. Rows without a decision are counted as pending.
Excel may save the sheet back with semicolons or commas, in UTF-8 or in Windows-1252; all are read.

    $env:PYTHONPATH = "src"; python scripts/nevo_foodon_types.py
"""

from __future__ import annotations

import argparse
import csv
import io
import re
import sys
from collections import Counter
from pathlib import Path

from rdflib import RDF, Graph, URIRef

from taco_rdf.namespaces import BUILD_DIR, OBO, ROOT

PILOT = BUILD_DIR / "nevo" / "foodon_pilot"
CLASSES = ROOT / "ontology" / "imports" / "foodon-classes.tsv"
SOURCES = ("name", "neighbour1", "neighbour2", "taco_neighbour", "ols1", "ols2", "ols3")


def read_sheet(path: Path) -> list[dict[str, str]]:
    data = path.read_bytes()
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = data.decode("cp1252")
    dialect = csv.Sniffer().sniff(text.split("\n", 1)[0], delimiters=";,")
    return list(csv.DictReader(io.StringIO(text), dialect=dialect))


def pinned_classes(path: Path = CLASSES) -> set[str]:
    with path.open(encoding="utf-8") as fh:
        return {line.split("\t", 1)[0] for line in fh if not line.startswith("#") and "\t" in line}


def curie(value: str) -> str:
    """FOODON_03301055 from FOODON_03301055, FOODON:03301055 or the class IRI."""
    m = re.search(r"FOODON[_:](\d+)", value.strip())
    return f"FOODON_{m.group(1)}" if m else value.strip()


def decide(row: dict[str, str], pinned: set[str]) -> tuple[str, str]:
    """(status, class or problem): status is typed, none, pending or error."""
    decision = (row.get("decision") or "").strip().lower()
    chosen = curie(row.get("chosen_class") or "")
    if not decision:
        return "pending", ""
    if decision == "none":
        return "none", ""
    if decision == "other":
        if not chosen:
            return "error", "decision is other but chosen_class is empty"
        found = chosen
    elif decision in SOURCES:
        options = [curie(c) for c in (row.get(f"{decision}_class") or "").split(";") if c.strip()]
        if not options:
            return "error", f"{decision} has no candidate"
        if len(options) > 1 and chosen not in options:
            return "error", f"{decision} has {len(options)} classes; put the one chosen in chosen_class"
        found = chosen if len(options) > 1 else options[0]
    else:
        return "error", f"unknown decision {decision!r}"
    if found not in pinned:
        return "error", f"{found} is not in the pinned FoodOn release"
    if found in {curie(c) for c in (row.get("organism_classes") or "").split(";") if c.strip()}:
        return "error", f"{found} is a class of whole organisms or plants"
    return "typed", found


def types(rows: list[dict[str, str]], pinned: set[str]) -> tuple[Graph, Counter, list[str]]:
    g = Graph()
    g.bind("obo", OBO)
    counts: Counter = Counter()
    problems = []
    for row in rows:
        status, value = decide(row, pinned)
        counts[status] += 1
        if status == "typed":
            g.add((URIRef(row["nevo_iri"]), RDF.type, OBO[value]))
        elif status == "error":
            problems.append(f"{row.get('nevo_release')} {row.get('nevo_code')}: {value}")
    return g, counts, problems


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--sheet", type=Path, default=PILOT / "candidates.csv", help="the reviewed sheet")
    p.add_argument("--out", type=Path, default=PILOT / "nevo_foodon_types.ttl", help="Turtle to write")
    args = p.parse_args()
    if not args.sheet.is_file():
        print(f"{args.sheet} is missing; run scripts/nevo_foodon_candidates.py first", file=sys.stderr)
        return 1
    g, counts, problems = types(read_sheet(args.sheet), pinned_classes())
    for problem in problems:
        print(f"  {problem}")
    print(f"typed {counts['typed']}, no FoodOn class {counts['none']}, pending {counts['pending']}, "
          f"to fix {counts['error']}")
    if problems:
        return 1
    g.serialize(args.out, format="turtle", encoding="utf-8")
    print(f"wrote {args.out} ({len(g)} triples)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
