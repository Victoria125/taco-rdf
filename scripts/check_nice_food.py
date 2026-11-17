"""Check NICE-Food's NEVO subgraph against SHACL shapes for the NICE-Food pattern.

shapes/nice-food/nevo-shapes.ttl turns what the TACO x NEVO comparison found by hand into checks: food items
without a FoodOn class, nutritional values without a CDNO class or with two values of one nutrient, NEVO's
available carbohydrate typed with CDNO's general carbohydrate class, units given only as strings, and the
sodium code read as not-a-number. Jena's SHACL engine validates the graph (the Fuseki jar of
triplestore/README.md bundles it; pySHACL would take far longer on 1.7 million triples), and this script
counts the results by check, nutrient and unit.

The report names nutrients and units and counts results; it holds no NEVO value.
"""

from __future__ import annotations

import argparse
import datetime
import subprocess
import sys
import tempfile
from collections import Counter
from pathlib import Path

from rdflib import RDFS, Graph, Namespace

from taco_rdf.namespaces import ROOT

SH = Namespace("http://www.w3.org/ns/shacl#")
FIO = Namespace("http://www.foodvoc.org/resource/fio#")
OM = Namespace("http://www.ontology-of-units-of-measure.org/resource/om-2/")
SHAPES = ROOT / "shapes" / "nice-food" / "nevo-shapes.ttl"
NEVO = ROOT / "data" / "external" / "nice-food" / "nevo21_graph.ttl"


def validate(java: str, jar: Path, data: Path) -> Graph:
    """Jena's SHACL validation report for data.

    The files go to Jena as file: URIs, since it reads a Windows path such as C:\\... as an IRI.
    """
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "report.ttl"
        with out.open("w", encoding="utf-8") as fh:
            subprocess.run([java, "-Xmx4g", "-cp", str(jar), "shacl.shacl", "validate", "--shapes",
                            SHAPES.resolve().as_uri(), "--data", data.resolve().as_uri()], stdout=fh,
                           check=True)
        return Graph().parse(out, format="turtle")


def nutrient_label(nevo: Graph, nutrient) -> str:
    code = str(nutrient).rsplit("#", 1)[-1]
    label = next((str(o) for o in nevo.objects(nutrient, RDFS.label) if getattr(o, "language", None) == "en"),
                 None)
    return f"{label} ({code})" if label else code


def breakdown(report: Graph, nevo: Graph) -> dict[str, Counter]:
    """For each check, its results counted by nutrient or by unit string."""
    measure_of = {m: v for v, m in nevo.subject_objects(OM.hasValue)}
    nutrient_of = dict(nevo.subject_objects(FIO.hasNutrient))
    counts: dict[str, Counter] = {}
    for result in report.subjects(SH.resultSeverity, None):
        message = str(report.value(result, SH.resultMessage))
        focus = report.value(result, SH.focusNode)
        if message.startswith("Measure whose unit"):
            key = ", ".join(sorted(str(u) for u in nevo.objects(focus, OM.hasUnit)))
        elif message.startswith("Two nutritional values"):
            key = nutrient_label(nevo, report.value(result, SH.value))
        elif focus in nutrient_of:
            key = nutrient_label(nevo, nutrient_of[focus])
        elif focus in measure_of and measure_of[focus] in nutrient_of:
            key = nutrient_label(nevo, nutrient_of[measure_of[focus]])
        else:
            key = ""
        counts.setdefault(message, Counter())[key] += 1
    return counts


def markdown(counts: dict[str, Counter], data: Path, run: str, top: int = 8) -> str:
    ranked = sorted(counts.items(), key=lambda kv: -sum(kv[1].values()))
    lines = ["# Checks of NICE-Food's NEVO subgraph", "",
             f"Generated on {run} by `python scripts/check_nice_food.py --report "
             "analysis/nice_food_nevo_checks.md`",
             f"from `{data.name}` of NICE-Food v3 (https://doi.org/10.5281/zenodo.18450818) and the shapes in",
             "[shapes/nice-food/nevo-shapes.ttl](../shapes/nice-food/nevo-shapes.ttl), validated with Jena's",
             "SHACL engine. It counts results by check and by nutrient or unit, and holds no NEVO value.", "",
             "| Check | Results |", "| --- | ---: |"]
    lines += [f"| {message} | {sum(c.values())} |" for message, c in ranked]
    for message, c in ranked:
        if len(c) > 1 or "" not in c:
            lines += ["", f"## {message}", "",
                      f"{len(c)} nutrients or units; the {min(top, len(c))} with most results:", "",
                      "| Nutrient or unit | Results |", "| --- | ---: |"]
            lines += [f"| {key or '(none)'} | {n} |" for key, n in c.most_common(top)]
    return "\n".join(lines) + "\n"


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--jar", type=Path, required=True, help="a jar bundling Jena's SHACL engine, e.g. "
                   "apache-jena-fuseki-6.2.0/fuseki-server.jar")
    p.add_argument("--java", default="java", help="the java executable (Java 21 for Fuseki 6)")
    p.add_argument("--data", type=Path, default=NEVO, help=f"NEVO subgraph to check (default {NEVO})")
    p.add_argument("--report", type=Path, help="write the counts as Markdown, e.g. "
                   "analysis/nice_food_nevo_checks.md")
    args = p.parse_args()
    if not args.data.is_file():
        print(f"{args.data} is missing; run scripts/fetch_nice_food.py first", file=sys.stderr)
        return 1
    report = validate(args.java, args.jar, args.data)
    counts = breakdown(report, Graph().parse(args.data, format="turtle"))
    for message, c in sorted(counts.items(), key=lambda kv: -sum(kv[1].values())):
        print(f"{sum(c.values()):7}  {message}")
    if args.report:
        args.report.write_text(markdown(counts, args.data, datetime.date.today().isoformat()),
                               encoding="utf-8", newline="\n")
        print(f"wrote {args.report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
