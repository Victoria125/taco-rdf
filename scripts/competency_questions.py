"""Questions only a knowledge graph of both tables can answer, asked of TACO and NEVO together in NICE-Food.

Each question names a kind of food by a FoodOn class and a nutrient by a CDNO class, the classes both tables
use. The answer lists, for Brazil (TACO) and the Netherlands (NEVO), the foods richest in the nutrient among
the foods typed with that class or any class under it. A last question counts the FoodOn types that foods of
both tables share. Where a table gives a food two values of one CDNO class (NEVO's total and animal protein,
for instance), the larger is taken.

In ontology work these are competency questions: what the graph must be able to answer. The queries run on
Fuseki's nicefood dataset (triplestore/README.md), in parallel.

    $env:PYTHONPATH = "src"; python scripts/competency_questions.py
"""

from __future__ import annotations

import argparse
import sys
from concurrent.futures import ThreadPoolExecutor

import requests

ENDPOINT = "http://localhost:3030/nicefood/sparql"
TACO = "https://nepa.unicamp.br/tabela-brasileira-de-composicao-de-alimentos-4a-edicao/"
NEVO = "https://www.rivm.nl/nederlands-voedingsstoffenbestand"
PREFIXES = """PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
PREFIX fio: <http://www.foodvoc.org/resource/fio#>
PREFIX om: <http://www.ontology-of-units-of-measure.org/resource/om-2/>
PREFIX dcterms: <http://purl.org/dc/terms/>
PREFIX obo: <http://purl.obolibrary.org/obo/>
"""
# (question, FoodOn class of the kind of food, CDNO class of the nutrient)
QUESTIONS = [
    ("Which fruits have the most vitamin C?", "FOODON_00001057", "CDNO_0200192"),
    ("Which legumes have the most iron?", "FOODON_00001264", "CDNO_0200651"),
    ("Which dairy foods have the most calcium?", "FOODON_00001256", "CDNO_0200544"),
    ("Which nuts have the most magnesium?", "FOODON_00001172", "CDNO_0200570"),
]


def richest(kind: str, nutrient: str) -> str:
    """The foods of a kind with their largest value of a nutrient, by table, richest first."""
    return PREFIXES + f"""SELECT ?source ?name (MAX(?value) AS ?amount) (SAMPLE(?u) AS ?unit) WHERE {{
  ?type rdfs:subClassOf* obo:{kind} .
  ?food rdf:type fio:FoodItem ; rdf:type ?type ; dcterms:isVersionOf ?source ; skos:prefLabel ?name .
  FILTER (LANG(?name) = "en")
  ?food fio:hasNutritionalValue ?v . ?v rdf:type obo:{nutrient} ; om:hasValue ?m .
  ?m om:hasNumericalValue ?value .
  OPTIONAL {{ ?m om:hasUnit ?u FILTER isLiteral(?u) }}
}} GROUP BY ?source ?name ORDER BY ?source DESC(?amount) ?name
"""


SHARED = PREFIXES + f"""SELECT ?label (COUNT(DISTINCT ?t) AS ?taco) (COUNT(DISTINCT ?n) AS ?nevo) WHERE {{
  ?t rdf:type fio:FoodItem ; rdf:type ?type ; dcterms:isVersionOf <{TACO}> .
  ?n rdf:type fio:FoodItem ; rdf:type ?type ; dcterms:isVersionOf <{NEVO}> .
  FILTER STRSTARTS(STR(?type), "http://purl.obolibrary.org/obo/FOODON_")
  ?type rdfs:label ?label .
}} GROUP BY ?label ORDER BY DESC(?taco + ?nevo) ?label
"""


def ask(endpoint: str, query: str) -> list[dict[str, str]]:
    r = requests.post(endpoint, data={"query": query}, headers={"Accept": "application/sparql-results+json"},
                      timeout=600)
    r.raise_for_status()
    return [{k: v["value"] for k, v in b.items()} for b in r.json()["results"]["bindings"]]


def top(rows: list[dict[str, str]], source: str, n: int) -> list[dict[str, str]]:
    return [r for r in rows if r["source"] == source][:n]


def amount(value: str) -> str:
    """A value for reading: whole from 10 up, one decimal below."""
    x = float(value)
    return f"{x:.0f}" if x >= 10 else f"{x:.1f}"


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--endpoint", default=ENDPOINT)
    p.add_argument("--top", type=int, default=3, help="foods per country (default 3)")
    p.add_argument("--exclude", nargs="*", default=[],
                   help="words whose shared FoodOn types are left out of the examples")
    args = p.parse_args()
    queries = [richest(kind, nutrient) for _, kind, nutrient in QUESTIONS] + [SHARED]
    with ThreadPoolExecutor(len(queries)) as pool:
        answers = list(pool.map(lambda q: ask(args.endpoint, q), queries))
    for i, ((question, _, _), rows) in enumerate(zip(QUESTIONS, answers, strict=False), start=1):
        print(f"\n{i}. {question}")
        for source, country in ((TACO, "Brazil"), (NEVO, "The Netherlands")):
            found = "; ".join(f"{r['name']} {amount(r['amount'])} {r.get('unit', '')}".rstrip()
                              for r in top(rows, source, args.top))
            print(f"   {country:16} {found}")
    shared = answers[-1]
    examples = [r["label"] for r in shared if not any(w.lower() in r["label"].lower() for w in args.exclude)]
    print(f"\n{len(QUESTIONS) + 1}. How many kinds of food do Brazil and the Netherlands share?")
    print(f"   {len(shared)} FoodOn types, holding {sum(int(r['taco']) for r in shared)} TACO foods and "
          f"{sum(int(r['nevo']) for r in shared)} NEVO foods; for example " + ", ".join(examples[:5]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
