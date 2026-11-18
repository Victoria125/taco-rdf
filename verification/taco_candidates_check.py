"""Check the TACO FoodOn candidates of scripts/taco_foodon_candidates.py; measure how often they are right.

1. Structure: the sheet holds exactly the foods without a FoodOn type, each once, none already typed, with
   in_round_1 as round 1's sample says.
2. A second implementation of the rule: which candidate classes have a whole organism or plant among their
   ancestors is asked of Fuseki again with a different query, and usable_classes is recomputed from it.
3. A second source: for every name match, the FoodOn in Fuseki must give the class the label of the pinned
   index.
4. Known answers, leaving one out: each of the 311 typed foods goes through the same sources as if it had no
   type, itself left out of the neighbours. How often its type is among the usable candidates, or a parent or
   child of one, estimates how often a reviewer finds the right class in the sheet. The existing types were
   found partly by name matching, so the name source may score higher here than on the untyped foods.
5. Lean: the foods and the rule flags of their usable classes go to build/verification/TacoCandidates.lean,
   with theorems stating the counts the script printed and that every usable class passes the publication
   rule; Lean with Mathlib checks them.

    $env:PYTHONPATH = "src"; python verification/taco_candidates_check.py --lake-project C:/path/to/project
"""

from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "verification"))
import taco_typing_state as state  # noqa: E402

SHEET = ROOT / "build" / "taco" / "foodon_round2" / "candidates.csv"
OUT = ROOT / "build" / "verification" / "TacoCandidates.lean"
OBO = "http://purl.obolibrary.org/obo/"
CLAIMS = {"foods": 286, "in_round1": 90, "any_candidate": 249, "usable": 242, "usable_not_in_round1": 171}


def load(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def split(value: str) -> set[str]:
    return {c.strip() for c in value.split(";") if c.strip()}


def ancestors(curies: set[str]) -> dict[str, set[str]]:
    """Every class's ancestors in Fuseki's FoodOn, the class itself included."""
    out: dict[str, set[str]] = {c: {c} for c in curies}
    items = sorted(curies)
    for i in range(0, len(items), 100):
        values = " ".join(f"<{OBO}{c}>" for c in items[i:i + 100])
        for b in state.sparql("PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#> SELECT ?c ?a WHERE { "
                              f"VALUES ?c {{ {values} }} ?c rdfs:subClassOf* ?a . FILTER isIRI(?a) }}"):
            out[b["c"]["value"].removeprefix(OBO)].add(b["a"]["value"].removeprefix(OBO))
    return out


def fuseki_labels(curies: set[str]) -> dict[str, set[str]]:
    out: dict[str, set[str]] = {}
    items = sorted(curies)
    for i in range(0, len(items), 150):
        values = " ".join(f"<{OBO}{c}>" for c in items[i:i + 150])
        for b in state.sparql("PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#> SELECT ?c ?l WHERE { "
                              f"VALUES ?c {{ {values} }} ?c rdfs:label ?l }}"):
            out.setdefault(b["c"]["value"].removeprefix(OBO), set()).add(b["l"]["value"].lower())
    return out


def leave_one_out(step1, endpoint: str, ols_cache: dict) -> list[dict]:
    """The candidates each typed TACO food would get without its type, by source."""
    labels = step1.tbca.foodon_labels(step1.tbca.CLASSES)
    folded = step1.nevo.foodon_labels()
    names = {int(r["food_number"]): r for r in step1.read(step1.NAMES)}
    typed = [{"food_number": int(r["food_number"]), "name_en": names[int(r["food_number"])]["name_en"],
              "classes": [(step1.curie(r["target_iri"]), r["target_label"])]}
             for r in step1.read(step1.TYPES)]
    nevo_typed = [f for f in step1.nevo.nevo_foods(endpoint) if f["classes"]]
    out = []
    for food in typed:
        name = food["name_en"]
        others = [t for t in typed if t["food_number"] != food["food_number"]]
        taco_near = step1.nevo.neighbours(name, others, n=1)
        nevo_near = step1.nevo.neighbours(name, nevo_typed)
        sources = {"name": {step1.name_candidate(name, labels, folded)[0]} - {""},
                   "taco_neighbour": {o["classes"][0][0] for _, o in taco_near},
                   "nevo_neighbour": {c for _, o in nevo_near for c, _ in o["classes"]},
                   "ols": {h["short_form"] for h in step1.nevo.ols_search(name, ols_cache, 0.3)[1][:3]}}
        out.append({"food": food["food_number"], "truth": food["classes"][0][0], "sources": sources})
    return out


def lean_data(rows: list[dict], flags: dict[str, tuple[bool, bool]]) -> str:
    def b(x: bool) -> str:
        return "true" if x else "false"
    entries = []
    for r in rows:
        usable = ", ".join(f"({b(flags[c][0])}, {b(flags[c][1])})"
                           for c in sorted(split(r["usable_classes"])))
        entries.append(f"⟨{r['food_number']}, {b(r['in_round_1'] == 'True')}, {b(r['any'])}, [{usable}]⟩")
    body = ",\n  ".join(entries)
    nums = ", ".join(r["food_number"] for r in rows)
    c = CLAIMS
    return f"""

/-! ## The candidates for the TACO foods without a type, from verification/taco_candidates_check.py -/

namespace TacoCandidates
open TacoTyping

set_option maxRecDepth 100000

/-- A food of the sheet; each usable class as (in the pinned release, has an organism ancestor), as
    recomputed independently of the script. -/
structure Food where
  num : Nat
  round1 : Bool
  anyCandidate : Bool
  usable : List (Prod Bool Bool)

def foods : List Food := [
  {body}]

/-- The sheet holds exactly the untyped foods of analysis/data/foodon_typing_gaps.csv, in order. -/
theorem exactly_the_untyped : foods.map (·.num) = [{nums}] := by decide

/-- Every class the script calls usable passes the publication rule. -/
theorem usable_passes_rule : foods.all (fun f => f.usable.all (fun u => published .type u.1 u.2)) = true := by
  decide

theorem n_foods : foods.length = {c['foods']} := by decide
theorem n_round1 : (foods.filter (·.round1)).length = {c['in_round1']} := by decide
theorem n_any : (foods.filter (·.anyCandidate)).length = {c['any_candidate']} := by decide
theorem n_usable : (foods.filter (fun f => !f.usable.isEmpty)).length = {c['usable']} := by decide
theorem n_usable_not_round1 :
    (foods.filter (fun f => !f.usable.isEmpty && !f.round1)).length = {c['usable_not_in_round1']} := by decide

end TacoCandidates
"""


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--lake-project", type=Path, default=ROOT / "verification" / "lean",
                   help="a Lake project with Mathlib built (default verification/lean)")
    p.add_argument("--endpoint", default=state.ENDPOINT)
    p.add_argument("--no-mutants", action="store_true", help="skip the mutation tests of the Lean file")
    args = p.parse_args()
    step1 = load("taco_foodon_candidates")
    with SHEET.open(encoding="utf-8-sig") as fh:
        rows = list(csv.DictReader(fh, delimiter=";"))
    problems = []

    # 1. Structure
    gaps = [int(r["food_number"]) for r in step1.read(step1.GAPS)]
    typed = {int(r["food_number"]) for r in step1.read(step1.TYPES)}
    round1 = {int(r["food_number"]) for r in step1.read(step1.ROUND_1)}
    nums = [int(r["food_number"]) for r in rows]
    if nums != gaps:
        problems.append("the sheet's foods are not exactly the untyped foods")
    if set(nums) & typed:
        problems.append(f"typed foods in the sheet: {sorted(set(nums) & typed)}")
    if any((r["in_round_1"] == "True") != (int(r["food_number"]) in round1) for r in rows):
        problems.append("in_round_1 disagrees with round 1's sample")
    print(f"1. structure: {len(rows)} foods, exactly the untyped ones: {nums == gaps}, none typed: "
          f"{not set(nums) & typed}")

    # 2. The rule, again
    pinned = state.pinned_release()
    every = set().union(*(step1.classes_in(r) for r in rows))
    blocked = {c.removeprefix(OBO) for c in state.with_organism_ancestor({OBO + c for c in every})}
    flags = {c: (OBO + c in pinned, c in blocked) for c in every}
    def passes(c: str) -> bool:
        return flags[c][0] and not flags[c][1]

    differ = [r["food_number"] for r in rows
              if split(r["usable_classes"]) != {c for c in step1.classes_in(r) if passes(c)}]
    if differ:
        problems.append(f"usable_classes differs from the recomputed rule for foods {differ[:10]}")
    print(f"2. rule recomputed for {len(every)} classes ({len(blocked)} with an organism ancestor): "
          f"{len(differ)} foods differ")

    # 3. Name matches against Fuseki's FoodOn
    named = {r["name_class"]: r["name_label"].lower() for r in rows if r["name_class"]}
    in_fuseki = fuseki_labels(set(named))
    mismatch = [c for c, label in named.items() if label not in in_fuseki.get(c, set())]
    if mismatch:
        problems.append(f"name matches whose label Fuseki does not give: {mismatch[:10]}")
    print(f"3. name matches: {len(named)} classes, {len(mismatch)} labels differ from Fuseki")

    # 4. Known answers
    cache_path = SHEET.parent / "ols_cache.json"
    cache = json.loads(cache_path.read_text(encoding="utf-8")) if cache_path.is_file() else {}
    known = leave_one_out(step1, args.endpoint, cache)
    cache_path.write_text(json.dumps(cache, ensure_ascii=False, indent=1), encoding="utf-8")
    classes = {k["truth"] for k in known} | {c for k in known for s in k["sources"].values() for c in s}
    up = ancestors(classes)
    blocked_known = {c.removeprefix(OBO) for c in state.with_organism_ancestor({OBO + c for c in classes})}
    hits: Counter = Counter()
    for k in known:
        t = k["truth"]
        use = {s: {c for c in cs if OBO + c in pinned and c not in blocked_known}
               for s, cs in k["sources"].items()}
        every_use = set().union(*use.values())
        for s, cs in use.items():
            hits[s] += t in cs
        hits["any: the type itself"] += t in every_use
        hits["any: the type, a parent or a child"] += any(t in up.get(c, {c}) or c in up.get(t, {t})
                                                         for c in every_use)
        hits["any usable candidate"] += bool(every_use)
    print(f"4. known answers, {len(known)} typed foods with their type hidden:")
    for key, n in hits.items():
        print(f"   {key:36} {n:4}  ({100 * n / len(known):.0f}%)")

    # 5. Lean
    for r in rows:
        r["any"] = bool(step1.classes_in(r))
    base = (ROOT / "verification" / "lean" / "TacoTyping.lean").read_text(encoding="utf-8")
    state.write_lean(OUT, base + lean_data(rows, flags))
    print(f"5. wrote {OUT}; checking with Lean")
    code = state.check_with_lean(OUT, args.lake_project)
    if not args.no_mutants:
        problems += state.mutants_rejected(OUT, args.lake_project, [
            ("a usable count off by one",
             rf"(\(foods\.filter \(fun f => !f\.usable\.isEmpty\)\)\.length = ){CLAIMS['usable']}",
             rf"\g<1>{CLAIMS['usable'] + 1}"),
            ("a blocked class among the usable ones", r"\[\(true, false\)", "[(true, true), (true, false)")])
    for problem in problems:
        print(f"PROBLEM: {problem}")
    return 1 if problems or code else 0


if __name__ == "__main__":
    sys.exit(main())
