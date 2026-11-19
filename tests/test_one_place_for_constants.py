"""Each namespace, Fuseki's address and the external tools' paths are written in one place.

src/taco_rdf/namespaces.py holds the namespaces and the tables' IRIs, src/taco_rdf/sparql.py Fuseki's
address and src/taco_rdf/tools.py where Java and Jena's jar are, so that a change the group agrees on is
made once. This test reads every string in the code (docstrings aside, as they show commands) and fails
where one of them is written again. The tests themselves keep the IRIs written out: they check what the
code writes against an independent text.
"""

from __future__ import annotations

import ast
from pathlib import Path

from taco_rdf.namespaces import FIO, NEVO_SOURCE, NEVONUT, OM, ROOT, TACO_SOURCE

HOMES = {"namespaces.py", "sparql.py", "tools.py"}
FORBIDDEN = {str(FIO): "taco_rdf.namespaces.FIO", str(OM): "taco_rdf.namespaces.OM",
             str(NEVONUT): "taco_rdf.namespaces.NEVONUT", str(TACO_SOURCE): "taco_rdf.namespaces.TACO_SOURCE",
             str(NEVO_SOURCE): "taco_rdf.namespaces.NEVO_SOURCE", "localhost:3030": "taco_rdf.sparql",
             "LOCALAPPDATA": "taco_rdf.tools.java()", "jdk-": "taco_rdf.tools.java()",
             "apache-jena-fuseki-": "taco_rdf.tools.fuseki_jar()"}


def strings(source: str) -> list[tuple[int, str]]:
    """The string constants of a module, f-string parts included, but not its docstrings."""
    tree = ast.parse(source)
    docs = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)) and node.body:
            first = node.body[0]
            if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant):
                docs.add(id(first.value))
    return [(n.lineno, n.value) for n in ast.walk(tree)
            if isinstance(n, ast.Constant) and isinstance(n.value, str) and id(n) not in docs]


def written_again(root: Path) -> list[str]:
    found = []
    for folder in ("src", "scripts", "verification", "analysis"):
        for path in sorted((root / folder).rglob("*.py")):
            if path.name in HOMES and path.parent.name == "taco_rdf":
                continue
            for line, text in strings(path.read_text(encoding="utf-8")):
                plain = text.replace("\\.", ".")  # IRIs written into regular expressions
                found += [f"{path.relative_to(root).as_posix()}:{line} writes {s!r}; use {home}"
                          for s, home in FORBIDDEN.items() if s in plain]
    return found


def test_namespaces_fuseki_and_tool_paths_are_written_in_one_place():
    found = written_again(ROOT)
    assert not found, "\n".join(found)


def test_the_check_finds_a_namespace_written_again(tmp_path):
    (tmp_path / "scripts").mkdir()
    (tmp_path / "scripts" / "new.py").write_text(
        '"""A docstring may say http://localhost:3030/nicefood."""\n'
        'OM = "http://www.ontology-of-units-of-measure.org/resource/om-2/"\n'
        'pattern = r"^https://data\\.rivm\\.nl/data/nvip/bigfood/nevo/nutrient#"\n', encoding="utf-8")
    found = written_again(tmp_path)
    assert [f.split(" writes ")[0] for f in found] == ["scripts/new.py:2", "scripts/new.py:3"]
