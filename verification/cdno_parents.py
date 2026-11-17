"""Compare the parents of the CDNO classes in use, as CDNO states them and as the loaded FoodOn has them.

TACO's and NEVO's values are typed with CDNO classes. The nicefood store holds FoodOn's release, which brings
CDNO classes with it; queries that climb the class hierarchy read those parents. This script lists every CDNO
class a value in the store is typed with, and compares its named parents (rdfs:subClassOf) in the store with
those of the CDNO release itself.

    $env:PYTHONPATH = "src"; python verification/cdno_parents.py --cdno path/to/cdno.owl
"""

from __future__ import annotations

import argparse
from collections import defaultdict
from pathlib import Path

import requests
from rdflib import OWL, RDFS, Graph, URIRef

ENDPOINT = "http://localhost:3030/nicefood/sparql"
CLASSES = """
PREFIX fio: <http://www.foodvoc.org/resource/fio#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
SELECT DISTINCT ?c ?parent WHERE {
  ?v a fio:NutritionalValue , ?c . FILTER STRSTARTS(STR(?c), "http://purl.obolibrary.org/obo/CDNO_")
  OPTIONAL { ?c rdfs:subClassOf ?parent . FILTER isIRI(?parent) }
}
"""


def short(iri: str) -> str:
    return iri.rsplit("/", 1)[-1]


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--cdno", type=Path, required=True, help="CDNO release, e.g. cdno.owl")
    args = p.parse_args()
    r = requests.post(ENDPOINT, data={"query": CLASSES},
                      headers={"Accept": "application/sparql-results+json"}, timeout=900)
    r.raise_for_status()
    store: dict[str, set[str]] = defaultdict(set)
    for b in r.json()["results"]["bindings"]:
        store[b["c"]["value"]]
        if "parent" in b:
            store[b["c"]["value"]].add(b["parent"]["value"])
    cdno = Graph().parse(args.cdno, format="xml")
    labels = {str(s): str(o) for s, o in cdno.subject_objects(RDFS.label)}
    differ = 0
    for c in sorted(store):
        release = {str(o) for o in cdno.objects(URIRef(c), RDFS.subClassOf) if isinstance(o, URIRef)}
        if (URIRef(c), None, None) not in cdno:
            print(f"{short(c)} is not in the CDNO release")
            differ += 1
        elif store[c] != release:
            differ += 1
            print(f"{short(c)} {labels.get(c, '')}")
            for x in sorted(store[c] - release):
                print(f"    only in the store:  {short(x)} {labels.get(x, '')}")
            for x in sorted(release - store[c]):
                print(f"    only in CDNO:       {short(x)} {labels.get(x, '')}")
        if (URIRef(c), OWL.deprecated, None) in cdno:
            print(f"{short(c)} is deprecated in CDNO")
    print(f"\n{len(store)} CDNO classes in use; parents differ for {differ}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
