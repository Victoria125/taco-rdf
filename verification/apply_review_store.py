"""Synchronize local Fuseki TACO data after review; preserve all other subjects.

The first run saves each previous TACO subgraph and both SPARQL directions.
Nutritional triples must already agree; only classification and provenance change.
"""

from __future__ import annotations

import gc
import json
import re

import requests
from rdflib import RDF, XSD, BNode, Graph, Literal, URIRef

from taco_rdf import sparql
from taco_rdf.namespaces import ID, ROOT, TACO

OUT = ROOT / "build/verification/review_application/store"
FOODON = "http://purl.obolibrary.org/obo/FOODON_"
MANAGED = re.compile(
    re.escape(str(ID)) + r"(?:food/|alignment/|review/|build-input/|alignment-set$|conversion$)")


def pairs(graph):
    return {
        (str(s), str(o))
        for s, o in graph.subject_objects(RDF.type)
        if str(s).startswith(str(ID) + "food/") and str(o).startswith(FOODON)
    }


def canonical(triples):
    # RDF 1.1 plain strings and xsd:string are the same RDF term; Jena emits the short form.
    def term(o):
        if isinstance(o, Literal):
            if o.datatype is None and o.language is None:
                return Literal(str(o), datatype=XSD.string)
            if o.datatype == XSD.decimal:
                return Literal(format(o.toPython().normalize(), "f"), datatype=XSD.decimal)
        return o

    return {(s, p, term(o)) for s, p, o in triples}


def nutrition(graph):
    return {
        triple
        for triple in graph
        if str(triple[0]).startswith(
            tuple(str(ID) + p for p in ("measurement/", "nutrient/", "category/", "reference/"))
        )
    }


def update_text(remove, insert):
    def block(rows):
        return "\n".join(sorted(" ".join(t.n3() for t in triple) + " ." for triple in rows))

    return "DELETE DATA {\n" + block(remove) + "\n};\nINSERT DATA {\n" + block(insert) + "\n}\n"


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    results = {}
    for dataset, filename in (("nicefood", "taco_nice_food.ttl"), ("taco_nevo", "taco.ttl")):
        desired_full = Graph().parse(ROOT / "build" / filename)
        desired = canonical(t for t in desired_full if MANAGED.match(str(t[0])))
        expected = pairs(desired_full)
        assert len(expected) == 597
        del desired_full
        gc.collect()
        # TBCA uses id/tbca/ in the same store; never include it in the review update.
        pattern = f"^{ID}(food/|alignment/|review/|build-input/|alignment-set$|conversion$)"
        query = f'CONSTRUCT {{ ?s ?p ?o }} WHERE {{ ?s ?p ?o FILTER REGEX(STR(?s), "{pattern}") }}'
        current_graph = sparql.construct(query, sparql.endpoint(dataset))
        current = canonical(current_graph)
        assert all(isinstance(t[0], URIRef) and MANAGED.match(str(t[0])) for t in desired | current)
        assert not nutrition(desired | current)
        assert not any(isinstance(term, BNode) for t in desired | current for term in t)
        removed, inserted = current - desired, desired - current
        assert all(p in (RDF.type, TACO.alignment) for s, p, _ in removed | inserted
                   if str(s).startswith(str(ID) + "food/")), "food values or labels differ"
        if dataset == "nicefood":
            assert all(p == RDF.type and str(o).startswith(FOODON) for _, p, o in removed | inserted), (
                "NICE-Food export changes more than food classes"
            )
        previous = OUT / f"{dataset}_managed_before.ttl"
        if not previous.exists():
            current_graph.serialize(previous, format="turtle")
        forward, rollback = update_text(removed, inserted), update_text(inserted, removed)
        if removed or inserted:
            (OUT / f"{dataset}_forward.ru").write_text(forward, encoding="utf-8")
            (OUT / f"{dataset}_rollback.ru").write_text(rollback, encoding="utf-8")
            response = requests.post(
                sparql.dataset(dataset) + "/update",
                data=forward.encode("utf-8"),
                headers={"Content-Type": "application/sparql-update"},
                timeout=300,
            )
            response.raise_for_status()
        actual = sparql.construct(query, sparql.endpoint(dataset))
        assert canonical(actual) == desired, f"{dataset}: store differs from generated graph"
        assert pairs(actual) == expected
        results[dataset] = {
            "removed": len(removed),
            "inserted": len(inserted),
            "foods_typed": len(expected),
            "nutrition_unchanged": True,
            "only_taco_subjects_modified": True,
            "exact_generated_classification_and_provenance": True,
        }
        print(dataset, results[dataset], flush=True)
        del current_graph, actual, current, desired
        gc.collect()
    (OUT / "result.json").write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
