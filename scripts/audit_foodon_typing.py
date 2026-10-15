"""Export published FoodOn types and foods awaiting a defensible class assignment."""

from __future__ import annotations

import argparse
import csv
from collections import Counter, defaultdict
from pathlib import Path

from rdflib import RDF, RDFS, SKOS, Graph, URIRef

from taco_rdf.cli import build_graph
from taco_rdf.graph import (
    Alignment,
    ReviewedMapping,
    food_iri,
    foodon_typing_obstacle,
    load_alignments,
    load_reviewed_mappings,
)
from taco_rdf.namespaces import CORRECTIONS_DIR, RAW_XLS, ROOT
from taco_rdf.parse import Table, load_corrections, parse_workbook

FOODON = "http://purl.obolibrary.org/obo/FOODON_"
SKOS_MATCHES = (SKOS.exactMatch, SKOS.closeMatch, SKOS.broadMatch, SKOS.narrowMatch, SKOS.relatedMatch)
REVIEW_FIELDS = ["review_status", "review_round", "reviewers", "reviewed_on", "foodon_release"]
FOOD_FIELDS = ["food_number", "name_pt", "group_id", "group"]
TYPE_FIELDS = [*FOOD_FIELDS, "predicate", "target_iri", "target_label", "note", *REVIEW_FIELDS]
GAP_FIELDS = [*FOOD_FIELDS, "candidate_predicate", "candidate_iri", "candidate_label", "candidate_note",
              "candidate_obstacle", *REVIEW_FIELDS]
AXIOM_CONFLICT, ORGANISM_CLASS = "foodon_axiom_conflict", "organism_class"
Row = dict[str, str | int]


def _review_fields(review: ReviewedMapping | None) -> dict[str, str]:
    if review is None:
        return dict.fromkeys(REVIEW_FIELDS, "") | {"review_status": "pending_review"}
    status = ("reviewed_no_term" if not review.target_iri else
              "reviewed_type" if review.predicate == "type" else "reviewed_no_type")
    return {"review_status": status, "review_round": review.round.name,
            "reviewers": "; ".join(review.reviewers), "reviewed_on": review.reviewed_on,
            "foodon_release": review.round.foodon_release}


def _label(graph: Graph, target: URIRef) -> str:
    labels = list(graph.objects(target, RDFS.label))
    labels.sort(key=lambda value: (getattr(value, "language", None) != "en", str(value)))
    return str(labels[0]) if labels else ""


def audit(graph: Graph, table: Table, alignments: list[Alignment],
          reviewed: dict[int, ReviewedMapping]) -> tuple[list[Row], list[Row]]:
    """Count actual graph types; retain excluded candidate evidence without asserting it.

    Only scored review mappings are supplied through ``reviewed``. A reviewer form
    alone cannot change a published type or establish an ontology gap. Candidate
    obstacles are read from the FoodOn module the build parses into ``graph``.
    """
    candidates: dict[int, list[Alignment]] = defaultdict(list)
    for alignment in alignments:
        if alignment.source_type == "food" and alignment.target_iri.startswith(FOODON):
            candidates[int(alignment.source_key)].append(alignment)
    typed: list[Row] = []
    gaps: list[Row] = []
    for food in sorted(table.foods.values(), key=lambda value: value.id):
        subject = food_iri(food.id)
        for predicate in SKOS_MATCHES:
            if any(str(target).startswith(FOODON) for target in graph.objects(subject, predicate)):
                raise ValueError(f"food {food.id}: published SKOS mapping to FoodOn")
        types = sorted({target for target in graph.objects(subject, RDF.type)
                        if isinstance(target, URIRef) and str(target).startswith(FOODON)}, key=str)
        metadata: Row = {"food_number": food.id, "name_pt": food.name, "group_id": food.group_id,
                         "group": table.groups[food.group_id - 1],
                         **_review_fields(reviewed.get(food.id))}
        matches = sorted(candidates[food.id], key=lambda value: (value.predicate, value.target_iri))
        if types:
            for target in types:
                notes = [a.note for a in matches if a.predicate == "type" and a.target_iri == str(target)]
                typed.append(metadata | {"predicate": "rdf:type", "target_iri": str(target),
                                         "target_label": _label(graph, target), "note": " | ".join(notes)})
        else:
            gaps.append(metadata | _candidate_fields(graph, matches))
    return typed, gaps


def _candidate_fields(graph: Graph, matches: list[Alignment]) -> Row:
    """The retained candidates of an untyped food, and why the FoodOn module cannot back each one."""
    return {
        "candidate_predicate": " | ".join(a.predicate for a in matches),
        "candidate_iri": " | ".join(a.target_iri for a in matches),
        "candidate_label": " | ".join(a.target_label for a in matches),
        "candidate_note": " | ".join(a.note for a in matches),
        "candidate_obstacle": " | ".join(foodon_typing_obstacle(graph, URIRef(a.target_iri)) for a in matches),
    }


def write_csv(path: Path, fields: list[str], rows: list[Row]) -> None:
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def report(table: Table, typed: list[Row], gaps: list[Row]) -> str:
    typed_foods = {int(row["food_number"]) for row in typed}
    candidates = sum(bool(row["candidate_iri"]) for row in gaps)
    obstacles = {row["food_number"]: set(str(row["candidate_obstacle"]).split(" | ")) for row in gaps}
    conflicts = [food for food, found in obstacles.items() if AXIOM_CONFLICT in found]
    organisms = [food for food, found in obstacles.items() if found == {ORGANISM_CLASS}]
    total = len(table.foods)
    coverage = f"{100 * len(typed_foods) / total:.1f}" if total else "0.0"
    lines = [
        "# Published FoodOn typing and unresolved foods", "",
        f"{len(typed_foods)} of {total} TACO foods have a published FoodOn `rdf:type` ({coverage}%).",
        f"Published type assertions: {len(typed)}. Foods without a FoodOn type: {len(gaps)}.",
        f"Of the untyped foods, {candidates} retain historical candidates and "
        f"{len(gaps) - candidates} have no candidate recorded in the alignment inputs.", "",
        "These are coverage counts, not semantic accuracy estimates. Absence of a type does not prove",
        "that FoodOn lacks a suitable class. The gap CSV is a review queue; a confirmed ontology gap",
        "requires documented class search and review. A valid general class may be used even when",
        "FoodOn does not express the food's more specific preparation or cultural identity.", "",
        "## Candidates the FoodOn module cannot back", "",
        f"FoodOn axiom conflicts: {len(conflicts)} untyped foods "
        f"({', '.join(map(str, conflicts)) or 'none'}) have a food class candidate that FoodOn also places",
        "under whole organisms or plants. FoodOn has a class for them, but `rdf:type` would entail that",
        "the food is an organism, so the build withholds it. These are not ontology gaps; the conflicting",
        "axioms should be reported to FoodOn. NICE-Food's notebooks type food items without this check.", "",
        f"Organism classes only: {len(organisms)} untyped foods retain only a class of whole organisms or",
        "plants as candidate. A food class, possibly a more general one, still has to be searched for.", "",
        "## Reproducible exports", "",
        "- `data/foodon_types.csv`: FoodOn types asserted in the graph built from current inputs.",
        "- `data/foodon_typing_gaps.csv`: every food without a type, with historical candidate evidence.",
        "  Multiple candidates, if present, use ` | ` in corresponding candidate columns.",
        "  `candidate_obstacle` gives why the FoodOn module cannot back each candidate as a type",
        "  (`foodon_axiom_conflict`, `organism_class`, `missing_class`, `deprecated_class`), or is empty.", "",
        "The build checks class availability, organism ancestry and consistency with scored reviews before",
        "the audit runs. Historical food SKOS candidates are not counted as published mappings and are",
        "not automatically converted to `rdf:type`. Group and nutrient mappings are outside this report.", "",
        "## Review status", "",
        "Review metadata comes only from the latest scored round for each food. Incomplete rounds and",
        "individual reviewer proposals do not change these exports. `pending_review` means no scored",
        "decision is available; `reviewed_type` records an accepted type; `reviewed_no_type` records a",
        "historical non-type decision; `reviewed_no_term` records `sssom:NoTermFound` in a scored round.",
        "A historical non-type decision does not establish the absence of a defensible FoodOn type.", "",
        "| Status | Typed foods | Untyped foods |", "| --- | ---: | ---: |",
    ]
    type_status = Counter({row["food_number"]: row["review_status"] for row in typed}.values())
    gap_status = Counter(row["review_status"] for row in gaps)
    for status in sorted(type_status.keys() | gap_status.keys()):
        lines.append(f"| {status} | {type_status[status]} | {gap_status[status]} |")
    lines += ["", "## Coverage by TACO group", "",
              "| Group | Foods | Typed | Untyped |", "| --- | ---: | ---: | ---: |"]
    for group_id, group in enumerate(table.groups, start=1):
        foods = {food.id for food in table.foods.values() if food.group_id == group_id}
        count = len(foods & typed_foods)
        lines.append(f"| {group} | {len(foods)} | {count} | {len(foods) - count} |")
    lines += ["", "Reproduce with `python scripts/audit_foodon_typing.py` from the repository root.", ""]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "analysis")
    output = parser.parse_args().output
    graph = build_graph()
    table = parse_workbook(RAW_XLS, load_corrections(CORRECTIONS_DIR))
    typed, gaps = audit(graph, table, load_alignments(), load_reviewed_mappings())
    (output / "data").mkdir(parents=True, exist_ok=True)
    write_csv(output / "data" / "foodon_types.csv", TYPE_FIELDS, typed)
    write_csv(output / "data" / "foodon_typing_gaps.csv", GAP_FIELDS, gaps)
    (output / "foodon_typing.md").write_text(report(table, typed, gaps), encoding="utf-8", newline="\n")
    print(f"{len({r['food_number'] for r in typed})}/{len(table.foods)} foods typed; "
          f"{len(gaps)} without a FoodOn type")


if __name__ == "__main__":
    main()
