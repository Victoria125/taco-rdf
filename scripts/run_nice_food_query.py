"""Run a NICE-Food query over the nicefood dataset and count its rows by group and by table.

The nicefood Fuseki dataset holds what NICE-Food's own store holds, NEVO's subgraphs and FoodOn, plus the
TACO subgraph of scripts/taco_to_nice_food.py (triplestore/README.md). NICE-Food's queries return food
names, not food IRIs, so a row is counted as TACO's when its food name is the English name of a TACO food
in the subgraph, and as NEVO's otherwise. The output names TACO foods and TACO values only.
"""

from __future__ import annotations

import argparse
import sys
import time
from collections import Counter
from pathlib import Path

import requests
from rdflib import SKOS, Graph

from taco_rdf import sparql
from taco_rdf.namespaces import BUILD_DIR

ENDPOINT = sparql.endpoint()
SUBGRAPH = BUILD_DIR / "taco_nice_food.ttl"


def taco_names(path: Path) -> set[str]:
    """English names of the TACO foods in the subgraph."""
    return {str(n) for n in Graph().parse(path, format="turtle").objects(None, SKOS.prefLabel)
            if getattr(n, "language", None) == "en"}


def run(query: str, endpoint: str) -> tuple[list[str], list[dict[str, str]]]:
    r = requests.post(endpoint, data={"query": query}, headers={"Accept": "application/sparql-results+json"},
                      timeout=900)
    r.raise_for_status()
    result = r.json()
    names = result["head"]["vars"]
    return names, [{k: b[k]["value"] for k in names if k in b} for b in result["results"]["bindings"]]


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("query", type=Path, help="a SPARQL query file, e.g. queries/nice-food/protein_groups.rq")
    p.add_argument("--endpoint", default=ENDPOINT, help=f"SPARQL endpoint (default {ENDPOINT})")
    p.add_argument("--subgraph", type=Path, default=SUBGRAPH, help=f"TACO subgraph (default {SUBGRAPH})")
    p.add_argument("--food", default="foodname", help="the variable holding the food name")
    p.add_argument("--group", default="grouplabel", help="the variable to count rows by")
    p.add_argument("--show", type=int, default=10, help="how many TACO rows to print")
    args = p.parse_args()
    if not args.subgraph.is_file():
        print(f"{args.subgraph} is missing; run scripts/taco_to_nice_food.py first", file=sys.stderr)
        return 1
    taco = taco_names(args.subgraph)
    start = time.perf_counter()
    names, rows = run(args.query.read_text(encoding="utf-8"), args.endpoint)
    seconds = time.perf_counter() - start
    source = ["TACO" if r.get(args.food) in taco else "NEVO" for r in rows]
    counts = Counter((r.get(args.group, ""), s) for r, s in zip(rows, source, strict=True))
    print(f"{args.query.name}: {len(rows)} rows in {seconds:.1f} s, "
          f"{source.count('TACO')} of them TACO foods")
    print(f"| {args.group} | NEVO rows | TACO rows |\n| --- | ---: | ---: |")
    for group in sorted({g for g, _ in counts}):
        print(f"| {group} | {counts[(group, 'NEVO')]} | {counts[(group, 'TACO')]} |")
    shown = [r for r, s in zip(rows, source, strict=True) if s == "TACO"][:args.show]
    if shown:
        print("\nTACO rows, in the query's order:")
        for r in shown:
            print("  " + " | ".join(r.get(k, "") for k in names))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
