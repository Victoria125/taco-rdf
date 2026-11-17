"""Validate a NICE-Food subgraph with two independent SHACL engines and compare their results.

scripts/check_nice_food.py validates with Jena's SHACL engine. This script also validates with pySHACL and
compares, for each check (result message), the set of focus nodes each engine reports. Two engines that
agree node by node make an error in either engine's reading of shapes/nice-food/nevo-shapes.ttl unlikely.

    $env:PYTHONPATH = "src"
    python verification/shacl_crosscheck.py --jar path/to/fuseki-server.jar --java java
"""

from __future__ import annotations

import argparse
import importlib.util
import time
from collections import defaultdict
from pathlib import Path

import pyshacl
from rdflib import Graph, Namespace

from taco_rdf.namespaces import BUILD_DIR, ROOT

SH = Namespace("http://www.w3.org/ns/shacl#")

spec = importlib.util.spec_from_file_location("check_nice_food", ROOT / "scripts" / "check_nice_food.py")
assert spec is not None and spec.loader is not None
check = importlib.util.module_from_spec(spec)
spec.loader.exec_module(check)


def focus_by_message(report: Graph) -> dict[str, set[str]]:
    out: dict[str, set[str]] = defaultdict(set)
    for result in report.subjects(SH.resultSeverity, None):
        out[str(report.value(result, SH.resultMessage))].add(str(report.value(result, SH.focusNode)))
    return out


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--jar", type=Path, required=True)
    p.add_argument("--java", default="java")
    p.add_argument("--data", type=Path, default=BUILD_DIR / "taco_nice_food.ttl")
    args = p.parse_args()

    start = time.perf_counter()
    jena = focus_by_message(check.validate(args.java, args.jar, args.data))
    print(f"Jena: {time.perf_counter() - start:.0f} s")

    start = time.perf_counter()
    data = Graph().parse(args.data, format="turtle")
    shapes = Graph().parse(check.SHAPES, format="turtle")
    _, report, _ = pyshacl.validate(data, shacl_graph=shapes, inference="none", advanced=True,
                                    allow_warnings=True)
    py = focus_by_message(report)
    print(f"pySHACL {pyshacl.__version__}: {time.perf_counter() - start:.0f} s")

    print(f"\n{'check':<75}{'Jena':>7}{'pySHACL':>9}{'same nodes':>12}")
    same = True
    for message in sorted(set(jena) | set(py)):
        a, b = jena.get(message, set()), py.get(message, set())
        print(f"{message[:74]:<75}{len(a):>7}{len(b):>9}{a == b!s:>12}")
        same &= a == b
    print(f"\nengines agree node by node: {same}")
    return 0 if same else 1


if __name__ == "__main__":
    raise SystemExit(main())
