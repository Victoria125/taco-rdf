"""Record the FoodOn searches (EBI OLS) behind the verdicts in analysis/data."""

from __future__ import annotations

import csv
import datetime
import json
import sys
import tempfile
import time
import urllib.parse
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
TABLES = {
    "regional": HERE / "data" / "regional_protein_foods.csv",
    "preparation": HERE / "data" / "preparation_probes.csv",
}
OUTPUT = HERE / "data" / "foodon_lookup.csv"
OLS = "https://www.ebi.ac.uk/ols4/api/"
OBO = "http://purl.obolibrary.org/obo/"
SEARCH_LIMIT = 5
FIELDS = ["table", "name_pt", "query_en", "source", "rank", "curie", "label", "retrieved",
          "foodon_release", "status", "search_limit", "returned_count"]


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


def search(query: str, rows: int = SEARCH_LIMIT) -> list[tuple[str, str]]:
    docs = get("search", q=query, ontology="foodon", type="class", rows=rows)["response"]["docs"]
    return [(d.get("obo_id", "").replace(":", "_"), d.get("label", "")) for d in docs]


def label_of(curie: str) -> str:
    terms = get("ontologies/foodon/terms", iri=OBO + curie).get("_embedded", {}).get("terms", [])
    if not isinstance(terms, list):
        return ""
    for term in terms:
        if isinstance(term, dict):
            label = term.get("label")
            if isinstance(label, str):
                return label
    return ""


def lookup_rows(table: str, food: dict, retrieved: str, release: str) -> list[dict]:
    base = dict.fromkeys(FIELDS, "") | {
        "table": table, "name_pt": food["name_pt"], "query_en": food["query_en"],
        "retrieved": retrieved, "foodon_release": release,
    }
    hits = search(food["query_en"])
    query = base | {"source": "search", "search_limit": SEARCH_LIMIT, "returned_count": len(hits)}
    records = [query | {"rank": rank, "curie": curie, "label": label, "status": "found"}
               for rank, (curie, label) in enumerate(hits, 1)]
    if not hits:
        records.append(query | {"status": "no_results"})
    if food["foodon_class"]:
        label = label_of(food["foodon_class"])
        records.append(base | {"source": "recorded", "curie": food["foodon_class"], "label": label,
                               "status": "found" if label else "not_found"})
    return records


def foodon_release() -> str:
    config = get("ontologies/foodon")["config"]
    release = config.get("versionIri") or config.get("version")
    if not release:
        raise ValueError("OLS did not report a FoodOn release")
    return release


def main() -> int:
    release = foodon_release()
    retrieved = datetime.date.today().isoformat()
    records, looked_up, wrong = [], 0, 0
    for table, path in TABLES.items():
        with open(path, newline="", encoding="utf-8") as src:
            foods = list(csv.DictReader(src))
        for food in foods:
            found = lookup_rows(table, food, retrieved, release)
            records.extend(found)
            for record in found:
                if record["source"] == "recorded" and record["label"] != food["foodon_label"]:
                    wrong += 1
                    print(f"MISMATCH {record['curie']}: recorded {food['foodon_label']!r}, "
                          f"OLS {record['label']!r}")
            looked_up += 1
    if foodon_release() != release:
        raise ValueError("FoodOn changed during the lookup; the previous log was preserved")
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", newline="", encoding="utf-8", dir=OUTPUT.parent,
                                         prefix=OUTPUT.name, suffix=".tmp", delete=False) as fh:
            temporary = Path(fh.name)
            out = csv.DictWriter(fh, fieldnames=FIELDS, lineterminator="\n")
            out.writeheader()
            out.writerows(records)
        temporary.replace(OUTPUT)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    print(f"wrote {OUTPUT}: {looked_up} rows looked up, {wrong} recorded classes missing or relabelled",
          file=sys.stderr)
    return 1 if wrong else 0


if __name__ == "__main__":
    raise SystemExit(main())
