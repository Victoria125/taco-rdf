"""Flag TACO and NEVO foods typed with the same FoodOn class whose composition says they are different foods.

Reads the pairs scripts/compare_taco_nevo.py writes; run it first, over every CDNO class. For each pair of
foods, a component disagrees strongly when:
- water differs by more than 15 g per 100 g, as between a raw and a cooked or a dry and a prepared food;
- protein, available carbohydrate or dietary fibre lies outside the EU labelling tolerance around TACO's
  value;
- a mineral is at least three times higher in one table, and the higher value is more than a trace amount.
A pair with three or more such components is flagged: one or two can be natural variation, three point to a
different product or state. A flag makes the pair a candidate for human review; it does not show an error.

The detailed CSV goes to build/, which git ignores, because it holds NEVO names; the --report file has TACO
foods, FoodOn classes, counts and the names of the disagreeing components only.
"""

from __future__ import annotations

import argparse
import csv
import datetime
import importlib.util
import sys
from collections import Counter
from pathlib import Path

from taco_rdf.namespaces import BUILD_DIR

_spec = importlib.util.spec_from_file_location(
    "compare_taco_nevo", Path(__file__).with_name("compare_taco_nevo.py"))
assert _spec is not None and _spec.loader is not None
compare = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(compare)

DETAIL = BUILD_DIR / "nevo" / "suspect_food_pairs.csv"
WATER = "0200002"
WATER_LIMIT = 15.0  # g per 100 g
TOLERANCE = {"0200040": "protein", "0200033": "available carbohydrate", "0200035": "dietary fibre"}
# For each mineral, the higher value in mg per 100 g up to which a difference is a trace and not counted.
MINERALS = {"0200544": ("calcium", 20), "0200570": ("magnesium", 10), "0200578": ("phosphorus", 30),
            "0200592": ("potassium", 50), "0200599": ("sodium", 20), "0200642": ("copper", 0.1),
            "0200651": ("iron", 0.5), "0200670": ("zinc", 0.3)}
MINERAL_RATIO = 3.0
MIN_DISAGREEING = 3
# Pairs judged not to be the same food by looking at the largest differences by hand, before this check
# existed, as (TACO food number, NEVO code). They test the rule; they did not set it.
BY_HAND = {("39", "3228"), ("53", "2356"), ("53", "3236"), ("159", "548"), ("455", "431"), ("547", "3229")}
FIELDS = ["taco_food", "taco_name", "nevo_code", "nevo_name", "foodon", "foodon_label", "components",
          "disagreeing", "flagged", "found_by_hand"]


def disagreeing(values: dict[str, tuple[float, float, str]]) -> list[str]:
    """Names of the components of one food pair that disagree strongly.

    values maps a CDNO code (e.g. 0200040) to (TACO value, NEVO value, unit).
    """
    found = []
    # As in compare.within_eu_tolerance, values are rounded to nine decimals and limits allow compare.EPSILON,
    # so that floating-point rounding cannot move a value lying exactly on a limit.
    values = {code: (round(t, 9), round(n, 9), unit) for code, (t, n, unit) in values.items()}
    if WATER in values and abs(values[WATER][0] - values[WATER][1]) > WATER_LIMIT + compare.EPSILON:
        found.append("water")
    for code, name in TOLERANCE.items():
        if code in values:
            taco, nevo, unit = values[code]
            if compare.within_eu_tolerance(compare.CDNO + code, unit, taco, nevo) is False:
                found.append(name)
    for code, (name, trace) in MINERALS.items():
        if code in values and values[code][2] == "mg":
            low, high = sorted(values[code][:2])
            if high > trace + compare.EPSILON and (low == 0 or high >= MINERAL_RATIO * low - compare.EPSILON):
                found.append(name)
    return found


def nevo_code(iri: str) -> str:
    return iri.rsplit("#", 1)[-1]


def count(row: dict[str, str]) -> int:
    """How many components of a checked pair disagree strongly."""
    return len(row["disagreeing"].split(", ")) if row["disagreeing"] else 0


def check(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    """One row per pair of foods, with the components compared and those that disagree strongly."""
    pairs: dict[tuple[str, str], dict] = {}
    for r in rows:
        p = pairs.setdefault((r["taco_food"], r["nevo_food"]), {"row": r, "values": {}})
        code = r["class"].rsplit("_", 1)[-1]
        p["values"][code] = (float(r["taco_value"]), float(r["nevo_value"]), r["unit"])
    out = []
    for (taco, nevo), p in pairs.items():
        found = disagreeing(p["values"])
        out.append({"taco_food": taco, "taco_name": p["row"]["taco_name"], "nevo_code": nevo_code(nevo),
                    "nevo_name": p["row"]["nevo_name"], "foodon": p["row"]["foodon"],
                    "foodon_label": p["row"]["foodon_label"], "components": str(len(p["values"])),
                    "disagreeing": ", ".join(found), "flagged": str(len(found) >= MIN_DISAGREEING),
                    "found_by_hand": str((taco, nevo_code(nevo)) in BY_HAND)})
    return sorted(out, key=lambda r: (-count(r), int(r["taco_food"]), r["nevo_code"]))


def summary(checked: list[dict[str, str]]) -> list[str]:
    flagged = [r for r in checked if r["flagged"] == "True"]
    by_hand = [r for r in checked if r["found_by_hand"] == "True"]
    return [f"{len(checked)} food pairs compared; {len(flagged)} flagged, between "
            f"{len({r['taco_food'] for r in flagged})} TACO foods",
            f"{sum(r['flagged'] == 'True' for r in by_hand)} of the {len(by_hand)} pairs found by hand "
            "are flagged"]


def report(checked: list[dict[str, str]], pairs: str, run: str) -> str:
    distribution = Counter(count(r) for r in checked)
    flagged: dict[str, list[dict[str, str]]] = {}
    for r in checked:
        if r["flagged"] == "True":
            flagged.setdefault(r["taco_food"], []).append(r)
    paired = Counter(r["taco_food"] for r in checked)
    total, by_hand = summary(checked)
    lines = [
        "# TACO and NEVO food pairs whose composition disagrees", "",
        f"Generated on {run} by `python scripts/check_food_pairs.py --report "
        "analysis/taco_nevo_food_pair_check.md`",
        f"from the pairs in `{pairs}`, written by `scripts/compare_taco_nevo.py`. NEVO's conditions of",
        "use do not let this project redistribute NEVO values, so this report names TACO foods and FoodOn",
        "classes only; the pairs with NEVO names stay in `build/nevo/suspect_food_pairs.csv`, which git",
        "ignores.", "",
        "## Rule", "",
        "A TACO food and a NEVO food typed with the same FoodOn class are compared component by component.",
        "A component disagrees strongly when:", "",
        f"- water differs by more than {WATER_LIMIT:g} g per 100 g, as between a raw and a cooked or a dry",
        "  and a prepared food;",
        "- protein, available carbohydrate or dietary fibre lies outside the tolerance the European",
        "  Commission's guidance of December 2012 allows a value declared on a label, with TACO's value as",
        "  the declared one;",
        "- a mineral (calcium, magnesium, phosphorus, potassium, sodium, copper, iron, zinc) is at least "
        f"{MINERAL_RATIO:g} times",
        "  higher in one table, and the higher value is more than a trace amount.", "",
        f"A pair with {MIN_DISAGREEING} or more strongly disagreeing components is flagged: one or two can",
        "be natural variation, several point to a different product or state. A flag makes the pair a",
        "candidate for human review; it does not show which table or which FoodOn type is wrong.", "",
        "## Result", "",
        total + ".", "",
        "| strongly disagreeing components | food pairs |", "| ---: | ---: |",
        *[f"| {n} | {distribution[n]} |" for n in sorted(distribution)], "",
        "Six pairs had been judged not to be the same food by looking at the largest differences by hand,",
        f"before this check existed; {by_hand}.", "",
        "## Flagged TACO foods", "",
        "| TACO food | TACO name | FoodOn class | NEVO foods flagged | strongly disagreeing components |",
        "| ---: | --- | --- | ---: | --- |",
    ]
    for taco, rs in sorted(flagged.items(), key=lambda kv: (-max(count(r) for r in kv[1]), int(kv[0]))):
        components = sorted({c for r in rs for c in r["disagreeing"].split(", ")})
        foodon = f"{rs[0]['foodon_label']} ({rs[0]['foodon'].rsplit('/', 1)[-1]})"
        lines.append(f"| {taco} | {rs[0]['taco_name']} | {foodon} | {len(rs)} of {paired[taco]} | "
                     f"{', '.join(components)} |")
    lines += [
        "", "## Limits", "",
        "- The components are not independent: a large difference in water moves every other component too.",
        "- Total fat is not compared: NICE-Food gives NEVO's total fat no CDNO class",
        "  ([nice_food_nevo_checks.md](nice_food_nevo_checks.md)), so the comparison yields no pairs for it.",
        "- The thresholds were set by hand and checked once against the six pairs found by hand; they have",
        "  not been tuned or validated on independent data.",
        "- Some flagged pairs may still be the same food, analysed in another season, variety or form.", "",
    ]
    return "\n".join(lines)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--pairs", type=Path, default=compare.OUT,
                   help=f"pairs CSV from scripts/compare_taco_nevo.py (default {compare.OUT})")
    p.add_argument("-o", "--output", type=Path, default=DETAIL, help=f"CSV to write (default {DETAIL})")
    p.add_argument("--report", type=Path, help="also write the aggregates as Markdown, e.g. "
                   "analysis/taco_nevo_food_pair_check.md")
    args = p.parse_args()
    if not args.pairs.is_file():
        print(f"{args.pairs} is missing; run scripts/compare_taco_nevo.py first", file=sys.stderr)
        return 1
    checked = check(compare.read_pairs(args.pairs))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS, lineterminator="\n")
        w.writeheader()
        w.writerows(checked)
    print(f"wrote {args.output}")
    print("\n".join(summary(checked)))
    if args.report:
        args.report.write_text(report(checked, args.pairs.name, datetime.date.today().isoformat()),
                               encoding="utf-8", newline="\n")
        print(f"wrote {args.report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
