"""Extract the FoodOn classes the alignments use, with their superclasses, from the pinned release.

Also writes the index of every FoodOn class in that release, against which reviewers' proposals are checked.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import logging
import sys
import tempfile
import urllib.request
from collections import defaultdict
from collections.abc import Callable
from pathlib import Path

from rdflib import OWL, RDF, RDFS, Graph, Literal, Namespace, URIRef
from rdflib.namespace import DCTERMS, PROV

ROOT = Path(__file__).resolve().parents[1]
CSV_PATH = ROOT / "data" / "alignment" / "alignments.csv"
OUT_PATH = ROOT / "ontology" / "imports" / "foodon-module.ttl"
CLASSES_PATH = ROOT / "ontology" / "imports" / "foodon-classes.tsv"

RELEASE = "http://purl.obolibrary.org/obo/foodon/releases/2026-09-20/foodon.owl"
SOURCE_COMMIT = "cd73540243a84bcd511a500d9a497d12d7dc02f6"
SOURCE_URL = f"https://raw.githubusercontent.com/FoodOntology/foodon/{SOURCE_COMMIT}/foodon.owl"
SOURCE_SHA256 = "b897bf64c1b265c422db9ee01e1235c10c0b809e7f02326ef810a52068347edf"
OBO = Namespace("http://purl.obolibrary.org/obo/")
ORGANISM_ROOTS = (OBO.COB_0000022, OBO.PO_0000003)
MODULE_IRI = URIRef("https://w3id.org/taco-rdf/imports/foodon-module")


def ancestors(parents: dict[URIRef, set[URIRef]], cls: URIRef) -> set[URIRef]:
    seen: set[URIRef] = set()
    stack: list[URIRef] = [cls]
    while stack:
        for p in parents.get(stack.pop(), ()):
            if p not in seen:
                seen.add(p)
                stack.append(p)
    return seen


def load_release(path: Path | None) -> Graph:
    if path is None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "foodon.owl"
            print(f"downloading {SOURCE_URL}", file=sys.stderr)
            urllib.request.urlretrieve(SOURCE_URL, str(path))
            return parse_release(path)
    return parse_release(path)


def parse_release(path: Path) -> Graph:
    digest = hashlib.sha256(Path(path).read_bytes()).hexdigest()
    if digest != SOURCE_SHA256:
        raise SystemExit(f"{path} is not the pinned FoodOn file: SHA-256 {digest}, expected {SOURCE_SHA256}")
    return Graph().parse(path, format="xml")


def write_class_index(
    foodon: Graph,
    deprecated: set[URIRef],
    label: Callable[[URIRef], str | None],
    path: Path,
) -> int:
    prefix = str(OBO) + "FOODON_"
    rows = sorted(
        (str(c).removeprefix(str(OBO)), label(c))
        for c in set(foodon.subjects(RDF.type, OWL.Class))
        if isinstance(c, URIRef)
        and str(c).startswith(prefix)
        and c not in deprecated
        and label(c) is not None
    )
    with open(path, "w", newline="", encoding="utf-8") as fh:
        fh.write(f"# release: {RELEASE}\n# source: {SOURCE_URL}\n# sha256: {SOURCE_SHA256}\n")
        writer = csv.writer(fh, delimiter="\t", lineterminator="\n")
        writer.writerow(["class", "label"])
        writer.writerows(rows)
    return len(rows)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--foodon", type=Path, help="local copy of the pinned FoodOn release")
    ap.add_argument("-o", "--output", type=Path, default=OUT_PATH)
    ap.add_argument("--classes", type=Path, default=CLASSES_PATH, help="where to write the class index")
    args = ap.parse_args()

    logging.getLogger("rdflib").setLevel(logging.ERROR)
    foodon = load_release(args.foodon)
    version = foodon.value(URIRef(str(OBO) + "foodon.owl"), OWL.versionIRI)
    if str(version) != RELEASE:
        print(f"expected release {RELEASE}, got {version}", file=sys.stderr)
        return 1

    parents: defaultdict[URIRef, set[URIRef]] = defaultdict(set)
    for s, o in foodon.subject_objects(RDFS.subClassOf):
        if isinstance(s, URIRef) and isinstance(o, URIRef):
            parents[s].add(o)
    deprecated = set(foodon.subjects(OWL.deprecated, Literal(True)))

    def label(c: URIRef) -> str | None:
        labels = sorted(str(v) for v in foodon.objects(c, RDFS.label))
        return labels[0] if labels else None

    with open(CSV_PATH, newline="", encoding="utf-8") as fh:
        rows = [r for r in csv.DictReader(fh) if r["target_ontology"] == "FoodOn"]

    fatal, drift, targets = [], [], set()
    for r in rows:
        target = URIRef(r["target_iri"])
        targets.add(target)
        where = f"{r['source_type']}:{r['source_key']} -> {target}"
        if label(target) is None or target in deprecated:
            fatal.append(f"missing or deprecated in the release: {where}")
            continue
        if label(target).casefold() != r["target_label"].casefold():
            drift.append(f"label {where}: recorded {r['target_label']!r}, release {label(target)!r}")
        if r["predicate"] == "type" and ancestors(parents, target) & set(ORGANISM_ROOTS):
            fatal.append(f"rdf:type to a class of whole organisms: {where} ({label(target)})")

    module = Graph()
    module.bind("obo", OBO)
    module.bind("owl", OWL)
    module.bind("dcterms", DCTERMS)
    module.bind("prov", PROV)
    module.add((MODULE_IRI, RDF.type, OWL.Ontology))
    module.add((MODULE_IRI, OWL.versionIRI, URIRef(RELEASE)))
    module.add((MODULE_IRI, DCTERMS.title, Literal("FoodOn module for taco-rdf", lang="en")))
    module.add((MODULE_IRI, DCTERMS.description, Literal(
        "The FoodOn classes targeted by the TACO alignments and all their named superclasses "
        "(rdfs:subClassOf and labels only), extracted by scripts/extract_foodon_module.py.", lang="en")))
    module.add((MODULE_IRI, PROV.wasDerivedFrom, URIRef(RELEASE)))
    module.add((MODULE_IRI, DCTERMS.license, URIRef("https://creativecommons.org/licenses/by/4.0/")))
    module.add((MODULE_IRI, DCTERMS.source, URIRef("https://foodon.org/")))
    module.add((URIRef(RELEASE), DCTERMS.source, URIRef(SOURCE_URL)))
    module.add((URIRef(RELEASE), DCTERMS.description, Literal(
        f"This versioned PURL does not resolve: FoodOn created no v2026-09-20 tag. The file declaring this "
        f"versionIRI is FoodOn commit {SOURCE_COMMIT}, SHA-256 {SOURCE_SHA256}.", lang="en")))

    keep = set(targets)
    for t in targets:
        keep |= ancestors(parents, t)
    for c in keep:
        module.add((c, RDF.type, OWL.Class))
        if label(c) is not None:
            module.add((c, RDFS.label, Literal(label(c), lang="en")))
        for p in parents.get(c, ()):
            module.add((c, RDFS.subClassOf, p))

    args.output.parent.mkdir(parents=True, exist_ok=True)
    module.serialize(destination=str(args.output), format="turtle")
    print(f"wrote {len(keep)} classes ({len(module)} triples) from {RELEASE} to {args.output}")
    args.classes.parent.mkdir(parents=True, exist_ok=True)
    print(f"wrote {write_class_index(foodon, deprecated, label, args.classes)} classes to {args.classes}")
    for line in drift:
        print("DRIFT", line)
    for line in fatal:
        print("ERROR", line)
    return 1 if fatal else 0


if __name__ == "__main__":
    sys.exit(main())
