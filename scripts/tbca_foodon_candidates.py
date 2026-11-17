"""Propose FoodOn classes for TBCA's foods by matching their English names to FoodOn labels, for review.

TBCA names a food in English as "Name, qualifier, ..., state, Brazil", e.g. "Ham, pork, cooked, Brazil";
FoodOn labels read "pork ham" or "ham (cooked)". The script rewrites each name into such labels, from the most
specific to the most general (qualifier and name with the state, name with the state, qualifier and name,
name, and a word given in parentheses, e.g. "cowpeas", in place of the name), and keeps the first one that
is the label of a class in ontology/imports/foodon-classes.tsv, the pinned FoodOn release. Each candidate
records the rule that produced it. With --endpoint, a Fuseki holding the FoodOn release
(scripts/load_triplestore.py --foodon) says which candidates are classes of whole organisms or plants, which
this project's FoodOn typing policy does not use as food types.

This is retrieval, not mapping: a candidate is a suggestion for a human reviewer, as in the project's review
rounds, and no FoodOn type is asserted from it. The CSV holds TBCA's food names, so it stays in
data/external/tbca/, which git ignores.
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
from collections import Counter
from pathlib import Path

from taco_rdf.namespaces import ROOT

SOURCE = ROOT / "data" / "external" / "tbca" / "foods.csv"
CLASSES = ROOT / "ontology" / "imports" / "foodon-classes.tsv"
OUT = ROOT / "data" / "external" / "tbca" / "foodon_candidates.csv"
STATES = {"raw": "raw", "fresh": "raw", "in natura": "raw", "en natura": "raw", "cooked": "cooked",
          "boiled": "cooked", "fried": "fried", "roasted": "roasted", "toasted": "roasted",
          "grilled": "grilled", "baked": "baked", "dried": "dried", "dry": "dried"}
ORGANISM_ROOTS = ("http://purl.obolibrary.org/obo/COB_0000022", "http://purl.obolibrary.org/obo/PO_0000003")
# Names TBCA puts before the food itself, as in "Crustacean, shrimp": the first qualifier is then the name.
CATEGORIES = {"crustacean", "meat", "fish", "mollusc", "mollusk", "seafood", "offal", "fruit", "vegetable",
              "beans", "bean", "cheese", "flour", "oil", "juice", "sauce", "sweets", "candy"}


def foodon_labels(path: Path) -> dict[str, tuple[str, str]]:
    """FoodOn labels in lower case, each with its class and label."""
    labels: dict[str, tuple[str, str]] = {}
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            if line.startswith("#") or "\t" not in line:
                continue
            curie, label = line.rstrip("\n").split("\t", 1)
            labels.setdefault(label.lower(), (curie, label))
    return labels


def singular(word: str) -> str:
    if word.endswith("ies"):
        return word[:-3] + "y"
    if word.endswith(("ches", "shes", "oes")):
        return word[:-2]
    return word[:-1] if word.endswith("s") and not word.endswith("ss") else word


def state_of(qualifier: str) -> str | None:
    """The state a qualifier names, e.g. cooked for "cooked (50% beans, 50% water)"."""
    return next((s for word, s in STATES.items() if qualifier == word or qualifier.startswith(word + " ")),
                None)


def variants(name_en: str) -> list[tuple[str, str]]:
    """Labels to try for one TBCA English name, most specific first, each with the rule that made it.

    TBCA often names a category first, e.g. "Crustacean, shrimp"; after such a name (CATEGORIES) the first
    qualifier is also tried as the name, before the category alone.
    """
    name = re.sub(r"\((?:average|mean|various|several)[^)]*\)", "", name_en, flags=re.IGNORECASE)
    segments = [s.strip().lower() for s in name.split(",")]
    segments = [s for s in segments if s and not s.startswith("brazil")]
    if not segments:
        return []
    head, qualifiers = segments[0], segments[1:]
    state = next((s for s in map(state_of, qualifiers) if s), None)
    words = [q for q in qualifiers if not state_of(q) and len(q.split()) <= 2 and "(" not in q]
    in_brackets = [w for s in segments for w in re.findall(r"\(([a-z -]+)\)", s)]
    heads = list(dict.fromkeys([head, singular(head)]))
    out: list[tuple[str, str]] = []
    for h in heads:
        for q in words[:2]:
            if state:
                out.append((f"{q} {h} ({state})", "qualifier, name and state"))
            out += [(f"{q} {h}", "qualifier and name"), (f"{h} {q}", "name and qualifier"),
                    (f"{h} {singular(q)}", "name and qualifier")]
    for q in words[:1] if head in CATEGORIES else []:
        for alt in dict.fromkeys([q, singular(q)]):
            if state:
                out.append((f"{alt} ({state})", "qualifier as name, and state"))
            out.append((alt, "qualifier as name"))
    for h in heads:
        if state:
            out.append((f"{h} ({state})", "name and state"))
        out.append((h, "name"))
    for w in in_brackets:
        for alt in dict.fromkeys([w, singular(w)]):
            if state:
                out.append((f"{alt} ({state})", "name in brackets and state"))
            out.append((alt, "name in brackets"))
    return out


def candidate(name_en: str, labels: dict[str, tuple[str, str]]) -> tuple[str, str, str]:
    """The FoodOn class, its label and the rule of the first variant that is a FoodOn label, or blanks."""
    for text, rule in variants(name_en):
        if text in labels:
            return (*labels[text], rule)
    return "", "", ""


def organism_classes(curies: set[str], endpoint: str) -> set[str]:
    """Those classes that FoodOn places under whole organisms or plants."""
    from SPARQLWrapper import JSON, SPARQLWrapper

    found: set[str] = set()
    items = sorted(curies)
    for i in range(0, len(items), 200):
        values = " ".join(f"<http://purl.obolibrary.org/obo/{c}>" for c in items[i:i + 200])
        roots = " ".join(f"<{r}>" for r in ORGANISM_ROOTS)
        sparql = SPARQLWrapper(endpoint)
        sparql.setReturnFormat(JSON)
        sparql.setQuery("PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#> SELECT DISTINCT ?c WHERE { "
                        f"VALUES ?c {{ {values} }} VALUES ?root {{ {roots} }} ?c rdfs:subClassOf+ ?root }}")
        for row in sparql.queryAndConvert()["results"]["bindings"]:
            found.add(row["c"]["value"].rsplit("/", 1)[-1])
    return found


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--foods", type=Path, default=SOURCE, help=f"foods.csv from fetch_tbca.py ({SOURCE})")
    p.add_argument("-o", "--output", type=Path, default=OUT, help=f"CSV to write (default {OUT})")
    p.add_argument("--endpoint", help="SPARQL endpoint with the FoodOn release, to flag organism classes")
    args = p.parse_args()
    if not args.foods.is_file():
        print(f"{args.foods} is missing; run scripts/fetch_tbca.py first", file=sys.stderr)
        return 1
    labels = foodon_labels(CLASSES)
    with args.foods.open(encoding="utf-8", newline="") as fh:
        foods = list(csv.DictReader(fh))
    rows = []
    for food in foods:
        curie, label, rule = candidate(food["name_en"], labels)
        rows.append({"code": food["code"], "food_type": food["food_type"], "name_en": food["name_en"],
                     "foodon": curie, "foodon_label": label, "rule": rule, "organism_class": ""})
    if args.endpoint:
        organisms = organism_classes({r["foodon"] for r in rows if r["foodon"]}, args.endpoint)
        for r in rows:
            r["organism_class"] = str(r["foodon"] in organisms) if r["foodon"] else ""
    with args.output.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]), lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    matched = [r for r in rows if r["foodon"]]
    print(f"wrote {args.output}: {len(matched)} of {len(rows)} TBCA foods have a FoodOn candidate")
    for rule, n in Counter(r["rule"] for r in matched).most_common():
        print(f"  {n:5}  {rule}")
    if args.endpoint:
        print(f"  {sum(r['organism_class'] == 'True' for r in rows)} candidates are organism classes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
