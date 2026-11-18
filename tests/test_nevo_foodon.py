"""NEVO's English names become FoodOn-style labels, and reviewed decisions become rdf:type triples.

The names here are made up in NEVO's style; no NEVO name or value is used.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

from rdflib import RDF, URIRef

from taco_rdf.namespaces import OBO, ROOT


def load(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


cand = load("nevo_foodon_candidates")
types = load("nevo_foodon_types")
FOOD = "https://data.rivm.nl/data/nvip/bigfood/nevo21/nevocode#1"


def test_abbreviations_are_spelled_out_and_averages_dropped():
    assert cand.words("Pear w skin av raw") == ["pear", "with", "skin", "raw"]
    assert cand.words("Crème fraîche prep") == ["creme", "fraiche", "prepared"]


def test_what_the_food_is_stops_at_without_and_excluding():
    assert cand.what(cand.words("Soup tomato wo cream")) == ["soup", "tomato"]
    assert cand.what(cand.words("Fruit tinned av excl pineapple")) == ["fruit"]
    assert cand.what(cand.words("Sauce herb 10-<20% oil")) == ["sauce", "herb", "oil"]


def test_fresh_gives_a_state_only_when_nothing_else_does():
    assert cand.state_of(cand.words("Pears fresh")) == "raw"
    assert cand.state_of(cand.words("Turnips mashed fresh prep")) == "cooked"
    assert cand.state_of(cand.words("Peas tinned")) == "canned"
    assert cand.state_of(cand.words("Peas")) is None


def test_names_meet_foodon_labels_most_specific_first():
    labels = {"pear (raw)": ("FOODON_1", "pear (raw)"), "pear": ("FOODON_2", "pear"),
              "spelt bread": ("FOODON_3", "spelt bread")}
    assert cand.lexical("Pears raw", labels) == ("FOODON_1", "pear (raw)", "head and state")
    assert cand.lexical("Pears tinned", labels) == ("FOODON_2", "pear", "head")
    assert cand.lexical("Bread spelt av", labels) == ("FOODON_3", "spelt bread", "qualifier and head")
    assert cand.lexical("Romanesco raw", labels) == ("", "", "")


def test_neighbours_share_the_first_word():
    typed = [{"name_en": "Pear Conference w skin", "classes": [("FOODON_1", "pear")]},
             {"name_en": "Apple w skin", "classes": [("FOODON_2", "apple")]}]
    found = cand.neighbours("Pear w skin av", typed)
    assert [food["name_en"] for _, food in found] == ["Pear Conference w skin"]


def test_typed_taco_foods_are_neighbours_with_their_foodon_type(tmp_path: Path):
    names, types = tmp_path / "names.csv", tmp_path / "types.csv"
    names.write_text("food_number,name_pt,name_en,status,note\n"
                     "1,\"Mandioca, crua\",\"Cassava, raw\",draft,\n", encoding="utf-8")
    types.write_text("food_number,name_pt,group_id,group,predicate,target_iri,target_label,note,"
                     "review_status,review_round,reviewers,reviewed_on,foodon_release\n"
                     "1,\"Mandioca, crua\",3,Verduras,rdf:type,http://purl.obolibrary.org/obo/FOODON_1,"
                     "cassava (raw),,,,,,\n", encoding="utf-8")
    taco = cand.taco_typed(types, names)
    assert taco == [{"food_number": "1", "name_en": "Cassava, raw",
                     "classes": [("FOODON_1", "cassava (raw)")]}]
    assert [food["name_en"] for _, food in cand.neighbours("Cassava boiled", taco, n=1)] == ["Cassava, raw"]


def row(**kw: str) -> dict[str, str]:
    base = {"nevo_release": "nevo21", "nevo_code": "1", "nevo_iri": FOOD, "name_class": "FOODON_1",
            "neighbour1_class": "FOODON_2; FOODON_3", "ols1_class": "FOODON_9",
            "organism_classes": "FOODON_9", "decision": "", "chosen_class": ""}
    return base | kw


def test_decisions():
    pinned = {"FOODON_1", "FOODON_2", "FOODON_3", "FOODON_9"}
    assert types.decide(row(decision="name"), pinned) == ("typed", "FOODON_1")
    assert types.decide(row(decision="taco_neighbour", taco_neighbour_class="FOODON_3"), pinned) == (
        "typed", "FOODON_3")
    assert types.decide(row(decision="Neighbour1", chosen_class="FOODON:3"), pinned) == ("typed", "FOODON_3")
    assert types.decide(row(decision="other", chosen_class="http://purl.obolibrary.org/obo/FOODON_2"),
                        pinned) == ("typed", "FOODON_2")
    assert types.decide(row(decision="none"), pinned) == ("none", "")
    assert types.decide(row(), pinned) == ("pending", "")
    assert types.decide(row(decision="neighbour1"), pinned)[0] == "error"
    assert types.decide(row(decision="ols1"), pinned)[0] == "error"
    assert types.decide(row(decision="other", chosen_class="FOODON_7"), pinned)[0] == "error"
    assert types.decide(row(decision="maybe"), pinned)[0] == "error"


def test_a_sheet_saved_by_excel_becomes_type_triples(tmp_path: Path):
    sheet = tmp_path / "candidates.csv"
    lines = ["nevo_release;nevo_code;nevo_iri;name_en;name_class;organism_classes;decision;chosen_class",
             f"nevo21;1;{FOOD};Pêra crua;FOODON_1;;name;",
             f"nevo21;2;{FOOD[:-1]}2;Kohlrabi raw;;;none;",
             f"nevo21;3;{FOOD[:-1]}3;Kale raw;;;;"]
    sheet.write_bytes("\r\n".join(lines).encode("cp1252"))
    g, counts, problems = types.types(types.read_sheet(sheet), {"FOODON_1"})
    assert problems == []
    assert counts == {"typed": 1, "none": 1, "pending": 1}
    assert set(g) == {(URIRef(FOOD), RDF.type, OBO.FOODON_1)}
