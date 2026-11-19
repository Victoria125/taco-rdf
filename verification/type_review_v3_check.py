# ruff: noqa: E501
"""Check the type review as prepared: round 1 under protocol 3 (docs/alignment-review-v3.md).

1. Forms: both forms hold all 597 TACO foods, once each and in the same order, with the context of context.csv
   and empty answers.
2. Blind: no typed food has a history candidate, and no file of the round has a column for the current type;
   the share of typed foods whose current type an independent search found again is reported.
3. Candidates: every candidate is a class of the pinned FoodOn release, and none is among the classes the
   candidate sheet blocked (a whole organism or plant among their ancestors).
4. No NEVO name: no cell of the round's files is a NEVO food name, English or Dutch, but FoodOn labels and
   TACO's own food names, which can be the same words ("Honey").
5. Manifest: the checksums of the inputs, the context, the items and the candidate sheet match the files.
6. Lean 4: the food numbers of both forms, the typed and untyped foods, and the typed foods with a history
   candidate go to build/verification/TypeReviewV3.lean, with theorems Lean decides; mutants must be rejected.
7. Mutants: each check above must reject a changed copy of its data.

    $env:PYTHONPATH = "src"; python verification/type_review_v3_check.py --lake-project C:/path/to/lake/project
"""

from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "verification"))
import taco_typing_state as state  # noqa: E402

from taco_rdf import sparql  # noqa: E402
from taco_rdf.evaluation import review_hash  # noqa: E402

ROUND = ROOT / "data" / "alignment" / "review" / "round-1"
SHEET = ROOT / "build" / "taco" / "foodon_round3" / "candidates.csv"
TYPES = ROOT / "analysis" / "data" / "foodon_types.csv"
CLASSES = ROOT / "ontology" / "imports" / "foodon-classes.tsv"
OUT = ROOT / "build" / "verification" / "TypeReviewV3.lean"
SEGMENT = re.compile(r"^(FOODON_\d+) (.*) \[(.*)\]$")


def load(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


prep = load("prepare_type_review")


def read(path: Path, delimiter: str = ",") -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh, delimiter=delimiter))


def candidates_of(row: dict[str, str]) -> list[tuple[str, str, list[str]]]:
    """A form row's candidates: (CURIE, FoodOn label, sources)."""
    out = []
    for seg in (s for s in row["candidates"].split(" | ") if s):
        m = SEGMENT.match(seg)
        out.append((m.group(1), m.group(2), [x.strip() for x in m.group(3).split(",")]) if m else (seg, "", []))
    return out


def check_forms(forms: dict[str, list[dict[str, str]]], context: list[dict[str, str]], numbers: list[int]) -> list[str]:
    out = []
    for name, rows in forms.items():
        got = [int(r["food_number"]) for r in rows]
        if got != numbers:
            out.append(f"1. {name}: {len(got)} rows, not the {len(numbers)} TACO foods once each in order")
        if [{k: r[k] for k in prep.CONTEXT} for r in rows] != context:
            out.append(f"1. {name}: its context is not context.csv")
        if any(r[k] for r in rows for k in prep.ANSWERS):
            out.append(f"1. {name}: holds answers")
        if list(rows[0]) != prep.CONTEXT + prep.ANSWERS:
            out.append(f"1. {name}: columns {list(rows[0])}")
    return out


def check_blind(rows: list[dict[str, str]], typed: dict[int, str], headers: dict[str, list[str]]) -> tuple[list[str], list[int], int]:
    history = [int(r["food_number"]) for r in rows if int(r["food_number"]) in typed
               and any("history" in sources for _, _, sources in candidates_of(r))]
    out = [f"2. typed food {n} has a history candidate" for n in history]
    out += [f"2. {name} has a column for the current type: {h}" for name, cols in headers.items() for h in cols
            if re.search(r"current|typed|type_now|target", h)]
    found = sum(typed[int(r["food_number"])] in {c for c, _, _ in candidates_of(r)}
                for r in rows if int(r["food_number"]) in typed)
    return out, history, found


def check_candidates(rows: list[dict[str, str]], pinned: set[str], blocked: set[str]) -> list[str]:
    out = []
    for r in rows:
        for c, _, _ in candidates_of(r):
            if c not in pinned:
                out.append(f"3. food {r['food_number']}: {c} is not in the pinned release")
            if c in blocked:
                out.append(f"3. food {r['food_number']}: {c} has an organism or plant ancestor")
    return out


def check_nevo_names(cells: list[tuple[str, str]], names: set[str], labels: set[str]) -> tuple[list[str], int]:
    found = [f"4. NEVO name in {where}: {cell}" for where, cell in cells
             if cell.strip().lower() in names and cell.strip().lower() not in labels]
    allowed = sum(cell.strip().lower() in names and cell.strip().lower() in labels for _, cell in cells)
    return found, allowed


def check_manifest(manifest: dict) -> list[str]:
    out = [f"5. {path} changed since the round was prepared" for path, h in manifest["inputs"].items()
           if review_hash(ROOT / path) != h]
    for key, path in (("context_sha256", ROUND / "context.csv"), ("items_sha256", ROUND / "items.csv"),
                      ("candidates_sha256", SHEET)):
        if review_hash(path) != manifest[key]:
            out.append(f"5. {path.name} is not the file the manifest recorded")
    if (manifest["round"], manifest["protocol_version"], manifest["foods"], manifest["sample_size"]) != (1, 3, 597, 597):
        out.append("5. the manifest is not round 1 under protocol 3 with 597 foods for both reviewers")
    return out


def lean_text(form1: list[int], form2: list[int], typed: list[int], untyped: list[int], history: list[int]) -> str:
    def nums(xs: list[int]) -> str:
        return "[" + ",\n  ".join(", ".join(map(str, xs[i:i + 25])) for i in range(0, len(xs), 25)) + "]"

    return f"""/-!
# The type review as prepared (round 1, protocol 3): generated by verification/type_review_v3_check.py
-/

namespace TypeReviewV3

def form1 : List Nat := {nums(form1)}
def form2 : List Nat := {nums(form2)}
def typed : List Nat := {nums(typed)}
def untyped : List Nat := {nums(untyped)}
/-- Typed foods with a history candidate, which would show where their type came from. -/
def historyShown : List Nat := {nums(history)}

theorem form1_every_food : form1 = List.range' 1 597 := by decide +kernel
theorem form2_same_foods : form2 = form1 := by decide +kernel
theorem split : typed.length = {len(typed)} ∧ untyped.length = {len(untyped)} ∧ typed.length + untyped.length = 597 := by decide +kernel
theorem disjoint : typed.all (fun n => !untyped.contains n) = true := by decide +kernel
theorem covers : (List.range' 1 597).all (fun n => typed.contains n || untyped.contains n) = true := by decide +kernel
theorem blind : historyShown = [] := by decide

end TypeReviewV3
"""


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--endpoint", default=sparql.endpoint())
    p.add_argument("--lake-project", type=Path, default=ROOT / "verification" / "lean")
    p.add_argument("--no-lean", action="store_true")
    args = p.parse_args()
    problems: list[str] = []

    forms = {name: read(ROUND / name) for name in ("reviewer-1.csv", "reviewer-2.csv")}
    context = read(ROUND / "context.csv")
    numbers = list(range(1, 598))
    found = check_forms(forms, context, numbers)
    problems += found
    print(f"1. forms: {len(forms['reviewer-1.csv'])} and {len(forms['reviewer-2.csv'])} foods; {len(found)} problems")

    typed = {int(r["food_number"]): r["target_iri"].rsplit("/", 1)[-1] for r in read(TYPES)}
    headers = {path.name: list(read(path)[0]) for path in sorted(ROUND.glob("*.csv"))}
    rows = forms["reviewer-1.csv"]
    found, history, again = check_blind(rows, typed, headers)
    problems += found
    print(f"2. blind: {len(typed)} typed foods, {len(history)} with a history candidate, no column for the "
          f"current type: {not any('column' in x for x in found)}; an independent search found the current "
          f"type again for {again} ({100 * again / len(typed):.0f}%)")

    with CLASSES.open(encoding="utf-8") as fh:
        labels = dict(line.rstrip("\n").split("\t", 1) for line in fh if line.startswith("FOODON_"))
    sheet = read(SHEET, ";")
    blocked = {c.strip() for r in sheet for c in r["blocked_classes"].split(";") if c.strip()}
    found = check_candidates(rows, set(labels), blocked)
    problems += found
    print(f"3. candidates: {sum(len(candidates_of(r)) for r in rows)} listed; {len(found)} outside the release "
          "or blocked")

    nevo = load("nevo_foodon_candidates")
    names = {n.lower() for f in nevo.nevo_foods(args.endpoint) for n in (f["name_en"], f["name_nl"]) if n}
    cells = [(path.name, c) for path in sorted(ROUND.glob("*.csv")) for r in read(path) for k, v in r.items()
             for c in ([label for _, label, _ in candidates_of(r)] if k == "candidates" else [v])]
    cells += [("manifest.json", c) for c in re.findall(r'"([^"]+)"', (ROUND / "manifest.json").read_text(encoding="utf-8"))]
    taco_names = {n.lower() for r in read(ROOT / "data" / "labels" / "food_names_en.csv")
                  for n in (r["name_pt"], r["name_en"])}
    found, allowed = check_nevo_names(cells, names, {v.lower() for v in labels.values()} | taco_names)
    problems += found
    print(f"4. NEVO names: {len(found)} in the review's files; {allowed} FoodOn labels or TACO names that are "
          "also NEVO names")

    manifest = json.loads((ROUND / "manifest.json").read_text(encoding="utf-8"))
    found = check_manifest(manifest)
    problems += found
    print(f"5. manifest: {len(manifest['inputs'])} inputs and 3 files checked; {len(found)} differ")

    first = rows[0]
    mutants = [
        ("a food missing from form 2", lambda: check_forms({**forms, "reviewer-2.csv": forms["reviewer-2.csv"][1:]}, context, numbers)),
        ("an answer already filled", lambda: check_forms({**forms, "reviewer-1.csv": [{**first, "decision": "none"}, *rows[1:]]}, context, numbers)),
        ("a history candidate on a typed food", lambda: check_blind(
            [{**r, "candidates": r["candidates"] + " | FOODON_00001002 food product [history]"}
             if int(r["food_number"]) in typed else r for r in rows[:50]], typed, headers)[0]),
        ("a column for the current type", lambda: check_blind(rows[:1], typed, {**headers, "items.csv": [*headers["items.csv"], "current_type"]})[0]),
        ("a class outside the release", lambda: check_candidates([{**first, "candidates": "FOODON_99999999 nothing [name]"}], set(labels), blocked)),
        ("a NEVO name in a cell", lambda: check_nevo_names([("reviewer-1.csv", next(n for n in sorted(names) if n not in {v.lower() for v in labels.values()}))], names, {v.lower() for v in labels.values()})[0]),
        ("a changed input", lambda: check_manifest({**manifest, "inputs": {**manifest["inputs"], "data/labels/food_names_en.csv": "0" * 64}})),
    ]
    for name, run in mutants:
        caught = bool(run())
        print(f"7. mutant '{name}': {'caught' if caught else 'NOT caught'}")
        if not caught:
            problems.append(f"7. mutant '{name}' was not caught")

    if not args.no_lean:
        typed_list = sorted(typed)
        untyped_list = [n for n in numbers if n not in typed]
        state.write_lean(OUT, lean_text([int(r["food_number"]) for r in rows],
                                        [int(r["food_number"]) for r in forms["reviewer-2.csv"]],
                                        typed_list, untyped_list, history))
        print(f"6. wrote {OUT}; checking with Lean")
        if state.check_with_lean(OUT, args.lake_project):
            problems.append("6. Lean rejected the theorems; its mutants were not run")
        else:
            problems += state.mutants_rejected(OUT, args.lake_project, [
                ("a food twice in form 2", r"(def form2 : List Nat := \[)1, 2", r"\g<1>1, 1"),
                ("a typed food also untyped", r"(def untyped : List Nat := \[)", rf"\g<1>{typed_list[0]}, "),
                ("a history candidate shown", r"def historyShown : List Nat := \[\]", "def historyShown : List Nat := [1]"),
            ])
    for problem in problems:
        print(f"PROBLEM: {problem}")
    print("all checks passed" if not problems else f"{len(problems)} problems")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
