# ruff: noqa: E501
"""Rebuild Fuseki's nicefood dataset from its files, and check that the rebuilt store answers as the old one did.

The nicefood dataset (triplestore/README.md) holds TACO's NICE-Food export, NICE-Food's NEVO graphs and the pinned
FoodOn release. A change made to the store by hand (an update, triples posted on their own) leaves a store that no
file describes. This script:

1. records the store as it is: its triples counted by property, and the rows that NICE-Food's protein queries, the
   competency questions and the shared-class query give (taco_rdf.nice_food_queries);
2. deletes the dataset with Fuseki's admin API; a database folder Fuseki leaves behind is renamed, not deleted,
   so the old store can be restored;
3. creates the dataset again, empties it if it is not empty, and loads build/taco_nice_food.ttl, the NEVO graphs
   and FoodOn with scripts/load_triplestore.py, as triplestore/README.md says;
4. records the new store and compares the two: the same triples by property and the same rows.

The records go to build/verification/, which is not committed: they hold NEVO rows.

    $env:PYTHONPATH = "src"; python scripts/rebuild_nicefood.py --fuseki-home C:/path/to/apache-jena-fuseki
"""

from __future__ import annotations

import argparse
import datetime
import json
import subprocess
import sys
from pathlib import Path

import requests  # Fuseki's admin API, to delete and create the dataset

from taco_rdf import sparql
from taco_rdf.namespaces import BUILD_DIR, ROOT
from taco_rdf.nice_food_queries import answers

FUSEKI = sparql.FUSEKI
DATASET = sparql.NICEFOOD
RECORDS = BUILD_DIR / "verification"


def count(endpoint: str, query: str) -> list[dict[str, str]]:
    return sparql.select(query, f"{endpoint}/sparql", timeout=3600)


def record(endpoint: str) -> dict:
    """The store's triples by property, its named graphs, and the rows of the queries."""
    by_property = {r["p"]: int(r["n"]) for r in count(endpoint, "SELECT ?p (COUNT(*) AS ?n) WHERE { ?s ?p ?o } "
                                                                "GROUP BY ?p")}
    named = int(count(endpoint, "SELECT (COUNT(*) AS ?n) WHERE { GRAPH ?g { ?s ?p ?o } }")[0]["n"])
    rows = answers(f"{endpoint}/sparql")
    return {"triples": sum(by_property.values()), "named graph triples": named, "by property": by_property,
            "rows": {k: [list(r) for r in v] for k, v in rows.items()}}


def compare(before: dict, after: dict) -> list[str]:
    out = []
    if before["triples"] != after["triples"]:
        out.append(f"triples: {before['triples']:,} before, {after['triples']:,} after")
    if before["named graph triples"] != after["named graph triples"]:
        out.append(f"named graph triples: {before['named graph triples']:,} before, "
                   f"{after['named graph triples']:,} after")
    for p in sorted(set(before["by property"]) | set(after["by property"])):
        a, b = before["by property"].get(p, 0), after["by property"].get(p, 0)
        if a != b:
            out.append(f"{p}: {a:,} triples before, {b:,} after")
    for k in sorted(set(before["rows"]) | set(after["rows"])):
        if sorted(map(tuple, before["rows"].get(k, []))) != sorted(map(tuple, after["rows"].get(k, []))):
            out.append(f"query {k}: {len(before['rows'].get(k, []))} rows before, "
                       f"{len(after['rows'].get(k, []))} after")
    return out


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--fuseki", default=FUSEKI, help=f"Fuseki's address (default {FUSEKI})")
    p.add_argument("--fuseki-home", type=Path, help="Fuseki's folder, to rename a database folder it leaves behind")
    args = p.parse_args()
    endpoint = f"{args.fuseki}/{DATASET}"
    RECORDS.mkdir(parents=True, exist_ok=True)
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")

    print("1. recording the store as it is", flush=True)
    before = record(endpoint)
    (RECORDS / f"nicefood_before_{stamp}.json").write_text(json.dumps(before), encoding="utf-8")
    print(f"   {before['triples']:,} triples, {len(before['by property']):,} properties", flush=True)

    print("2. deleting the dataset", flush=True)
    requests.delete(f"{args.fuseki}/$/datasets/{DATASET}", timeout=600).raise_for_status()
    if args.fuseki_home:
        folder = args.fuseki_home / "run" / "databases" / DATASET
        if folder.exists():
            kept = folder.with_name(f"{DATASET}.before-rebuild-{stamp}")
            try:
                folder.rename(kept)
                print(f"   the old database folder is kept as {kept}", flush=True)
            except OSError as e:  # Fuseki may still hold its files; step 3 then empties the dataset
                print(f"   could not rename the old database folder ({e}); it will be emptied", flush=True)

    print("3. creating it again and loading the files", flush=True)
    requests.post(f"{args.fuseki}/$/datasets", data={"dbName": DATASET, "dbType": "tdb2"},
                  timeout=600).raise_for_status()
    left = int(count(endpoint, "SELECT (COUNT(*) AS ?n) WHERE { ?s ?p ?o }")[0]["n"])
    if left:
        print(f"   the new dataset holds {left:,} triples; emptying it", flush=True)
        requests.post(f"{endpoint}/update", data={"update": "DROP ALL"}, timeout=3600).raise_for_status()
        left = int(count(endpoint, "SELECT (COUNT(*) AS ?n) WHERE { ?s ?p ?o }")[0]["n"])
    if left:
        print(f"the new dataset still holds {left:,} triples", file=sys.stderr)
        return 1
    print("   the new dataset is empty", flush=True)
    load = subprocess.run([sys.executable, str(ROOT / "scripts" / "load_triplestore.py"), "--endpoint", endpoint,
                           "--graph", str(BUILD_DIR / "taco_nice_food.ttl"), "--foodon"], cwd=ROOT)
    if load.returncode:
        return load.returncode

    print("4. recording the new store and comparing", flush=True)
    after = record(endpoint)
    (RECORDS / f"nicefood_after_{stamp}.json").write_text(json.dumps(after), encoding="utf-8")
    problems = compare(before, after)
    print(f"   {after['triples']:,} triples, {len(after['by property']):,} properties; "
          f"{len(after['rows'])} queries compared")
    for problem in problems:
        print(f"DIFFERS: {problem}")
    print("the rebuilt store is the same as the old one" if not problems else f"{len(problems)} differences")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
