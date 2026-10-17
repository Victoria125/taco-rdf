"""The pinned CDNO module backs the CDNO classes that type TACO measurements."""

from __future__ import annotations

import importlib.util

import pytest
from rdflib import Graph, Literal, URIRef
from rdflib.namespace import OWL

from taco_rdf import graph as graphmod
from taco_rdf.namespaces import CDNO_MODULE_TTL, OBO, QUERIES_DIR, RAW_XLS, RDF, RDFS, ROOT
from taco_rdf.queries import run_query

spec = importlib.util.spec_from_file_location(
    "extract_cdno_module", ROOT / "scripts" / "extract_cdno_module.py")
assert spec is not None and spec.loader is not None
extractor = importlib.util.module_from_spec(spec)
spec.loader.exec_module(extractor)

RELEASE = URIRef("http://purl.obolibrary.org/obo/cdno/releases/2026-06-10/cdno.owl")
FATTY_ACID, MINERAL, AMINO_ACID = OBO.CDNO_0200465, OBO.CDNO_0200136, OBO.CDNO_0200464


@pytest.fixture(scope="module")
def module():
    return Graph().parse(CDNO_MODULE_TTL)


def test_module_records_the_pinned_release(module):
    assert (extractor.MODULE_IRI, OWL.versionIRI, RELEASE) in module
    assert str(RELEASE) == extractor.RELEASE


def test_every_cdno_target_is_in_the_module_with_its_release_label(module, alignments):
    targets = [a for a in alignments if a.target_ontology == "CDNO"]
    assert len(targets) == 62
    for a in targets:
        cls = URIRef(a.target_iri)
        assert (cls, RDF.type, OWL.Class) in module, a
        assert str(module.value(cls, RDFS.label)) == a.target_label, a


def test_module_keeps_every_superclass_of_its_classes(module):
    classes = set(module.subjects(RDF.type, OWL.Class))
    for parent in module.objects(None, RDFS.subClassOf):
        assert parent in classes, parent


def test_measurement_types_are_module_classes(graph, module):
    classes = set(module.subjects(RDF.type, OWL.Class))
    used = {t for t in graph.objects(None, RDF.type) if str(t).startswith(str(OBO) + "CDNO_")}
    assert len(used) == 53
    assert used <= classes


def test_build_refuses_a_cdno_class_missing_from_the_module(table):
    bad = graphmod.Alignment("nutrient", "protein", "closeMatch", str(OBO.CDNO_9999999), "x", "CDNO", "")
    with pytest.raises(ValueError, match=r"CDNO class missing from cdno-module\.ttl"):
        graphmod.build_graph(table, [bad], source_file=RAW_XLS, include_ontology=False)


def test_extractor_flags_missing_deprecated_and_drifted_targets():
    release = Graph()
    for suffix, label in (("0200040", "concentration of protein in material entity"),
                          ("0200068", "concentration of lipid in material entity")):
        release.add((OBO["CDNO_" + suffix], RDFS.label, Literal(label, lang="en")))
    rows = [
        {"source_type": "nutrient", "source_key": "protein", "target_iri": str(OBO.CDNO_0200040),
         "target_label": "concentration of protein in material entity"},
        {"source_type": "nutrient", "source_key": "lipids", "target_iri": str(OBO.CDNO_0200068),
         "target_label": "concentration of total lipid in material entity"},
        {"source_type": "nutrient", "source_key": "ash", "target_iri": str(OBO.CDNO_0200004),
         "target_label": "concentration of ash in material entity"},
    ]
    fatal, drift, targets = extractor.check_targets(rows, {OBO.CDNO_0200068}, extractor.labeller(release))
    assert len(targets) == 3
    assert fatal == [f"missing or deprecated in the release: nutrient:lipids -> {OBO.CDNO_0200068}",
                     f"missing or deprecated in the release: nutrient:ash -> {OBO.CDNO_0200004}"]
    assert drift == []
    fatal, drift, _ = extractor.check_targets(rows[1:2], set(), extractor.labeller(release))
    assert fatal == [] and len(drift) == 1


def query(graph, cls, food):
    return run_query(graph, QUERIES_DIR / "measurements_in_cdno_class.rq",
                     {"class": f"<{cls}>", "food_number": str(food)})


def test_cdno_hierarchy_selects_a_foods_fatty_acids(graph, table, alignments):
    types = graphmod.cdno_measurement_types(alignments)
    module = Graph().parse(CDNO_MODULE_TTL)
    expected = {o.nutrient for o in table.observations
                if o.food_id == 1 and o.nutrient in types
                and FATTY_ACID in set(module.transitive_objects(types[o.nutrient], RDFS.subClassOf))}
    _, rows = query(graph, FATTY_ACID, 1)
    assert len(rows) == len(expected) > 0
    assert all("acid" in str(r[2]) for r in rows)


def test_module_omits_the_axiom_that_makes_methionine_a_mineral_nutrient(module):
    # CDNO 2026-06-10 groups every sulfur compound under dietary sulfur, a macro element:
    # methionine -> organosulfur compound -> dietary sulfur -> macro element -> mineral nutrient.
    ancestors = set(module.transitive_objects(OBO.CDNO_0200060, RDFS.subClassOf))
    assert (OBO.CDNO_0200627, RDFS.subClassOf, OBO.CDNO_0200619) not in module
    assert MINERAL not in ancestors
    assert AMINO_ACID in ancestors
    assert (OBO.CDNO_0200060, RDFS.subClassOf, OBO.CDNO_0200627) in module
    comments = [str(c) for c in module.objects(extractor.MODULE_IRI, RDFS.comment)]
    assert any(str(OBO.CDNO_0200627) in c and str(OBO.CDNO_0200619) in c for c in comments)


def test_omitted_axioms_are_removed_and_must_still_be_in_the_release():
    parents = {OBO.CDNO_0200627: {OBO.CDNO_0200619, OBO.CDNO_0200001}}
    assert extractor.omit_axioms(parents) == []
    assert parents[OBO.CDNO_0200627] == {OBO.CDNO_0200001}
    problems = extractor.omit_axioms({})
    assert len(problems) == 1
    assert "not in the release" in problems[0]


def test_mineral_query_leaves_methionine_with_the_amino_acids(graph, table):
    food = next(o.food_id for o in table.observations if o.nutrient == "methionine")
    _, minerals = query(graph, MINERAL, food)
    _, amino_acids = query(graph, AMINO_ACID, food)
    assert minerals
    assert "Methionine" not in {str(r[1]) for r in minerals}
    assert "Methionine" in {str(r[1]) for r in amino_acids}
