"""Check round 2 of the alignment review (docs/alignment-review-v2.md) as prepared, and its scoring.

1. Structure: reviewer 1's form holds exactly the untyped foods that round 1 did not sample; reviewer 2's
   holds the sample of items.csv; each group's sample is the allocation of manifest.json; the manifest's
   checksums match the files.
2. Candidates: every class on the forms is a usable class of the step-1 sheet for that food, with its label
   in the pinned FoodOn release.
3. No NEVO name: no cell of round 2's files is a NEVO food name (English or Dutch), except FoodOn labels.
4. Scoring, simulated on copies of the forms: identical answers give 100% agreement, kappa 1 and nothing to
   adjudicate; answers that differ give the disagreements counted independently and the kappa of exact
   fractions; a class outside the pinned release, one with an organism ancestor, and none without searched
   terms are refused.
5. Lean: the foods, groups and sample go to build/verification/TypeReviewRound2.lean, with theorems for the
   counts, for no food of round 1, and for each group's sample being within one of its exact quota.

    $env:PYTHONPATH = "src"; python verification/type_review_check.py --lake-project C:/path/to/project
"""

from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import os
import random
import re
import shutil
import subprocess
import sys
import tempfile
from collections import Counter
from fractions import Fraction
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "verification"))
import taco_typing_state as state  # noqa: E402

from taco_rdf.evaluation import review_hash  # noqa: E402

ROUND = ROOT / "data" / "alignment" / "review" / "round-2"
SHEET = ROOT / "build" / "taco" / "foodon_round2" / "candidates.csv"
OUT = ROOT / "build" / "verification" / "TypeReviewRound2.lean"
CLAIMS = {"foods": 196, "sample": 60}


def load(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def read(path: Path, delimiter: str = ",") -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig") as fh:
        return list(csv.DictReader(fh, delimiter=delimiter))


def write(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]), lineterminator="\r\n")
        w.writeheader()
        w.writerows(rows)


def classes_on(form_row: dict[str, str]) -> list[tuple[str, str]]:
    """(class, label) of each candidate on a form row."""
    out = []
    for part in form_row["candidates"].split(" | "):
        m = re.match(r"(FOODON_\d+) (.*) \[[^\]]*\]$", part.strip())
        if m:
            out.append((m.group(1), m.group(2)))
    return out


def exact_kappa(a: list[str], b: list[str]) -> Fraction | None:
    n = len(a)
    ca, cb = Counter(a), Counter(b)
    expected = Fraction(sum(ca[k] * cb[k] for k in ca), n * n)
    observed = Fraction(sum(x == y for x, y in zip(a, b, strict=True)), n)
    return None if expected == 1 else (observed - expected) / (1 - expected)


def run_score(folder: Path, endpoint: str) -> tuple[int, str]:
    command = [sys.executable, str(ROOT / "scripts" / "score_type_review.py"), "--round", str(folder),
               "--endpoint", endpoint]
    result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8",
                            env={**os.environ, "PYTHONPATH": str(ROOT / "src")})
    return result.returncode, result.stdout + result.stderr


def simulate(endpoint: str, blocked_class: str) -> list[str]:
    """Score copies of the forms filled with known answers; return what went wrong."""
    wrong = []
    first, second = read(ROUND / "reviewer-1.csv"), read(ROUND / "reviewer-2.csv")
    rng = random.Random(1)
    for r in first:
        options = [c for c, _ in classes_on(r)]
        r["decision"] = options[0] if options else "none"
        r["searched_terms"] = "" if options else "simulated search"
    by_food = {r["food_number"]: r for r in first}
    with tempfile.TemporaryDirectory() as tmp:
        folder = Path(tmp) / "round-2"
        shutil.copytree(ROUND, folder)
        # identical answers
        same = [by_food[r["food_number"]] for r in second]
        write(folder / "reviewer-1.csv", first)
        write(folder / "reviewer-2.csv", same)
        code, out = run_score(folder, endpoint)
        if code or "exact agreement 100%" not in out or "0 disagreements" not in out:
            wrong.append(f"identical answers: {out.strip()}")
        elif len({r["decision"] for r in same}) > 1 and "kappa 1.00" not in out:
            wrong.append(f"identical answers without kappa 1: {out.strip()}")
        # answers that differ
        other = []
        for r in second:
            options = [c for c, _ in classes_on(r)] + ["none"]
            choice = rng.choice(options)
            terms = "simulated search" if choice == "none" else ""
            other.append(r | {"decision": choice, "searched_terms": terms})
        write(folder / "reviewer-2.csv", other)
        code, out = run_score(folder, endpoint)
        a = [by_food[r["food_number"]]["decision"] for r in other]
        b = [r["decision"] for r in other]
        differ = sum(x != y for x, y in zip(a, b, strict=True))
        k = exact_kappa(a, b)
        if code or f"{differ} disagreements" not in out:
            wrong.append(f"differing answers: expected {differ} disagreements; {out.strip()}")
        if k is not None and f"kappa {float(k):.2f}" not in out:
            wrong.append(f"differing answers: expected kappa {float(k):.2f}; {out.strip()}")
        adjudication = read(folder / "adjudication.csv")
        if len(adjudication) != differ:
            wrong.append(f"adjudication.csv has {len(adjudication)} rows, not {differ}")
        # answers the scorer must refuse
        bad = [dict(r) for r in other]
        bad[0]["decision"], bad[1]["decision"] = "FOODON_99999999", blocked_class
        bad[2] |= {"decision": "none", "searched_terms": ""}
        write(folder / "reviewer-2.csv", bad)
        code, out = run_score(folder, endpoint)
        for expected in ("FOODON_99999999 is not a class of the pinned FoodOn release",
                         f"{blocked_class} has a whole organism or plant among its ancestors",
                         "none without searched_terms"):
            if expected not in out:
                wrong.append(f"not refused: {expected}")
        if code == 0:
            wrong.append("invalid answers were scored")
    return wrong


def lean_data(items: list[dict[str, str]], round1: list[int], allocation: dict[str, int]) -> str:
    gid = {g: i for i, g in enumerate(sorted(allocation))}
    sizes = Counter(r["group"] for r in items)
    def flag(r: dict[str, str]) -> str:
        return "true" if r["in_sample"] == "True" else "false"

    foods = ",\n  ".join(f"⟨{r['food_number']}, {gid[r['group']]}, {flag(r)}⟩" for r in items)
    groups = ", ".join(f"({gid[g]}, {sizes[g]}, {allocation[g]})" for g in sorted(allocation))
    c = CLAIMS
    return f"""

/-! ## Round 2's forms, from verification/type_review_check.py -/

namespace TypeReviewRound2

set_option maxRecDepth 100000

structure Food where
  num : Nat
  group : Nat
  inSample : Bool

def foods : List Food := [
  {foods}]

/-- The untyped foods that round 1 sampled. -/
def round1 : List Nat := [{", ".join(map(str, round1))}]

/-- Each group as (group, foods in round 2, seats in the sample). -/
def groups : List (Prod Nat (Prod Nat Nat)) := [{groups}]

def total : Nat := {c['foods']}
def seats : Nat := {c['sample']}

theorem n_foods : foods.length = total := by decide
theorem n_sample : (foods.filter (·.inSample)).length = seats := by decide
theorem each_food_once : (foods.map (·.num)).Nodup := by decide
theorem no_food_of_round_1 : foods.all (fun f => !round1.contains f.num) = true := by decide
theorem group_sizes :
    groups.all (fun g => (foods.filter (·.group == g.1)).length == g.2.1) = true := by decide
theorem group_seats :
    groups.all (fun g => (foods.filter (fun f => f.group == g.1 && f.inSample)).length == g.2.2) = true := by
  decide
theorem seats_add_up : (groups.map (·.2.2)).sum = seats := by decide
/-- Each group's seats are within one of its exact quota seats · size / total. -/
theorem seats_within_one_of_quota :
    groups.all (fun g =>
      g.2.2 * total < seats * g.2.1 + total && seats * g.2.1 < g.2.2 * total + total) = true := by
  decide

end TypeReviewRound2
"""


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--lake-project", type=Path, default=ROOT / "verification" / "lean",
                   help="a Lake project with Mathlib built (default verification/lean)")
    p.add_argument("--endpoint", default=state.ENDPOINT)
    p.add_argument("--no-mutants", action="store_true", help="skip the mutation tests of the Lean file")
    args = p.parse_args()
    problems = []
    items, first, second = (read(ROUND / f) for f in ("items.csv", "reviewer-1.csv", "reviewer-2.csv"))
    manifest = json.loads((ROUND / "manifest.json").read_text(encoding="utf-8"))
    sheet = {r["food_number"]: r for r in read(SHEET, ";")}

    # 1. Structure
    gaps = [r["food_number"] for r in read(ROOT / "analysis" / "data" / "foodon_typing_gaps.csv")]
    round1_all = {r["food_number"]
                  for r in read(ROOT / "data" / "alignment" / "review" / "round-1" / "items.csv")}
    expected = [n for n in gaps if n not in round1_all]
    if [r["food_number"] for r in first] != expected:
        problems.append("reviewer 1's foods are not the untyped foods outside round 1")
    in_sample = [r["food_number"] for r in items if r["in_sample"] == "True"]
    if [r["food_number"] for r in second] != in_sample:
        problems.append("reviewer 2's foods are not items.csv's sample")
    seats = Counter(r["group"] for r in items if r["in_sample"] == "True")
    if dict(seats) != {g: s for g, s in manifest["allocation"].items() if s}:
        problems.append("the sample per group differs from the manifest's allocation")
    for path, digest in [*manifest["inputs"].items(), (str(SHEET), manifest["candidates_sha256"]),
                         ("data/alignment/review/round-2/context.csv", manifest["context_sha256"]),
                         ("data/alignment/review/round-2/items.csv", manifest["items_sha256"])]:
        if review_hash(ROOT / path) != digest:
            problems.append(f"checksum of {path} differs from the manifest")
    if "hortaliças" not in json.dumps(manifest, ensure_ascii=False):
        problems.append("manifest.json lost its accents")
    print(f"1. structure: reviewer 1 {len(first)} foods, reviewer 2 {len(second)}, "
          f"{len(manifest['inputs']) + 1} checksums compared")

    # 2. Candidates
    with (ROOT / "ontology" / "imports" / "foodon-classes.tsv").open(encoding="utf-8") as fh:
        labels = dict(line.rstrip("\n").split("\t", 1) for line in fh if line.startswith("FOODON_"))
    shown = 0
    for r in first:
        usable = {c.strip() for c in sheet[r["food_number"]]["usable_classes"].split(";") if c.strip()}
        for c, label in classes_on(r):
            shown += 1
            if c not in usable or labels.get(c) != label:
                problems.append(f"food {r['food_number']}: candidate {c} {label!r} is not a usable class "
                                "with its pinned label")
    print(f"2. candidates: {shown} shown, each a usable class with its pinned FoodOn label")

    # 3. No NEVO name
    nevo = load("nevo_foodon_candidates")
    names = {n.lower() for f in nevo.nevo_foods(args.endpoint) for n in (f["name_en"], f["name_nl"]) if n}
    foodon_labels = {v.lower() for v in labels.values()}
    found, allowed = [], []
    for path in sorted(ROUND.iterdir()):
        text = path.read_text(encoding="utf-8")
        cells = ([c for r in read(path) for k, v in r.items() for c in
                  ([seg for _, seg in classes_on(r)] if k == "candidates" else [v])]
                 if path.suffix == ".csv" else re.findall(r'"([^"]+)"', text))
        for cell in cells:
            if cell.strip().lower() in names:
                (allowed if cell.strip().lower() in foodon_labels else found).append(f"{path.name}: {cell}")
    problems += [f"NEVO name in {x}" for x in found]
    print(f"3. NEVO names: {len(found)} in round 2's files; {len(allowed)} FoodOn labels that are also NEVO "
          "names (FoodOn's text)")

    # 4. Scoring, simulated
    blocked_class = next(c for r in sheet.values() for c in r["blocked_classes"].split("; ")
                         if c.strip() in labels)
    wrong = simulate(args.endpoint, blocked_class.strip())
    problems += wrong
    print(f"4. scoring simulated (identical, differing and invalid answers): {len(wrong)} problems")

    # 5. Lean
    round1_untyped = sorted(int(n) for n in gaps if n in round1_all)
    base = (ROOT / "verification" / "lean" / "TacoTyping.lean").read_text(encoding="utf-8")
    state.write_lean(OUT, base + lean_data(items, round1_untyped, manifest["allocation"]))
    print(f"5. wrote {OUT}; checking with Lean")
    code = state.check_with_lean(OUT, args.lake_project)
    if not args.no_mutants:
        problems += state.mutants_rejected(OUT, args.lake_project, [
            ("a food taken out of the sample", r", true⟩", ", false⟩"),
            ("a round-1 food put in round 2", r"def round1 : List Nat := \[",
             f"def round1 : List Nat := [{items[0]['food_number']}, ")])
    shutil.rmtree(ROOT / "verification" / "__pycache__", ignore_errors=True)
    for problem in problems:
        print(f"PROBLEM: {problem}")
    return 1 if problems or code else 0


if __name__ == "__main__":
    sys.exit(main())
