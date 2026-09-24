from __future__ import annotations

import pytest
from owlrl import DeductiveClosure, OWLRL_Semantics
from rdflib import Graph, Namespace

from taco_rdf.namespaces import FIO, ONTOLOGY_TTL, RDF, TACO

EX = Namespace("https://example.org/")


@pytest.mark.parametrize("statement", [
    (EX.value, TACO.ofFood, EX.food),
    (EX.food, TACO.hasNutritionalValue, EX.value),
])
def test_taco_measurement_links_entail_fio_links(statement):
    graph = Graph().parse(ONTOLOGY_TTL)
    graph.add(statement)
    graph.add((EX.value, TACO.ofNutrient, EX.nutrient))

    DeductiveClosure(OWLRL_Semantics).expand(graph)

    assert (EX.value, TACO.ofFood, EX.food) in graph
    assert (EX.food, TACO.hasNutritionalValue, EX.value) in graph
    assert (EX.food, FIO.hasNutritionalValue, EX.value) in graph
    assert (EX.value, FIO.hasNutrient, EX.nutrient) in graph
    assert (EX.food, RDF.type, TACO.Food) in graph
    assert (EX.food, RDF.type, FIO.FoodItem) in graph
    assert (EX.value, RDF.type, TACO.NutrientMeasurement) in graph
    assert (EX.value, RDF.type, FIO.NutritionalValue) in graph


def test_external_fio_measurements_do_not_entail_taco_membership():
    graph = Graph().parse(ONTOLOGY_TTL)
    graph.add((EX.food, FIO.hasNutritionalValue, EX.value))
    graph.add((EX.value, FIO.hasNutrient, EX.nutrient))

    DeductiveClosure(OWLRL_Semantics).expand(graph)

    assert (EX.food, RDF.type, FIO.FoodItem) in graph
    assert (EX.value, RDF.type, FIO.NutritionalValue) in graph
    assert (EX.nutrient, RDF.type, FIO.Nutrient) in graph
    assert (EX.food, RDF.type, TACO.Food) not in graph
    assert (EX.value, RDF.type, TACO.NutrientMeasurement) not in graph
    assert (EX.nutrient, RDF.type, TACO.Nutrient) not in graph
    assert (EX.value, TACO.ofFood, EX.food) not in graph
    assert (EX.food, TACO.hasNutritionalValue, EX.value) not in graph
    assert (EX.value, TACO.ofNutrient, EX.nutrient) not in graph
