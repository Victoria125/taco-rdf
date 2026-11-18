"""Prepare round 2 of the alignment review: FoodOn types for the TACO foods that have none (protocol 2).

Round 2 covers the foods without a FoodOn type that round 1 did not sample (docs/alignment-review-v2.md). The
first reviewer's form holds all of them; the second reviewer's holds a sample, allocated to TACO's food groups
in proportion to their size (largest remainders) and drawn within each group with a recorded seed. Each row
lists the candidates of scripts/taco_foodon_candidates.py that the build could publish, with their FoodOn
labels and the sources that proposed them, and no NEVO food name.

    $env:PYTHONPATH = "src"; python scripts/prepare_type_review.py
"""

from __future__ import annotations

import argparse
import csv
import datetime
import json
import random
import sys
from fractions import Fraction
from pathlib import Path

from taco_rdf.evaluation import review_hash
from taco_rdf.namespaces import BUILD_DIR, ROOT

SHEET = BUILD_DIR / "taco" / "foodon_round2" / "candidates.csv"
OUT = ROOT / "data" / "alignment" / "review" / "round-2"
PROTOCOL = ROOT / "docs" / "alignment-review-v2.md"
CLASSES = ROOT / "ontology" / "imports" / "foodon-classes.tsv"
ROUND_1 = ROOT / "data" / "alignment" / "review" / "round-1" / "items.csv"
INPUTS = [ROOT / "analysis" / "data" / "foodon_typing_gaps.csv",
          ROOT / "data" / "labels" / "food_names_en.csv", CLASSES, ROUND_1, PROTOCOL]
SOURCES = {"history": "history", "name": "name", "taco_neighbour": "TACO neighbour",
           "nevo_neighbour1": "NEVO neighbour", "nevo_neighbour2": "NEVO neighbour",
           "ols1": "OLS", "ols2": "OLS", "ols3": "OLS"}
CONTEXT = ["food_number", "name_pt", "name_en", "group", "candidates"]
ANSWERS = ["decision", "justification", "searched_terms", "unsure"]


def allocate(sizes: dict[str, int], n: int) -> dict[str, int]:
    """n seats over groups in proportion to their sizes: each its whole quota, then one more to the largest
    remainders (ties by group name)."""
    total = sum(sizes.values())
    if not 0 <= n <= total:
        raise ValueError(f"cannot sample {n} of {total}")
    quotas = {g: Fraction(n * s, total) for g, s in sizes.items()}
    seats = {g: int(q) for g, q in quotas.items()}
    left = n - sum(seats.values())
    for g in sorted(quotas, key=lambda g: (-(quotas[g] - seats[g]), g))[:left]:
        seats[g] += 1
    return seats


def draw(groups: dict[str, list[int]], n: int, seed: int) -> set[int]:
    """The sample: allocate(n) foods from each group, drawn with random.Random(seed) in group order."""
    rng = random.Random(seed)
    seats = allocate({g: len(f) for g, f in groups.items()}, n)
    return {food for g in sorted(groups) for food in rng.sample(sorted(groups[g]), seats[g])}


def candidates(row: dict[str, str], labels: dict[str, str]) -> str:
    """The usable classes of a sheet row, each with its FoodOn label and the sources that proposed it."""
    def proposed(key: str) -> set[str]:
        return {x.strip() for x in row.get(f"{key}_class", "").replace("|", ";").split(";")}

    out = []
    for c in [c.strip() for c in row["usable_classes"].split(";") if c.strip()]:
        found = sorted({name for key, name in SOURCES.items() if c in proposed(key)})
        out.append(f"{c} {labels.get(c, '')} [{', '.join(found)}]")
    return " | ".join(out)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--sheet", type=Path, default=SHEET,
                   help="candidates from scripts/taco_foodon_candidates.py")
    p.add_argument("--out", type=Path, default=OUT)
    p.add_argument("--sample", type=int, default=60, help="foods for the second reviewer (default 60)")
    p.add_argument("--seed", type=int, default=20261117)
    p.add_argument("--force", action="store_true", help="overwrite forms that already hold answers")
    args = p.parse_args()
    for form in ("reviewer-1.csv", "reviewer-2.csv"):
        path = args.out / form
        if path.is_file() and not args.force:
            with path.open(encoding="utf-8") as fh:
                if any(r.get("decision") for r in csv.DictReader(fh)):
                    print(f"{path} already holds answers; use --force to overwrite", file=sys.stderr)
                    return 1
    with CLASSES.open(encoding="utf-8") as fh:
        labels = dict(line.rstrip("\n").split("\t", 1) for line in fh if line.startswith("FOODON_"))
    with args.sheet.open(encoding="utf-8-sig") as fh:
        rows = [r for r in csv.DictReader(fh, delimiter=";") if r["in_round_1"] == "False"]
    groups: dict[str, list[int]] = {}
    for r in rows:
        groups.setdefault(r["group"], []).append(int(r["food_number"]))
    sample = draw(groups, args.sample, args.seed)
    args.out.mkdir(parents=True, exist_ok=True)
    items = [{"food_number": r["food_number"], "group": r["group"],
              "in_sample": str(int(r["food_number"]) in sample)} for r in rows]
    forms = [{"food_number": r["food_number"], "name_pt": r["name_pt"], "name_en": r["name_en"],
              "group": r["group"], "candidates": candidates(r, labels)} | dict.fromkeys(ANSWERS, "")
             for r in rows]
    context = [{k: f[k] for k in CONTEXT} for f in forms]
    for name, data in (("items.csv", items), ("context.csv", context), ("reviewer-1.csv", forms),
                       ("reviewer-2.csv", [f for f in forms if int(f["food_number"]) in sample])):
        with (args.out / name).open("w", encoding="utf-8", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(data[0]), lineterminator="\r\n")
            w.writeheader()
            w.writerows(data)
    allocation = allocate({g: len(f) for g, f in groups.items()}, args.sample)
    inputs = {str(path.relative_to(ROOT)).replace("\\", "/"): review_hash(path) for path in INPUTS}
    manifest = {"round": 2, "protocol": "docs/alignment-review-v2.md", "protocol_version": 2,
                "hash_format": "sha256-lf-v1", "created": datetime.date.today().isoformat(),
                "foodon_release": "2026-09-20", "foods": len(rows), "sample_size": len(sample),
                "seed": args.seed, "allocation": allocation,
                "excluded": "foods without a FoodOn type that round 1 sampled", "inputs": inputs,
                "context_sha256": review_hash(args.out / "context.csv"),
                "items_sha256": review_hash(args.out / "items.csv"),
                "candidates_sha256": review_hash(args.sheet)}
    (args.out / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
                                            encoding="utf-8")
    print(f"round 2: {len(rows)} foods for reviewer 1, {len(sample)} for reviewer 2 (seed {args.seed}); "
          f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
