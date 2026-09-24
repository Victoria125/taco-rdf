"""Prepare a round of alignment review: the item list, and one blank form for each of two reviewers."""

from __future__ import annotations

import argparse
import datetime
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

from rdflib import Graph, URIRef
from rdflib.namespace import PROV

from taco_rdf.evaluation import (
    ANSWER,
    CONTEXT,
    FoodOnIndex,
    foodon_index,
    form_rows,
    input_hashes,
    item_rows,
    load_problem_cases,
    review_hash,
    review_items,
    write_rows,
)
from taco_rdf.graph import load_alignments, load_food_names_en
from taco_rdf.namespaces import (
    ALIGNMENTS_CSV,
    CORRECTIONS_DIR,
    FOOD_NAMES_EN,
    FOODON_MODULE_TTL,
    RAW_XLS,
    ROOT,
)
from taco_rdf.parse import load_corrections, parse_workbook

PROBLEM_CASES = ROOT / "data" / "alignment" / "review" / "problem_cases.csv"
MODULE_IRI = URIRef("https://w3id.org/taco-rdf/imports/foodon-module")
OLS = "https://www.ebi.ac.uk/ols4/api/"


def get(path: str, **params) -> dict:
    url = OLS + path + "?" + urllib.parse.urlencode(params)
    for attempt in range(4):
        try:
            with urllib.request.urlopen(url, timeout=60) as resp:
                return json.load(resp)
        except OSError:
            if attempt == 3:
                raise
            time.sleep(2 * (attempt + 1))
    return {}


def definition(curie: str) -> str:
    terms = get("ontologies/foodon/terms", iri="http://purl.obolibrary.org/obo/" + curie)
    terms = terms.get("_embedded", {}).get("terms", [])
    return " ".join(terms[0].get("description") or []) if terms else ""


def search(query: str) -> list[tuple[str, str]]:
    docs = get("search", q=query, ontology="foodon", type="class", rows=6)["response"]["docs"]
    return [(d.get("obo_id", "").replace(":", "_"), d.get("label", "")) for d in docs]


def candidates(name_en: str, current: str, pinned: FoodOnIndex, wanted: int = 5) -> str:
    """Classes OLS finds for the English name, kept only if the pinned release has them, with its labels."""
    glosses = re.findall(r"\(([^)]*)\)", name_en)
    parts = [p.strip() for p in re.sub(r"\([^)]*\)", "", name_en).split(",") if p.strip()]
    queries = [" ".join(parts), *[f"{parts[0]} {g}" for g in glosses], " ".join(parts[:2]), parts[0]]
    found: dict[str, str] = {}
    for query in dict.fromkeys(queries):
        for curie, _ in search(query):
            if curie and curie != current and curie in pinned.labels:
                found.setdefault(curie, pinned.labels[curie])
        if len(found) >= wanted:
            break
    return "; ".join(f"{label} ({curie})" for curie, label in list(found.items())[:wanted])


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output", type=Path, default=ROOT / "data" / "alignment" / "review" / "round-1")
    p.add_argument("--per-stratum", type=int, default=2)
    p.add_argument("--seed", default="taco-review-v1")
    p.add_argument("--offline", action="store_true", help="skip the FoodOn definitions and candidates (OLS)")
    args = p.parse_args()
    if args.output.exists() and any(args.output.iterdir()):
        p.error(f"{args.output} is not empty; filled forms are never overwritten")

    hashes = input_hashes()
    table = parse_workbook(RAW_XLS, load_corrections(CORRECTIONS_DIR))
    alignments = load_alignments(ALIGNMENTS_CSV)
    names_en = load_food_names_en(FOOD_NAMES_EN)
    items = review_items(table, alignments, load_problem_cases(PROBLEM_CASES), seed=args.seed,
                         per_stratum=args.per_stratum)
    release = str(Graph().parse(FOODON_MODULE_TTL).value(MODULE_IRI, PROV.wasDerivedFrom))
    rows = form_rows(items, table, alignments, names_en, release)
    if not args.offline:
        pinned = foodon_index()
        lookup = {}
        for row in rows:
            current = row["current_class"]
            lookup[row["food_number"]] = (definition(current) if current else "",
                                          candidates(row["name_en"], current, pinned))
            print(f"{row['food_number']}: looked up", file=sys.stderr)
        rows = form_rows(items, table, alignments, names_en, release, lookup)

    if input_hashes() != hashes:
        p.error("review inputs changed during preparation; run the command again")
    args.output.mkdir(parents=True, exist_ok=True)
    write_rows(args.output / "items.csv", item_rows(items), list(item_rows(items[:1])[0]))
    write_rows(args.output / "context.csv", rows, CONTEXT)
    for reviewer in ("a", "b"):
        write_rows(args.output / f"reviewer-{reviewer}.csv", rows, CONTEXT + ANSWER)
    parts = {part: sum(i.part == part for i in items) for part in ("sample", "problem case", "prepared dish")}
    manifest = {
        "created": datetime.date.today().isoformat(), "seed": args.seed, "per_stratum": args.per_stratum,
        "items": len(items), "parts": parts, "foodon_release": release, "candidates": not args.offline,
        **hashes,
        "hash_format": "sha256-lf-v1",
        "context_sha256": review_hash(args.output / "context.csv"),
        "items_sha256": review_hash(args.output / "items.csv"),
        "protocol": "docs/alignment-review.md",
    }
    (args.output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
