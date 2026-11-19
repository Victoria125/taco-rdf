"""Check docs/structure.md against the data, and that the checks catch a wrong document.

1. Up to date: the document generated again from the data (scripts/describe_structure.py) is the same, but for
   its date.
2. TACO's numbers (section 2), counted again with rdflib from the export file on GitHub, not from Fuseki.
3. URI patterns (section 4): every URI of every kind follows its pattern.
4. Schema (section 5): each arrow of the class diagram is used in the data, with a subject of the source class
   and an object of the target class or datatype, asked of Fuseki.
5. Example (section 6): each arrow of the instance diagram is a triple of the export file.
6. Foods in common (section 10): the classes TACO and NEVO share, counted with another query
   (scripts/competency_questions.py).
7. Links: each file the document links on GitHub is in origin/main, and each other repository exists.
8. Mutants: a document with a number changed, a URI count changed, or an arrow added must fail checks 2, 3, 4
   and 5.

    $env:PYTHONPATH = "src"; python verification/structure_check.py --nicekg C:/path/to/nicekg_processing
"""

from __future__ import annotations

import argparse
import importlib.util
import re
import subprocess
import sys
from pathlib import Path

from rdflib import RDF, Graph, Literal, URIRef

from taco_rdf import sparql
from taco_rdf.namespaces import FIO as FIO_NS
from taco_rdf.namespaces import OM as OM_NS

ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "docs" / "structure.md"
EXPORT = ROOT / "docs" / "taco-in-nice-food" / "files" / "knowledge-graph" / "taco_nice_food.ttl"


def load(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ds = load("describe_structure")
OBO, FIO, OM = ds.OBO, str(FIO_NS), str(OM_NS)
TACO_NS = "https://w3id.org/taco-rdf/vocab#"
NODE = {  # what a node of the schema diagram means, as a SPARQL constraint on ?X
    "FoodItem": "?X a fio:FoodItem .", "Value": "?X a fio:NutritionalValue .",
    "Nutrient": "?X a fio:Nutrient .",
    "Measure": "?X a om:Measure .", "Unit": f'FILTER (isIRI(?X) && STRSTARTS(STR(?X), "{OM}"))',
    "Status": "VALUES ?X { taco:Measured taco:Trace taco:NotApplicable taco:UnderReevaluation }",
    "Source": "FILTER isIRI(?X)", "Label": 'FILTER (isLiteral(?X) && LANG(?X) != "")',
    "Number": "FILTER isNumeric(?X)", "UnitText": 'FILTER (isLiteral(?X) && !isNumeric(?X) && LANG(?X) = "")',
    "Version": 'FILTER (isLiteral(?X) && LANG(?X) != "")'}


def section(doc: str, number: int) -> str:
    match = re.search(rf"(?ms)^## {number}\. .*?(?=^## \d+\. |\Z)", doc)
    return match.group(0) if match else ""


def mermaid_edges(block: str) -> list[tuple[str, str, str]]:
    return re.findall(r"^\s*(\w+) -->\|([^|]+)\| (\w+)\s*$", block, re.M)


def expand(term: str) -> str:
    prefix, local = term.split(":", 1)
    for p, ns, _ in ds.NAMESPACES:
        if p == prefix:
            return ns + local
    return {"rdf": str(RDF)}[prefix] + local


def taco_numbers(g: Graph) -> dict[str, int]:
    """Section 2's TACO column, counted with rdflib from the export file."""
    fio, om = lambda t: URIRef(FIO + t), lambda t: URIRef(OM + t)
    foods = set(g.subjects(URIRef("http://purl.org/dc/terms/isVersionOf"), URIRef(ds.TACO)))
    values = {v for f in foods for v in g.objects(f, fio("hasNutritionalValue"))}

    def cdno(v: object) -> bool:
        return any(str(t).startswith(OBO + "CDNO_") for t in g.objects(v, RDF.type))

    return {"food items": len(foods),
            "with a FoodOn type": sum(any(str(t).startswith(OBO + "FOODON_") for t in g.objects(f, RDF.type))
                                      for f in foods),
            "nutritional values": len(values), "values with a CDNO class": sum(cdno(v) for v in values),
            "values with a number": sum((v, om("hasValue"), None) in g for v in values),
            "values with a status instead": sum((v, URIRef(TACO_NS + "valueStatus"), None) in g
                                                for v in values),
            "calculated values (PROV)": sum((v, URIRef("http://www.w3.org/ns/prov#wasDerivedFrom"), None) in g
                                            for v in values),
            "nutrients": len({n for v in values for n in g.objects(v, fio("hasNutrient"))}),
            "CDNO classes": len({t for v in values for t in g.objects(v, RDF.type)
                                 if str(t).startswith(OBO + "CDNO_")})}


def check_numbers(doc: str, counted: dict[str, int]) -> list[str]:
    table = dict(re.findall(r"^\| ([^|]+?) \| ([\d,]+) \| [\d,]+ \|$", section(doc, 2), re.M))
    return [f"section 2, {k}: the document says {table.get(k)}, the file has {v:,}"
            for k, v in counted.items() if table.get(k, "").replace(",", "") != str(v)]


def check_patterns(doc: str) -> list[str]:
    found = re.findall(r"\| ([\d,]+) of ([\d,]+) \|$", section(doc, 4), re.M)
    out = [f"section 4: {a} of {b} URIs follow their pattern" for a, b in found if a != b]
    return out if found else ["section 4: no URI counts found"]


def ask(endpoint: str, query: str) -> bool:
    return sparql.ask(ds.PREFIXES + query, endpoint)


def check_schema(doc: str, endpoint: str) -> tuple[list[str], int]:
    block = re.search(r"```mermaid\n(.*?)```", section(doc, 5), re.S)
    edges = mermaid_edges(block.group(1)) if block else []
    out = []
    for s, p, o in edges:
        if s not in NODE or o not in NODE:
            out.append(f"section 5: unknown node in {s} {p} {o}")
            continue
        query = (f"ASK {{ {NODE[s].replace('?X', '?s')} ?s <{expand(p)}> ?o . "
                 f"{NODE[o].replace('?X', '?o')} }}")
        if not ask(endpoint, query):
            out.append(f"section 5: no data for {s} {p} {o}")
    return out, len(edges)


def check_example(doc: str, g: Graph) -> tuple[list[str], int]:
    block = re.search(r"```mermaid\n(.*?)```", section(doc, 6), re.S)
    text = block.group(1) if block else ""
    nodes = re.findall(r'^\s*(n\d+)\(?\["(.*?)"\]\)?\s*$', text, re.M)
    labels = {i: html.split("<br/>")[0] for i, html in nodes}
    out = []
    edges = mermaid_edges(text)
    for s, p, o in edges:
        subject = URIRef(expand(labels[s]))
        obj_label = labels[o].replace("&quot;", '"')
        obj = (Literal(obj_label.strip('"')) if obj_label.startswith('"') else URIRef(expand(obj_label)))
        found = any(str(x) == str(obj) for x in g.objects(subject, URIRef(expand(p))))
        if not found:
            out.append(f"section 6: the file has no triple {labels[s]} {p} {labels[o]}")
    return out, len(edges)


def check_shared(doc: str, endpoint: str) -> list[str]:
    cq = load("competency_questions")
    shared = cq.ask(endpoint, cq.SHARED)
    m = re.search(r"share a FoodOn class \(([\d,]+) classes\)", section(doc, 10))
    if not m:
        return ["section 10: no count of shared classes"]
    return [] if int(m.group(1).replace(",", "")) == len(shared) else \
        [f"section 10: {m.group(1)} shared classes in the document, {len(shared)} by the other query"]


def check_links(doc: str, strict: bool) -> tuple[list[str], list[str]]:
    subprocess.run(["git", "-C", str(ROOT), "fetch", "--quiet", "origin"], check=False)
    tree = set(subprocess.run(["git", "-C", str(ROOT), "ls-tree", "-r", "--name-only", "origin/main"],
                              capture_output=True, text=True).stdout.split())
    paths = sorted(set(re.findall(r"https://github\.com/Victoria125/taco-rdf/blob/main/([^)\s]+)", doc)))
    missing = [p for p in paths if p not in tree]
    repos = sorted(set(re.findall(r"\((https://github\.com/(?!Victoria125)[\w.-]+/[\w.-]+)\)", doc)))
    gone = [r for r in repos if subprocess.run(["git", "ls-remote", "--exit-code", r, "HEAD"],
                                               capture_output=True).returncode != 0]
    problems = [f"repository not found: {r}" for r in gone]
    notes = [f"not on GitHub yet (commit and push it): {p}" for p in missing]
    return problems + (notes if strict else []), ([] if strict else notes)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--endpoint", default=ds.ENDPOINT)
    p.add_argument("--nicekg", type=Path, help="the clone of rivm-syso/nicekg_processing the document used")
    p.add_argument("--require-pushed", action="store_true", help="fail when a linked file is not on GitHub")
    args = p.parse_args()
    doc = DOC.read_text(encoding="utf-8")
    problems: list[str] = []

    fresh, fresh_summary = ds.build_all(args.endpoint, args.nicekg)
    summary = ds.SUMMARY.read_text(encoding="utf-8") if ds.SUMMARY.is_file() else ""
    for name, old, new in (("docs/structure.md", doc, fresh), ("docs/summary.md", summary, fresh_summary)):
        undated = [re.sub(r"Generated on \S+", "Generated on", t) for t in (old, new)]
        pairs = zip(undated[0].splitlines(), undated[1].splitlines(), strict=False)
        differ = [i for i, (a, b) in enumerate(pairs) if a != b]
        if differ or len(undated[0].splitlines()) != len(undated[1].splitlines()):
            problems.append(f"1. {name} is not up to date with the data (first difference at line "
                            f"{differ[0] + 1 if differ else 'end'}); run scripts/describe_structure.py")
    print(f"1. structure.md and summary.md up to date with the data: {not problems}")
    words = len(summary.split())
    if words > 1000:
        problems.append(f"1. docs/summary.md has {words} words, more than two pages")
    print(f"1. summary.md: {words} words (at most 1,000, two pages)")

    g = Graph().parse(EXPORT, format="turtle")
    counted = taco_numbers(g)
    found = check_numbers(doc, counted)
    problems += found
    print(f"2. TACO's numbers counted from the file on GitHub: {len(counted)} checked, {len(found)} differ")
    found = check_patterns(doc)
    problems += found
    print(f"3. URI patterns: {len(found)} kinds with URIs off their pattern")
    found, n = check_schema(doc, args.endpoint)
    problems += found
    print(f"4. schema diagram: {n} arrows, {len(found)} without data")
    found, n = check_example(doc, g)
    problems += found
    print(f"5. example diagram: {n} arrows, {len(found)} not in the export file")
    found = check_shared(doc, args.endpoint)
    problems += found
    print(f"6. foods in common, by another query: {len(found)} differences")
    found, notes = check_links(doc, args.require_pushed)
    problems += found
    print(f"7. links: {len(found)} problems" + (f"; {len(notes)} files still to push" if notes else ""))
    for note in notes:
        print(f"   {note}")

    mutants = [("a TACO count changed", lambda d: d.replace("| food items | 597 |", "| food items | 598 |"),
                lambda d: check_numbers(d, counted)),
               ("a URI count changed", lambda d: d.replace("597 of 597", "596 of 597"), check_patterns),
               ("an arrow added to the schema", lambda d: d.replace(
                   "  Measure -->|om:hasUnit| Unit",
                   "  Measure -->|om:hasUnit| Unit\n  Measure -->|fio:hasNutrient| Unit"),
                lambda d: check_schema(d, args.endpoint)[0]),
               ("an arrow added to the example", lambda d: re.sub(
                   r"(  (n\d+) -->\|fio:hasNutritionalValue\| (n\d+)\n)",
                   r"\1  \3 -->|fio:hasNutrient| \2\n", d, count=1),
                lambda d: check_example(d, g)[0])]
    for name, mutate, check in mutants:
        mutant = mutate(doc)
        if mutant == doc:
            problems.append(f"8. mutant '{name}' did not change the document")
        elif not check(mutant):
            problems.append(f"8. mutant '{name}' was not caught")
        else:
            print(f"8. mutant '{name}': changed the document, and the check caught it")
    for problem in problems:
        print(f"PROBLEM: {problem}")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
