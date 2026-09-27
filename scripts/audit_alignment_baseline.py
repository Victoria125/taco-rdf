"""Measure mapping coverage and flag explicit preparation conflicts for review."""

from __future__ import annotations

import csv
import re
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
OUTPUT = ROOT / "analysis"


def read(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


def write(path: Path, fields: list[str], rows: list[dict[str, str | int]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def preparation_conflict(name: str, label: str) -> str:
    source = {part.strip().casefold() for part in name.split(",")}
    target = set(re.findall(r"\w+", label.casefold()))
    if "cru" in source and "cooked" in target:
        return "raw TACO name / cooked FoodOn label"
    if (source & {"cozido", "assado", "frito", "refogado", "grelhado"}) and "raw" in target:
        return "prepared TACO name / raw FoodOn label"
    if (source & {"cozido", "assado", "frito", "refogado", "grelhado"}) and not (
        target & {"cooked", "roasted", "roast", "fried", "sauteed", "sautéed", "grilled", "boiled", "baked"}
    ):
        return "preparation not explicit in FoodOn label"
    return ""


def audit(foods: list[dict[str, str]], groups: list[dict[str, str]],
          links: list[dict[str, str]]) -> tuple[list[dict[str, str | int]], list[dict[str, str]]]:
    group_names = {row["id"]: row["name"] for row in groups}
    by_food: dict[str, list[dict[str, str]]] = defaultdict(list)
    for link in links:
        if link["source_type"] == "food" and link["target_ontology"] == "FoodOn":
            by_food[link["source_key"]].append(link)
    unknown = set(by_food) - {food["id"] for food in foods}
    if unknown:
        raise ValueError(f"FoodOn alignments refer to absent TACO IDs: {sorted(unknown)}")
    counts: dict[str, Counter[str]] = defaultdict(Counter)
    conflicts: list[dict[str, str]] = []
    for food in foods:
        group = group_names[food["categoryId"]]
        matches = by_food[food["id"]]
        counts[group]["foods"] += 1
        if matches:
            counts[group]["linked_foods"] += 1
        for link in matches:
            counts[group][link["predicate"]] += 1
            reason = preparation_conflict(food["name"], link["target_label"])
            if reason:
                conflicts.append({
                    "food_number": food["id"], "name_pt": food["name"], "group": group,
                    "predicate": link["predicate"], "target_iri": link["target_iri"],
                    "target_label": link["target_label"], "screening_flag": reason,
                })
    fields = ["group", "foods", "linked_foods", "unlinked_foods", "coverage_percent",
              "type", "exactMatch", "closeMatch", "narrowMatch", "broadMatch", "relatedMatch"]
    rows: list[dict[str, str | int]] = []
    for group in [row["name"] for row in groups] + ["TOTAL"]:
        tally = (sum((counts[name] for name in counts), Counter())
                 if group == "TOTAL" else counts[group])
        total = tally["foods"]
        rows.append({
            "group": group, "foods": total, "linked_foods": tally["linked_foods"],
            "unlinked_foods": total - tally["linked_foods"],
            "coverage_percent": f"{100 * tally['linked_foods'] / total:.1f}" if total else "0.0",
            **{field: tally[field] for field in fields[5:]},
        })
    return rows, sorted(conflicts, key=lambda row: int(row["food_number"]))


def main() -> None:
    rows, conflicts = audit(read(DATA / "raw" / "food.csv"),
                            read(DATA / "raw" / "categories.csv"),
                            read(DATA / "alignment" / "alignments.csv"))
    OUTPUT.joinpath("data").mkdir(parents=True, exist_ok=True)
    write(OUTPUT / "data" / "alignment_baseline_by_group.csv", list(rows[0]), rows)
    write(OUTPUT / "data" / "preparation_conflicts.csv",
          ["food_number", "name_pt", "group", "predicate", "target_iri", "target_label",
           "screening_flag"], conflicts)
    total = rows[-1]
    flag_counts = Counter(row["screening_flag"] for row in conflicts)
    lines = [
        "# FoodOn alignment baseline", "",
        "This is a reproducible screening of the current CSV inputs, not a human assessment of mapping",
        "quality.",
        "Coverage counts foods with at least one FoodOn link. Relation columns count links, so their sum can",
        "exceed the number of linked foods. No precision, accuracy or cultural adequacy is inferred.", "",
        f"{total['linked_foods']} of {total['foods']} TACO foods have a FoodOn link "
        f"({total['coverage_percent']}%). {total['unlinked_foods']} have no link.", "",
        "| Group | Foods | Linked | Unlinked | Coverage |", "| --- | ---: | ---: | ---: | ---: |",
    ]
    lines += [f"| {row['group']} | {row['foods']} | {row['linked_foods']} | "
              f"{row['unlinked_foods']} | {row['coverage_percent']}% |" for row in rows]
    lines += [
        "", f"## Preparation screening ({len(conflicts)} flagged links)", "",
        "The screen checks only explicit Portuguese preparation terms against the English FoodOn label:",
        "`cru` versus `cooked`, and `cozido`, `assado`, `frito`, `refogado` or `grelhado` versus `raw`.",
        "It also flags a prepared TACO name when the target label lacks an explicit preparation term.",
        "A flag is a review priority, not a demonstrated mapping error. The target class definition,",
        "relationship (`relatedMatch` may describe a different preparation), and TACO context still matter.",
        "The screen misses many mismatches because it does not interpret synonyms or ontology definitions.",
        "The full flagged list is in `data/preparation_conflicts.csv`.", "",
        *[f"- {reason}: {count} links" for reason, count in sorted(flag_counts.items())], "",
        "The prepared round in `../data/alignment/review/round-1/` contains 86 randomly sampled foods",
        "plus targeted cases. Its two reviewer forms are empty. The scientific question about mapping",
        "correctness and loss of Brazilian food distinctions requires the independent reviews, adjudication",
        "and scoring described in `../docs/alignment-review.md`.", "",
        "Reproduce with `python scripts/audit_alignment_baseline.py` from the repository root.", "",
    ]
    (OUTPUT / "alignment_baseline.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"{total['linked_foods']}/{total['foods']} linked; {len(conflicts)} screening flags")


if __name__ == "__main__":
    main()
