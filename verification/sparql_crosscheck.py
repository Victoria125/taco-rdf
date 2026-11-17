"""Run NICE-Food queries on two SPARQL engines, Fuseki and rdflib, and compare their answers row by row.

The nicefood Fuseki dataset holds TACO's NICE-Food subgraph, NEVO's subgraphs and FoodOn. rdflib loads the
same TACO and NEVO files in memory; FoodOn is left out, so label columns are not compared. Each query's rows
are compared as multisets over the columns that do not depend on labels.

    $env:PYTHONPATH = "src"; python verification/sparql_crosscheck.py
"""

from __future__ import annotations

import time
from collections import Counter

import requests
from rdflib import Graph

from taco_rdf.namespaces import BUILD_DIR, ROOT

ENDPOINT = "http://localhost:3030/nicefood/sparql"
NEVO = ROOT / "data" / "external" / "nice-food"
QUERIES = {
    # query file: the columns compared
    "cdno_coverage.rq": ["cdno", "table", "nutrients", "foods"],
    "one_taco_food.rq": ["food", "value", "unit"],
}


def number(text: str) -> str:
    """A number written the same way by both engines (1.0 and 1.00 are the same value)."""
    try:
        return repr(float(text))
    except ValueError:
        return text


def fuseki(query: str, columns: list[str]) -> Counter:
    r = requests.post(ENDPOINT, data={"query": query},
                      headers={"Accept": "application/sparql-results+json"}, timeout=900)
    r.raise_for_status()
    rows = r.json()["results"]["bindings"]
    return Counter(tuple(number(b[c]["value"]) if c in b else "" for c in columns) for b in rows)


def rdflib_rows(graph: Graph, query: str, columns: list[str]) -> Counter:
    rows = graph.query(query)
    return Counter(tuple(number(str(r[c])) if r[c] is not None else "" for c in columns) for r in rows)


def main() -> int:
    start = time.perf_counter()
    g = Graph()
    for path in (BUILD_DIR / "taco_nice_food.ttl", NEVO / "nevo21_graph.ttl", NEVO / "nevo23_graph.ttl"):
        g.parse(path, format="turtle")
    print(f"rdflib loaded {len(g)} triples in {time.perf_counter() - start:.0f} s\n")
    same = True
    for name, columns in QUERIES.items():
        query = (ROOT / "queries" / "nice-food" / name).read_text(encoding="utf-8")
        a = fuseki(query, columns)
        start = time.perf_counter()
        b = rdflib_rows(g, query, columns)
        agree = a == b
        same &= agree
        print(f"{name}: Fuseki {sum(a.values())} rows, rdflib {sum(b.values())} rows "
              f"({time.perf_counter() - start:.0f} s); same rows: {agree}")
        if not agree:
            print(f"  only Fuseki: {list((a - b).items())[:5]}")
            print(f"  only rdflib: {list((b - a).items())[:5]}")
    print(f"\nengines agree: {same}")
    return 0 if same else 1


if __name__ == "__main__":
    raise SystemExit(main())
