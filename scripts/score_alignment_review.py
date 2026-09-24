"""Check a round of alignment review, then report agreement, coverage, review results and errors."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from taco_rdf.evaluation import (
    ADJUDICATION,
    Answer,
    Item,
    adjudication_rows,
    compare,
    coverage,
    final_answers,
    outcome,
    read_answers,
    read_rows,
    sssom_rows,
    summarise,
    validate_round,
    write_rows,
    write_sssom,
)
from taco_rdf.graph import load_alignments
from taco_rdf.namespaces import ALIGNMENTS_CSV, CORRECTIONS_DIR, RAW_XLS
from taco_rdf.parse import load_corrections, parse_workbook

OUTCOMES = ["correct", "wrong relation", "wrong class", "should not be mapped", "class missed",
            "correctly unmapped", "unsure"]
JUDGED = ("correct", "wrong relation", "wrong class", "should not be mapped")
PARTS = ["sample", "problem case", "prepared dish"]
RESULT_FIELDS = ["food_number", "part", "outcome", "decision", "relation", "class", "certainty",
                 "justification", "evidence", "a_evidence", "b_evidence", "reviewer", "reviewed_on",
                 "foodon_release"]


def load_items(path: Path) -> list[Item]:
    return [Item(int(r["food_number"]), r["part"], r["stratum"], int(r["stratum_size"]),
                 int(r["sample_size"]), r["flag"]) for r in read_rows(path)]


def table_md(header: list[str], rows: list[list]) -> list[str]:
    lines = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    return lines + ["| " + " | ".join(str(c) for c in row) + " |" for row in rows]


def report(name: str, manifest: dict, table, alignments, items: list[Item], a: dict[int, Answer],
           b: dict[int, Answer], agreement, final: dict[int, Answer]) -> str:
    summary = summarise(items, final)
    reviewers = sorted({x.reviewer for x in a.values()} | {x.reviewer for x in b.values()})
    dates = sorted(x.reviewed_on for x in final.values())
    cover = coverage(table, alignments)
    linked = sum(n for link, n in cover.items() if link != "none")
    sample = summary["parts"].get("sample", Counter())
    judged = sum(sample.get(o, 0) for o in JUDGED)

    lines = [
        f"# Alignment review, {name}", "",
        f"FoodOn release: {manifest['foodon_release']}. Reviewers: {', '.join(reviewers)}. "
        f"Reviewed {dates[0]} to {dates[-1]}. Protocol: {manifest['protocol']}.", "",
        "This is a dual review of existing mappings. Reviewers work independently of each other but see "
        "the original mappings and candidates. Anchoring bias remains possible; agreement does not "
        "establish an independent gold standard.", "",
        "## Agreement before adjudication", "",
        f"{len(final)} foods. The two reviewers agreed on {len(agreement.agreed)} "
        f"({agreement.share:.0%}); Cohen's kappa on the decision is {agreement.kappa_text}. "
        f"{len(agreement.disagreed)} disagreements were resolved by adjudication.", "",
        *(["Kappa is not estimable when there are no paired decisions or both reviewers use only "
           "the same category; the observed agreement is reported separately.", ""]
          if agreement.kappa is None else []),
        f"## Coverage of the whole alignment ({len(table.foods)} foods)", "",
        *table_md(["link", "foods"], [[link, n] for link, n in cover.most_common()]), "",
        "Coverage counts the foods that have a link. It says nothing about whether the links are right.", "",
        "## Review results by part", "",
    ]
    rows = []
    for part in PARTS:
        counts = summary["parts"].get(part, Counter())
        rows.append([part, sum(counts.values()), *[counts.get(o, 0) for o in OUTCOMES]])
    lines += table_md(["part", "reviewed", *OUTCOMES], rows)
    lines += [
        "", "Only the sample was drawn at random. Problem cases and prepared dishes were chosen on purpose, "
        "so their results say nothing about the rest of the alignment.", "",
        "## The random sample", "",
        f"{sample.get('correct', 0)} of the {judged} linked foods in the sample were judged correct "
        f"({sample.get('unsure', 0)} unsure). The sample has {sum(sample.values())} foods, "
        f"{manifest['per_stratum']} per group and link; it is a diagnostic sample, not an estimate of the "
        f"precision of the {linked} links.", "",
    ]
    groups = dict(enumerate(table.groups, 1))
    stratum_rows = []
    for stratum, counts in sorted(summary["strata"].items(), key=lambda kv: int(kv[0].split("/")[0])):
        group, link = stratum.split("/")
        stratum_rows.append([groups[int(group)], link, *[counts.get(o, 0) for o in OUTCOMES]])
    lines += table_md(["group", "link", *OUTCOMES], stratum_rows)

    links = {int(x.source_key): x for x in alignments if x.source_type == "food"}
    error_rows = []
    for e in summary["errors"]:
        link = links.get(e.food_number)
        current = f"{link.predicate} {link.target_label}" if link else "none"
        proposed = {"relation": f"{e.relation} (same class)", "class": f"{e.relation} {e.target}",
                    "none": "no FoodOn class"}.get(e.decision, "")
        error_rows.append([e.food_number, table.foods[e.food_number].name, current, outcome(e), proposed,
                           e.certainty, e.justification])
    lines += ["", f"## Errors found ({len(error_rows)})", ""]
    lines += table_md(["food", "name", "current", "finding", "proposed", "certainty", "justification"],
                      error_rows)
    lines += ["", "This report does not change data/alignment/alignments.csv.", ""]
    return "\n".join(lines)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("review", type=Path, help="the round's folder, e.g. data/alignment/review/round-1")
    folder = p.parse_args().review
    try:
        manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
        context = validate_round(folder, manifest)
        items = load_items(folder / "items.csv")
        a = read_answers(folder / "reviewer-a.csv", context)
        b = read_answers(folder / "reviewer-b.csv", context)
    except (OSError, KeyError, ValueError) as exc:
        print(exc)
        return 1
    if set(a) != {i.food_number for i in items}:
        p.error("reviewer-a.csv does not cover the items of this round")
    if {x.reviewer for x in a.values()} & {x.reviewer for x in b.values()}:
        p.error("the two forms must come from different reviewers")
    agreement = compare(a, b)
    adjudication = folder / "adjudication.csv"
    expected_adjudication = adjudication_rows(context, a, b, agreement.disagreed)
    if not adjudication.exists():
        write_rows(adjudication, expected_adjudication, ADJUDICATION)
        print(f"agreement {agreement.share:.0%}, kappa {agreement.kappa_text}; "
              f"{len(agreement.disagreed)} disagreements written to {adjudication}")
        if agreement.disagreed:
            print("resolve them together in that file, then run this script again")
            return 0
    try:
        adjudicated = read_answers(adjudication, expected_adjudication)
        final = final_answers(a, b, agreement, adjudicated)
    except (OSError, KeyError, ValueError) as exc:
        print(exc)
        return 1
    table = parse_workbook(RAW_XLS, load_corrections(CORRECTIONS_DIR))
    alignments = load_alignments(ALIGNMENTS_CSV)
    try:
        validate_round(folder, manifest)
        mappings = sssom_rows(final, table, alignments)
    except (OSError, KeyError, ValueError) as exc:
        print(exc)
        return 1
    text = report(folder.name, manifest, table, alignments, items, a, b, agreement, final)
    (folder / "results.md").write_text(text, encoding="utf-8")
    parts = {i.food_number: i.part for i in items}
    results = [{"food_number": f, "part": parts[f], "outcome": outcome(x), "decision": x.decision,
                "relation": x.relation, "class": x.target, "certainty": x.certainty,
                "justification": x.justification, "reviewer": x.reviewer, "reviewed_on": x.reviewed_on,
                "evidence": x.evidence, "a_evidence": x.a_evidence, "b_evidence": x.b_evidence,
                "foodon_release": x.foodon_release} for f, x in sorted(final.items())]
    write_rows(folder / "results.csv", results, RESULT_FIELDS)
    write_sssom(folder / "reviewed.sssom.tsv", mappings, folder.name)
    print(f"wrote results.md, results.csv and reviewed.sssom.tsv in {folder}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
