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

from taco_rdf import sparql
from taco_rdf.nice_food_queries import NEVO, PREFIXES, QUESTIONS, SHARED, TACO, richest

__all__ = ["NEVO", "PREFIXES", "QUESTIONS", "SHARED", "TACO", "ask", "richest"]
ENDPOINT = sparql.endpoint()


def ask(endpoint: str, query: str) -> list[dict[str, str]]:
    return sparql.select(query, endpoint, timeout=600)


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
