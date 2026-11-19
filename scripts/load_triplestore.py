"""Load the TACO graph and the NEVO subgraphs of NICE-Food into a local Apache Jena Fuseki.

NICE-Food's analysis runs its SPARQL queries against a local Fuseki (rivm-syso/nicekg_analysis), with its
Turtle files uploaded through the Fuseki web page. This script uploads the files that
scripts/compare_taco_nevo.py reads to a Fuseki dataset's default graph, with the SPARQL Graph Store Protocol,
so the queries in queries/ run there unchanged. triplestore/README.md says how to start Fuseki. The NEVO
values stay in the local store and are not published.

With --foodon it also loads the whole FoodOn release this project pins (scripts/extract_foodon_module.py),
checked against its SHA-256: the TACO graph carries only the FoodOn module for TACO's classes, and NICE-Food's
graph the superclasses of few of NEVO's classes, so queries over the FoodOn hierarchy need the release. With
--tbca it also loads TBCA as scripts/tbca_to_rdf.py writes it; like NEVO's, TBCA's values stay local.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import sys
import time
import urllib.request
from pathlib import Path

import requests

from taco_rdf import sparql
from taco_rdf.namespaces import BUILD_DIR, ROOT

NEVO_DIR = ROOT / "data" / "external" / "nice-food"
NEVO_FILES = ("nevo21_graph.ttl", "nevo23_graph.ttl")
FOODON = ROOT / "data" / "external" / "foodon" / "foodon.owl"
TBCA = BUILD_DIR / "tbca.ttl"
FUSEKI = sparql.dataset(sparql.TACO_NEVO)
MEDIA_TYPES = {".ttl": "text/turtle; charset=utf-8", ".owl": "application/rdf+xml"}

_spec = importlib.util.spec_from_file_location(
    "extract_foodon_module", Path(__file__).with_name("extract_foodon_module.py"))
assert _spec is not None and _spec.loader is not None
foodon_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(foodon_module)


def pinned_foodon(path: Path) -> Path:
    """The pinned FoodOn release at path, downloaded first if missing; refused unless its SHA-256 matches."""
    if not path.is_file():
        path.parent.mkdir(parents=True, exist_ok=True)
        print(f"downloading {foodon_module.SOURCE_URL}", flush=True)
        urllib.request.urlretrieve(foodon_module.SOURCE_URL, path)
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if digest != foodon_module.SOURCE_SHA256:
        raise SystemExit(f"{path} is not the pinned FoodOn release: SHA-256 {digest}")
    return path


def upload(endpoint: str, path: Path) -> None:
    start = time.monotonic()
    with path.open("rb") as fh:
        r = requests.post(f"{endpoint}/data", params={"default": ""}, data=fh, timeout=3600,
                          headers={"Content-Type": MEDIA_TYPES[path.suffix]})
    r.raise_for_status()
    print(f"loaded {path.name} in {time.monotonic() - start:.0f} s", flush=True)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--endpoint", default=FUSEKI, help=f"Fuseki dataset URL (default {FUSEKI})")
    p.add_argument("--graph", type=Path, default=BUILD_DIR / "taco.ttl", help="TACO Turtle snapshot to load")
    p.add_argument("--nevo", type=Path, default=NEVO_DIR, help=f"folder with the NEVO subgraphs ({NEVO_DIR})")
    p.add_argument("--foodon", action="store_true", help=f"also load the pinned FoodOn release ({FOODON})")
    p.add_argument("--only-foodon", action="store_true", help="load the FoodOn release and nothing else")
    p.add_argument("--tbca", type=Path, nargs="?", const=TBCA,
                   help=f"also load TBCA in RDF, from scripts/tbca_to_rdf.py (default {TBCA})")
    p.add_argument("--only-tbca", action="store_true", help="load TBCA and nothing else")
    args = p.parse_args()
    if args.only_tbca:
        args.tbca = args.tbca or TBCA
    only = args.only_foodon or args.only_tbca
    files = [] if only else [args.graph, *(args.nevo / name for name in NEVO_FILES)]
    if args.tbca:
        files.append(args.tbca)
    missing = [f for f in files if not f.is_file()]
    if missing:
        print(f"missing: {', '.join(map(str, missing))}; build the graph and run scripts/fetch_nice_food.py",
              file=sys.stderr)
        return 1
    if args.foodon or args.only_foodon:
        files.append(pinned_foodon(FOODON))
    for path in files:
        upload(args.endpoint, path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
