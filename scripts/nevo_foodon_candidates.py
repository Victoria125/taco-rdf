"""Propose FoodOn classes for the NEVO foods that NICE-Food's graph leaves without one, for human review.

NICE-Food v3 types 1,300 of its 1,673 NEVO food items with a FoodOn class. For each of the other 373 this
script gathers candidates from four sources:
- name: NEVO's English name, rewritten as FoodOn labels are written ("Millet pearl raw" as "pearl millet
  (raw)"), matched exactly against the labels of the pinned FoodOn release
  (ontology/imports/foodon-classes.tsv);
- neighbours: the FoodOn classes NICE-Food gave the two most similar NEVO foods that have one, by the words
  their English names share ("Quince w skin av" next to "Quince Vranja w skin");
- TACO neighbour: the FoodOn type of the most similar typed TACO food, by its English name, so that the
  Brazilian table helps the Dutch one;
- OLS (with --ols): EBI's Ontology Lookup Service, searching FoodOn's labels and synonyms; each hit says
  whether it is in the pinned release.

This is retrieval, not mapping: a candidate is a suggestion and nothing is asserted from it; reviewers decide,
as in the project's TACO review rounds, by filling the decision column (name, neighbour1, neighbour2,
taco_neighbour, ols1, ols2, ols3, other with chosen_class, or none), and scripts/nevo_foodon_types.py
turns the decisions into rdf:type triples. The sheet is separated by semicolons, as Excel reads CSV in
Portuguese. It holds NEVO's food names, which NEVO's conditions of use do not let this project redistribute,
so it goes to build/, which git ignores.

    $env:PYTHONPATH = "src"; python scripts/nevo_foodon_candidates.py --ols
"""

from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import re
import sys
import time
import unicodedata
from pathlib import Path

import requests

from taco_rdf.namespaces import BUILD_DIR, ROOT

ENDPOINT = "http://localhost:3030/nicefood/sparql"
OUT_DIR = BUILD_DIR / "nevo" / "foodon_pilot"
TACO_TYPES = ROOT / "analysis" / "data" / "foodon_types.csv"
TACO_NAMES = ROOT / "data" / "labels" / "food_names_en.csv"
OLS = "https://www.ebi.ac.uk/ols4/api/search"
FOODON = "http://purl.obolibrary.org/obo/FOODON_"
NEVO_FOODS = """
PREFIX fio: <http://www.foodvoc.org/resource/fio#>
PREFIX dcterms: <http://purl.org/dc/terms/>
PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
SELECT ?f (SAMPLE(STR(?en)) AS ?name_en) (SAMPLE(STR(?nl)) AS ?name_nl)
       (GROUP_CONCAT(DISTINCT CONCAT(STR(?c), "|", COALESCE(STR(?cl), "")); separator="||") AS ?classes)
WHERE {
  ?f a fio:FoodItem ; dcterms:isVersionOf <https://www.rivm.nl/nederlands-voedingsstoffenbestand> .
  OPTIONAL { ?f skos:prefLabel ?en FILTER (LANG(?en) = "en") }
  OPTIONAL { ?f skos:prefLabel ?nl FILTER (LANG(?nl) = "nl") }
  OPTIONAL { ?f a ?c . FILTER STRSTARTS(STR(?c), "http://purl.obolibrary.org/obo/FOODON_")
             OPTIONAL { ?c rdfs:label ?cl } }
} GROUP BY ?f
"""
# NEVO's English names: abbreviations, the words that give a state, and the words after which a name says
# what the food is not ("Fruit tinned av excl pineapple", "Nut paste wo salt").
ABBREVIATIONS = {"w": "with", "m": "with", "wo": "without", "excl": "excluding", "incl": "including",
                 "prep": "prepared", "unprep": "unprepared", "s-sk": "semi-skimmed",
                 "semi-sk": "semi-skimmed", "prod": "product", "av": "", "average": "", "averaged": "",
                 "gem": ""}
STATES = {"raw": "raw", "fresh": "raw", "boiled": "cooked", "cooked": "cooked", "prepared": "cooked",
          "steamed": "cooked", "stewed": "cooked", "fried": "fried", "deep-fried": "fried",
          "baked": "baked", "roasted": "roasted", "grilled": "grilled", "dried": "dried",
          "tinned": "canned", "canned": "canned", "frozen": "frozen", "smoked": "smoked"}
NOT = {"without", "excluding", "except"}
STOPWORDS = {"with", "in", "and", "of", "the", "a", "for", "ready", "made", "home", "industrial", "own",
             "fat", "type", "various", "kinds", "e.g", "unprepared", "including", "glass", "pack", "bottle"}


def load(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


tbca = load("tbca_foodon_candidates")


def fold(text: str) -> str:
    """Lower case without accents, so that "Creme fraiche" meets "crème fraîche"."""
    return "".join(c for c in unicodedata.normalize("NFKD", text.lower()) if not unicodedata.combining(c))


def foodon_labels() -> dict[str, tuple[str, str]]:
    """The pinned FoodOn labels, folded, each with its class and label."""
    labels: dict[str, tuple[str, str]] = {}
    for text, (curie, label) in tbca.foodon_labels(tbca.CLASSES).items():
        if curie.startswith(("FOODON_", "CHEBI_", "NCBITaxon_")):
            labels.setdefault(fold(text), (curie, label))
    return labels


def words(name: str) -> list[str]:
    """NEVO's English name as folded words, with abbreviations spelled out or dropped."""
    out = []
    for w in re.split(r"[\s/,+]+", fold(name)):
        w = w.strip("()-.&'\"")
        w = ABBREVIATIONS.get(w, w)
        if w:
            out.append(w)
    return out


def what(ws: list[str]) -> list[str]:
    """The words that say what the food is: none after "without" or "excluding", no state, filler or
    number."""
    if any(w in NOT for w in ws):
        ws = ws[:min(ws.index(w) for w in NOT if w in ws)]
    return [w for w in ws if w not in STATES and w not in STOPWORDS and not any(c.isdigit() for c in w)]


def content(name: str) -> set[str]:
    return {tbca.singular(w) for w in what(words(name))}


def state_of(ws: list[str]) -> str | None:
    """The state a name gives; "fresh" counts only when nothing else does ("mashed fresh prepared")."""
    found = [w for w in ws[1:] if w in STATES]
    strong = [w for w in found if w != "fresh"]
    return STATES[(strong or found)[0]] if found else None


def variants(name: str) -> list[tuple[str, str]]:
    """FoodOn-style labels to try for one NEVO name, most specific first, each with its rule."""
    ws = words(name)
    if not ws:
        return []
    head = ws[0]
    state = state_of(ws)
    qualifiers = what(ws[1:])[:2]
    heads = list(dict.fromkeys([head, tbca.singular(head)]))
    plain = " ".join(w for w in ws if w not in STATES)
    out: list[tuple[str, str]] = []
    if state:
        out.append((f"{plain} ({state})", "name and state"))
    out.append((plain, "name"))
    for h in heads:
        for q in qualifiers:
            if state:
                out.append((f"{q} {h} ({state})", "qualifier, head and state"))
            out += [(f"{q} {h}", "qualifier and head"), (f"{h} {q}", "head and qualifier")]
    for h in heads:
        if state:
            out.append((f"{h} ({state})", "head and state"))
        out.append((h, "head"))
    return out


def lexical(name: str, labels: dict[str, tuple[str, str]]) -> tuple[str, str, str]:
    for text, rule in variants(name):
        if text in labels:
            return (*labels[text], rule)
    return "", "", ""


def neighbours(name: str, typed: list[dict], n: int = 2) -> list[tuple[float, dict]]:
    """The n typed NEVO foods whose names share most words with this one, sharing its first word."""
    mine = content(name)
    head = tbca.singular(words(name)[0]) if words(name) else ""
    scored = []
    for food in typed:
        theirs = content(food["name_en"])
        if not mine or not theirs or head not in theirs:
            continue
        score = len(mine & theirs) / len(mine | theirs)
        scored.append((round(score, 2), food))
    return sorted(scored, key=lambda s: (-s[0], s[1]["name_en"]))[:n]


def ols_search(name: str, cache: dict, delay: float) -> tuple[str, list[dict]]:
    """FoodOn hits of OLS, best first, and the query that found them: the words that say what the food
    is, then the first two of them, then the first."""
    ws = what(words(name))
    queries = list(dict.fromkeys(q for q in (" ".join(ws), " ".join(ws[:2]), " ".join(ws[:1])) if q))
    for query in queries:
        if query not in cache:
            r = requests.get(OLS, params={"q": query, "ontology": "foodon", "rows": 5, "type": "class",
                                          "fieldList": "iri,label,short_form"},
                             headers={"User-Agent": "taco-rdf candidate search"}, timeout=60)
            r.raise_for_status()
            cache[query] = [d for d in r.json()["response"]["docs"] if d.get("iri", "").startswith(FOODON)]
            time.sleep(delay)
        if cache[query]:
            return query, cache[query]
    return "", []


def taco_typed(types: Path = TACO_TYPES, names: Path = TACO_NAMES) -> list[dict]:
    """TACO's typed foods, by English name and with their FoodOn type, as neighbours for NEVO's foods."""
    with names.open(encoding="utf-8") as fh:
        name_en = {r["food_number"]: r["name_en"] for r in csv.DictReader(fh)}
    with types.open(encoding="utf-8") as fh:
        return [{"food_number": r["food_number"], "name_en": name_en[r["food_number"]],
                 "classes": [(r["target_iri"].rsplit("/", 1)[-1], r["target_label"])]}
                for r in csv.DictReader(fh)]


def nevo_foods(endpoint: str) -> list[dict]:
    r = requests.post(endpoint, data={"query": NEVO_FOODS},
                      headers={"Accept": "application/sparql-results+json"}, timeout=900)
    r.raise_for_status()
    foods = []
    for b in r.json()["results"]["bindings"]:
        iri = b["f"]["value"]
        value = b.get("classes", {}).get("value", "")
        classes = [c.split("|", 1) for c in value.split("||") if c]
        foods.append({"iri": iri, "release": iri.split("/")[-2], "code": iri.rsplit("#", 1)[-1],
                      "name_en": b.get("name_en", {}).get("value", ""),
                      "name_nl": b.get("name_nl", {}).get("value", ""),
                      "classes": [(c.rsplit("/", 1)[-1], label) for c, label in classes]})
    return foods


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--endpoint", default=ENDPOINT, help=f"nicefood Fuseki endpoint (default {ENDPOINT})")
    p.add_argument("--ols", action="store_true", help="also search FoodOn in EBI's OLS (cached)")
    p.add_argument("--delay", type=float, default=0.3, help="seconds between OLS requests")
    p.add_argument("--out", type=Path, default=OUT_DIR, help=f"folder to write (default {OUT_DIR})")
    args = p.parse_args()
    labels = foodon_labels()
    pinned = {curie for curie, _ in tbca.foodon_labels(tbca.CLASSES).values()}
    foods = nevo_foods(args.endpoint)
    typed = [f for f in foods if f["classes"]]
    untyped = sorted((f for f in foods if not f["classes"]), key=lambda f: f["name_en"].lower())
    taco = taco_typed()
    args.out.mkdir(parents=True, exist_ok=True)
    cache_path = args.out / "ols_cache.json"
    cache = json.loads(cache_path.read_text(encoding="utf-8")) if cache_path.is_file() else {}
    rows = []
    for food in untyped:
        row = {"nevo_release": food["release"], "nevo_code": food["code"], "nevo_iri": food["iri"],
               "name_en": food["name_en"], "name_nl": food["name_nl"]}
        row["name_class"], row["name_label"], row["name_rule"] = lexical(food["name_en"], labels)
        for i in (1, 2):
            row |= {f"neighbour{i}_class": "", f"neighbour{i}_label": "", f"neighbour{i}_food": "",
                    f"neighbour{i}_score": ""}
        for i, (score, other) in enumerate(neighbours(food["name_en"], typed), start=1):
            row |= {f"neighbour{i}_class": "; ".join(c for c, _ in other["classes"]),
                    f"neighbour{i}_label": "; ".join(label for _, label in other["classes"]),
                    f"neighbour{i}_food": other["name_en"], f"neighbour{i}_score": score}
        row |= {"taco_neighbour_class": "", "taco_neighbour_label": "", "taco_neighbour_food": "",
                "taco_neighbour_score": ""}
        for score, other in neighbours(food["name_en"], taco, n=1):
            cls, label = other["classes"][0]
            row |= {"taco_neighbour_class": cls, "taco_neighbour_label": label,
                    "taco_neighbour_food": other["name_en"], "taco_neighbour_score": score}
        if args.ols:
            query, hits = ols_search(food["name_en"], cache, args.delay)
            row["ols_query"] = query
            for i in (1, 2, 3):
                hit = hits[i - 1] if i <= len(hits) else {}
                row |= {f"ols{i}_class": hit.get("short_form", ""), f"ols{i}_label": hit.get("label", ""),
                        f"ols{i}_in_pinned_release": str(hit["short_form"] in pinned) if hit else ""}
        rows.append(row)
    if args.ols:
        cache_path.write_text(json.dumps(cache, ensure_ascii=False, indent=1), encoding="utf-8")
    candidates = {c for r in rows for k, v in r.items() if k.endswith("_class") for c in v.split("; ") if c}
    organisms = tbca.organism_classes(candidates, args.endpoint.replace("/sparql", "/query"))
    for r in rows:
        r["organism_classes"] = "; ".join(sorted(
            {c for k, v in r.items() if k.endswith("_class") for c in v.split("; ") if c in organisms}))
        r |= {"decision": "", "chosen_class": "", "note": ""}
    fields = list(dict.fromkeys(k for r in rows for k in r))
    out = args.out / "candidates.csv"
    with out.open("w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields, delimiter=";", lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    any_candidate = sum(1 for r in rows if r.get("name_class") or r.get("neighbour1_class")
                        or r.get("taco_neighbour_class") or r.get("ols1_class"))
    print(f"NEVO foods: {len(foods)}, with a FoodOn class {len(typed)}, without {len(untyped)}")
    print(f"wrote {out}")
    print(f"  name match:      {sum(1 for r in rows if r.get('name_class'))}")
    print(f"  neighbour:       {sum(1 for r in rows if r.get('neighbour1_class'))}")
    print(f"  TACO neighbour:  {sum(1 for r in rows if r.get('taco_neighbour_class'))}")
    if args.ols:
        print(f"  OLS hit:         {sum(1 for r in rows if r.get('ols1_class'))}")
    print(f"  any candidate:   {any_candidate} of {len(rows)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
