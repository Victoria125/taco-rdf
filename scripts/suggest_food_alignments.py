from __future__ import annotations

import csv
import json
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

OLS = "https://www.ebi.ac.uk/ols4/api/search?"


def ols_search(query: str, ontology: str = "foodon", rows: int = 6) -> list[dict]:
    url = OLS + urllib.parse.urlencode({"q": query, "ontology": ontology, "rows": rows})
    for attempt in range(4):
        try:
            with urllib.request.urlopen(url, timeout=60) as resp:
                docs = json.load(resp).get("response", {}).get("docs", [])
            return [{"label": d.get("label", ""), "iri": d.get("iri", ""),
                      "short_form": d.get("short_form", "")} for d in docs]
        except OSError:
            if attempt == 3:
                raise
            time.sleep(2 * (attempt + 1))
    return []


def main() -> int:
    in_path = Path(sys.argv[1])
    out_path = Path(sys.argv[2])
    with open(in_path, newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))

    with open(out_path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["food_id", "name_pt", "gloss_en", "rank", "label", "iri"])
        for r in rows:
            candidates = ols_search(r["gloss_en"])
            if not candidates:
                w.writerow([r["food_id"], r["name_pt"], r["gloss_en"], 0, "(no result)", ""])
                continue
            for i, c in enumerate(candidates, 1):
                w.writerow([r["food_id"], r["name_pt"], r["gloss_en"], i, c["label"], c["iri"]])
            print(f"{r['food_id']}\t{r['name_pt']}: {len(candidates)} candidate(s)", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
