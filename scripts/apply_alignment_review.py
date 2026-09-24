from __future__ import annotations

import argparse
import csv
from collections import Counter
from pathlib import Path

from rdflib import OWL, RDF, Graph

from taco_rdf.evaluation import foodon_index
from taco_rdf.graph import ReviewedMapping, read_review_round
from taco_rdf.namespaces import ALIGNMENTS_CSV, FOODON_MODULE_TTL

FIELDS = [
    "source_type",
    "source_key",
    "predicate",
    "target_iri",
    "target_label",
    "target_ontology",
    "note"
    ]


Row = dict[str, str]


def _row_for_food(rows: list[Row], index: dict[int, int], food: int) -> tuple[int | None, Row | None]:
    at = index.get(food)
    return at, rows[at] if at is not None else None


def _revised_row(mapping: ReviewedMapping, labels: dict[str, str]) -> Row:
    curie = mapping.target_iri.rsplit("/", 1)[-1]
    return {
        "source_type": "food",
        "source_key": str(mapping.food),
        "predicate": mapping.predicate,
        "target_iri": mapping.target_iri,
        "target_label": labels[curie],
        "target_ontology": "FoodOn",
        "note": f"Revised by review {mapping.round.name}.",
    }


def apply(rows: list[Row], mappings: list[ReviewedMapping], labels: dict[str, str]) -> tuple[list[Row], Counter[str]]:
    index = {int(r["source_key"]): i for i, r in enumerate(rows) if r["source_type"] == "food"}
    rows = list(rows)
    changes: Counter[str] = Counter()
    removed: set[int] = set()

    for mapping in mappings:
        at, row = _row_for_food(rows, index, mapping.food)

        if not mapping.target_iri:
            changes["removed" if row else "unchanged"] += 1
            if row:
                removed.add(at)
            continue

        if row and (row["predicate"], row["target_iri"]) == (mapping.predicate, mapping.target_iri):
            changes["unchanged"] += 1
            continue

        if row is None:
            changes["added"] += 1
            rows.append(_revised_row(mapping, labels))
            continue

        change = "relation changed" if row["target_iri"] == mapping.target_iri else "class changed"
        changes[change] += 1
        rows[at] = _revised_row(mapping, labels)

    return [r for i, r in enumerate(rows) if i not in removed], changes


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("review", type=Path, help="a scored round, e.g. data/alignment/review/round-1")
    p.add_argument("--alignments", type=Path, default=ALIGNMENTS_CSV)
    args = p.parse_args()
    if not (args.review / "reviewed.sssom.tsv").is_file():
        p.error(f"{args.review} has no reviewed.sssom.tsv; score the round first")
    mappings = read_review_round(args.review)
    pinned = foodon_index()
    if mappings and mappings[0].round.foodon_release != pinned.release:
        p.error(f"the round was reviewed against {mappings[0].round.foodon_release}, "
                f"not the pinned release {pinned.release}")

    raw = args.alignments.read_bytes()
    with open(args.alignments, newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    rows, changes = apply(rows, mappings, pinned.labels)
    with open(args.alignments, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=FIELDS, lineterminator="\r\n" if b"\r\n" in raw else "\n")
        writer.writeheader()
        writer.writerows(rows)
    print(f"{args.review.name}: " + ", ".join(f"{n} {what}" for what, n in sorted(changes.items())))

    module = {str(c) for c in Graph().parse(FOODON_MODULE_TTL).subjects(RDF.type, OWL.Class)}
    absent = sorted({m.target_iri for m in mappings if m.target_iri and m.target_iri not in module})
    if absent:
        print(f"{len(absent)} classes are not yet in {FOODON_MODULE_TTL.name}; "
              "run scripts/extract_foodon_module.py before building")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
