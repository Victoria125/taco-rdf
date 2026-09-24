from __future__ import annotations

import csv
import json
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

CSV_PATH = Path(__file__).resolve().parents[1] / "data" / "alignment" / "alignments.csv"
MODULE_PATH = Path(__file__).resolve().parents[1] / "ontology" / "imports" / "foodon-module.ttl"
OLS = "https://www.ebi.ac.uk/ols4/api/terms?"


def ols_label(iri: str, ontology: str) -> str | None:
    url = OLS + urllib.parse.urlencode({"iri": iri, "ontology": ontology.lower()})
    for attempt in range(4):
        try:
            with urllib.request.urlopen(url, timeout=60) as resp:
                terms = json.load(resp).get("_embedded", {}).get("terms", [])
            return terms[0]["label"] if terms else None
        except OSError:
            if attempt == 3:
                raise
            time.sleep(2 * (attempt + 1))
    return None


def pinned_foodon_labels() -> dict[str, str]:
    """Labels of the pinned FoodOn release, as extracted into the module (OLS may serve another release)."""
    from rdflib import RDFS, Graph

    module = Graph().parse(MODULE_PATH, format="turtle")
    return {str(s): str(o) for s, o in module.subject_objects(RDFS.label)}


def main() -> int:
    with open(CSV_PATH, newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    pinned = pinned_foodon_labels()
    cache: dict[tuple[str, str], str | None] = {}
    bad = 0
    for r in rows:
        key = (r["target_iri"], r["target_ontology"])
        if key not in cache:
            cache[key] = ols_label(*key)
        got = cache[key]
        where = f"{r['source_type']}:{r['source_key']} {r['target_iri']}"
        if got is not None and got.casefold() == r["target_label"].casefold():
            continue
        in_pinned_release = pinned.get(r["target_iri"]) == r["target_label"]
        if got is not None and r["target_ontology"] == "FoodOn" and in_pinned_release:
            print(f"NOTE {where}: {r['target_label']!r} as in the pinned FoodOn release, OLS says {got!r}")
            continue
        bad += 1
        print(f"MISMATCH {where}: expected {r['target_label']!r}, OLS says {got!r}")
    print(f"{len(rows) - bad}/{len(rows)} target IRIs exist in OLS with the recorded label "
          "(or, for FoodOn, the pinned release's label)")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
