"""Compare TACO and NEVO foods typed with the same FoodOn class, value by value.

Runs the queries in queries/nevo/ over the TACO graph together with the NEVO subgraphs of NICE-Food (fetch
them first with scripts/fetch_nice_food.py): one pairs values typed with the same CDNO class, the other
compares available carbohydrate, because NICE-Food types NEVO's available carbohydrate with the CDNO class
TACO's total carbohydrate has. Every pair goes to a CSV under build/, which git ignores: the rows hold NEVO
values, which NEVO's conditions of use do not let this project redistribute (data/SOURCES.md). The printed
summary has aggregates only: counts, rank correlations and median differences.
"""

from __future__ import annotations

import argparse
import csv
import statistics
import sys
import time
from collections import defaultdict
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
# Tolerances for foods other than supplements, including measurement uncertainty, from the European
# Commission's guidance document on tolerances for nutrient values declared on a label (December 2012),
# by CDNO class. TACO's value is taken as the declared one. Water, ash, cholesterol and single fatty acids
# have no tolerance there.
EU_MACRONUTRIENTS = {"0200040", "0200033", "0200035"}  # protein, available carbohydrate, dietary fibre
EU_FATTY_ACIDS = {"0200458", "0200456", "0200449"}  # saturated, monounsaturated, polyunsaturated
EU_SODIUM = "0200599"
# calcium, magnesium, phosphorus, potassium, copper, iron, zinc
EU_MINERALS = {"0200544", "0200570", "0200578", "0200592", "0200642", "0200651", "0200670"}
EU_VITAMINS = {"0200185", "0200186", "0200188", "0200192", "0200420"}  # B2, niacin, B6, C, retinol
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
    if code in EU_MACRONUTRIENTS and unit == "g":
        return abs(nevo - taco) <= (2 if taco < 10 else 0.2 * taco if taco <= 40 else 8)
    if code in EU_FATTY_ACIDS and unit == "g":
        return abs(nevo - taco) <= (0.8 if taco < 4 else 0.2 * taco)
    if code == EU_SODIUM and unit == "mg":
        return abs(nevo - taco) <= (150 if taco < 500 else 0.2 * taco)
    if code in EU_MINERALS:
        return 0.65 * taco <= nevo <= 1.45 * taco
    if code in EU_VITAMINS:
        return 0.65 * taco <= nevo <= 1.50 * taco
    return None


def summary(rows: list[dict[str, str]]) -> list[str]:
    def count(key: str) -> int:
        return len({r[key] for r in rows})

    lines = [f"{len(rows)} value pairs: {count('taco_food')} TACO foods and {count('nevo_food')} NEVO foods "
             f"in {count('foodon')} shared FoodOn classes, {count('class')} CDNO classes"]
    by_pair: dict[tuple[str, str, str, str], list[tuple[float, float]]] = defaultdict(list)
    for r in rows:
        key = (r["cdno_label"] or r["class"], r["class"], r["nevo_nutrient"], r["unit"])
        by_pair[key].append((float(r["taco_value"]), float(r["nevo_value"])))
    lines.append("CDNO class | NEVO nutrient | unit | pairs | Spearman | median TACO - NEVO | within 20% | "
                 "within EU tolerance")
    for (label, cdno, nevo, unit), pairs in sorted(by_pair.items(), key=lambda kv: -len(kv[1])):
        t, n = [a for a, _ in pairs], [b for _, b in pairs]
        varied = len(pairs) > 2 and len(set(t)) > 1 and len(set(n)) > 1
        rho = f"{statistics.correlation(t, n, method='ranked'):.2f}" if varied else "-"
        diff = statistics.median(a - b for a, b in pairs)
        near = sum(abs(a - b) <= 0.2 * max(abs(a), abs(b)) for a, b in pairs) / len(pairs)
        eu = [within_eu_tolerance(cdno, unit, a, b) for a, b in pairs]
        eu_share = "-" if eu[0] is None else f"{sum(bool(x) for x in eu) / len(eu):.0%}"
        lines.append(f"{label} | {nevo} | {unit} | {len(pairs)} | {rho} | {diff:+.3g} | {near:.0%} | "
                     f"{eu_share}")
    return lines


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--graph", help="TACO Turtle snapshot to use; otherwise rebuild from current inputs")
    p.add_argument("--nevo", type=Path, default=NEVO_DIR,
                   help=f"folder with the NEVO subgraphs (default {NEVO_DIR})")
    p.add_argument("--bind", action="append", metavar="VAR=VALUE",
                   help="pre-bind a query variable, e.g. class=<http://purl.obolibrary.org/obo/CDNO_0200040>")
    p.add_argument("-o", "--output", type=Path, default=OUT, help=f"CSV to write (default {OUT})")
    args = p.parse_args()
    try:
        nevo = load_nevo(args.nevo)
        taco = load_graph(Path(args.graph) if args.graph else None)
    except (OSError, ValueError) as exc:
        print(exc, file=sys.stderr)
        return 1
    bindings = dict(b.split("=", 1) for b in args.bind or [])
    cls = bindings.pop("class", None)
    classes = [cls] if cls else [f"<{r[0]}>" for r in taco.query(TACO_CDNO_CLASSES)]
    both = ReadOnlyGraphAggregate([taco, nevo])
    rows = same_class_pairs(both, bindings, [c for c in classes if c != f"<{AVAILABLE_CARBOHYDRATE}>"])
    if cls is None or cls in CARBOHYDRATE_CLASSES:
        rows += available_carbohydrate_pairs(both, bindings)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    print(f"wrote {args.output}")
    if rows:
        print("\n".join(summary(rows)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
