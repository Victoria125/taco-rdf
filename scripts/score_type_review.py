"""Score round 2 of the alignment review (FoodOn types only, docs/alignment-review-v2.md).

Checks every decision of both forms (a CURIE of the pinned FoodOn release, or none; with --endpoint, no whole
organism or plant among the class's ancestors), and on the second reviewer's sample reports exact agreement,
Cohen's kappa (taco_rdf.evaluation.cohen_kappa, as in round 1) and, with --endpoint, near agreement: the same
class, or one an ancestor of the other. The sample foods whose decisions differ go to adjudication.csv.

    $env:PYTHONPATH = "src"; python scripts/score_type_review.py --endpoint http://localhost:3030/nicefood/sparql
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from pathlib import Path

import requests

from taco_rdf.evaluation import cohen_kappa, review_hash
from taco_rdf.namespaces import ROOT
from taco_rdf.type_review import input_path

ROUND = ROOT / "data" / "alignment" / "review" / "round-1"  # the type-only review under protocol 3
CLASSES = ROOT / "ontology" / "imports" / "foodon-classes.tsv"
OBO = "http://purl.obolibrary.org/obo/"
ROOTS = ("COB_0000022", "PO_0000003")


def normal(decision: str) -> str:
    """FOODON_03301449 from FOODON_03301449, FOODON:03301449 or the class IRI; none stays none."""
    d = decision.strip()
    if d.lower() == "none":
        return "none"
    m = re.search(r"FOODON[_:](\d+)", d)
    return f"FOODON_{m.group(1)}" if m else d


def read(path: Path) -> dict[int, dict[str, str]]:
    with path.open(encoding="utf-8-sig") as fh:
        return {int(r["food_number"]): r for r in csv.DictReader(fh)}


CONTEXT = ["food_number", "name_pt", "name_en", "group", "candidates"]


def validate(folder: Path, manifest: dict) -> list[dict[str, str]]:
    """Round 2 as prepared: the recorded inputs unchanged, and each form's context as in context.csv.

    Returns context.csv's rows; raises ValueError otherwise.
    """
    if manifest.get("protocol_version") not in (2, 3) or manifest.get("hash_format") != "sha256-lf-v1":
        raise ValueError("not a round prepared under protocol version 2 or 3 with sha256-lf-v1 checksums")
    changed = [p for p, digest in manifest["inputs"].items()
               if review_hash(input_path(folder, p)) != digest]
    changed += [f"{n}.csv" for n in ("context", "items")
                if review_hash(folder / f"{n}.csv") != manifest[f"{n}_sha256"]]
    if changed:
        raise ValueError("the round's inputs differ from the manifest: " + ", ".join(changed))
    with (folder / "context.csv").open(encoding="utf-8-sig") as fh:
        context = list(csv.DictReader(fh))
    with (folder / "items.csv").open(encoding="utf-8-sig") as fh:
        sample = [r["food_number"] for r in csv.DictReader(fh) if r["in_sample"] == "True"]
    if len(context) != manifest["foods"]:
        raise ValueError("context.csv does not hold the manifest's foods")
    by_food = {r["food_number"]: r for r in context}
    for form, foods in (("reviewer-1.csv", [r["food_number"] for r in context]), ("reviewer-2.csv", sample)):
        with (folder / form).open(encoding="utf-8-sig") as fh:
            rows = list(csv.DictReader(fh))
        if [r["food_number"] for r in rows] != foods:
            raise ValueError(f"{form}: foods differ from the prepared round")
        for r in rows:
            if any(r[k] != by_food[r["food_number"]][k] for k in CONTEXT):
                raise ValueError(f"{form}: food {r['food_number']} differs from context.csv")
    return context


def problems(form: dict[int, dict[str, str]], pinned: set[str], blocked: set[str]) -> list[str]:
    out = []
    for n, r in form.items():
        d = normal(r.get("decision", ""))
        if not d:
            continue
        if d == "none":
            if not r.get("searched_terms", "").strip():
                out.append(f"{n}: none without searched_terms")
        elif d not in pinned:
            out.append(f"{n}: {d} is not a class of the pinned FoodOn release")
        elif d in blocked:
            out.append(f"{n}: {d} has a whole organism or plant among its ancestors")
    return out


def agreement(first: list[str], second: list[str]) -> float | None:
    if len(first) != len(second):
        raise ValueError("agreement requires equally sized sets of decisions")
    return sum(a == b for a, b in zip(first, second, strict=True)) / len(first) if first else None


def sparql(endpoint: str, query: str) -> list[dict]:
    r = requests.post(endpoint, data={"query": query}, headers={"Accept": "application/sparql-results+json"},
                      timeout=600)
    r.raise_for_status()
    return r.json()["results"]["bindings"]


def ancestors(endpoint: str, classes: set[str]) -> dict[str, set[str]]:
    out = {c: {c} for c in classes}
    if classes:
        values = " ".join(f"<{OBO}{c}>" for c in sorted(classes))
        for b in sparql(endpoint, "PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#> SELECT ?c ?a WHERE { "
                        f"VALUES ?c {{ {values} }} ?c rdfs:subClassOf* ?a FILTER isIRI(?a) }}"):
            out[b["c"]["value"].removeprefix(OBO)].add(b["a"]["value"].removeprefix(OBO))
    return out


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--round", type=Path, default=ROUND)
    p.add_argument("--endpoint", help="SPARQL endpoint with the FoodOn release, for organism checks and near "
                   "agreement")
    args = p.parse_args()
    adjudication = args.round / "adjudication.csv"
    if adjudication.is_file():
        with adjudication.open(encoding="utf-8-sig", newline="") as stream:
            if any(row.get("adjudicated", "").strip() or row.get("justification", "").strip()
                   for row in csv.DictReader(stream)):
                print("adjudication.csv already contains human decisions; scoring will not overwrite it",
                      file=sys.stderr)
                return 1
    try:
        validate(args.round, json.loads((args.round / "manifest.json").read_text(encoding="utf-8")))
    except ValueError as e:
        print(e, file=sys.stderr)
        return 1
    with CLASSES.open(encoding="utf-8") as fh:
        pinned = {line.split("\t", 1)[0] for line in fh if line.startswith("FOODON_")}
    first, second = read(args.round / "reviewer-1.csv"), read(args.round / "reviewer-2.csv")
    chosen = {normal(r["decision"]) for f in (first, second) for r in f.values()} - {"", "none"}
    up = ancestors(args.endpoint, chosen) if args.endpoint else {}
    blocked = {c for c, a in up.items() if a & set(ROOTS)}
    found = problems(first, pinned, blocked) + problems(second, pinned, blocked)
    done = [n for n in second if normal(second[n]["decision"]) and normal(first[n]["decision"])]
    print(f"reviewer 1: {sum(bool(normal(r['decision'])) for r in first.values())} of {len(first)} answered; "
          f"reviewer 2: {sum(bool(normal(r['decision'])) for r in second.values())} of {len(second)}")
    for problem in found:
        print(f"  {problem}")
    if found:
        return 1
    a = [normal(first[n]["decision"]) for n in done]
    b = [normal(second[n]["decision"]) for n in done]
    exact, kappa = agreement(a, b), cohen_kappa(a, b)
    print(f"sample answered by both: {len(done)}; exact agreement "
          f"{'-' if exact is None else f'{exact:.0%}'}; kappa {'-' if kappa is None else f'{kappa:.2f}'}")
    if args.endpoint and done:
        near = sum(x == y or x in up.get(y, set()) or y in up.get(x, set())
                   for x, y in zip(a, b, strict=True))
        print(f"near agreement (same class, or one an ancestor of the other): {near / len(done):.0%}")
    differ = [n for n, x, y in zip(done, a, b, strict=True) if x != y]
    with (args.round / "adjudication.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh, lineterminator="\r\n")
        w.writerow(["food_number", "name_pt", "reviewer_1", "reviewer_2", "adjudicated", "justification"])
        w.writerows([n, first[n]["name_pt"], normal(first[n]["decision"]), normal(second[n]["decision"]),
                     "", ""] for n in differ)
    print(f"{len(differ)} disagreements in {args.round / 'adjudication.csv'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
