# ruff: noqa: E501
"""Write docs/structure.md: how TACO sits in NICE-Food, with numbers, namespaces, URIs, schema and an example.

Every number, table and the example diagram are read from Fuseki's nicefood dataset (triplestore/README.md),
where TACO's NICE-Food export and NICE-Food's NEVO graphs are loaded, from TACO-RDF's own graph
(build/taco.ttl), from the FoodOn candidate sheets of TACO and NEVO (build/), and, with --nicekg, from the code
of NICE-Food's pipeline (a clone of https://github.com/rivm-syso/nicekg_processing). The schema diagram shows
classes only and the example diagram instances only. NEVO appears by its structure and by counts, never by a
food name or value, which NEVO's conditions of use keep out of this repository.
verification/structure_check.py checks the document against the data.

    $env:PYTHONPATH = "src"; python scripts/describe_structure.py --nicekg C:/path/to/nicekg_processing
"""

from __future__ import annotations

import argparse
import csv
import datetime
import importlib.util
import json
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

from rdflib import RDF, Graph

from taco_rdf import sparql
from taco_rdf.namespaces import BUILD_DIR, FIO, NEVO_SOURCE, NEVONUT, OM, ROOT, TACO_SOURCE

ENDPOINT = sparql.endpoint()
OUT = ROOT / "docs" / "structure.md"
SUMMARY = ROOT / "docs" / "summary.md"
DEFINITIONS = ROOT / "analysis" / "data" / "nutrient_definitions.csv"
GITHUB = "https://github.com/Victoria125/taco-rdf/blob/main/"
TACO = str(TACO_SOURCE)
NEVO = str(NEVO_SOURCE)
OBO = "http://purl.obolibrary.org/obo/"
EXAMPLE = "https://w3id.org/taco-rdf/id/food/574"
TACO_SHEET = BUILD_DIR / "taco" / "foodon_round2" / "candidates.csv"
NEVO_SHEET = BUILD_DIR / "nevo" / "foodon_pilot" / "candidates.csv"
PINNED = ROOT / "ontology" / "imports" / "foodon-classes.tsv"
TERM_REQUESTS = ROOT / "analysis" / "data" / "foodon_term_requests.csv"
NAMESPACES = [  # prefix, namespace, what it is
    ("tacoid", "https://w3id.org/taco-rdf/id/", "TACO's instances: foods, values, measures"),
    ("taco", "https://w3id.org/taco-rdf/vocab#", "TACO's vocabulary (ontology/taco.ttl)"),
    ("nevo21", "https://data.rivm.nl/data/nvip/bigfood/nevo21/", "NEVO 2021 food items and measures"),
    ("nevo23", "https://data.rivm.nl/data/nvip/bigfood/nevo23/", "NEVO 2023 food items and measures"),
    ("nevonut", str(NEVONUT), "NEVO's nutrients (and NEVO's values)"),
    ("fio", str(FIO), "NICE-Food's vocabulary: food item, nutritional value"),
    ("obo", OBO, "FoodOn (FOODON_) and CDNO (CDNO_) classes"),
    ("om", str(OM), "Ontology of units of Measure 2.0"),
    ("skos", "http://www.w3.org/2004/02/skos/core#", "SKOS, for names (prefLabel)"),
    ("dcterms", "http://purl.org/dc/terms/", "Dublin Core terms: source table, identifier, version"),
    ("prov", "http://www.w3.org/ns/prov#", "PROV: where a calculated value came from"),
]
PREFIXES = "".join(f"PREFIX {p}: <{ns}> " for p, ns, _ in NAMESPACES) + \
    "PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#> "
FILES = [
    ("docs/taco-in-nice-food/files/knowledge-graph/taco_nice_food.ttl", "TACO in the NICE-Food pattern, all foods"),
    ("docs/taco-in-nice-food/files/knowledge-graph/example_food_574.ttl", "one food of it, to read"),
    ("ontology/taco.ttl", "TACO's vocabulary, on top of FIO"),
    ("ontology/imports/foodon-module.ttl", "the FoodOn classes the graph uses, release 2026-09-20"),
    ("ontology/imports/cdno-module.ttl", "the CDNO classes the graph uses, release 2026-06-10"),
    ("data/alignment/taco_nevo_nutrients.csv", "each TACO nutrient and its NEVO nutrient code"),
    ("data/alignment/nevo_cdno_completion.csv", "CDNO classes TACO's mapping offers NEVO's values"),
    ("analysis/nutrient_definitions.md", "whether each shared nutrient code is the same quantity in both tables"),
    ("analysis/foodon_term_requests.md", "FoodOn term-search leads for unresolved TACO foods"),
]
LEVELS = {"food item": "?x dcterms:isVersionOf <{src}>",
          "nutritional value": "?f dcterms:isVersionOf <{src}> ; fio:hasNutritionalValue ?x",
          "measure": "?f dcterms:isVersionOf <{src}> ; fio:hasNutritionalValue ?v . ?v om:hasValue ?x"}
# Each kind of IRI with the pattern every IRI of that kind must match.
PATTERNS = {
    ("TACO", "food item"): r"^https://w3id\.org/taco-rdf/id/food/\d+$",
    ("TACO", "nutritional value"): r"^https://w3id\.org/taco-rdf/id/measurement/\d+/[a-z0-9_]+$",
    ("TACO", "measure"): r"^https://w3id\.org/taco-rdf/id/measurement/\d+/[a-z0-9_]+/measure$",
    ("NEVO", "food item"): r"^https://data\.rivm\.nl/data/nvip/bigfood/nevo2[13]/nevocode#\d+$",
    ("NEVO", "nutritional value"): "^" + re.escape(str(NEVONUT)) + r"\S+$",
    ("NEVO", "measure"): r"^https://data\.rivm\.nl/data/nvip/bigfood/nevo2[13]/value#\S+$",
}
TEMPLATES = {
    ("TACO", "food item"): "tacoid:food/{TACO number}",
    ("TACO", "nutritional value"): "tacoid:measurement/{TACO number}/{nutrient key}",
    ("TACO", "measure"): "tacoid:measurement/{TACO number}/{nutrient key}/measure",
    ("NEVO", "food item"): "nevo21:nevocode#{NEVO code} (or nevo23:)",
    ("NEVO", "nutritional value"): "nevonut:{nutrient code and identifier}",
    ("NEVO", "measure"): "nevo21:value#{identifier} (or nevo23:)",
}
PY_PREFIX = {"FIO": "fio", "OM2": "om", "DCT": "dcterms", "SKOS": "skos", "RDFS": "rdfs", "RDF": "rdf",
             "SOSA": "sosa", "SSN": "ssn", "SAREF": "saref", "SCHEMA": "schema", "FOBI": "fobi",
             "KAP_PARAM": "kap_param"}
# The terms TACO and NEVO share, as a candidate minimal profile.
PROFILE_CLASSES = ["fio:FoodItem", "a FoodOn class", "fio:NutritionalValue", "a CDNO class", "fio:Nutrient",
                   "om:Measure", "om:Unit"]
PROFILE_PROPERTIES = ["fio:hasNutritionalValue", "fio:hasNutrient", "om:hasValue", "om:hasNumericalValue",
                      "om:hasUnit", "dcterms:isVersionOf", "dcterms:hasVersion", "skos:prefLabel"]
# NEVO's own food codes; TACO gives its food number with dcterms:identifier.
NEVO_CODES = {"fio:hasNevoCode21", "fio:hasNevoCode23"}
SCHEMA = """```mermaid
flowchart LR
  FoodItem["fio:FoodItem<br/><i>also a FoodOn class</i>"]
  Value["fio:NutritionalValue<br/><i>also a CDNO class</i>"]
  Nutrient["fio:Nutrient<br/><i>NEVO's nutrient codes</i>"]
  Measure["om:Measure"]
  Unit["om:Unit"]
  Status["taco:ValueStatus<br/><i>TACO only</i>"]
  Source["source table<br/><i>IRI</i>"]
  Label(["rdf:langString"])
  Number(["xsd:decimal"])
  UnitText(["xsd:string"])
  Version(["rdf:langString"])
  FoodItem -->|fio:hasNutritionalValue| Value
  FoodItem -->|dcterms:isVersionOf| Source
  FoodItem -->|dcterms:hasVersion| Version
  FoodItem -->|skos:prefLabel| Label
  Value -->|fio:hasNutrient| Nutrient
  Value -->|om:hasValue| Measure
  Value -->|taco:valueStatus| Status
  Value -->|prov:wasDerivedFrom| Value
  Measure -->|om:hasNumericalValue| Number
  Measure -->|om:hasUnit| Unit
  Measure -->|om:hasUnit| UnitText
```"""


def rows(endpoint: str, query: str) -> list[dict[str, str]]:
    return sparql.select(PREFIXES + query, endpoint)


def one(endpoint: str, query: str) -> int:
    return int(next(iter(rows(endpoint, query)[0].values())))


def short(iri: str) -> str:
    for p, ns, _ in sorted(NAMESPACES, key=lambda n: -len(n[1])):
        if iri.startswith(ns):
            return f"{p}:{iri[len(ns):]}"
    if iri.startswith("http://www.w3.org/1999/02/22-rdf-syntax-ns#"):
        return "rdf:" + iri.rsplit("#", 1)[-1]
    return iri


def facts(endpoint: str) -> dict:
    out: dict = {"numbers": {}, "properties": {}, "patterns": {}, "units": {}, "minted": {}}
    for name, src in (("TACO", TACO), ("NEVO", NEVO)):
        n = out["numbers"].setdefault(name, {})
        food = LEVELS["food item"].format(src=src)
        value = LEVELS["nutritional value"].format(src=src)
        cdno = f'FILTER STRSTARTS(STR(?c), "{OBO}CDNO_")'
        n["food items"] = one(endpoint, f"SELECT (COUNT(DISTINCT ?x) AS ?n) WHERE {{ {food} }}")
        n["with a FoodOn type"] = one(endpoint, f"SELECT (COUNT(DISTINCT ?x) AS ?n) WHERE {{ {food} ; a ?t . "
                                      f'FILTER STRSTARTS(STR(?t), "{OBO}FOODON_") }}')
        n["nutritional values"] = one(endpoint, f"SELECT (COUNT(DISTINCT ?x) AS ?n) WHERE {{ {value} }}")
        n["values with a CDNO class"] = one(endpoint, f"SELECT (COUNT(DISTINCT ?x) AS ?n) WHERE {{ {value} . "
                                            f"?x a ?c {cdno} }}")
        n["values with a number"] = one(endpoint, f"SELECT (COUNT(DISTINCT ?x) AS ?n) WHERE {{ {value} . "
                                        "?x om:hasValue ?m }")
        n["values with a status instead"] = one(endpoint, f"SELECT (COUNT(DISTINCT ?x) AS ?n) WHERE {{ {value} . "
                                                "?x taco:valueStatus ?s }")
        n["calculated values (PROV)"] = one(endpoint, f"SELECT (COUNT(DISTINCT ?x) AS ?n) WHERE {{ {value} . "
                                            "?x prov:wasDerivedFrom ?d }")
        n["nutrients"] = one(endpoint, f"SELECT (COUNT(DISTINCT ?nu) AS ?n) WHERE {{ {value} . "
                             "?x fio:hasNutrient ?nu }")
        n["CDNO classes"] = one(endpoint, f"SELECT (COUNT(DISTINCT ?c) AS ?n) WHERE {{ {value} . ?x a ?c {cdno} }}")
        for level, pattern in LEVELS.items():
            p = pattern.format(src=src)
            for r in rows(endpoint, f"SELECT ?p (COUNT(*) AS ?n) WHERE {{ {p} . ?x ?p ?o }} GROUP BY ?p"):
                out["properties"].setdefault((level, short(r["p"])), {})[name] = int(r["n"])
            iris = [r["x"] for r in rows(endpoint, f"SELECT DISTINCT ?x WHERE {{ {p} }}")]
            regex = re.compile(PATTERNS[(name, level)])
            out["patterns"][(name, level)] = (sum(bool(regex.match(i)) for i in iris), len(iris), iris[0])
            out["minted"].setdefault(name, set()).update(short(i).split(":")[0] for i in iris)
        for r in rows(endpoint, f"SELECT ?u (COUNT(*) AS ?n) WHERE {{ {value} . ?x om:hasValue ?m . "
                      "?m om:hasUnit ?u } GROUP BY ?u"):
            unit = short(r["u"]) if r["u"].startswith("http") else f'"{r["u"]}"'
            out["units"].setdefault(unit, {})[name] = int(r["n"])
    not_foodon = (f'FILTER (STRSTARTS(STR(?t), "{OBO}") && !STRSTARTS(STR(?t), "{OBO}FOODON_"))')
    nevo_food = LEVELS["food item"].format(src=NEVO)
    other = rows(endpoint, f"SELECT DISTINCT ?t WHERE {{ {nevo_food} ; a ?t . {not_foodon} }}")
    out["other food classes"] = sorted({re.sub(r"_\d+$", "", short(r["t"])) for r in other})
    out["other food items"] = one(endpoint, f"SELECT (COUNT(DISTINCT ?x) AS ?n) WHERE {{ {nevo_food} ; a ?t . "
                                  f"{not_foodon} }}")
    out["nutrient types"] = sorted(short(r["t"]) for r in rows(endpoint, "SELECT DISTINCT ?t WHERE "
                                                                           "{ nevonut:PROT a ?t }"))
    taco_value = LEVELS["nutritional value"].format(src=TACO)
    names: dict[str, dict[str, int]] = {"nevonut": {}, "tacoid": {}}
    for r in rows(endpoint, f"SELECT ?nu (COUNT(*) AS ?n) WHERE {{ {taco_value} . ?x fio:hasNutrient ?nu }} "
                  "GROUP BY ?nu"):
        prefix, local = short(r["nu"]).split(":", 1)
        names[prefix][local] = int(r["n"])
    out["TACO nutrient names"] = names
    return out


def example(endpoint: str) -> list[tuple[str, str, str]]:
    """The example's triples: food 574, its protein value and measure, and one value without a number."""
    triples = [(EXAMPLE, r["p"], r["o"]) for r in rows(endpoint, f"SELECT ?p ?o WHERE {{ <{EXAMPLE}> ?p ?o }}")
               if r["p"].endswith(("#type", "prefLabel", "/hasVersion")) or r["o"].endswith("/protein")]
    status = rows(endpoint, f"SELECT ?v WHERE {{ <{EXAMPLE}> fio:hasNutritionalValue ?v . "
                  "?v taco:valueStatus taco:Trace } ORDER BY ?v LIMIT 1")
    values = [EXAMPLE.replace("/food/", "/measurement/") + "/protein"] + [r["v"] for r in status]
    triples += [(EXAMPLE, str(FIO.hasNutritionalValue), v) for v in values[1:]]
    for v in values:
        for r in rows(endpoint, f"SELECT ?p ?o WHERE {{ <{v}> ?p ?o }}"):
            triples.append((v, r["p"], r["o"]))
            if r["p"].endswith("hasValue"):
                triples += [(r["o"], m["p"], m["o"])
                            for m in rows(endpoint, f"SELECT ?p ?o WHERE {{ <{r['o']}> ?p ?o }}")]
    # Fuseki returns triples in the order of its indexes, which a rebuilt store may change; the diagram numbers
    # its nodes in this order, so the order is fixed here: the food's own triples first, then by value.
    return sorted(dict.fromkeys(triples), key=lambda t: (t[0] != EXAMPLE, t[0], t[1], t[2]))


def mermaid_example(triples: list[tuple[str, str, str]]) -> str:
    """Instances only: each node lists its classes; literals are separate, rounded nodes."""
    types: dict[str, list[str]] = {}
    for s, p, o in triples:
        if p.endswith("#type"):
            types.setdefault(s, []).append(short(o))
    ids: dict[str, str] = {}
    lines = ["```mermaid", "flowchart LR"]
    for s, p, o in triples:
        if p.endswith("#type"):
            continue
        for term in (s, o):
            if term in ids:
                continue
            ids[term] = f"n{len(ids)}"
            label = short(term) if term.startswith("http") else f'"{term}"'
            if term in types:
                label += "<br/><i>a " + ", ".join(sorted(types[term])) + "</i>"
            left, right = ('["', '"]') if term.startswith("http") else ('(["', '"])')
            lines.append(f"  {ids[term]}{left}{label.replace(chr(34), '&quot;')}{right}")
        lines.append(f"  {ids[s]} -->|{short(p)}| {ids[o]}")
    lines.append("```")
    return "\n".join(lines)


def nicefood_code(folder: Path) -> dict:
    """What each NICE-Food notebook mints and uses, read from its code (comments left out): the namespaces
    under data.rivm.nl, the classes it types with, and the properties it adds."""
    commit = subprocess.run(["git", "-C", str(folder), "rev-parse", "--short", "HEAD"], capture_output=True,
                            text=True).stdout.strip()
    out: dict = {"commit": commit, "datasets": {}}
    term = r"([A-Z][A-Z0-9_]*)\.([A-Za-z_][A-Za-z0-9_]*)"
    for nb in sorted(folder.glob("*_processing.ipynb")):
        cells = json.loads(nb.read_text(encoding="utf-8"))["cells"]
        code = "\n".join("".join(c["source"]) for c in cells if c["cell_type"] == "code")
        code = "\n".join(line for line in code.splitlines() if not line.lstrip().startswith("#"))
        minted = sorted(set(re.findall(r'Namespace\(\s*"(https://data\.rivm\.nl/[^"]+)"', code)))
        classes = sorted({f"{PY_PREFIX.get(p, p.lower())}:{t}" for p, t in re.findall(r"RDF\.type,\s*" + term, code)})
        props = sorted({f"{PY_PREFIX.get(p, p.lower())}:{t}"
                        for p, t in re.findall(r"g\.add\(\s*\(\s*[^,]+,\s*" + term, code) if p != "RDF"})
        out["datasets"][nb.stem.removesuffix("_processing").upper()] = {"minted": minted, "classes": classes,
                                                                          "properties": props}
    return out


def read_sheet(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig") as fh:
        return list(csv.DictReader(fh, delimiter=";"))


def shared_foods(endpoint: str) -> dict:
    """Foods of TACO and NEVO that share a FoodOn class today, that are linked through one subclass step, and
    that could share one once reviewers accept a candidate: a candidate class the other table already uses."""
    typed: dict[str, dict[str, set[str]]] = {"TACO": {}, "NEVO": {}}
    for r in rows(endpoint, f"SELECT ?f ?src ?t WHERE {{ VALUES ?src {{ <{TACO}> <{NEVO}> }} "
                  f'?f dcterms:isVersionOf ?src ; a ?t . FILTER STRSTARTS(STR(?t), "{OBO}FOODON_") }}'):
        typed["TACO" if r["src"] == TACO else "NEVO"].setdefault(r["f"], set()).add(r["t"].removeprefix(OBO))
    classes = {name: set().union(*foods.values()) for name, foods in typed.items()}
    common = classes["TACO"] & classes["NEVO"]
    out = {"classes now": len(common),
           "TACO now": sum(bool(c & common) for c in typed["TACO"].values()),
           "NEVO now": sum(bool(c & common) for c in typed["NEVO"].values())}
    parents: dict[str, set[str]] = {}
    every = sorted(classes["TACO"] | classes["NEVO"])
    for i in range(0, len(every), 150):
        values = " ".join(f"<{OBO}{c}>" for c in every[i:i + 150])
        for r in rows(endpoint, f"SELECT ?a ?b WHERE {{ VALUES ?a {{ {values} }} ?a rdfs:subClassOf ?b . "
                      "FILTER isIRI(?b) }"):
            parents.setdefault(r["a"].removeprefix(OBO), set()).add(r["b"].removeprefix(OBO))

    def near(cs: set[str], others: set[str]) -> bool:
        return any(c in others or parents.get(c, set()) & others or any(c in parents.get(o, set()) for o in others)
                   for c in cs)

    out["TACO linked"] = sum(near(c, classes["NEVO"]) and not c & common for c in typed["TACO"].values())
    out["NEVO linked"] = sum(near(c, classes["TACO"]) and not c & common for c in typed["NEVO"].values())
    with PINNED.open(encoding="utf-8") as fh:
        pinned = {line.split("\t", 1)[0] for line in fh if line.startswith("FOODON_")}
    taco_rows = [r for r in read_sheet(TACO_SHEET)
                 if f"https://w3id.org/taco-rdf/id/food/{r['food_number']}" not in typed["TACO"]] \
        if TACO_SHEET.is_file() else []
    out["TACO could join"] = sum(bool({c.strip() for c in r["usable_classes"].split(";")} & classes["NEVO"])
                                 for r in taco_rows)
    out["TACO could join by name"] = sum(r["name_class"] in classes["NEVO"] and r["name_class"] in r["usable_classes"]
                                         for r in taco_rows)
    nevo_rows = [r for r in read_sheet(NEVO_SHEET) if r["nevo_iri"] not in typed["NEVO"]] \
        if NEVO_SHEET.is_file() else []
    keys = ("name_class", "neighbour1_class", "neighbour2_class", "taco_neighbour_class", "ols1_class",
            "ols2_class", "ols3_class")

    def usable(r: dict[str, str]) -> set[str]:
        found = {c.strip() for k in keys for c in r.get(k, "").split(";") if c.strip()}
        return {c for c in found if c in pinned} - {c.strip() for c in r.get("organism_classes", "").split(";")}

    out["NEVO could join"] = sum(bool(usable(r) & classes["TACO"]) for r in nevo_rows)
    out["NEVO could join by name"] = sum(r["name_class"] in classes["TACO"] and r["name_class"] in usable(r)
                                         for r in nevo_rows)
    out["sheets"] = TACO_SHEET.is_file() and NEVO_SHEET.is_file()
    return out


def table(header: list[str], body: list[list[object]]) -> list[str]:
    return ["| " + " | ".join(header) + " |", "| " + " | ".join("---" for _ in header) + " |"] + \
        ["| " + " | ".join(str(c) for c in row) + " |" for row in body]


def num(x: object) -> str:
    return f"{x:,}" if isinstance(x, int) else str(x)


def document(f: dict, triples: list[tuple[str, str, str]], taco_graph: Graph | None, code: dict | None,
             shared: dict, term_requests: int) -> str:
    t, n = f["numbers"]["TACO"], f["numbers"]["NEVO"]
    lines = [
        "# TACO in NICE-Food: data, namespaces, URIs, schema and an example", "",
        f"Generated on {datetime.date.today().isoformat()} by `python scripts/describe_structure.py` from Fuseki's "
        "`nicefood` dataset, where TACO's NICE-Food export and NICE-Food's NEVO graphs are loaded together with "
        "FoodOn, and checked by `python verification/structure_check.py`. NEVO is described by its structure "
        "and by counts only, not by food names or values.", "",
        "TACO, the Brazilian food composition table, is written in the pattern NICE-Food uses for NEVO, so that "
        "the two tables sit in one knowledge graph and the same queries answer for both. This file lists what "
        "the graph uses, so that we can agree on a common structure: which namespaces and URIs stand for which "
        "things.", "", "## 1. Files to open", "", "No code has to be run: the RDF files are on GitHub.", ""]
    lines += table(["File", "What it holds"], [[f"[{p}]({GITHUB}{p})", what] for p, what in FILES])
    lines += ["", "## 2. The data in numbers", ""]
    lines += table(["", "TACO", "NEVO in NICE-Food"], [[k, num(t[k]), num(n[k])] for k in t])
    lines += ["", "NEVO in NICE-Food holds the 2021 and 2023 releases. A value \"with a status instead\" is a TACO "
              "cell with no number: a trace, not applicable, or under re-evaluation. The calculated values are "
              "TACO's available carbohydrate, its carbohydrate minus its dietary fibre.", "", "## 3. Namespaces", ""]
    used = {name: {prop.split(":")[0] for (_, prop), counts in f["properties"].items() if name in counts}
            | f["minted"][name] for name in ("TACO", "NEVO")}
    lines += table(["Prefix", "Namespace", "What it is", "TACO", "NEVO"],
                   [[f"`{p}`", f"`{ns}`", what, "yes" if p in used["TACO"] or p == "obo" else "",
                     "yes" if p in used["NEVO"] or p == "obo" else ""] for p, ns, what in NAMESPACES])
    lines += ["", "## 4. URIs", "",
              "The URIs each table mints for its food items, nutritional values and measures. The last column "
              "counts how many URIs of each kind follow the pattern.", ""]
    lines += table(["Table", "Kind", "Pattern", "Example", "Follow it"],
                   [[name, level, f"`{TEMPLATES[(name, level)]}`", f"`{short(eg)}`", f"{ok:,} of {total:,}"]
                    for (name, level), (ok, total, eg) in f["patterns"].items()])
    nevo_named, own = f["TACO nutrient names"]["nevonut"], f["TACO nutrient names"]["tacoid"]
    lines += ["", "NEVO names nutrients with its own URIs (`nevonut:PROT` for protein). TACO uses NEVO's URI "
              f"wherever NEVO has the same nutrient: {len(nevo_named)} of its {len(nevo_named) + len(own)} "
              f"nutrients, {sum(nevo_named.values()):,} of its {sum(nevo_named.values()) + sum(own.values()):,} "
              "values (`data/alignment/taco_nevo_nutrients.csv`). For the other "
              f"{len(own)} nutrients, {sum(own.values()):,} values, TACO uses its own URI "
              "(for example `tacoid:nutrient/manganese`): NEVO has no manganese, no amino acid but tryptophan and "
              "no code for total carbohydrate, and has some fatty acids only as cis and trans, or n-3 and n-6, "
              f"apart. For {len(definitions().COULD_TAKE)} of those fatty acids TACO's own INFOODS tagnames or names "
              "give the form NEVO has a code for, so they could take NEVO's code; and a shared code is not always "
              "the same quantity: TACO calculates carbohydrate and energy another way than NEVO "
              f"([analysis/nutrient_definitions.md]({GITHUB}analysis/nutrient_definitions.md)). "
              "Food types are FoodOn classes (`obo:FOODON_…`), nutrient classes are CDNO classes "
              "(`obo:CDNO_…`), and units are OM units. In NEVO's graph, `nevonut:PROT` is a "
              + ", ".join(f"`{x}`" for x in f["nutrient types"]) + ".", "",
              "## 5. Schema: classes and properties only", "",
              "Boxes are classes; rounded boxes are datatypes. A food item is also an instance of a FoodOn "
              "class, and a nutritional value of a CDNO class (`rdf:type`).", "", SCHEMA, ""]
    props = sorted(f["properties"].items(), key=lambda kv: (list(LEVELS).index(kv[0][0]), kv[0][1]))
    lines += table(["On a", "Property", "TACO uses it", "NEVO uses it"],
                   [[level, f"`{prop}`", num(c.get("TACO", "")), num(c.get("NEVO", ""))]
                    for (level, prop), c in props])
    lines += ["", "## 6. Example: instances only", "",
              "TACO food 574, raw red beans: its protein value with its measure, and a value TACO reports as a "
              "trace, which has a status and no measure. Each box is an instance and lists its classes; rounded "
              "boxes are literals.", "", mermaid_example(triples), "",
              f"The same food as RDF: [example_food_574.ttl]({GITHUB}docs/taco-in-nice-food/files/knowledge-graph/"
              "example_food_574.ttl).", "", "## 7. Same and different, TACO and NEVO", ""]
    both = [p for (_, p), c in props if "TACO" in c and "NEVO" in c]
    only_taco = [p for (_, p), c in props if "TACO" in c and "NEVO" not in c]
    only_nevo = [p for (_, p), c in props if "NEVO" in c and "TACO" not in c]
    lines += [f"- Both tables use: {', '.join(f'`{p}`' for p in dict.fromkeys(both))}.",
              f"- Only TACO uses: {', '.join(f'`{p}`' for p in dict.fromkeys(only_taco))}.",
              f"- Only NEVO uses: {', '.join(f'`{p}`' for p in dict.fromkeys(only_nevo))}"
              + (": NEVO's own food codes, where TACO gives its food number with `dcterms:identifier`. Every "
                 "other property NEVO uses, TACO uses too." if set(only_nevo) <= NEVO_CODES else "."),
              "- Units, as `om:hasUnit` values (an OM unit and the same unit as a string):", ""]
    lines += table(["Unit", "TACO", "NEVO"], [[u, num(c.get("TACO", "")), num(c.get("NEVO", ""))]
                                             for u, c in sorted(f["units"].items())])
    lines += ["", f"- {f['other food items']} NEVO food items are typed with classes other than FoodOn's "
              f"({', '.join(f['other food classes'])}); TACO types foods only with FoodOn classes, and none "
              "with a class FoodOn places under an organism or plant.", ""]
    section = 8
    if code:
        lines += [f"## {section}. NICE-Food's datasets, read from its code", "",
                  "What each notebook of NICE-Food's pipeline ([rivm-syso/nicekg_processing]"
                  f"(https://github.com/rivm-syso/nicekg_processing), commit `{code['commit']}`) mints and uses, "
                  "read from its code. TACO is added for comparison.", ""]
        body = [[name, "<br/>".join(f"`{m}`" for m in d["minted"]), ", ".join(f"`{c}`" for c in d["classes"]),
                 ", ".join(f"`{p}`" for p in d["properties"])] for name, d in code["datasets"].items()]
        body.append(["TACO", "`https://w3id.org/taco-rdf/id/`", "`fio:FoodItem`, `fio:NutritionalValue`, "
                     "`om:Measure`", ", ".join(f"`{p}`" for p in dict.fromkeys(both + only_taco))])
        lines += table(["Dataset", "Mints URIs under", "Types with", "Properties it adds"], body)
        lines += ["", "NEVO, LEDA, LCA and TACO describe food items with `fio:FoodItem` and their numbers with "
                  "`om:Measure`, `om:hasValue`, `om:hasNumericalValue` and `om:hasUnit`; NEVO, LEDA and TACO also "
                  "share `fio:NutritionalValue` and `fio:hasNutrient`. KAP describes its measurements with SOSA "
                  "and SAREF.", ""]
        section += 1
    if taco_graph is not None:
        classes = Counter(short(str(o)) for o in taco_graph.objects(None, RDF.type)
                          if str(o).startswith("https://w3id.org/taco-rdf/vocab#"))
        lines += [f"## {section}. TACO-RDF's own graph", "",
                  f"The converter first builds TACO-RDF's own graph ({len(taco_graph):,} triples), with TACO's "
                  "vocabulary and QUDT units: " + ", ".join(f"{c:,} `{k}`" for k, c in classes.most_common(5)) +
                  ". It keeps alignment provenance and corrections. The NICE-Food export above is derived from it "
                  "and uses the same URIs for foods and values; it adds the calculated available carbohydrate.", ""]
        section += 1
    lines += [f"## {section}. More foods in common", "",
              f"Today {num(shared['TACO now'])} TACO foods and {num(shared['NEVO now'])} NEVO food items share a "
              f"FoodOn class ({num(shared['classes now'])} classes), so the same queries find them as the same kind "
              f"of food. Another {num(shared['TACO linked'])} TACO foods and {num(shared['NEVO linked'])} NEVO food "
              "items are one subclass step from a class of the other table, so a query for the more general "
              "class finds both."]
    if shared["sheets"]:
        lines += ["", f"Among the foods still without a type, the candidates for review include a class the other "
                  f"table already uses for {num(shared['TACO could join'])} TACO foods "
                  f"({num(shared['TACO could join by name'])} from the food's own name) and "
                  f"{num(shared['NEVO could join'])} NEVO food items ({num(shared['NEVO could join by name'])} from "
                  "the name). If reviewers accept those candidates, these foods join the shared ones. They are "
                  "upper bounds: reviewers decide."]
    lines.append("")
    section += 1
    lines += [f"## {section}. Points to agree on", "",
              "1. Each table mints its own URIs under its own domain. TACO uses one pattern for foods, values and "
              "measures (section 4); NEVO's values sit in the same namespace as its nutrients. Do we want a "
              "common pattern for values and measures?",
              "2. Nutrients: TACO reuses NEVO's nutrient URIs where NEVO has the nutrient, so NICE-Food's "
              "queries work unchanged; it names the nutrients NEVO lacks under its own domain. If every "
              "value also carries a CDNO class, queries can select by CDNO and each table can keep its own "
              "nutrient codes. Which should the shared queries use? A shared code is not always the same quantity: "
              "TACO calculates carbohydrate and energy another way than NEVO (`analysis/nutrient_definitions.md`).",
              f"3. CDNO on every value: {num(n['values with a CDNO class'])} of {num(n['nutritional values'])} "
              f"NEVO values and {num(t['values with a CDNO class'])} of {num(t['nutritional values'])} TACO values "
              "have a CDNO class. TACO's mapping offers classes for NEVO's total fat and tryptophan "
              "(`data/alignment/nevo_cdno_completion.csv`).",
              "4. Values without a number: TACO states trace, not applicable or under re-evaluation with "
              "`taco:valueStatus`. Should NICE-Food have a common term for this?",
              "5. Calculated values: TACO records what a value was calculated from with `prov:wasDerivedFrom`.",
              "6. Units: both tables give an OM unit and a string for g, mg, kcal and kJ, and only a string for "
              "µg. Should µg get an OM unit too?",
              "7. Food types: `rdf:type` to a FoodOn class, from a fixed release (FoodOn 2026-09-20, CDNO "
              "2026-06-10). Should the shared structure fix the releases, and allow classes outside FoodOn?",
              "8. Measurements: NEVO, LEDA, LCA and TACO use FIO with OM; KAP uses SOSA and SAREF. Is one "
              "pattern for measurements part of the common structure?", ""]
    section += 1
    terms = len(PROFILE_CLASSES) + len(PROFILE_PROPERTIES)
    lines += [f"## {section}. Towards a minimal interoperability profile", "",
              "A Minimal Interoperability Profile ([MIP](https://github.com/fensel/MIP)) is the smallest "
              "ontology-based model, 10 to 15 classes and properties, that lets datasets exchange data, reusing "
              f"established ontologies and checked with SHACL. The structure TACO and NEVO share has {terms} terms: "
              f"the classes {', '.join(f'`{c}`' if ':' in c else c for c in PROFILE_CLASSES)}, and the properties "
              f"{', '.join(f'`{p}`' for p in PROFILE_PROPERTIES)}. NEVO, LEDA and LCA already use its core. A "
              "draft profile could be these terms with SHACL shapes; TACO-RDF already checks NEVO's graph with "
              "SHACL shapes for this pattern (`shapes/nice-food/nevo-shapes.ttl`), and TACO's export follows the "
              "same pattern, so TACO can be the first table checked against the profile.", ""]
    section += 1
    lines += [f"## {section}. Where this meets work in progress", "",
              "- NEVO's representation: the CDNO classes TACO's mapping offers NEVO (point 3), and a sheet with "
              f"FoodOn suggestions for NEVO's {num(n['food items'] - n['with a FoodOn type'])} food items "
              "without a type, among them suggestions from similar typed TACO foods.",
              f"- Matching food terms to FoodOn: {term_requests} currently untyped TACO foods have no usable "
              "candidate in the historical search "
              "([analysis/foodon_term_requests.md](" + GITHUB + "analysis/foodon_term_requests.md)). "
              "A failed candidate search does not establish an ontology gap. The decompose-then-match approach "
              "of [rivm-syso/matching-complex-food-terms](https://github.com/rivm-syso/matching-complex-food-terms) "
              "can help investigate unresolved composite dishes or opportunities for more specific terms.", ""]
    return "\n".join(lines)


def definitions():
    """scripts/nutrient_definitions.py, for the TACO nutrients that could take a NEVO code."""
    spec = importlib.util.spec_from_file_location("nutrient_definitions", Path(__file__).with_name(
        "nutrient_definitions.py"))
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def protein_query_foods(endpoint: str) -> int:
    """How many TACO foods NICE-Food's own query protein_groups.rq finds, run as it is."""
    def run(query: str) -> list[dict[str, str]]:
        return sparql.select(query, endpoint)

    names = {r["n"] for r in run(f"SELECT DISTINCT ?n WHERE {{ ?f <http://purl.org/dc/terms/isVersionOf> <{TACO}> ; "
                                 "<http://www.w3.org/2004/02/skos/core#prefLabel> ?n FILTER(LANG(?n) = \"en\") }")}
    rows = run((ROOT / "queries" / "nice-food" / "protein_groups.rq").read_text(encoding="utf-8"))
    return len({r["foodname"] for r in rows} & names)


def summary(f: dict, shared: dict, protein_foods: int) -> str:
    """Two pages for the group: what TACO shares with NEVO, where it differs and why, and what to agree on."""
    t, n = f["numbers"]["TACO"], f["numbers"]["NEVO"]
    nevo_named, own = f["TACO nutrient names"]["nevonut"], f["TACO nutrient names"]["tacoid"]
    with DEFINITIONS.open(encoding="utf-8", newline="") as fh:
        verdicts = Counter(r["verdict"] for r in csv.DictReader(fh))
    nd = definitions()
    could = len(set(nd.COULD_TAKE) & {k.rsplit("/", 1)[-1] for k in own})  # own's keys are nutrient/<key>
    same = verdicts[nd.VERDICTS[0]] + verdicts[nd.VERDICTS[1]]
    only_nevo = sorted({p for (_, p), c in f["properties"].items() if "NEVO" in c and "TACO" not in c})
    kg = f"{GITHUB}docs/taco-in-nice-food/files/knowledge-graph/"
    lines = [
        "# TACO in NICE-Food: summary", "",
        f"Generated on {datetime.date.today().isoformat()} by `python scripts/describe_structure.py` from the same "
        f"data as [docs/structure.md]({GITHUB}docs/structure.md), the full description, and checked by "
        "`python verification/structure_check.py`.", "",
        "TACO, the Brazilian food composition table (NEPA-UNICAMP, 4th edition, 2011), is written in the pattern "
        f"NICE-Food uses for NEVO: {num(t['food items'])} foods and {num(t['nutritional values'])} nutritional "
        f"values in one Turtle file, [taco_nice_food.ttl]({kg}taco_nice_food.ttl), with one food to read in "
        f"[example_food_574.ttl]({kg}example_food_574.ttl). Loaded next to NICE-Food's NEVO graphs and FoodOn, "
        f"NICE-Food's own query `protein_groups.rq` runs unchanged and finds {protein_foods} TACO foods.", "",
        "## What TACO shares with NEVO", "",
        f"- The same {len(PROFILE_CLASSES) + len(PROFILE_PROPERTIES)} terms: the classes "
        + ", ".join(f"`{c}`" if ":" in c else c for c in PROFILE_CLASSES) + ", and the properties "
        + ", ".join(f"`{p}`" for p in PROFILE_PROPERTIES) + ".",
        f"- Foods typed with a FoodOn class by `rdf:type`, not linked by SKOS: {num(t['with a FoodOn type'])} of "
        f"{num(t['food items'])} TACO foods. {num(shared['TACO now'])} TACO foods and {num(shared['NEVO now'])} NEVO "
        f"food items share a FoodOn class ({num(shared['classes now'])} classes).",
        f"- Values typed with a CDNO class: {num(t['values with a CDNO class'])} of "
        f"{num(t['nutritional values'])} TACO values, {num(n['values with a CDNO class'])} of "
        f"{num(n['nutritional values'])} NEVO values.",
        "- Units as an OM unit and a string; the edition as `dcterms:hasVersion`, in each table's language.",
        f"- NEVO's nutrient URIs: {len(nevo_named)} of TACO's {len(nevo_named) + len(own)} nutrients use them, "
        f"{sum(nevo_named.values()):,} of {sum(nevo_named.values()) + sum(own.values()):,} values.", "",
        "## Where TACO differs, and why", ""]
    lines += table(["Difference", "Why"], [
        ["TACO's URIs are under `https://w3id.org/taco-rdf/id/`", "each table mints its own URIs"],
        [f"{len(own)} nutrients have TACO's own URI", "NEVO lacks some (manganese, amino acids but tryptophan, total "
         "carbohydrate) and has some fatty acids only in forms TACO does not tell apart; "
         f"{could} could take NEVO's code, as TACO's own tagnames name NEVO's form"],
        [f"{num(t['values with a status instead'])} values have `taco:valueStatus` instead of a number",
         "TACO reports a trace, not applicable or under re-evaluation; a trace is not zero"],
        [f"{num(t['calculated values (PROV)'])} values have `prov:wasDerivedFrom`",
         "available carbohydrate is calculated from TACO's carbohydrate and fibre"],
        ["the food's number is `dcterms:identifier`",
         "NEVO's " + " and ".join(f"`{p}`" for p in only_nevo) + " name NEVO"]])
    lines += ["", "## Is a shared nutrient code the same quantity?", "",
              f"Of the {sum(verdicts.values())} codes TACO shares with NEVO "
              f"([analysis/nutrient_definitions.md]({GITHUB}analysis/nutrient_definitions.md)), {same} are the same "
              f"quantity ({verdicts[nd.VERDICTS[0]]} checked with the data, {verdicts[nd.VERDICTS[1]]} the same "
              f"element or compound), {verdicts[nd.VERDICTS[2]]} is in another unit, {verdicts[nd.VERDICTS[3]]} are "
              f"calculated another way, {verdicts[nd.VERDICTS[4]]} has NEVO's values under another code, and "
              f"{verdicts[nd.VERDICTS[5]]} are to confirm with NEVO's method.", "",
              "- Carbohydrate: NEVO's available carbohydrate is sugars plus starch, TACO's is calculated by "
              "difference.",
              "- Energy: NEVO's follows the general EU factors, TACO's Atwater's specific factors.",
              "- Sodium: NICE-Food's graph writes NEVO's sodium as `nevonut:nan`, since pandas reads the code `NA` "
              "as a missing value, so TACO's sodium and NEVO's never meet in a query.",
              "- Tryptophan: g in TACO, mg in NEVO.", "",
              "## Points to agree on", "",
              "1. Nutrient identity: NEVO's codes, which make NEVO the reference for every table, or a neutral one, "
              "such as a CDNO class with how the value was obtained, or INFOODS tagnames, which TACO already "
              "declares?",
              "2. Values calculated another way: separate codes, or the method on each value?",
              "3. Values without a number: one term for a trace, not applicable or under re-evaluation?",
              "4. Food codes: one property for each table's own food code?",
              "5. Releases: the shared graph pinned to FoodOn 2026-09-20 and CDNO 2026-06-10?", "",
              "## More", "",
              f"- [docs/structure.md]({GITHUB}docs/structure.md): namespaces, URIs, the schema, an example, "
              "NICE-Food's other datasets, foods in common.",
              f"- [analysis/nutrient_definitions.md]({GITHUB}analysis/nutrient_definitions.md): each shared "
              "nutrient code, with TACO's INFOODS tagnames and the tests on both tables.", ""]
    return "\n".join(lines)


def build_all(endpoint: str, nicekg: Path | None) -> tuple[str, str]:
    """docs/structure.md and docs/summary.md, from one reading of the data."""
    taco_graph = Graph().parse(BUILD_DIR / "taco.ttl", format="turtle") if (BUILD_DIR / "taco.ttl").is_file() \
        else None
    code = nicefood_code(nicekg) if nicekg else None
    with TERM_REQUESTS.open(encoding="utf-8") as fh:
        term_requests = sum(1 for _ in csv.DictReader(fh))
    f, shared = facts(endpoint), shared_foods(endpoint)
    return (document(f, example(endpoint), taco_graph, code, shared, term_requests),
            summary(f, shared, protein_query_foods(endpoint)))


def build(endpoint: str, nicekg: Path | None) -> str:
    return build_all(endpoint, nicekg)[0]


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--endpoint", default=ENDPOINT)
    p.add_argument("--nicekg", type=Path, help="a clone of rivm-syso/nicekg_processing, to read its code")
    p.add_argument("--out", type=Path, default=OUT)
    p.add_argument("--summary", type=Path, default=SUMMARY)
    args = p.parse_args()
    doc, short = build_all(args.endpoint, args.nicekg)
    args.out.write_text(doc, encoding="utf-8", newline="\n")
    args.summary.write_text(short, encoding="utf-8", newline="\n")
    print(f"wrote {args.out} and {args.summary} ({len(short.split())} words)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
