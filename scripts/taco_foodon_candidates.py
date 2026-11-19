"""Propose FoodOn types for the TACO foods that have none, for a type-only review round.

311 of TACO's 597 foods have a FoodOn rdf:type (analysis/foodon_typing.md). For each of the other 286 this
script gathers candidates from five sources:
- history: the candidate the alignment inputs keep for the food, with why the build cannot use it as a type
  (analysis/data/foodon_typing_gaps.csv);
- name: TACO's English name (data/labels/food_names_en.csv) rewritten as FoodOn labels are written, by the
  rules of scripts/tbca_foodon_candidates.py ("Rice, brown, cooked" as "brown rice (cooked)") and then of
  scripts/nevo_foodon_candidates.py, and matched exactly against the pinned FoodOn release;
- TACO neighbour: the FoodOn type of the typed TACO food whose English name shares most words with it;
- NEVO neighbours: the FoodOn classes NICE-Food gives the two most similar NEVO foods;
- OLS: EBI's Ontology Lookup Service, searching FoodOn.
Every class is checked against the pinned release and, in Fuseki, for a whole organism or plant among its
ancestors, which the build refuses as a type (docs/foodon-typing.md); usable_classes lists the candidates
that pass both. in_round_1 marks the foods that round 1 sampled, which its adjudication may type first.

With --all-foods the sheet covers all 597 foods, for round 3 (docs/alignment-review-v3.md), and goes to
build/taco/foodon_round3/. The 311 typed foods are searched blind: they get no history candidate, which is
where their type came from, and a food is never its own TACO neighbour, so their type is among the
candidates only when a search finds it again.

This is retrieval, not mapping: reviewers decide, and nothing is typed from a candidate. The sheet is
separated by semicolons, as Excel reads CSV in Portuguese. It holds NEVO's food names, which NEVO's
conditions of use do not let this project redistribute, so it goes to build/, which git ignores.

    $env:PYTHONPATH = "src"; python scripts/taco_foodon_candidates.py --ols [--all-foods]
"""

from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import sys
from pathlib import Path

from taco_rdf import sparql
from taco_rdf.namespaces import BUILD_DIR, ROOT

ENDPOINT = sparql.endpoint()
OUT_DIR = BUILD_DIR / "taco" / "foodon_round2"
OUT_DIR_ALL = BUILD_DIR / "taco" / "foodon_round3"
HISTORY = ("history_relation", "history_class", "history_label", "history_obstacle")
GAPS = ROOT / "analysis" / "data" / "foodon_typing_gaps.csv"
TYPES = ROOT / "analysis" / "data" / "foodon_types.csv"
NAMES = ROOT / "data" / "labels" / "food_names_en.csv"
ROUND_1 = ROOT / "data" / "alignment" / "review" / "round-1" / "items.csv"
OBO = "http://purl.obolibrary.org/obo/"


def load(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


tbca = load("tbca_foodon_candidates")
nevo = load("nevo_foodon_candidates")


def curie(iri: str) -> str:
    return iri.strip().removeprefix(OBO)


def read(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def old_round_1() -> set[int]:
    """The foods a round under protocol 1 sampled, if review/round-1 holds one; a type-only review
    (protocol 3) in that folder is no such round."""
    manifest = ROUND_1.parent / "manifest.json"
    if not manifest.is_file():
        return set()
    if json.loads(manifest.read_text(encoding="utf-8")).get("protocol_version") != 1:
        return set()
    return {int(r["food_number"]) for r in read(ROUND_1)}


def name_candidate(name_en: str, labels: dict, folded: dict) -> tuple[str, str, str]:
    """The first FoodOn label TACO's English name gives, by TBCA's comma rules, then NEVO's word rules."""
    found = tbca.candidate(name_en, labels)
    return found if found[0] else nevo.lexical(name_en, folded)


def classes_in(row: dict[str, str]) -> set[str]:
    """Every FoodOn class a sheet row proposes, from any source."""
    out = set()
    for key, value in row.items():
        if key.endswith("_class"):
            out |= {c.strip() for c in value.replace("|", ";").split(";") if c.strip()}
    return out


def usable(classes: set[str], pinned: set[str], blocked: set[str]) -> list[str]:
    """The classes the build could publish as a type: in the pinned release, no organism ancestor."""
    return sorted(c for c in classes if c in pinned and c not in blocked)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--endpoint", default=ENDPOINT, help=f"nicefood Fuseki endpoint (default {ENDPOINT})")
    p.add_argument("--ols", action="store_true", help="also search FoodOn in EBI's OLS (cached)")
    p.add_argument("--delay", type=float, default=0.3, help="seconds between OLS requests")
    p.add_argument("--all-foods", action="store_true",
                   help=f"all 597 foods, the typed ones blind, for round 3 (default folder {OUT_DIR_ALL})")
    p.add_argument("--out", type=Path, help=f"folder to write (default {OUT_DIR})")
    args = p.parse_args()
    args.out = args.out or (OUT_DIR_ALL if args.all_foods else OUT_DIR)
    labels = tbca.foodon_labels(tbca.CLASSES)
    folded = nevo.foodon_labels()
    pinned = {c for c, _ in labels.values() if c.startswith("FOODON_")}
    names = {int(r["food_number"]): r for r in read(NAMES)}
    round1 = old_round_1()
    typed = [{"food_number": int(r["food_number"]), "name_en": names[int(r["food_number"])]["name_en"],
              "classes": [(curie(r["target_iri"]), r["target_label"])]} for r in read(TYPES)]
    nevo_typed = [f for f in nevo.nevo_foods(args.endpoint) if f["classes"]]
    args.out.mkdir(parents=True, exist_ok=True)
    cache_path = args.out / "ols_cache.json"
    cache = json.loads(cache_path.read_text(encoding="utf-8")) if cache_path.is_file() else {}
    entries = [{"food_number": int(g["food_number"]), "name_pt": g["name_pt"], "group": g["group"],
                "history_relation": g["candidate_predicate"],
                "history_class": "; ".join(curie(c) for c in g["candidate_iri"].split(" | ") if c),
                "history_label": g["candidate_label"].replace(" | ", "; "),
                "history_obstacle": g["candidate_obstacle"].replace(" | ", "; ")} for g in read(GAPS)]
    if args.all_foods:  # the typed foods, blind: no history candidate, which is where their type came from
        entries += [{"food_number": int(t["food_number"]), "name_pt": t["name_pt"], "group": t["group"]}
                    | dict.fromkeys(HISTORY, "") for t in read(TYPES)]
        entries.sort(key=lambda e: e["food_number"])
    rows = []
    for entry in entries:
        n = entry["food_number"]
        name_en = names[n]["name_en"]
        row = {"food_number": n, "name_pt": entry["name_pt"], "name_en": name_en, "group": entry["group"],
               "in_round_1": str(n in round1)} | {k: entry[k] for k in HISTORY}
        row["name_class"], row["name_label"], row["name_rule"] = name_candidate(name_en, labels, folded)
        near = nevo.neighbours(name_en, [t for t in typed if t["food_number"] != n], n=1)  # never itself
        row |= {"taco_neighbour_class": "", "taco_neighbour_label": "", "taco_neighbour_food": "",
                "taco_neighbour_score": ""}
        if near:
            score, other = near[0]
            cls, label = other["classes"][0]
            row |= {"taco_neighbour_class": cls, "taco_neighbour_label": label,
                    "taco_neighbour_food": other["name_en"], "taco_neighbour_score": score}
        for i in (1, 2):
            row |= {f"nevo_neighbour{i}_class": "", f"nevo_neighbour{i}_label": "",
                    f"nevo_neighbour{i}_food": "", f"nevo_neighbour{i}_score": ""}
        for i, (score, other) in enumerate(nevo.neighbours(name_en, nevo_typed), start=1):
            row |= {f"nevo_neighbour{i}_class": "; ".join(c for c, _ in other["classes"]),
                    f"nevo_neighbour{i}_label": "; ".join(label for _, label in other["classes"]),
                    f"nevo_neighbour{i}_food": other["name_en"], f"nevo_neighbour{i}_score": score}
        if args.ols:
            query, hits = nevo.ols_search(name_en, cache, args.delay)
            row["ols_query"] = query
            for i in (1, 2, 3):
                hit = hits[i - 1] if i <= len(hits) else {}
                row |= {f"ols{i}_class": hit.get("short_form", ""), f"ols{i}_label": hit.get("label", ""),
                        f"ols{i}_in_pinned_release": str(hit["short_form"] in pinned) if hit else ""}
        rows.append(row)
    if args.ols:
        cache_path.write_text(json.dumps(cache, ensure_ascii=False, indent=1), encoding="utf-8")
    blocked = tbca.organism_classes(set().union(*(classes_in(r) for r in rows)), args.endpoint)
    for r in rows:
        found = classes_in(r)
        r["blocked_classes"] = "; ".join(sorted(found & blocked))
        r["usable_classes"] = "; ".join(usable(found, pinned, blocked))
        r |= {"decision": "", "chosen_class": "", "note": ""}
    out = args.out / "candidates.csv"
    with out.open("w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(dict.fromkeys(k for r in rows for k in r)), delimiter=";",
                           lineterminator="\n")
        w.writeheader()
        w.writerows(rows)

    def count(key: str, subset: list[dict] = rows) -> int:
        return sum(1 for r in subset if r.get(key))

    in_round_1 = sum(1 for r in rows if r["in_round_1"] == "True")
    typed_now = {t["food_number"] for t in typed}
    with_type = sum(r["food_number"] in typed_now for r in rows)
    print(f"TACO foods: {len(rows)} ({with_type} with a type, searched blind; {in_round_1} in round 1)")
    print(f"wrote {out}")
    for key in ("history_class", "name_class", "taco_neighbour_class", "nevo_neighbour1_class", "ols1_class"):
        print(f"  {key.removesuffix('_class'):16} {count(key)}")
    print(f"  any candidate    {sum(1 for r in rows if classes_in(r))}")
    print(f"  usable candidate {count('usable_classes')}"
          f" (not in round 1: {count('usable_classes', [r for r in rows if r['in_round_1'] == 'False'])})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
