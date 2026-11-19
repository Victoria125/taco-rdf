# ruff: noqa: E501
"""Check analysis/nutrient_definitions.md (scripts/nutrient_definitions.py) in independent ways.

1. Transcription: each INFOODS tagname and each method phrase the script takes from TACO's printed table is in
   the PDF's text, on the page the script gives (whitespace and case ignored).
2. Two readers: the data tests, the units and the counts of values per code, read again with rdflib from the files
   (TACO's export, NICE-Food's NEVO graphs), are the ones read from Fuseki.
3. Sodium: NICE-Food's own file has NEVO's sodium under nevonut:nan and none under nevonut:NA.
4. The document is up to date: generated again, it is the same.
5. Lean 4: each nutrient's facts (NEVO has values, units agree, what a data test says, same element or compound)
   go to build/verification/NutrientDefinitions.lean, where the rule is written again; Lean checks that it gives
   each nutrient the verdict the script gave, and the counts.
6. Mutants: the checks above must reject a wrong tagname, a broken data test and a changed verdict, and Lean
   mutants of its file.

    $env:PYTHONPATH = "src;<folder with pypdf>"; python verification/nutrient_definitions_check.py
        --lake-project C:/path/to/lake/project
"""

from __future__ import annotations

import argparse
import csv
import importlib.util
import re
import sys
from pathlib import Path

from pypdf import PdfReader
from rdflib import Graph

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "verification"))
import taco_typing_state as state  # noqa: E402

OUT = ROOT / "build" / "verification" / "NutrientDefinitions.lean"
EXPORT = ROOT / "docs" / "taco-in-nice-food" / "files" / "knowledge-graph" / "taco_nice_food.ttl"
NEVO_FILES = [ROOT / "data" / "external" / "nice-food" / f for f in ("nevo21_graph.ttl", "nevo23_graph.ttl")]


def load(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


nd = load("nutrient_definitions")


def squeeze(text: str) -> str:
    return re.sub(r"\s+", "", text).lower()


def check_transcription(pages: dict[int, str], tagnames: dict[str, str], methods: dict) -> tuple[list[str], int]:
    out, checked = [], 0
    for key, tagname in tagnames.items():
        page = nd.TAGNAME_PAGE[key]
        for tag in tagname.split():
            checked += 1
            if squeeze(f"<{tag}>") not in pages[page]:
                out.append(f"1. {key}: <{tag}> is not on PDF page {page}")
    for key, (page, phrase, _) in methods.items():
        checked += 1
        if squeeze(phrase) not in pages[page]:
            out.append(f"1. {key}: '{phrase}' is not on PDF page {page}")
    for key, (_, evidence, _, _) in nd.COULD_TAKE.items():
        for name in re.findall(r"Quadro 5: ([^;(]+?)(?: \(|$|,)", evidence):
            checked += 1
            if squeeze(name) not in pages[19]:
                out.append(f"1. {key}: '{name}' is not in Quadro 5 (PDF page 19)")
    return out, checked


def compare(a: object, b: object, what: str) -> list[str]:
    return [] if a == b else [f"2. {what}: Fuseki and rdflib differ"]


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--endpoint", default=nd.ENDPOINT)
    p.add_argument("--lake-project", type=Path, default=ROOT / "verification" / "lean")
    p.add_argument("--no-lean", action="store_true")
    args = p.parse_args()
    problems: list[str] = []

    reader = PdfReader(nd.PDF)
    pages = {i: squeeze(reader.pages[i - 1].extract_text() or "") for i in (16, 17, 18, 19, 20, 21)}
    found, checked = check_transcription(pages, nd.TAGNAMES, nd.METHODS)
    problems += found
    print(f"1. transcription from TACO's PDF: {checked} tagnames, phrases and names checked, {len(found)} not found")

    fuseki = {t: nd.from_fuseki(args.endpoint, t) for t in ("TACO", "NEVO")}
    nevo_graph = Graph()
    for f in NEVO_FILES:
        nevo_graph.parse(f, format="turtle")
    files = {"TACO": nd.from_graph(Graph().parse(EXPORT, format="turtle"), "TACO"),
             "NEVO": nd.from_graph(nevo_graph, "NEVO")}
    results = {name: nd.tests(src["TACO"][0], src["NEVO"][0]) for name, src in (("Fuseki", fuseki), ("rdflib", files))}
    found = compare(results["Fuseki"], results["rdflib"], "data tests")
    for t in ("TACO", "NEVO"):
        found += compare(fuseki[t][1], files[t][1], f"{t} units") + compare(fuseki[t][2], files[t][2], f"{t} values per code")
    found += compare(nd.protein_ratios(fuseki["NEVO"][0]), nd.protein_ratios(files["NEVO"][0]), "NEVO protein ratios")
    problems += found
    print(f"2. Fuseki against rdflib on the files: {len(results['rdflib'])} tests, units and counts of 2 tables, "
          f"{len(found)} differ")
    for name, r in results["rdflib"].items():
        print(f"   {name.split(':')[0]:13} NEVO {r['NEVO'][0]:,} of {r['NEVO'][1]:,}, TACO {r['TACO'][0]:,} of {r['TACO'][1]:,}")

    nan, na = files["NEVO"][2].get("nan", 0), files["NEVO"][2].get("NA", 0)
    if not (nan > 0 and na == 0):
        problems.append(f"3. NICE-Food's file has {nan} sodium values under nan and {na} under NA")
    print(f"3. NICE-Food's NEVO files: {nan:,} values under nevonut:nan, {na} under nevonut:NA")

    rows, _own, text = nd.build(args.endpoint)
    with nd.OUT_CSV.open(encoding="utf-8", newline="") as fh:
        written = list(csv.DictReader(fh))
    if text != nd.OUT_MD.read_text(encoding="utf-8") or written != rows:
        problems.append("4. analysis/nutrient_definitions.md or its CSV is not up to date; run scripts/nutrient_definitions.py")
    print(f"4. the document and the CSV are up to date: {not any(x.startswith('4.') for x in problems)}")

    # The facts behind each verdict, for Lean and the mutants.
    tests_say = {name: nd.test_says(name, results["rdflib"], nd.protein_ratios(files["NEVO"][0])[0])
                 for name in {nd.TEST_OF[k] for k in nd.TEST_OF}}
    facts = []
    for r in rows:
        key, test = r["taco_nutrient"], r["test"]
        facts.append({"key": key, "nevo": int(r["nevo_values"]) > 0, "units": r["taco_unit"] == r["nevo_unit"],
                      "test": {"same": 1, "differs": 2}.get(tests_say.get(test, ""), 0) if test else 0,
                      "element": key in nd.BY_DEFINITION, "verdict": nd.VERDICTS.index(r["verdict"])})

    def rule(f: dict) -> int:  # the rule written again, independently of nd.verdict
        if not f["nevo"]:
            return 4
        if not f["units"]:
            return 2
        if f["test"]:
            return 0 if f["test"] == 1 else 3
        return 1 if f["element"] else 5

    off = [f["key"] for f in facts if rule(f) != f["verdict"]]
    problems += [f"5. {k}: the rule written again gives another verdict" for k in off]
    print(f"5. the rule written again in the check: {len(facts) - len(off)} of {len(facts)} verdicts the same")

    mutants = [
        ("a wrong tagname", lambda: check_transcription(pages, {**nd.TAGNAMES, "protein": "PROT"}, nd.METHODS)[0]),
        ("a method phrase TACO does not print", lambda: check_transcription(
            pages, nd.TAGNAMES, {**nd.METHODS, "lipids": (16, "extração por Bligh-Dyer", "")})[0]),
        ("NEVO's energy without fibre", lambda: compare(results["Fuseki"], nd.tests(
            fuseki["TACO"][0], {f: {**v, "FIBT": 0.0} for f, v in fuseki["NEVO"][0].items()}), "data tests")),
        ("a changed verdict", lambda: [f["key"] for f in [{**facts[0], "verdict": 5 - facts[0]["verdict"] or 1}]
                                       if rule(f) != f["verdict"]]),
    ]
    for name, run in mutants:
        print(f"6. mutant '{name}': " + ("caught" if run() else "NOT caught"))
        if not run():
            problems.append(f"6. mutant '{name}' was not caught")

    if not args.no_lean:
        entries = ",\n  ".join(
            f'{{ key := "{f["key"]}", nevo := {str(f["nevo"]).lower()}, units := {str(f["units"]).lower()}, '
            f'test := {f["test"]}, element := {str(f["element"]).lower()}, verdict := {f["verdict"]} }}' for f in facts)
        counts = [sum(f["verdict"] == i for f in facts) for i in range(len(nd.VERDICTS))]
        legend = "\n".join(f"  {i} {v}" for i, v in enumerate(nd.VERDICTS))
        state.write_lean(OUT, f"""/-!
# Is TACO's value the same quantity as NEVO's? The verdicts of scripts/nutrient_definitions.py

Generated by verification/nutrient_definitions_check.py. Verdicts:
{legend}
A data test says 0 nothing, 1 the same, 2 differs.
-/

namespace NutrientDefinitions

structure Row where
  key : String
  nevo : Bool
  units : Bool
  test : Nat
  element : Bool
  verdict : Nat

/-- The rule: no NEVO values under the code; else another unit; else what a data test says; else the same
element or compound; else to confirm. -/
def rule (r : Row) : Nat :=
  if !r.nevo then 4 else if !r.units then 2 else if r.test == 1 then 0 else if r.test == 2 then 3
  else if r.element then 1 else 5

def rows : List Row := [
  {entries}]

theorem every_verdict_follows_the_rule : rows.all (fun r => rule r == r.verdict) = true := by decide
theorem counts : (List.range {len(nd.VERDICTS)}).map (fun v => (rows.filter (·.verdict == v)).length) = {counts} := by decide
theorem nutrients : rows.length = {len(facts)} := by decide

end NutrientDefinitions
""")
        print(f"5. wrote {OUT}; checking with Lean")
        if state.check_with_lean(OUT, args.lake_project):
            problems.append("5. Lean rejected the theorems; its mutants were not run")
        else:
            problems += state.mutants_rejected(OUT, args.lake_project, [
                ("a verdict changed", r"(verdict := )3 \}", r"\g<1>0 }"),
                ("a test that says differs read as the same", r"(test := )2(, element)", r"\g<1>1\2"),
                ("NEVO's values found under sodium's code", r"(nevo := )false", r"\g<1>true"),
                ("a count off by one", r"(= \[\d+, )(\d+)", lambda m: f"{m.group(1)}{int(m.group(2)) + 1}"),
            ])
    for problem in problems:
        print(f"PROBLEM: {problem}")
    print("all checks passed" if not problems else f"{len(problems)} problems")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
