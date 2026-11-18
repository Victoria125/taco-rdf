"""Why TACO's foods link to FoodOn by rdf:type and not SKOS, and why old SKOS candidates are not converted.

1. NICE-Food's own graph (Fuseki's nicefood dataset): how its NEVO food items link to FoodOn, and which SKOS
   properties they use.
2. NICE-Food's query, run with Jena's ARQ on the part of TACO's NICE-Food export it reads (food items, their
   types and names, their protein values), with the FoodOn subclass edges above TACO's classes and the
   nutrient definitions as loaded in Fuseki: once as it is, compared with the same query on Fuseki over the
   whole dataset, and once with every food's FoodOn rdf:type replaced by skos:closeMatch. The SKOS version
   is only a copy in a temporary folder; nothing in the project or in Fuseki changes.
3. A reasoner: owlrl computes the RDFS closure of those skos:closeMatch links with the SKOS axioms that bear
   on them (W3C SKOS: closeMatch is a subproperty of mappingRelation, of semanticRelation, whose domain and
   range are skos:Concept): does any food get a FoodOn type, and do the foods become concepts?
4. The 125 untyped foods whose candidates are SKOS rows: their relations, their notes, and what converting
   the rows to rdf:type would entail, by the owlrl closure with FoodOn's subclass edges.
5. Lean: the rows of point 4 go to build/verification/SkosRows.lean, with theorems for their counts and for
   the publication rule giving none of them a type; mutants must be rejected. verification/lean/
   TacoTyping.lean proves that a food without an asserted type is entailed a member of no class.

No tool shows a person's view: that food items are not SKOS concepts is also Vivishwan's position, as he
told Vitória; point 3 shows only what SKOS's own axioms entail.

    $env:PYTHONPATH = "src"; python verification/skos_check.py --lake-project C:/path/to/project
"""

from __future__ import annotations

import argparse
import csv
import io
import os
import subprocess
import sys
import tempfile
from collections import Counter
from pathlib import Path

import owlrl
import requests
from rdflib import RDF, RDFS, SKOS, Graph, Namespace, URIRef

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "verification"))
import taco_typing_state as state  # noqa: E402

OBO = "http://purl.obolibrary.org/obo/"
FOODON = OBO + "FOODON_"
FIO = Namespace("http://www.foodvoc.org/resource/fio#")
OM = Namespace("http://www.ontology-of-units-of-measure.org/resource/om-2/")
NEVO_SOURCE = "https://www.rivm.nl/nederlands-voedingsstoffenbestand"
QUERY = ROOT / "queries" / "nice-food" / "protein_groups_cdno.rq"
OUT = ROOT / "build" / "verification" / "SkosRows.lean"
JAVA = Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Java" / "jdk-21.0.12.1+1" / "bin" / "java.exe"
JAR = ROOT.parent / "tools" / "apache-jena-fuseki-6.2.0" / "fuseki-server.jar"
ROOTS = ("COB_0000022", "PO_0000003")
MAPPINGS = ["exactMatch", "closeMatch", "narrowMatch", "broadMatch", "relatedMatch"]
RELATION_ID = {"exactMatch": 1, "closeMatch": 2, "narrowMatch": 3, "broadMatch": 4, "relatedMatch": 5}
PREFIXES = ("PREFIX fio: <http://www.foodvoc.org/resource/fio#> PREFIX dcterms: <http://purl.org/dc/terms/> "
            "PREFIX skos: <http://www.w3.org/2004/02/skos/core#> "
            "PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#> ")


def construct(query: str) -> Graph:
    """A CONSTRUCT query on Fuseki's nicefood dataset, as a graph."""
    r = requests.post(state.ENDPOINT, data={"query": query}, headers={"Accept": "text/turtle"}, timeout=900)
    r.raise_for_status()
    return Graph().parse(data=r.text, format="turtle")


def values(iris: set[str]) -> str:
    return " ".join(f"<{i}>" for i in sorted(iris))


def edges_above(classes: set[str]) -> Graph:
    g = Graph()
    items = sorted(classes)
    for i in range(0, len(items), 150):
        g += construct(f"{PREFIXES} CONSTRUCT {{ ?a rdfs:subClassOf ?b }} WHERE {{ VALUES ?c {{ "
                       f"{values(set(items[i:i + 150]))} }} ?c rdfs:subClassOf* ?a . "
                       "?a rdfs:subClassOf ?b . FILTER (isIRI(?a) && isIRI(?b)) }")
    return g


def skos_axioms() -> Graph:
    """The axioms of the W3C SKOS RDF schema (http://www.w3.org/2004/02/skos/core) that bear on closeMatch."""
    g = Graph()
    g.add((SKOS.closeMatch, RDFS.subPropertyOf, SKOS.mappingRelation))
    g.add((SKOS.mappingRelation, RDFS.subPropertyOf, SKOS.semanticRelation))
    g.add((SKOS.semanticRelation, RDFS.domain, SKOS.Concept))
    g.add((SKOS.semanticRelation, RDFS.range, SKOS.Concept))
    return g


def what_the_query_reads(taco: Graph) -> Graph:
    """The triples of TACO's export that NICE-Food's protein query reads: food items, their types and names,
    and their protein values with measures."""
    g = Graph()
    for f in taco.subjects(RDF.type, FIO.FoodItem):
        g += taco.triples((f, RDF.type, None))
        g += taco.triples((f, SKOS.prefLabel, None))
        for v in taco.objects(f, FIO.hasNutritionalValue):
            if (v, RDF.type, URIRef(OBO + "CDNO_0200040")) in taco:
                g.add((f, FIO.hasNutritionalValue, v))
                g += taco.triples((v, None, None))
                for m in taco.objects(v, OM.hasValue):
                    g += taco.triples((m, None, None))
    return g


def jena(java: Path, jar: Path, graph: Graph, query: Path) -> set[str]:
    """The food names NICE-Food's query finds in a graph, by Jena's ARQ on a temporary file."""
    with tempfile.TemporaryDirectory() as tmp:
        data = Path(tmp) / "data.nt"
        graph.serialize(data, format="nt", encoding="utf-8")
        result = subprocess.run([str(java), "-cp", str(jar), "arq.sparql", "--data", data.as_uri(),
                                 "--query", query.resolve().as_uri(), "--results", "CSV"],
                                capture_output=True, check=True)
    text = result.stdout.decode("utf-8")
    return {r["foodname"] for r in csv.DictReader(io.StringIO(text))}


def lean_data(rows: list[dict], claims: dict[str, int]) -> str:
    def b(x: bool) -> str:
        return "true" if x else "false"

    entries = ",\n  ".join(f"⟨{r['food']}, {r['relation']}, {b(r['pinned'])}, {b(r['blocked'])}⟩"
                           for r in rows)
    counts = "\n".join(f"theorem n_{name} : (rows.filter (·.relation == {i})).length = {claims[name]} := by "
                       "decide" for name, i in (("exact", 1), ("close", 2), ("narrow", 3), ("broad", 4),
                                                ("related", 5)))
    return f"""

/-! ## The SKOS candidate rows of the untyped TACO foods, from verification/skos_check.py -/

namespace SkosRows
open TacoTyping

set_option maxRecDepth 100000

/-- A row: food, relation (0 type, 1 exact, 2 close, 3 narrow, 4 broad, 5 related), class in the pinned
    release, class with an organism or whole-plant ancestor. -/
structure Row where
  food : Nat
  relation : Nat
  pinned : Bool
  blocked : Bool

def rows : List Row := [
  {entries}]

theorem n_rows : rows.length = {claims['rows']} := by decide
theorem n_foods : (rows.map (·.food)).eraseDups.length = {claims['foods']} := by decide
{counts}
/-- None of these rows is a type row, so the publication rule gives none of them a type. -/
theorem none_published : rows.all (fun r => !published (relation r.relation) r.pinned r.blocked) = true := by
  decide

end SkosRows
"""


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--lake-project", type=Path, default=ROOT / "verification" / "lean",
                   help="a Lake project with Mathlib built (default verification/lean)")
    p.add_argument("--java", type=Path, default=JAVA, help="Java 21, for Jena's ARQ")
    p.add_argument("--jar", type=Path, default=JAR, help="a jar bundling Jena's ARQ, e.g. fuseki-server.jar")
    p.add_argument("--no-mutants", action="store_true", help="skip the mutation tests of the Lean file")
    args = p.parse_args()
    problems = []

    # 1. NICE-Food's own graph
    nevo_items = f"?f a fio:FoodItem ; dcterms:isVersionOf <{NEVO_SOURCE}>"
    typed = state.sparql(f"{PREFIXES} SELECT (COUNT(DISTINCT ?f) AS ?n) WHERE {{ {nevo_items} ; a ?c . "
                         f'FILTER STRSTARTS(STR(?c), "{FOODON}") }}')
    used = state.sparql(f"{PREFIXES} SELECT ?p (COUNT(*) AS ?n) WHERE {{ {nevo_items} ; ?p ?o . "
                        'FILTER STRSTARTS(STR(?p), "http://www.w3.org/2004/02/skos/core#") } GROUP BY ?p')
    mapping = " ".join(f"skos:{m}" for m in MAPPINGS)
    to_foodon = state.sparql(f"{PREFIXES} SELECT ?p (COUNT(*) AS ?n) WHERE {{ ?s ?p ?o . VALUES ?p {{ "
                             f'{mapping} }} FILTER STRSTARTS(STR(?o), "{FOODON}") }} GROUP BY ?p')
    n_typed = int(typed[0]["n"]["value"])
    skos_used = {b["p"]["value"].rsplit("#", 1)[-1]: int(b["n"]["value"]) for b in used}
    n_mapped = sum(int(b["n"]["value"]) for b in to_foodon)
    print(f"1. NICE-Food: {n_typed} NEVO food items typed with FoodOn by rdf:type; SKOS properties on NEVO "
          f"food items: {skos_used or 'none'}; SKOS mapping links to FoodOn in the dataset: {n_mapped}")
    if n_mapped or set(skos_used) & set(MAPPINGS):
        problems.append("NICE-Food links food items to FoodOn by SKOS somewhere")

    # 2. NICE-Food's query, with rdf:type and with skos:closeMatch
    taco = what_the_query_reads(Graph().parse(ROOT / "build" / "taco_nice_food.ttl", format="turtle"))
    types = {(s, o) for s, o in taco.subject_objects(RDF.type) if str(o).startswith(FOODON)}
    nutrients = {str(o) for o in taco.objects(None, FIO.hasNutrient)}
    support = edges_above({str(o) for _, o in types})
    support += construct(f"{PREFIXES} CONSTRUCT {{ ?n a ?t . ?n rdfs:label ?l }} WHERE {{ VALUES ?n {{ "
                         f"{values(nutrients)} }} ?n a ?t . OPTIONAL {{ ?n rdfs:label ?l }} }}")
    as_is = jena(args.java, args.jar, taco + support, QUERY)
    taco_names = {str(o) for o in taco.objects(None, SKOS.prefLabel)}
    on_fuseki = {b["foodname"]["value"] for b in state.sparql(QUERY.read_text(encoding="utf-8"))} & taco_names
    with_skos = taco + support
    for s, o in types:
        with_skos.remove((s, RDF.type, o))
        with_skos.add((s, SKOS.closeMatch, o))
    as_skos = jena(args.java, args.jar, with_skos, QUERY)
    print(f"2. NICE-Food's query on TACO (Jena ARQ): {len(as_is)} foods with rdf:type (Fuseki, whole "
          f"dataset: {len(on_fuseki)}); {len(as_skos)} with skos:closeMatch")
    if as_is != on_fuseki:
        problems.append(f"ARQ and Fuseki differ: {sorted(as_is ^ on_fuseki)[:5]}")
    if as_skos or not as_is:
        problems.append("the query should find TACO foods by rdf:type and none by skos:closeMatch")

    # 3. The reasoner on the SKOS links
    closure = Graph()
    for s, o in types:
        closure.add((s, SKOS.closeMatch, o))
    closure += edges_above({str(o) for _, o in types}) + skos_axioms()
    owlrl.DeductiveClosure(owlrl.RDFS_Semantics).expand(closure)
    foods = {s for s, _ in types}
    typed_after = {s for s in foods for o in closure.objects(s, RDF.type) if str(o).startswith(FOODON)}
    concepts = {s for s in foods if (s, RDF.type, SKOS.Concept) in closure}
    class_concepts = {o for _, o in types if (o, RDF.type, SKOS.Concept) in closure}
    print(f"3. owlrl, RDFS closure of {len(foods)} foods linked by skos:closeMatch: {len(typed_after)} get a "
          f"FoodOn type; {len(concepts)} become skos:Concept, and so do {len(class_concepts)} FoodOn classes")
    if typed_after or len(concepts) != len(foods):
        problems.append("the closure should give no FoodOn type and make every food a skos:Concept")

    # 4. The SKOS candidates of the untyped foods
    with (ROOT / "data" / "alignment" / "alignments.csv").open(encoding="utf-8") as fh:
        alignment = [r for r in csv.DictReader(fh)
                     if r["source_type"] == "food" and r["target_iri"].startswith(FOODON)]
    with (ROOT / "analysis" / "data" / "foodon_typing_gaps.csv").open(encoding="utf-8") as fh:
        untyped = {r["food_number"] for r in csv.DictReader(fh)}
    skos_rows = [r for r in alignment
                 if r["source_key"] in untyped and r["predicate"] not in ("type", "rdf:type")]
    targets = {r["target_iri"] for r in skos_rows}
    pinned = state.pinned_release()
    blocked = state.with_organism_ancestor(targets)
    convert = Graph()
    for r in skos_rows:
        convert.add((URIRef(f"urn:taco:food/{r['source_key']}"), RDF.type, URIRef(r["target_iri"])))
    convert += edges_above(targets)
    owlrl.DeductiveClosure(owlrl.RDFS_Semantics).expand(convert)
    organisms = {s for s in convert.subjects(RDF.type, None)
                 if any((s, RDF.type, URIRef(OBO + x)) in convert for x in ROOTS)}
    relations = Counter(r["predicate"] for r in skos_rows)
    notes = [r for r in skos_rows if r["note"].strip()]
    print(f"4. SKOS candidate rows of untyped foods: {len(skos_rows)} rows for "
          f"{len({r['source_key'] for r in skos_rows})} foods: {dict(relations)}")
    print(f"   converted to rdf:type, the RDFS closure would make {len(organisms)} foods organisms or plants")
    print(f"   {len(notes)} rows carry a note, for example:")
    for r in notes[:4]:
        print(f"     food {r['source_key']}: {r['predicate']} {r['target_label']}: {r['note'][:90]}")

    # 5. Lean
    rows = [{"food": int(r["source_key"]), "relation": RELATION_ID[r["predicate"]],
             "pinned": r["target_iri"] in pinned, "blocked": r["target_iri"] in blocked} for r in skos_rows]
    claims = {"rows": len(rows), "foods": 125, "exact": relations["exactMatch"],
              "close": relations["closeMatch"], "narrow": relations["narrowMatch"],
              "broad": relations["broadMatch"], "related": relations["relatedMatch"]}
    base = (ROOT / "verification" / "lean" / "TacoTyping.lean").read_text(encoding="utf-8")
    state.write_lean(OUT, base + lean_data(rows, claims))
    print(f"5. wrote {OUT}; checking with Lean")
    code = state.check_with_lean(OUT, args.lake_project)
    if not args.no_mutants:
        problems += state.mutants_rejected(OUT, args.lake_project, [
            ("a SKOS row turned into a type row", r"⟨(\d+), [1-5], true, false⟩", r"⟨\1, 0, true, false⟩"),
            ("a food count off by one", r"(eraseDups\.length = )125", r"\g<1>126")])
    for problem in problems:
        print(f"PROBLEM: {problem}")
    return 1 if problems or code else 0


if __name__ == "__main__":
    sys.exit(main())
