from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation
from pathlib import Path

from rdflib import Graph, Literal, URIRef
from rdflib.term import Node


def parse_binding(text: str) -> Node:
    if text.startswith("<") and text.endswith(">"):
        return URIRef(text[1:-1])
    if re.fullmatch(r"-?\d+", text):
        return Literal(int(text))
    try:
        return Literal(Decimal(text))
    except InvalidOperation:
        return Literal(text)


def run_query(
    graph: Graph, path: Path, bindings: dict[str, str] | None = None
) -> tuple[list[str], list[tuple]]:
    text = Path(path).read_text(encoding="utf-8")
    init = {k: parse_binding(v) for k, v in (bindings or {}).items()}
    result = graph.query(text, initBindings=init)
    header = [str(v) for v in result.vars]
    rows = [tuple(row) for row in result]
    return header, rows
