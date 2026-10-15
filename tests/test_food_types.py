"""Foods as FIO food items typed with FoodOn, and the NICE-Food alignment claims made about them."""

from __future__ import annotations

import pytest
from rdflib import Graph, Literal, URIRef
from rdflib.namespace import OWL

from taco_rdf import graph as graphmod
from taco_rdf.namespaces import (
    FIO,
    FOODON_MODULE_TTL,
    OBO,
    ONTOLOGY_TTL,
    QUERIES_DIR,
    RAW_XLS,
    RDF,
    RDFS,
    SKOS,
    TACO,
)
from taco_rdf.queries import run_query

FOODON = "http://purl.obolibrary.org/obo/FOODON_"


def foodon_types(g, food):
    return {t for t in g.objects(food, RDF.type) if str(t).startswith(FOODON)}


def rows_of(alignments, source_type, predicate=None):
    return [a for a in alignments
            if a.source_type == source_type and (predicate is None or a.predicate == predicate)]


def test_every_taco_food_is_a_fio_food_item(graph):
    foods = set(graph.subjects(RDF.type, TACO.Food))
    assert len(foods) == 597
    assert foods == set(graph.subjects(RDF.type, FIO.FoodItem))


def test_close_food_alignments_are_foodon_types_not_skos_links(graph, alignments):
    typed = rows_of(alignments, "food", "type")
    assert len(typed) == 311
    for a in typed:
        food, cls = graphmod.food_iri(int(a.source_key)), URIRef(a.target_iri)
        assert foodon_types(graph, food) == {cls}
        assert (food, SKOS.closeMatch, cls) not in graph


def test_untyped_food_candidates_are_withheld_from_published_mappings(graph, alignments):
    kept = rows_of(alignments, "food", "closeMatch") + rows_of(alignments, "food", "relatedMatch")
    assert len(kept) == 11 + 114
    for a in kept:
        food = graphmod.food_iri(int(a.source_key))
        assert foodon_types(graph, food) == set()
        assert (food, SKOS[a.predicate], URIRef(a.target_iri)) not in graph
        assert not list(graph.objects(food, TACO.alignment))
    assert all("not asserted as rdf:type" in a.note for a in rows_of(alignments, "food", "closeMatch"))


@pytest.mark.parametrize("predicate", [
    "exactMatch", "closeMatch", "relatedMatch", "narrowMatch", "broadMatch",
])
def test_food_skos_candidates_are_never_asserted_or_promoted(table, predicate):
    # Even a valid food class is not a type merely because it was a SKOS candidate.
    candidate = graphmod.Alignment("food", "1", predicate, str(OBO.FOODON_00004678),
                                   "rice (cooked)", "FoodOn", "Candidate only")
    graph = graphmod.build_graph(table, [candidate], source_file=RAW_XLS, include_ontology=False)
    food = graphmod.food_iri(1)
    assert not foodon_types(graph, food)
    assert (food, SKOS[predicate], None) not in graph
    assert not list(graph.objects(food, TACO.alignment))
    assert not list(graph.subjects(RDF.type, TACO.AlignmentAssertion))
    assert (food, RDF.type, TACO.Food) in graph
    assert (food, RDF.type, FIO.FoodItem) in graph


def test_foods_without_a_candidate_keep_their_food_identity(graph, table, alignments):
    # Chosen from the inputs, not by number, so applying a review round cannot invalidate it.
    with_rows = {int(a.source_key) for a in rows_of(alignments, "food")}
    without = sorted(set(table.foods) - with_rows)
    assert without
    for number in without:
        food = graphmod.food_iri(number)
        assert (food, RDF.type, FIO.FoodItem) in graph
        assert not foodon_types(graph, food)


@pytest.mark.parametrize("predicate", ["closeMatch", "exactMatch"])
def test_food_skos_link_to_another_dataset_is_published(table, predicate):
    # NICE-Food links LCA items to NEVO codes with skos:closeMatch; only FoodOn links must be types.
    nevo = URIRef("https://data.rivm.nl/data/nvip/bigfood/nevo23/nevocode#1")
    link = graphmod.Alignment("food", "1", predicate, str(nevo), "Potatoes raw", "NEVO", "")
    graph = graphmod.build_graph(table, [link], source_file=RAW_XLS, include_ontology=False)
    food = graphmod.food_iri(1)
    assert (food, SKOS[predicate], nevo) in graph
    assert len(list(graph.objects(food, TACO.alignment))) == 1
    assert not foodon_types(graph, food)


@pytest.mark.parametrize(("target", "obstacle"), [
    ("FOODON_03311340", "foodon_axiom_conflict"),  # scallion (raw), food 108
    ("FOODON_00002576", "foodon_axiom_conflict"),  # bean sprout, food 125
    ("FOODON_00004236", "foodon_axiom_conflict"),  # green bean pod (raw), food 162
    ("FOODON_03309932", "foodon_axiom_conflict"),  # tamarind pod (raw), food 250
    ("FOODON_03413876", "organism_class"),         # pollock
    ("FOODON_02021822", "organism_class"),         # catfish
    ("FOODON_03412059", "organism_class"),         # mate plant
    ("FOODON_03301449", ""),                       # potato (raw), food 92
    ("FOODON_99999999", "missing_class"),
])
def test_typing_obstacles_separate_foodon_axiom_conflicts_from_organisms(target, obstacle):
    module = Graph().parse(FOODON_MODULE_TTL)
    assert graphmod.foodon_typing_obstacle(module, OBO[target]) == obstacle


def test_no_food_is_typed_with_a_class_of_whole_organisms(graph):
    module = Graph().parse(FOODON_MODULE_TTL)
    for food in graph.subjects(RDF.type, TACO.Food):
        for cls in foodon_types(graph, food):
            ancestors = set(module.transitive_objects(cls, RDFS.subClassOf))
            assert OBO.COB_0000022 not in ancestors, (food, cls)
            assert OBO.PO_0000003 not in ancestors, (food, cls)


def test_recorded_foodon_labels_are_the_pinned_release_labels(alignments):
    module = Graph().parse(FOODON_MODULE_TTL)
    for a in alignments:
        if a.target_ontology == "FoodOn":
            assert str(module.value(URIRef(a.target_iri), RDFS.label)) == a.target_label, a


@pytest.mark.parametrize(("key", "target", "reason"), [
    ("273", "FOODON_03413876", "whole organisms"),
    ("108", "FOODON_03311340", "under whole organisms or plants"),
    ("1", "FOODON_99999999", "missing from"),
])
def test_build_refuses_unsupported_food_types(table, key, target, reason):
    bad = graphmod.Alignment("food", key, "type", str(OBO[target]), "x", "FoodOn", "")
    with pytest.raises(ValueError, match=reason):
        graphmod.build_graph(table, [bad], source_file=RAW_XLS)


def test_build_refuses_typing_a_nutrient(table):
    bad = graphmod.Alignment("nutrient", "protein", "type", OBO.FOODON_00004678, "x", "FoodOn", "")
    with pytest.raises(ValueError, match="only foods"):
        graphmod.build_graph(table, [bad], source_file=RAW_XLS)


def test_a_foodon_label_alone_does_not_establish_a_valid_class():
    target = OBO.FOODON_00004678
    candidate = graphmod.Alignment("food", "1", "type", str(target), "rice", "FoodOn", "")
    module = Graph()
    module.add((target, RDFS.label, Literal("rice", lang="en")))
    with pytest.raises(ValueError, match="missing from"):
        graphmod._check_food_typing(module, candidate, target)
    module.add((target, RDF.type, OWL.Class))
    module.add((target, OWL.deprecated, Literal(True)))
    with pytest.raises(ValueError, match="deprecated"):
        graphmod._check_food_typing(module, candidate, target)


def test_the_foodon_hierarchy_classifies_taco_foods(graph, table):
    legume = "http://purl.obolibrary.org/obo/FOODON_00001264"
    _, rows = run_query(graph, QUERIES_DIR / "foods_in_foodon_class.rq", {"class": f"<{legume}>"})
    found = {int(r[0]) for r in rows}
    expected = {
        int(str(f).rsplit("/", 1)[1]) for f in graph.subjects(RDF.type, TACO.Food)
        for c in foodon_types(graph, f) if URIRef(legume) in set(graph.transitive_objects(c, RDFS.subClassOf))
    }
    assert found == expected
    names = {table.foods[i].name for i in found}
    assert {"Feijão, preto, cozido", "Grão-de-bico, cru", "Lentilha, crua"} <= names


def test_group_and_food_alignments_coherence(graph, table, alignments):
    _, rows = run_query(graph, QUERIES_DIR / "group_food_coherence.rq")
    got = {str(r[0]): (int(r[1]), int(r[2])) for r in rows}
    group_classes = {}
    for a in rows_of(alignments, "group"):
        if a.predicate in ("closeMatch", "narrowMatch"):
            group_classes.setdefault(int(a.source_key), set()).add(URIRef(a.target_iri))
    expected = {}
    for a in rows_of(alignments, "food", "type"):
        gid = table.foods[int(a.source_key)].group_id
        label = next(str(v) for v in graph.objects(graphmod.group_iri(gid), SKOS.prefLabel)
                     if v.language == "en")
        inside = bool(set(graph.transitive_objects(URIRef(a.target_iri), RDFS.subClassOf))
                      & group_classes.get(gid, set()))
        typed, under = expected.get(label, (0, 0))
        expected[label] = (typed + 1, under + inside)
    assert got == expected
    assert sum(t for t, _ in got.values()) == 311
    assert sum(u for _, u in got.values()) == 140


NICE_FOOD_SELECTION = """
PREFIX fio:    <http://www.foodvoc.org/resource/fio#>
PREFIX foodon: <http://purl.obolibrary.org/obo/FOODON>
PREFIX rdfs:   <http://www.w3.org/2000/01/rdf-schema#>
PREFIX rdf:    <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
SELECT DISTINCT ?food_item WHERE {
    ?foodontype rdfs:subClassOf* foodon:_00001264 .
    ?food_item rdf:type fio:FoodItem .
    ?food_item rdf:type ?foodontype .
}"""


def test_nice_food_food_selection_finds_taco_foods(graph):
    """Aligned: NICE-Food's way of picking foods (FIO item + FoodOn class) works on the TACO graph as is."""
    found = {row[0] for row in graph.query(NICE_FOOD_SELECTION)}
    _, rows = run_query(graph, QUERIES_DIR / "foods_in_foodon_class.rq",
                        {"class": "<http://purl.obolibrary.org/obo/FOODON_00001264>"})
    assert found == {graphmod.food_iri(int(r[0])) for r in rows}
    assert len(found) == 21


def test_composition_is_aligned_to_fio_by_axioms_only(graph):
    """The vocabulary relates TACO's measurement links to FIO's; the graph does not materialise them."""
    vocab = Graph().parse(ONTOLOGY_TTL)
    assert (TACO.hasNutritionalValue, OWL.inverseOf, TACO.ofFood) in vocab
    assert (TACO.hasNutritionalValue, RDFS.subPropertyOf, FIO.hasNutritionalValue) in vocab
    assert (TACO.ofFood, OWL.inverseOf, FIO.hasNutritionalValue) not in vocab
    assert (TACO.ofNutrient, RDFS.subPropertyOf, FIO.hasNutrient) in vocab
    assert (TACO.NutrientMeasurement, RDFS.subClassOf, FIO.NutritionalValue) in vocab
    assert (None, FIO.hasNutritionalValue, None) not in graph
    assert (None, TACO.hasNutritionalValue, None) not in graph
    assert not any("ontology-of-units-of-measure" in str(p) for p in set(graph.predicates()))
