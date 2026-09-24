from __future__ import annotations

import pytest
from rdflib import Graph

from taco_rdf import graph as graphmod
from taco_rdf.namespaces import ALIGNMENTS_CSV, CORRECTIONS_DIR, FOOD_NAMES_EN, RAW_XLS, SHAPES_DIR
from taco_rdf.parse import load_corrections, parse_workbook
from taco_rdf.validate import validate


@pytest.fixture(scope="session")
def table():
    return parse_workbook(RAW_XLS, load_corrections(CORRECTIONS_DIR))


@pytest.fixture(scope="session")
def alignments():
    return graphmod.load_alignments(ALIGNMENTS_CSV)


@pytest.fixture(scope="session")
def food_names_en():
    return graphmod.load_food_names_en(FOOD_NAMES_EN)


@pytest.fixture(scope="session")
def graph(table, alignments, food_names_en) -> Graph:
    return graphmod.build_graph(table, alignments, source_file=RAW_XLS, food_names_en=food_names_en)


@pytest.fixture(scope="session")
def report(graph):
    return validate(graph, SHAPES_DIR)


@pytest.fixture(scope="session")
def value_of(table):
    return {(o.food_id, o.nutrient): o for o in table.observations}
