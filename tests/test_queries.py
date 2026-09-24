from __future__ import annotations

from decimal import Decimal

import pytest

from taco_rdf.cli import main
from taco_rdf.namespaces import QUERIES_DIR
from taco_rdf.parse import Status
from taco_rdf.queries import parse_binding, run_query


def q(graph, name, **bindings):
    return run_query(graph, QUERIES_DIR / f"{name}.rq", bindings)


def measured(value_of, key):
    return {fid: o.value for (fid, k), o in value_of.items() if k == key and o.status is Status.MEASURED}


def test_every_query_file_parses_and_runs(graph):
    binds = {
        "amino_acid_profile": {"food": "<https://w3id.org/taco-rdf/id/food/56>"},
        "mineral_profile": {"food": "<https://w3id.org/taco-rdf/id/food/100>"},
        "richest_in": {"key": "iron"},
        "foods_in_foodon_class": {"class": "<http://purl.obolibrary.org/obo/FOODON_00001264>"},
    }
    for path in sorted(QUERIES_DIR.glob("*.rq")):
        header, rows = run_query(graph, path, binds.get(path.stem, {}))
        assert header and rows, path.name


def test_graph_overview(graph):
    _, rows = q(graph, "graph_overview")
    assert {str(r[0]): int(r[1]) for r in rows} == {
        "NutrientMeasurement": 21150, "Food": 597, "Nutrient": 67, "FoodGroup": 15,
    }


def test_richest_in_iron(graph, value_of):
    _, rows = q(graph, "richest_in", key="iron")
    iron = measured(value_of, "iron")
    top = sorted(iron.items(), key=lambda kv: -kv[1])[:10]
    assert [int(r[0]) for r in rows] == [fid for fid, _ in top]
    assert [Decimal(str(r[3])) for r in rows] == [v for _, v in top]
    assert str(rows[0][4]) == "MilliGM"


def test_group_protein_summary(graph, table, value_of):
    _, rows = q(graph, "group_protein_summary")
    protein = measured(value_of, "protein")
    assert len(rows) == 15
    by_group = {}
    for fid, v in protein.items():
        by_group.setdefault(table.foods[fid].group_id, []).append(v)
    meats = by_group[6]
    row = next(r for r in rows if str(r[0]).startswith("Meats"))
    assert int(row[1]) == len(meats)
    assert float(row[2]) == pytest.approx(float(sum(meats) / len(meats)), abs=0.006)
    assert Decimal(str(row[3])) == min(meats) and Decimal(str(row[4])) == max(meats)


def test_high_protein_low_fat(graph, value_of):
    _, rows = q(graph, "high_protein_low_fat")
    protein, lipids = measured(value_of, "protein"), measured(value_of, "lipids")
    expected = {f for f in protein if f in lipids and protein[f] >= 20 and lipids[f] <= 5}
    assert {int(r[0]) for r in rows} == expected and len(expected) == 32


def test_trace_counts_per_nutrient(graph, value_of):
    _, rows = q(graph, "value_status_summary")
    top = rows[0]
    assert str(top[0]) == "Pyridoxine"
    traces = sum(1 for (f, k), o in value_of.items() if k == "pyridoxine" and o.status is Status.TRACE)
    assert int(top[1]) == traces == 318


def test_alignment_query_lists_all_groups(graph):
    _, rows = q(graph, "food_group_alignments")
    assert len(rows) == 20 and len({str(r[0]) for r in rows}) == 15


def test_food_alignment_query_lists_most_foods(graph):
    _, rows = q(graph, "food_alignments")
    assert len(rows) == 436
    assert len({int(r[0]) for r in rows}) == 436
    relations = {}
    for r in rows:
        relations[str(r[2])] = relations.get(str(r[2]), 0) + 1
    assert relations == {"type": 311, "closeMatch": 11, "relatedMatch": 114}


def test_documented_corrections_query(graph):
    _, rows = q(graph, "documented_corrections")
    origins = {}
    for r in rows:
        origins[str(r[3])] = origins.get(str(r[3]), 0) + 1
    assert origins == {"DocumentedCorrection": 19, "LegendFootnote": 2}


def test_provenance_query(graph):
    _, rows = q(graph, "provenance")
    assert len(rows) == 1 and len(str(rows[0][4])) == 64


def test_amino_acid_profile_of_a_food(graph, value_of):
    _, rows = q(graph, "amino_acid_profile", food="<https://w3id.org/taco-rdf/id/food/56>")
    assert len(rows) == 18
    assert str(rows[0][1]) == "Glutamic acid"
    assert Decimal(str(rows[0][2])) == value_of[(56, "glutamic_acid")].value


def test_mineral_profile_uses_the_category_hierarchy(graph):
    _, rows = q(graph, "mineral_profile", food="<https://w3id.org/taco-rdf/id/food/100>")
    assert {str(r[1]) for r in rows} >= {"Calcium", "Iron", "Potassium"}
    assert all(str(r[3]) == "MilliGM" for r in rows)


def test_binding_parser():
    assert str(parse_binding("<http://x/y>")) == "http://x/y"
    assert parse_binding("5").toPython() == 5
    assert parse_binding("2.5").toPython() == Decimal("2.5")
    assert str(parse_binding("iron")) == "iron"


def test_cli_build_and_query_round_trip(tmp_path, capsys):
    out = tmp_path / "taco.ttl"
    assert main(["build", "-o", str(out)]) == 0
    assert out.stat().st_size > 1_000_000
    capsys.readouterr()
    assert main(["stats", "--graph", str(out)]) == 0
    text = capsys.readouterr().out
    assert "NutrientMeasurement" in text and "21150" in text
