from __future__ import annotations

import argparse
import sys
from pathlib import Path

from rdflib import Graph

from . import graph as graphmod
from .namespaces import (
    ALIGNMENTS_CSV,
    BUILD_DIR,
    CORRECTIONS_DIR,
    FOOD_NAMES_EN,
    GRAPH_TTL,
    ID,
    ONTOLOGY_TTL,
    POLICY_TTL,
    PROV,
    QUERIES_DIR,
    RAW_XLS,
    RDF,
    ROOT,
    SHAPES_DIR,
    TACO,
)
from .parse import load_corrections, parse_workbook

_FORMATS = {"turtle": ".ttl", "nt": ".nt", "xml": ".rdf", "json-ld": ".jsonld"}


def build_graph(xls: Path = RAW_XLS) -> Graph:
    table = parse_workbook(xls, load_corrections(CORRECTIONS_DIR))
    g = graphmod.build_graph(table, graphmod.load_alignments(ALIGNMENTS_CSV), source_file=xls,
                             food_names_en=graphmod.load_food_names_en(FOOD_NAMES_EN))
    from rdflib import Literal
    paths = [ALIGNMENTS_CSV, FOOD_NAMES_EN, ONTOLOGY_TTL, POLICY_TTL,
             *sorted(CORRECTIONS_DIR.glob("*.csv")), *sorted((ROOT / "src" / "taco_rdf").glob("*.py"))]
    for path in paths:
        relative = path.relative_to(ROOT).as_posix()
        entity = ID["build-input/" + relative]
        g.add((entity, RDF.type, PROV.Entity))
        g.add((entity, TACO.sourceFile, Literal(relative)))
        g.add((entity, TACO.sha256, Literal(graphmod.sha256_of(path))))
        g.add((ID["conversion"], PROV.used, entity))
    return g


def load_graph(path: Path | None = None) -> Graph:
    """Build the graph from the current inputs, or load the given Turtle file unchanged."""
    if path is None:
        print("building from current workbook, corrections and alignments", file=sys.stderr)
        return build_graph()
    path = Path(path).resolve(strict=True)
    print(f"loading snapshot {path} (SHA-256 {graphmod.sha256_of(path)})", file=sys.stderr)
    return Graph().parse(str(path), format="turtle")


def _selected_graph(args: argparse.Namespace) -> Graph:
    return load_graph(Path(args.graph) if args.graph else None)


def _cmd_build(args: argparse.Namespace) -> int:
    g = build_graph(Path(args.xls))
    out = Path(args.output or GRAPH_TTL.with_suffix(_FORMATS[args.format]))
    out.parent.mkdir(parents=True, exist_ok=True)
    g.serialize(destination=str(out), format=args.format)
    print(f"wrote {len(g):,} triples to {out}")
    return 0


def _cmd_validate(args: argparse.Namespace) -> int:
    from .validate import validate

    g = _selected_graph(args)
    report = validate(g, SHAPES_DIR)
    print(report.summary())
    if args.details:
        print(report.details(limit=args.limit))
    return 0 if report.conforms_strict else 1


def _cmd_query(args: argparse.Namespace) -> int:
    from .queries import run_query

    g = _selected_graph(args)
    path = Path(args.query)
    if not path.exists():
        path = QUERIES_DIR / (args.query if args.query.endswith(".rq") else args.query + ".rq")
    bindings = dict(b.split("=", 1) for b in args.bind or [])
    header, rows = run_query(g, path, bindings)
    print("\t".join(header))
    for row in rows:
        print("\t".join("" if v is None else str(v) for v in row))
    print(f"# {len(rows)} row(s)", file=sys.stderr)
    return 0


def _cmd_stats(args: argparse.Namespace) -> int:
    from .queries import run_query

    g = _selected_graph(args)
    _, rows = run_query(g, QUERIES_DIR / "graph_overview.rq")
    print(f"{len(g):,} triples")
    for row in rows:
        print(f"{row[0]:<28} {row[1]}")
    return 0


def _cmd_publish(args: argparse.Namespace) -> int:
    from .publish import publish

    g = _selected_graph(args)
    count = publish(g, Path(args.output))
    print(f"wrote the static site ({count} resource documents) to {args.output}")
    return 0


def _cmd_serve(args: argparse.Namespace) -> int:
    from .serve import serve

    serve(_selected_graph(args), host=args.host, port=args.port)
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="taco-rdf", description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)

    b = sub.add_parser("build", help="convert the TACO workbook to RDF")
    b.add_argument("--xls", default=str(RAW_XLS))
    b.add_argument("-o", "--output")
    b.add_argument("--format", choices=sorted(_FORMATS), default="turtle")
    b.set_defaults(func=_cmd_build)

    v = sub.add_parser("validate", help="validate the graph against the SHACL shapes")
    v.add_argument("--graph", help="use this graph file instead of rebuilding")
    v.add_argument("--details", action="store_true", help="list individual findings")
    v.add_argument("--limit", type=int, default=15, help="findings to list per shape")
    v.set_defaults(func=_cmd_validate)

    q = sub.add_parser("query", help="run a SPARQL query (file path or name in queries/)")
    q.add_argument("query")
    q.add_argument("--graph", help="load this Turtle snapshot; otherwise rebuild current inputs")
    q.add_argument("--bind", action="append", metavar="VAR=VALUE",
                   help="pre-bind a query variable (IRIs as <...>, numbers/strings as-is)")
    q.set_defaults(func=_cmd_query)

    s = sub.add_parser("stats", help="counts of the main resources in the graph")
    s.add_argument("--graph", help="load this Turtle snapshot; otherwise rebuild current inputs")
    s.set_defaults(func=_cmd_stats)

    pub = sub.add_parser("publish", help="write the static site that the w3id IRIs redirect to")
    pub.add_argument("--graph", help="use this graph file instead of rebuilding")
    pub.add_argument("-o", "--output", default=str(BUILD_DIR / "site"))
    pub.set_defaults(func=_cmd_publish)

    sv = sub.add_parser("serve", help="run a read-only SPARQL endpoint at /sparql")
    sv.add_argument("--graph", help="load this Turtle snapshot; otherwise rebuild current inputs")
    sv.add_argument("--host", default="127.0.0.1")
    sv.add_argument("--port", type=int, default=8000)
    sv.set_defaults(func=_cmd_serve)

    args = p.parse_args(argv)
    try:
        return args.func(args)
    except (OSError, ValueError) as exc:
        p.error(str(exc))


if __name__ == "__main__":
    raise SystemExit(main())
