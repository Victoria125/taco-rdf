"""Compare TACO and NEVO foods typed with the same FoodOn class, value by value.

Runs the queries in queries/nevo/ over the TACO graph together with the NEVO subgraphs of NICE-Food (fetch
them first with scripts/fetch_nice_food.py): one pairs values typed with the same CDNO class, the other
compares available carbohydrate, because NICE-Food types NEVO's available carbohydrate with the CDNO class
TACO's total carbohydrate has. Every pair goes to a CSV under build/, which git ignores: the rows hold NEVO
values, which NEVO's conditions of use do not let this project redistribute (data/SOURCES.md). The printed
summary and the --report file have aggregates only: counts, rank correlations and ratio quartiles.
"""

from __future__ import annotations

import argparse
import csv
import datetime
import io
import statistics
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

from rdflib import Graph
from rdflib.graph import ReadOnlyGraphAggregate

from taco_rdf.cli import load_graph
from taco_rdf.namespaces import BUILD_DIR, QUERIES_DIR, ROOT
from taco_rdf.queries import run_query

NEVO_DIR = ROOT / "data" / "external" / "nice-food"
NEVO_FILES = ("nevo21_graph.ttl", "nevo23_graph.ttl")
SAME_CLASS = QUERIES_DIR / "nevo" / "taco_nevo_same_foodon_class.rq"
CARBOHYDRATE = QUERIES_DIR / "nevo" / "taco_nevo_available_carbohydrate.rq"
OUT = BUILD_DIR / "nevo" / "taco_nevo_same_foodon_class.csv"
CDNO = "http://purl.obolibrary.org/obo/CDNO_"
AVAILABLE_CARBOHYDRATE = f"{CDNO}0200033"
CARBOHYDRATE_CLASSES = {f"<{CDNO}0200005>", f"<{AVAILABLE_CARBOHYDRATE}>"}
FIELDS = ["comparison", "foodon", "foodon_label", "class", "cdno_label", "taco_food", "taco_name",
          "taco_nutrient", "taco_value", "nevo_food", "nevo_name", "nevo_nutrient", "nevo_value", "unit"]
# Below this many TACO foods a nutrient gets counts only, no correlation or quartiles.
MIN_FOODS = 10
# Tolerances for foods other than supplements, including measurement uncertainty, from the European
# Commission's guidance document on tolerances for nutrient values declared on a label (December 2012),
# by CDNO class. TACO's value is taken as the declared one. Water, ash, cholesterol and single fatty acids
# have no tolerance there. They were set to check a label against analyses of the same product, not to
# compare two food composition tables, so the report keeps them apart as an exploratory reading.
EU_MACRONUTRIENTS = {"0200040", "0200033", "0200035"}  # protein, available carbohydrate, dietary fibre
EU_FATTY_ACIDS = {"0200458", "0200456", "0200449"}  # saturated, monounsaturated, polyunsaturated
EU_SODIUM = "0200599"
# calcium, magnesium, phosphorus, potassium, copper, iron, zinc
EU_MINERALS = {"0200544", "0200570", "0200578", "0200592", "0200642", "0200651", "0200670"}
EU_VITAMINS = {"0200185", "0200186", "0200188", "0200192", "0200420"}  # B2, niacin, B6, C, retinol
# Values have at most six decimals. Comparisons round them to nine and allow this much, so that floating-point
# rounding cannot move a value lying exactly on a limit: 1.45 * 20 is 28.999999999999996, and the median of
# 0.6 and 0.7 is 0.6499999999999999 (verification/boundary_impact.py).
EPSILON = 1e-9
# rdflib is far faster with ?class bound, so without --bind class=... the query runs once per CDNO class.
TACO_CDNO_CLASSES = """
SELECT DISTINCT ?class WHERE {
  ?m a <https://w3id.org/taco-rdf/vocab#NutrientMeasurement> , ?class .
  FILTER (STRSTARTS(STR(?class), "http://purl.obolibrary.org/obo/CDNO_"))
} ORDER BY ?class
"""


def load_nevo(folder: Path) -> Graph:
    g = Graph()
    for name in NEVO_FILES:
        path = folder / name
        if not path.is_file():
            raise OSError(f"{path} is missing; run scripts/fetch_nice_food.py first")
        print(f"loading {path}", file=sys.stderr)
        g.parse(path, format="turtle")
    return g


def as_rows(header: list[str], result: list[tuple]) -> list[dict[str, str]]:
    return [{k: "" if v is None else str(v) for k, v in zip(header, row, strict=True)} for row in result]


def timed(graph: Graph, query: Path, bindings: dict[str, str], what: str) -> list[dict[str, str]]:
    start = time.monotonic()
    rows = as_rows(*run_query(graph, query, bindings))
    print(f"{what}: {len(rows)} pairs in {time.monotonic() - start:.0f} s", file=sys.stderr, flush=True)
    return rows


def same_class_pairs(graph: Graph, bindings: dict[str, str], classes: list[str]) -> list[dict[str, str]]:
    rows = []
    for cls in classes:
        for r in timed(graph, SAME_CLASS, {**bindings, "class": cls}, cls.strip("<>").rsplit("/", 1)[-1]):
            rows.append({"comparison": "same CDNO class", **r})
    return rows


def available_carbohydrate_pairs(graph: Graph, bindings: dict[str, str]) -> list[dict[str, str]]:
    rows = []
    for r in timed(graph, CARBOHYDRATE, bindings, "available carbohydrate"):
        rows.append({
            "comparison": "available carbohydrate: TACO carbohydrate by difference minus dietary fibre",
            "foodon": r["foodon"], "foodon_label": r["foodon_label"], "class": AVAILABLE_CARBOHYDRATE,
            "cdno_label": "concentration of available carbohydrate in material entity",
            "taco_food": r["taco_food"], "taco_name": r["taco_name"],
            "taco_nutrient": f"Carbohydrate {r['taco_carbohydrate']} minus Dietary fibre {r['taco_fibre']}",
            "taco_value": r["taco_value"], "nevo_food": r["nevo_food"], "nevo_name": r["nevo_name"],
            "nevo_nutrient": "Carbohydrate available", "nevo_value": r["nevo_value"], "unit": r["unit"]})
    return rows


def within_eu_tolerance(cdno: str, unit: str, taco: float, nevo: float) -> bool | None:
    """Whether NEVO's value lies within the EU labelling tolerance around TACO's; None if none applies."""
    code = cdno.rsplit("CDNO_", 1)[-1]
    taco, nevo = round(taco, 9), round(nevo, 9)
    if code in EU_MACRONUTRIENTS and unit == "g":
        return abs(nevo - taco) <= (2 if taco < 10 else 0.2 * taco if taco <= 40 else 8) + EPSILON
    if code in EU_FATTY_ACIDS and unit == "g":
        return abs(nevo - taco) <= (0.8 if taco < 4 else 0.2 * taco) + EPSILON
    if code == EU_SODIUM and unit == "mg":
        return abs(nevo - taco) <= (150 if taco < 500 else 0.2 * taco) + EPSILON
    if code in EU_MINERALS:
        return 0.65 * taco - EPSILON <= nevo <= 1.45 * taco + EPSILON
    if code in EU_VITAMINS:
        return 0.65 * taco - EPSILON <= nevo <= 1.50 * taco + EPSILON
    return None


Nutrient = tuple[str, str, str, str]  # CDNO label, CDNO class, NEVO nutrient, unit


def per_food(rows: list[dict[str, str]]) -> dict[Nutrient, list[tuple[float, float]]]:
    """For each nutrient, one (TACO value, median NEVO value) per TACO food.

    A broad FoodOn class can pair one TACO food with many NEVO foods; counting every pair would weigh that
    TACO value as many times, so each TACO food is compared once with the NEVO foods of its class.
    """
    by_food: dict[Nutrient, dict[str, tuple[float, list[float]]]] = defaultdict(dict)
    for r in rows:
        key = (r["cdno_label"] or r["class"], r["class"], r["nevo_nutrient"], r["unit"])
        _, nevo = by_food[key].setdefault(r["taco_food"], (float(r["taco_value"]), []))
        nevo.append(float(r["nevo_value"]))
    return {key: [(taco, statistics.median(nevo)) for taco, nevo in foods.values()]
            for key, foods in by_food.items()}


def within_20_percent(taco: float, nevo: float) -> bool:
    taco, nevo = round(taco, 9), round(nevo, 9)
    return abs(taco - nevo) <= 0.2 * max(abs(taco), abs(nevo)) + EPSILON


def share(flags: list[bool]) -> str:
    return f"{sum(flags) / len(flags):.0%}"


def coverage(rows: list[dict[str, str]]) -> str:
    def count(key: str) -> int:
        return len({r[key] for r in rows})

    food_pairs = len({(r["taco_food"], r["nevo_food"]) for r in rows})
    return (f"{len(rows)} value pairs between {count('taco_food')} TACO foods and {count('nevo_food')} NEVO "
            f"foods ({food_pairs} food pairs) in {count('foodon')} shared FoodOn classes and "
            f"{count('class')} CDNO classes")


def nutrients(rows: list[dict[str, str]]) -> list[tuple[Nutrient, list[tuple[float, float]]]]:
    return sorted(per_food(rows).items(), key=lambda kv: (-len(kv[1]), kv[0]))


def agreement_table(rows: list[dict[str, str]]) -> list[str]:
    """By nutrient: TACO foods, rank correlation and quartiles of the TACO/NEVO ratio."""
    pairs = Counter((r["class"], r["nevo_nutrient"], r["unit"]) for r in rows)
    lines = ["| CDNO class | NEVO nutrient | unit | TACO foods | value pairs | Spearman rho "
             "| TACO/NEVO median | TACO/NEVO quartiles | foods with a zero |",
             "| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for (label, cdno, nevo, unit), foods in nutrients(rows):
        t, n = [a for a, _ in foods], [b for _, b in foods]
        ratios = [a / b for a, b in foods if a > 0 and b > 0]
        rho = median = quartiles = "-"
        if len(foods) >= MIN_FOODS and len(set(t)) > 1 and len(set(n)) > 1:
            rho = f"{statistics.correlation(t, n, method='ranked'):.2f}"
        if len(foods) >= MIN_FOODS and len(ratios) >= 4:
            q1, q2, q3 = statistics.quantiles(ratios, n=4)
            median, quartiles = f"{q2:.2f}", f"{q1:.2f} to {q3:.2f}"
        lines.append(f"| {label} | {nevo} | {unit} | {len(foods)} | {pairs[cdno, nevo, unit]} | {rho} | "
                     f"{median} | {quartiles} | {len(foods) - len(ratios)} |")
    return lines


def thresholds_table(rows: list[dict[str, str]]) -> list[str]:
    """By nutrient: shares of TACO foods within 20% and within the EU labelling tolerance (exploratory)."""
    lines = ["| CDNO class | TACO foods | within 20% | within EU labelling tolerance |",
             "| --- | ---: | ---: | ---: |"]
    for (label, cdno, _, unit), foods in nutrients(rows):
        eu = [within_eu_tolerance(cdno, unit, a, b) for a, b in foods]
        eu_share = "-" if eu[0] is None else share([bool(x) for x in eu])
        lines.append(f"| {label} | {len(foods)} | {share([within_20_percent(a, b) for a, b in foods])} | "
                     f"{eu_share} |")
    return lines


def classes_table(rows: list[dict[str, str]]) -> list[str]:
    """FoodOn classes with the TACO foods they pair and the number of NEVO foods, no NEVO names or values."""
    taco: dict[tuple[str, str], set[int]] = defaultdict(set)
    nevo: dict[tuple[str, str], set[str]] = defaultdict(set)
    for r in rows:
        key = (r["foodon"].rsplit("/", 1)[-1], r["foodon_label"])
        taco[key].add(int(r["taco_food"]))
        nevo[key].add(r["nevo_food"])
    lines = ["| FoodOn class | label | TACO foods | NEVO foods |", "| --- | --- | --- | ---: |"]
    for key in sorted(taco, key=lambda k: (-len(nevo[k]) * len(taco[k]), k)):
        lines.append(f"| {key[0]} | {key[1]} | {', '.join(map(str, sorted(taco[key])))} | {len(nevo[key])} |")
    return lines


def report(rows: list[dict[str, str]], graph: str, run: str) -> str:
    return "\n".join([
        "# TACO and NEVO values for foods typed with the same FoodOn class", "",
        f"Generated on {run} by",
        "`python scripts/compare_taco_nevo.py --report analysis/taco_nevo_comparison.md`",
        f"from {graph} and the NEVO subgraphs of NICE-Food v3 (NEVO-Online 2021 7.0,",
        "https://doi.org/10.5281/zenodo.18450818). NEVO's conditions of use do not let this project",
        "redistribute NEVO values ([data/SOURCES.md](../data/SOURCES.md)), so this report holds aggregates",
        "only; the matched values stay in `build/nevo/`, which git ignores.", "",
        "## What the comparison can show", "",
        "A pair is a TACO food and a NEVO food typed with the same FoodOn class, with values typed with the",
        "same CDNO class in the same unit. Only identical classes match, a class can be broad, and every",
        "FoodOn type in the TACO graph is still unreviewed. The pairs show where the two tables can be",
        "compared. Agreement suggests that the shared typing brings comparable foods and nutrients together;",
        "disagreement can come from the typing, from varieties, fortification, sampling, analytical methods",
        "or table conventions, and does not say which table is wrong. Neither tests whether two foods or two",
        "tables are equivalent.", "",
        "## Coverage", "",
        coverage(rows) + ".", "",
        "## Agreement by nutrient", "",
        "Each TACO food counts once: its value is compared with the median value of the NEVO foods of its",
        "FoodOn class. Spearman's rho says whether the two tables rank the foods alike; the TACO/NEVO ratio,",
        "over the foods with both values above zero, says how far apart the values are (1.00: equal, 0.50:",
        f"TACO's value is half NEVO's). A nutrient with fewer than {MIN_FOODS} TACO foods gets counts only.",
        "`value pairs` counts every TACO-NEVO pair before the median.", "",
        *agreement_table(rows), "",
        "## Exploratory: fixed thresholds", "",
        "Share of TACO foods whose value lies within 20% of the median NEVO value (the difference at most",
        "20% of the larger value), and within the tolerance the European Commission's guidance of December",
        "2012 allows a nutrient value declared on a label, with TACO's value as the declared one. Those",
        "tolerances were set to check a label against analyses of the same product; they are not a measure",
        "of agreement between two food composition tables. They are wide for small amounts (±150 mg of",
        "sodium below 500 mg, ±2 g of protein, carbohydrate or fibre below 10 g) and do not exist for water,",
        "ash, cholesterol or single fatty acids. A share within them does not show that the tables agree,",
        "and a value outside them is not an error.", "",
        *thresholds_table(rows), "",
        "## FoodOn classes", "",
        "TACO food numbers and the number of NEVO foods for each shared class, the classes that give the",
        "most pairs first.", "",
        *classes_table(rows), "",
    ])


def query_pairs(taco: Graph, nevo: Graph, bindings: dict[str, str]) -> list[dict[str, str]]:
    cls = bindings.pop("class", None)
    classes = [cls] if cls else [f"<{r[0]}>" for r in taco.query(TACO_CDNO_CLASSES)]
    both = ReadOnlyGraphAggregate([taco, nevo])
    rows = same_class_pairs(both, bindings, [c for c in classes if c != f"<{AVAILABLE_CARBOHYDRATE}>"])
    if cls is None or cls in CARBOHYDRATE_CLASSES:
        rows += available_carbohydrate_pairs(both, bindings)
    return rows


def read_pairs(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--graph", help="TACO Turtle snapshot to use; otherwise rebuild from current inputs")
    p.add_argument("--nevo", type=Path, default=NEVO_DIR,
                   help=f"folder with the NEVO subgraphs (default {NEVO_DIR})")
    p.add_argument("--bind", action="append", metavar="VAR=VALUE",
                   help="pre-bind a query variable, e.g. class=<http://purl.obolibrary.org/obo/CDNO_0200040>")
    p.add_argument("-o", "--output", type=Path, default=OUT, help=f"CSV to write (default {OUT})")
    p.add_argument("--pairs", type=Path,
                   help="summarize this CSV of a previous run instead of running the queries")
    p.add_argument("--report", type=Path, help="also write the aggregates as Markdown, e.g. "
                   "analysis/taco_nevo_comparison.md; only for a run over every CDNO class")
    args = p.parse_args()
    if isinstance(sys.stdout, io.TextIOWrapper):  # CDNO labels have Greek letters; Windows pipes use cp1252
        sys.stdout.reconfigure(encoding="utf-8")
    if args.report and args.bind:
        p.error("--report needs every CDNO class and food; drop --bind")
    if args.pairs:
        rows = read_pairs(args.pairs)
    else:
        try:
            nevo = load_nevo(args.nevo)
            taco = load_graph(Path(args.graph) if args.graph else None)
        except (OSError, ValueError) as exc:
            print(exc, file=sys.stderr)
            return 1
        rows = query_pairs(taco, nevo, dict(b.split("=", 1) for b in args.bind or []))
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("w", encoding="utf-8", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=FIELDS, lineterminator="\n")
            w.writeheader()
            w.writerows(rows)
        print(f"wrote {args.output}")
    if rows:
        print(coverage(rows))
        print("\n".join([*agreement_table(rows), "", *thresholds_table(rows)]))
    if args.report and rows:
        source = "the TACO graph built from current inputs"
        if args.graph:
            source = f"the TACO snapshot `{Path(args.graph).name}`"
        if args.pairs:
            source = f"the pairs an earlier run wrote to `{args.pairs.name}`"
        args.report.write_text(report(rows, source, datetime.date.today().isoformat()), encoding="utf-8",
                               newline="\n")
        print(f"wrote {args.report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
