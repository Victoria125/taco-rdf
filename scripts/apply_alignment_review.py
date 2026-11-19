from __future__ import annotations

import argparse
import csv
import json
import os
import tempfile
from collections import Counter
from pathlib import Path

from rdflib import OWL, RDF, Graph

from taco_rdf.evaluation import foodon_index
from taco_rdf.graph import Alignment, ReviewedMapping, is_foodon_food_link, read_review_round
from taco_rdf.namespaces import ALIGNMENTS_CSV, FOODON_MODULE_TTL, OBO, ROOT
from taco_rdf.type_review import (
    AUDITS,
    check_hierarchy,
    csv_bytes,
    marker_for,
)
from taco_rdf.type_review import (
    validate as validate_type_review,
)

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


def _change(row: Row | None, mapping: ReviewedMapping) -> str:
    """What the reviewed mapping does to the food's row in alignments.csv, if the food has one."""
    if row is None:
        return "added" if mapping.target_iri else "unchanged"
    if not mapping.target_iri:
        return "removed"
    if (row["predicate"], row["target_iri"]) == (mapping.predicate, mapping.target_iri):
        return "unchanged"
    return "relation changed" if row["target_iri"] == mapping.target_iri else "class changed"


def apply(rows: list[Row], mappings: list[ReviewedMapping],
          labels: dict[str, str]) -> tuple[list[Row], Counter[str]]:
    by_food = {mapping.food: mapping for mapping in mappings}
    if len(by_food) != len(mappings):
        raise ValueError("review contains duplicate foods")
    previous: dict[int, list[Row]] = {n: [] for n in by_food}
    for row in rows:
        if is_foodon_food_link(Alignment(**row)) and int(row["source_key"]) in previous:
            previous[int(row["source_key"])].append(row)
    changes: Counter[str] = Counter()
    revised = {}
    for mapping in mappings:
        old = previous[mapping.food]
        change = _change(old[0] if old else None, mapping)
        if len(old) > 1 and change == "unchanged":
            change = "deduplicated"
        changes[change] += 1
        if mapping.target_iri:
            revised[mapping.food] = old[0] if change == "unchanged" else _revised_row(mapping, labels)
    result, seen = [], set()
    for row in rows:
        food = int(row["source_key"]) if is_foodon_food_link(Alignment(**row)) else None
        if food not in by_food:
            result.append(row)
        elif food not in seen:
            if food in revised:
                result.append(revised[food])
            seen.add(food)
    result.extend(row for food, row in revised.items() if food not in seen)
    return result, changes


def replace_bytes(path: Path, data: bytes) -> None:
    """Stage on the same filesystem, then replace atomically."""
    staged = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix=path.name + ".", delete=False) as stream:
            staged = Path(stream.name)
            stream.write(data)
        os.replace(staged, path)
    finally:
        if staged is not None and staged.exists():
            staged.unlink()


def apply_type_review(review: Path, alignments: Path, foodon: Path, *, applied_on: str,
                      reviewer_1: str, reviewer_2: str, root: Path = ROOT) -> Counter[str]:
    """Validate completely before any mutation, then activate the applied review."""
    checked = validate_type_review(review, root=root)
    for relative in AUDITS:
        if not (review / "baseline" / relative).is_file():
            raise ValueError(f"freeze the original review input before application: baseline/{relative}")
    check_hierarchy(checked, foodon)
    raw = alignments.read_bytes()
    with alignments.open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    # This temporary mapping uses the same conversion as graph.read_review_round, before activation.
    from taco_rdf.graph import ReviewRound

    provenance = ReviewRound(review.name, review / "reviewed-types.csv",
                             checked.manifest["inputs"][checked.manifest["protocol"]],
                             checked.foodon["release"], checked.manifest["protocol"])
    mappings = [ReviewedMapping(n, "" if row["decision"] == "none" else "type",
                "" if row["decision"] == "none" else str(OBO) + row["decision"],
                (), checked.receipt["processed_on"], provenance) for n, row in sorted(checked.rows.items())]
    result, changes = apply(rows, mappings, checked.labels)
    data = csv_bytes(result, FIELDS, "\r\n" if b"\r\n" in raw else "\n")
    marker = marker_for(checked, review, applied_on=applied_on, reviewer_1=reviewer_1,
                        reviewer_2=reviewer_2, alignments_data=data)
    marker_path = review / "application.json"
    if checked.application is not None:
        if (checked.application["reviewers"] != marker["reviewers"]
                or checked.application["decision_recorded_on"] != marker["decision_recorded_on"]):
            raise ValueError("cannot change the attribution of an already applied review")
        marker = checked.application  # idempotent reruns preserve the original application record.
    if data == raw and marker_path.is_file():
        return changes
    replace_bytes(alignments, data)
    try:
        if not marker_path.is_file():
            content = (json.dumps(marker, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
            replace_bytes(marker_path, content)
    except OSError:
        replace_bytes(alignments, raw)
        raise
    return changes


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("review", type=Path, help="a scored round, e.g. data/alignment/review/round-1")
    p.add_argument("--alignments", type=Path, default=ALIGNMENTS_CSV)
    p.add_argument("--foodon", type=Path, help="hash-pinned full FoodOn OWL; required for protocol 3")
    p.add_argument("--applied-on", help="application date YYYY-MM-DD; required for protocol 3")
    p.add_argument("--reviewer-1", help="name of the first independent reviewer")
    p.add_argument("--reviewer-2", help="name of the second independent reviewer")
    args = p.parse_args()
    review, alignments = args.review, args.alignments
    manifest = json.loads((review / "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("protocol_version") == 3:
        if not all((args.foodon, args.applied_on, args.reviewer_1, args.reviewer_2)):
            p.error("protocol 3 requires --foodon, --applied-on, --reviewer-1 and --reviewer-2")
        try:
            changes = apply_type_review(review, alignments, args.foodon, applied_on=args.applied_on,
                                        reviewer_1=args.reviewer_1, reviewer_2=args.reviewer_2)
        except (ValueError, OSError) as error:
            p.error(str(error))
        print(f"{review.name}: " + ", ".join(f"{n} {what}" for what, n in sorted(changes.items())))
        return 0
    if not (review / "reviewed.sssom.tsv").is_file():
        p.error(f"{review} has no reviewed.sssom.tsv; score the round first")
    mappings = read_review_round(review)
    pinned = foodon_index()
    if mappings and mappings[0].round.foodon_release != pinned.release:
        p.error(f"the round was reviewed against {mappings[0].round.foodon_release}, "
                f"not the pinned release {pinned.release}")

    raw = alignments.read_bytes()
    with open(alignments, newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    rows, changes = apply(rows, mappings, pinned.labels)
    with open(alignments, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=FIELDS, lineterminator="\r\n" if b"\r\n" in raw else "\n")
        writer.writeheader()
        writer.writerows(rows)
    print(f"{review.name}: " + ", ".join(f"{n} {what}" for what, n in sorted(changes.items())))

    module = {str(c) for c in Graph().parse(FOODON_MODULE_TTL).subjects(RDF.type, OWL.Class)}
    absent = sorted({m.target_iri for m in mappings
                     if m.predicate == "type" and m.target_iri and m.target_iri not in module})
    if absent:
        print(f"{len(absent)} classes are not yet in {FOODON_MODULE_TTL.name}; "
              "run scripts/extract_foodon_module.py before building")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
