"""Print TACO-RDF's ontology in short: its classes and properties, what each extends, and its imports.

ontology/taco.ttl is a small vocabulary on top of NICE-Food's (FIO): TACO's food is a fio:FoodItem, its
nutrient measurement a fio:NutritionalValue, and its properties specialise FIO's. It adds what is TACO's own:
the status of a value (measured, trace, not applicable, under re-evaluation), the origin of corrected values,
food groups, and the provenance of reviewed alignments. FoodOn and CDNO come in as modules of the classes the
graph uses, each from a fixed release.

    $env:PYTHONPATH = "src"; python scripts/show_ontology.py
"""

from __future__ import annotations

import sys

from rdflib import OWL, RDF, RDFS, Graph, URIRef

from taco_rdf.namespaces import FIO, ROOT

ONTOLOGY = ROOT / "ontology" / "taco.ttl"
VOCAB = "https://w3id.org/taco-rdf/vocab"
MODULES = [("FoodOn", ROOT / "ontology" / "imports" / "foodon-module.ttl"),
           ("CDNO", ROOT / "ontology" / "imports" / "cdno-module.ttl")]


def short(g: Graph, term: object) -> str:
    if isinstance(term, URIRef):
        try:
            return g.namespace_manager.normalizeUri(term)
        except ValueError:
            return str(term)
    return ""


def main() -> int:
    g = Graph().parse(ONTOLOGY, format="turtle")
    g.bind("fio", FIO)
    print(f"TACO vocabulary {g.value(URIRef(VOCAB), OWL.versionInfo)} (ontology/taco.ttl)")
    print("\nClasses, and what they extend:")
    for c in sorted(set(g.subjects(RDF.type, OWL.Class)), key=str):
        if str(c).startswith(VOCAB):
            parents = [short(g, p) for p in g.objects(c, RDFS.subClassOf) if isinstance(p, URIRef)]
            print(f"  {short(g, c):28} {', '.join(parents)}")
    print("\nProperties, and what they extend:")
    properties = (set(g.subjects(RDF.type, OWL.ObjectProperty))
                  | set(g.subjects(RDF.type, OWL.DatatypeProperty)))
    for p in sorted(properties, key=str):
        if str(p).startswith(VOCAB) and (p, RDFS.subPropertyOf, None) in g:
            print(f"  {short(g, p):28} {', '.join(short(g, s) for s in g.objects(p, RDFS.subPropertyOf))}")
    statuses = sorted(short(g, s) for s in g.subjects(RDF.type, URIRef(VOCAB + "#ValueStatus")))
    print(f"\nValue status: {', '.join(statuses)}")
    print("\nImported modules (only the classes the graph uses):")
    for name, path in MODULES:
        m = Graph().parse(path, format="turtle")
        classes = len(set(m.subjects(RDF.type, OWL.Class)))
        release = next((str(o) for o in m.objects(None, OWL.versionIRI)), "")
        print(f"  {name:7} {classes:5} classes, release {release.split('/releases/')[-1].split('/')[0]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
