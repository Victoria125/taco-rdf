"""Extract the CDNO classes the nutrient alignments use, with their superclasses, from the pinned release.

The build types every measurement with its nutrient's close CDNO class, as NICE-Food types each NEVO
nutritional value; the module lets the build check those classes and lets queries use their hierarchy.
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
from rdflib.term import Node

ROOT = Path(__file__).resolve().parents[1]
CSV_PATH = ROOT / "data" / "alignment" / "alignments.csv"
OUT_PATH = ROOT / "ontology" / "imports" / "cdno-module.ttl"

RELEASE = "http://purl.obolibrary.org/obo/cdno/releases/2026-06-10/cdno.owl"
SOURCE_TAG = "v2026-06-10"
SOURCE_COMMIT = "a0dec27552ad3920b7b6c16ee82b1936dcf9b368"
SOURCE_URL = (f"https://raw.githubusercontent.com/CompositionalDietaryNutritionOntology/cdno/"
              f"{SOURCE_COMMIT}/cdno.owl")
SOURCE_SHA256 = "16d40da53cc56bcadc41add2dbc27d98d2eb40f285c9e26e2c80f2da3fb4c8bb"
# As declared by dcterms:license in the release file.
LICENSE = "https://creativecommons.org/licenses/by/3.0/"
OBO = Namespace("http://purl.obolibrary.org/obo/")
MODULE_IRI = URIRef("https://w3id.org/taco-rdf/imports/cdno-module")
# Release axioms the module leaves out, each with its reason; the module records them. CDNO groups every
# sulfur compound under dietary sulfur, a macro element, so the concentration of methionine, an amino
# acid TACO reports with the other amino acids, would be a concentration of a mineral nutrient.
OMITTED_SUBCLASS_AXIOMS = {
    (OBO.CDNO_0200627, OBO.CDNO_0200619): (
        "concentration of organosulfur compound is_a concentration of dietary sulfur would place "
        "methionine and cysteine under mineral nutrient"),
}


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
            path = Path(tmp) / "cdno.owl"
            print(f"downloading {SOURCE_URL}", file=sys.stderr)
            urllib.request.urlretrieve(SOURCE_URL, str(path))
            return parse_release(path)
    return parse_release(path)


def parse_release(path: Path) -> Graph:
    digest = hashlib.sha256(Path(path).read_bytes()).hexdigest()
    if digest != SOURCE_SHA256:
        raise SystemExit(f"{path} is not the pinned CDNO file: SHA-256 {digest}, expected {SOURCE_SHA256}")
    return Graph().parse(path, format="xml")


def subclass_parents(cdno: Graph) -> defaultdict[URIRef, set[URIRef]]:
    parents: defaultdict[URIRef, set[URIRef]] = defaultdict(set)
    for s, o in cdno.subject_objects(RDFS.subClassOf):
        if isinstance(s, URIRef) and isinstance(o, URIRef):
            parents[s].add(o)
    return parents


def omit_axioms(parents: dict[URIRef, set[URIRef]]) -> list[str]:
    """Remove the omitted axioms from ``parents``; an omitted axiom the release lacks is a problem."""
    problems = []
    for (child, parent), _reason in sorted(OMITTED_SUBCLASS_AXIOMS.items()):
        if parent in parents.get(child, set()):
            parents[child].discard(parent)
        else:
            problems.append(f"omitted axiom not in the release, remove it: {child} rdfs:subClassOf {parent}")
    return problems


def labeller(cdno: Graph) -> Callable[[URIRef], str | None]:
    def label(c: URIRef) -> str | None:
        labels = sorted(str(v) for v in cdno.objects(c, RDFS.label))
        return labels[0] if labels else None

    return label


def check_targets(
    rows: list[dict[str, str]],
    deprecated: set[Node],
    label: Callable[[URIRef], str | None],
) -> tuple[list[str], list[str], set[URIRef]]:
    """The fatal problems and label drift of the alignment targets, and the targets themselves."""
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
    return fatal, drift, targets


def build_module(
    keep: set[URIRef], parents: dict[URIRef, set[URIRef]], label: Callable[[URIRef], str | None]
) -> Graph:
    module = Graph()
    module.bind("obo", OBO)
    module.bind("owl", OWL)
    module.bind("dcterms", DCTERMS)
    module.bind("prov", PROV)
    module.add((MODULE_IRI, RDF.type, OWL.Ontology))
    module.add((MODULE_IRI, OWL.versionIRI, URIRef(RELEASE)))
    module.add((MODULE_IRI, DCTERMS.title, Literal("CDNO module for taco-rdf", lang="en")))
    module.add((MODULE_IRI, DCTERMS.description, Literal(
        "The CDNO classes targeted by the TACO nutrient alignments and all their named superclasses "
        "(rdfs:subClassOf and labels only), extracted by scripts/extract_cdno_module.py.", lang="en")))
    module.add((MODULE_IRI, PROV.wasDerivedFrom, URIRef(RELEASE)))
    module.add((MODULE_IRI, DCTERMS.license, URIRef(LICENSE)))
    module.add((MODULE_IRI, DCTERMS.source, URIRef("https://github.com/CompositionalDietaryNutritionOntology/cdno")))
    module.add((URIRef(RELEASE), DCTERMS.source, URIRef(SOURCE_URL)))
    module.add((URIRef(RELEASE), DCTERMS.description, Literal(
        f"This versioned PURL resolves to CDNO tag {SOURCE_TAG}, commit {SOURCE_COMMIT}, "
        f"SHA-256 {SOURCE_SHA256}.", lang="en")))
    for (child, parent), reason in sorted(OMITTED_SUBCLASS_AXIOMS.items()):
        module.add((MODULE_IRI, RDFS.comment, Literal(
            f"Omits the release axiom {child} rdfs:subClassOf {parent}: {reason}.", lang="en")))
    for c in keep:
        module.add((c, RDF.type, OWL.Class))
        if label(c) is not None:
            module.add((c, RDFS.label, Literal(label(c), lang="en")))
        for p in parents.get(c, ()):
            module.add((c, RDFS.subClassOf, p))
    return module


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cdno", type=Path, help="local copy of the pinned CDNO release")
    ap.add_argument("-o", "--output", type=Path, default=OUT_PATH)
    args = ap.parse_args()

    logging.getLogger("rdflib").setLevel(logging.ERROR)
    cdno = load_release(args.cdno)
    version = cdno.value(URIRef(str(OBO) + "cdno.owl"), OWL.versionIRI)
    if str(version) != RELEASE:
        print(f"expected release {RELEASE}, got {version}", file=sys.stderr)
        return 1

    parents = subclass_parents(cdno)
    omission_problems = omit_axioms(parents)
    deprecated = set(cdno.subjects(OWL.deprecated, Literal(True)))
    label = labeller(cdno)

    with open(CSV_PATH, newline="", encoding="utf-8") as fh:
        rows = [r for r in csv.DictReader(fh) if r["target_ontology"] == "CDNO"]

    fatal, drift, targets = check_targets(rows, deprecated, label)
    fatal += omission_problems
    keep = set(targets)
    for t in targets:
        keep |= ancestors(parents, t)
    module = build_module(keep, parents, label)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    module.serialize(destination=str(args.output), format="turtle")
    print(f"wrote {len(keep)} classes ({len(module)} triples) from {RELEASE} to {args.output}")
    for line in drift:
        print("DRIFT", line)
    for line in fatal:
        print("ERROR", line)
    return 1 if fatal else 0


if __name__ == "__main__":
    sys.exit(main())
