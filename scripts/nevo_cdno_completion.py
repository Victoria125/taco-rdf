"""Give NEVO's nutritional values in NICE-Food the CDNO classes TACO's mapping already supplies.

In NICE-Food's NEVO graph some nutrients carry no CDNO class, so questions that select values by CDNO class
cannot find them. TACO's NICE-Food export names its nutrients by NEVO's codes (data/alignment/
taco_nevo_nutrients.csv) and types each value with a CDNO class. Where a NEVO code has no CDNO class in NEVO's
graph but has one in TACO's, this script proposes TACO's class for NEVO's values of that code:

- data/alignment/nevo_cdno_completion.csv: the codes, their CDNO class and the number of NEVO values (codes
  and counts only, no NEVO value);
- build/nevo/nevo_cdno_completion.ttl: one rdf:type triple per NEVO value, to load beside NICE-Food's graph
  (in build/, which git ignores, as it lists NEVO's value identifiers);
- with --question, the same competency question asked before and after, by Jena's ARQ on the foods of one
  kind, so that nothing changes in Fuseki; the result goes to build/nevo/nevo_cdno_completion.json.

    $env:PYTHONPATH = "src"; python scripts/nevo_cdno_completion.py --question
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import subprocess
import sys
import tempfile
from pathlib import Path

from rdflib import RDF, Graph, URIRef

from taco_rdf import sparql as store
from taco_rdf import tools
from taco_rdf.namespaces import BUILD_DIR, NEVO_SOURCE, ROOT, TACO_SOURCE
from taco_rdf.nice_food_queries import richest

ENDPOINT = store.endpoint()
TACO = str(TACO_SOURCE)
NEVO = str(NEVO_SOURCE)
OBO = "http://purl.obolibrary.org/obo/"
CSV_OUT = ROOT / "data" / "alignment" / "nevo_cdno_completion.csv"
TTL_OUT = BUILD_DIR / "nevo" / "nevo_cdno_completion.ttl"
JSON_OUT = BUILD_DIR / "nevo" / "nevo_cdno_completion.json"
PREFIXES = store.prefixes("rdf", "rdfs", "skos", "fio", "om", "dcterms", "obo")
WITHOUT_CDNO = PREFIXES + f"""SELECT ?n (SAMPLE(STR(?l)) AS ?label) (COUNT(?v) AS ?values) WHERE {{
  ?f dcterms:isVersionOf <{NEVO}> ; fio:hasNutritionalValue ?v . ?v fio:hasNutrient ?n .
  OPTIONAL {{ ?n rdfs:label ?l FILTER (LANG(?l) = "en") }}
  FILTER NOT EXISTS {{ ?v rdf:type ?c FILTER STRSTARTS(STR(?c), "{OBO}CDNO_") }}
}} GROUP BY ?n"""
TACO_CLASSES = PREFIXES + f"""SELECT DISTINCT ?n ?c (SAMPLE(STR(?l)) AS ?label) WHERE {{
  ?f dcterms:isVersionOf <{TACO}> ; fio:hasNutritionalValue ?v . ?v fio:hasNutrient ?n ; rdf:type ?c .
  FILTER STRSTARTS(STR(?c), "{OBO}CDNO_") OPTIONAL {{ ?c rdfs:label ?l }}
}} GROUP BY ?n ?c"""


def rows(endpoint: str, query: str) -> list[dict[str, str]]:
    return store.select(query, endpoint)


def completion(without: list[dict[str, str]], taco: list[dict[str, str]]) -> list[dict[str, str]]:
    """NEVO codes without a CDNO class whose TACO values have exactly one, with that class."""
    classes: dict[str, set[tuple[str, str]]] = {}
    for r in taco:
        classes.setdefault(r["n"], set()).add((r["c"], r.get("label", "")))
    out = []
    for r in without:
        found = classes.get(r["n"], set())
        if len(found) == 1:
            (cls, label), = found
            out.append({"nevo_code": r["n"].rsplit("#", 1)[-1], "nevo_label": r.get("label", ""),
                        "cdno_class": cls.rsplit("/", 1)[-1], "cdno_label": label, "nevo_values": r["values"],
                        "evidence": "TACO's values of the same NEVO code carry this class"})
    return sorted(out, key=lambda r: -int(r["nevo_values"]))


def additions(endpoint: str, mapping: list[dict[str, str]], nutrient_ns: str) -> Graph:
    g = Graph()
    for m in mapping:
        g += store.construct(PREFIXES + f"CONSTRUCT {{ ?v rdf:type obo:{m['cdno_class']} }} WHERE {{ "
                             f"?f dcterms:isVersionOf <{NEVO}> ; fio:hasNutritionalValue ?v . "
                             f"?v fio:hasNutrient <{nutrient_ns}{m['nevo_code']}> }}", endpoint)
    return g


def jena(java: Path, jar: Path, graph: Graph, query: str) -> list[dict[str, str]]:
    """A SELECT query on a graph, by Jena's ARQ on temporary files."""
    with tempfile.TemporaryDirectory() as tmp:
        data, q = Path(tmp) / "data.nt", Path(tmp) / "query.rq"
        graph.serialize(data, format="nt", encoding="utf-8")
        q.write_text(query, encoding="utf-8")
        out = subprocess.run([str(java), "-cp", str(jar), "arq.sparql", "--data", data.as_uri(), "--query",
                              q.as_uri(), "--results", "CSV"], capture_output=True, check=True).stdout
    return list(csv.DictReader(io.StringIO(out.decode("utf-8"))))


def question(endpoint: str, java: Path, jar: Path, kind: str, code: str, cdno: str, extra: Graph,
             nutrient_ns: str) -> dict[str, list[dict[str, str]]]:
    """The foods of a kind richest in a nutrient, before and after the additions, by ARQ."""
    subset = store.construct(PREFIXES + f"""CONSTRUCT {{
        ?food rdf:type fio:FoodItem ; rdf:type ?type ; dcterms:isVersionOf ?src ; skos:prefLabel ?name ;
              fio:hasNutritionalValue ?v . ?v ?vp ?vo . ?m om:hasNumericalValue ?x ; om:hasUnit ?u }} WHERE {{
        ?type rdfs:subClassOf* obo:{kind} .
        ?food rdf:type fio:FoodItem ; rdf:type ?type ; dcterms:isVersionOf ?src ; skos:prefLabel ?name ;
              fio:hasNutritionalValue ?v .
        ?v fio:hasNutrient <{nutrient_ns}{code}> ; ?vp ?vo ; om:hasValue ?m .
        ?m om:hasNumericalValue ?x . OPTIONAL {{ ?m om:hasUnit ?u }} }}""", endpoint)
    subset += store.construct(PREFIXES + f"CONSTRUCT {{ ?a rdfs:subClassOf ?b }} WHERE {{ "
                              f"?a rdfs:subClassOf* obo:{kind} . ?a rdfs:subClassOf ?b . FILTER isIRI(?b) }}",
                              endpoint)
    values = set(subset.subjects(None, None))
    after = subset + Graph()
    for v, _, c in extra.triples((None, RDF.type, None)):
        if v in values:
            after.add((v, RDF.type, URIRef(c)))
    query = richest(kind, cdno)
    return {"before": jena(java, jar, subset, query), "after": jena(java, jar, after, query)}


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--endpoint", default=ENDPOINT)
    p.add_argument("--question", action="store_true",
                   help="ask which foods of a kind have the most fat, before and after")
    p.add_argument("--kind", default="FOODON_00001256", help="FoodOn class of the kind (default dairy)")
    p.add_argument("--java", type=Path, default=tools.java())
    p.add_argument("--jar", type=Path, default=tools.fuseki_jar())
    args = p.parse_args()
    without = rows(args.endpoint, WITHOUT_CDNO)
    mapping = completion(without, rows(args.endpoint, TACO_CLASSES))
    nutrient_ns = without[0]["n"].rsplit("#", 1)[0] + "#"
    with CSV_OUT.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(mapping[0]), lineterminator="\n")
        w.writeheader()
        w.writerows(mapping)
    extra = additions(args.endpoint, mapping, nutrient_ns)
    TTL_OUT.parent.mkdir(parents=True, exist_ok=True)
    extra.serialize(TTL_OUT, format="turtle", encoding="utf-8")
    print(f"NEVO nutrients without a CDNO class: {len(without)} "
          f"({sum(int(r['values']) for r in without)} values)")
    for m in mapping:
        print(f"  {m['nevo_code']} {m['nevo_label']}: {m['cdno_class']} {m['cdno_label']} "
              f"({m['nevo_values']} NEVO values)")
    print(f"wrote {CSV_OUT} and {TTL_OUT} ({len(extra)} triples)")
    if args.question:
        answer = question(args.endpoint, args.java, args.jar, args.kind, "FAT", "CDNO_0200068", extra,
                          nutrient_ns)
        for when, found in answer.items():
            nevo = [r for r in found if r["source"] == NEVO]
            taco = [r for r in found if r["source"] == TACO]
            print(f"  {args.kind}, most fat, {when}: {len(taco)} TACO foods, {len(nevo)} NEVO foods; first: "
                  + "; ".join(f"{r['name']} {float(r['amount']):.0f} g" for r in taco[:3] + nevo[:3]))
        summary = {"kind": args.kind, "without": len(without),
                   "without_values": sum(int(r["values"]) for r in without), "mapping": mapping,
                   "question": answer}
        JSON_OUT.write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"wrote {JSON_OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
