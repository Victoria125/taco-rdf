"""Regenerate local aggregate reports after applying the confirmed review to Fuseki."""

from __future__ import annotations

import csv
import importlib.util
import json
from collections import Counter

from taco_rdf import sparql
from taco_rdf.namespaces import ROOT


def main():
    spec = importlib.util.spec_from_file_location("compare", ROOT / "scripts/compare_taco_nevo.py")
    compare = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(compare)
    endpoint = sparql.endpoint("taco_nevo")
    rows = [
        {"comparison": "same CDNO class", **r}
        for r in sparql.select(compare.SAME_CLASS.read_text(encoding="utf-8"), endpoint)
    ]
    compare.timed = lambda _graph, query, _bindings, _what: sparql.select(
        query.read_text(encoding="utf-8"), endpoint
    )
    rows += compare.available_carbohydrate_pairs(None, {})
    compare.OUT.parent.mkdir(parents=True, exist_ok=True)
    with compare.OUT.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=compare.FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    (ROOT / "analysis/taco_nevo_comparison.md").write_text(
        compare.report(rows, "the local Fuseki graph after the completed 597-food review", "2026-11-19"),
        encoding="utf-8",
    )
    print(compare.coverage(rows), flush=True)
    with (ROOT / "data/labels/food_names_en.csv").open(encoding="utf-8-sig") as stream:
        names = {r["name_en"] for r in csv.DictReader(stream)}
    protein = {}
    previous = None
    for name in ("protein_groups", "protein_groups_cdno"):
        result = sparql.select((ROOT / f"queries/nice-food/{name}.rq").read_text(encoding="utf-8"))
        counts = Counter((r["grouplabel"], "TACO" if r["foodname"] in names else "NEVO") for r in result)
        protein[name] = {f"{g}|{s}": n for (g, s), n in sorted(counts.items())}
        if previous is not None:
            assert sorted(tuple(sorted(r.items())) for r in result) == previous
        previous = sorted(tuple(sorted(r.items())) for r in result)
        print(name, protein[name], flush=True)
    out = ROOT / "build/verification/review_application/protein_queries.json"
    out.write_text(json.dumps(protein, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
