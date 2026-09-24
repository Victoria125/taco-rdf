"""Check in FoodOn as published (EBI OLS) which classes of the legume foods are legume food products."""

from __future__ import annotations

import csv
import datetime
import json
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
FOODS = HERE / "data" / "legume_foods.csv"
ALIGNMENTS = ROOT / "data" / "alignment" / "alignments.csv"
OUTPUT = HERE / "data" / "foodon_ancestors.csv"
OLS = "https://www.ebi.ac.uk/ols4/api/ontologies/foodon/"
LEGUME = "http://purl.obolibrary.org/obo/FOODON_00001264"


def get(url: str) -> dict:
    for attempt in range(4):
        try:
            with urllib.request.urlopen(url, timeout=60) as resp:
                return json.load(resp)
        except OSError:
            if attempt == 3:
                raise
            time.sleep(2 * (attempt + 1))
    return {}


def ancestors(iri: str) -> list[str]:
    encoded = urllib.parse.quote(urllib.parse.quote(iri, safe=""), safe="")
    terms = get(f"{OLS}terms/{encoded}/ancestors?size=1000").get("_embedded", {}).get("terms", [])
    return [t["iri"] for t in terms]


def main() -> int:
    with open(FOODS, newline="", encoding="utf-8") as fh:
        foods = {r["food_number"] for r in csv.DictReader(fh)}
    with open(ALIGNMENTS, newline="", encoding="utf-8") as fh:
        classes = sorted({r["target_iri"] for r in csv.DictReader(fh)
                          if r["source_type"] == "food" and r["source_key"] in foods})
    config = get(OLS.rstrip("/"))["config"]
    retrieved = datetime.date.today().isoformat()
    release = config.get("versionIri") or config.get("version") or ""
    with open(OUTPUT, "w", newline="", encoding="utf-8") as fh:
        out = csv.writer(fh, lineterminator="\n")
        out.writerow(["class", "label", "legume_food_product", "ancestors", "retrieved", "foodon_release"])
        for iri in classes:
            terms = get(f"{OLS}terms?" + urllib.parse.urlencode({"iri": iri}))["_embedded"]["terms"]
            label = terms[0]["label"]
            found = ancestors(iri)
            out.writerow([iri.rsplit("/", 1)[1], label, "yes" if LEGUME in found else "no", len(found),
                          retrieved, release])
    print(f"wrote {OUTPUT}: {len(classes)} classes", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
