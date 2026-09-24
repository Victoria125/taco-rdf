from __future__ import annotations

import csv
import importlib.util

import pytest

from taco_rdf.namespaces import ROOT

SPEC = importlib.util.spec_from_file_location("foodon_lookup", ROOT / "analysis/foodon_lookup.py")
lookup = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(lookup)


@pytest.fixture
def food():
    return {"name_pt": "Example food", "query_en": "example food", "foodon_class": "", "foodon_label": ""}


def test_empty_searches_are_recorded_without_claiming_ontology_absence(monkeypatch, food):
    monkeypatch.setattr(lookup, "search", lambda query: [])
    rows = lookup.lookup_rows("regional", food, "2026-09-24", "release")
    assert len(rows) == 1
    row = rows[0]
    assert (row["source"], row["status"], row["returned_count"]) == ("search", "no_results", 0)
    assert row["search_limit"] == 5
    assert row["query_en"] == food["query_en"]
    assert (row["retrieved"], row["foodon_release"]) == ("2026-09-24", "release")
    assert row["rank"] == row["curie"] == row["label"] == ""


def test_recorded_classes_are_distinct_from_search_results(monkeypatch, food):
    monkeypatch.setattr(lookup, "search", lambda query: [])
    monkeypatch.setattr(lookup, "label_of", lambda curie: "Example food class")
    food.update(foodon_class="FOODON_00000001", foodon_label="Example food class")
    rows = lookup.lookup_rows("regional", food, "2026-09-24", "release")
    assert [(row["source"], row["status"]) for row in rows] == [
        ("search", "no_results"), ("recorded", "found")]


@pytest.mark.parametrize("failure", ["request", "release"])
def test_failed_or_mixed_release_lookups_preserve_the_previous_log(tmp_path, monkeypatch, food, failure):
    source = tmp_path / "foods.csv"
    with source.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(food))
        writer.writeheader()
        writer.writerow(food)
    output = tmp_path / "lookup.csv"
    output.write_text("previous search evidence\n", encoding="utf-8")
    monkeypatch.setattr(lookup, "TABLES", {"regional": source})
    monkeypatch.setattr(lookup, "OUTPUT", output)
    releases = iter(["release one", "release two"])
    monkeypatch.setattr(lookup, "foodon_release", lambda: next(releases))

    def search(query):
        if failure == "request":
            raise OSError("lookup unavailable")
        return []

    monkeypatch.setattr(lookup, "search", search)
    with pytest.raises((OSError, ValueError)):
        lookup.main()
    assert output.read_text(encoding="utf-8") == "previous search evidence\n"


def test_successful_lookup_writes_a_complete_log(tmp_path, monkeypatch, food):
    source = tmp_path / "foods.csv"
    with source.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(food))
        writer.writeheader()
        writer.writerow(food)
    output = tmp_path / "lookup.csv"
    monkeypatch.setattr(lookup, "TABLES", {"regional": source})
    monkeypatch.setattr(lookup, "OUTPUT", output)
    monkeypatch.setattr(lookup, "foodon_release", lambda: "release")
    monkeypatch.setattr(lookup, "search", lambda query: [("FOODON_00000001", "Example food class")])
    assert lookup.main() == 0
    with output.open(encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    assert len(rows) == 1
    assert rows[0]["status"] == "found"
    assert rows[0]["returned_count"] == "1"
    assert rows[0]["rank"] == "1"
    assert not list(tmp_path.glob("*.tmp"))
