"""Returned adjudication is extracted only when answers and their context are unambiguous."""

from __future__ import annotations

import csv
import importlib.util

import pytest
from openpyxl import Workbook, load_workbook

from taco_rdf.namespaces import ROOT

spec = importlib.util.spec_from_file_location("adjudication", ROOT / "scripts/import_type_adjudication.py")
assert spec is not None and spec.loader is not None
adjudication = importlib.util.module_from_spec(spec)
spec.loader.exec_module(adjudication)


@pytest.fixture
def books(tmp_path):
    template, returned = tmp_path / "template.xlsx", tmp_path / "returned.xlsx"
    wb = Workbook()
    wb.active.title = "Instruções"
    wb.active.append(["Read this", "preserve context"])
    for name, number, food in (("Discordâncias", 1, "Arroz"), ("Acordos bloqueados", 2, "Tamarindo")):
        ws = wb.create_sheet(name)
        ws.append(["Nº", "Alimento", "Classe bloqueada?", "Decisão final", "Justificativa final"])
        ws.append([number, food, True, "", ""])
    wb.save(template)
    for ws in list(wb)[1:]:
        ws["D2"] = "FOODON_00001002"
        ws["E2"] = "Food product justified by the description."
    wb.save(returned)
    wb.close()
    return template, returned, tmp_path / "answers.csv"


def test_extract_preserves_sources_and_refuses_to_overwrite(books):
    template, returned, out = books
    originals = template.read_bytes(), returned.read_bytes()
    assert adjudication.extract(template, returned, out) == 2
    with out.open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    assert rows == [
        {"food_number": "1", "name_pt": "Arroz", "source_sheet": "Discordâncias",
         "adjudicated": "FOODON_00001002", "justification": "Food product justified by the description."},
        {"food_number": "2", "name_pt": "Tamarindo", "source_sheet": "Acordos bloqueados",
         "adjudicated": "FOODON_00001002", "justification": "Food product justified by the description."}]
    saved = out.read_bytes()
    with pytest.raises(FileExistsError):
        adjudication.extract(template, returned, out)
    assert out.read_bytes() == saved
    assert (template.read_bytes(), returned.read_bytes()) == originals


def test_empty_formatting_none_and_integral_ids_are_accepted(books):
    template, returned, _ = books
    wb = load_workbook(returned)
    for sheet in wb:
        sheet["Z20"].number_format = "0.00"
    ws = wb["Discordâncias"]
    ws["A2"] = "1"
    ws["D2"] = "none"
    ws["E2"] = "No class justified; searched rice and cooked rice."
    wb.save(returned)
    wb.close()
    rows = adjudication.read_adjudication(template, returned)
    assert rows[0]["adjudicated"] == "none"
    assert rows[0]["food_number"] == "1"


@pytest.mark.parametrize(("sheet", "cell", "value", "match"), [
    ("Discordâncias", "B2", "Changed food", "context changed"),
    ("Discordâncias", "C2", 1, "context changed"),
    ("Discordâncias", "A2", 1.5, "invalid food number"),
    ("Discordâncias", "A2", True, "invalid food number"),
    ("Discordâncias", "A2", 0, "invalid food number"),
    ("Discordâncias", "A2", None, "invalid food number"),
    ("Discordâncias", "A2", 99, "foods differ"),
    ("Discordâncias", "D1", "Decision", "headers changed"),
    ("Discordâncias", "D2", "FOODON_123", "invalid or missing decision"),
    ("Discordâncias", "D2", None, "invalid or missing decision"),
    ("Discordâncias", "E2", "  ", "written justification"),
    ("Discordâncias", "E2", 123, "written justification"),
    ("Discordâncias", "D2", '=CONCAT("FOODON_", "00001002")', "formulas"),
    ("Discordâncias", "Z2", "extra", "outside the form"),
    ("Instruções", "A1", "Changed", "read-only sheet changed"),
])
def test_bad_returns_are_refused_without_writing(books, sheet, cell, value, match):
    template, returned, out = books
    wb = load_workbook(returned)
    wb[sheet][cell] = value
    wb.save(returned)
    wb.close()
    originals = template.read_bytes(), returned.read_bytes()
    with pytest.raises(ValueError, match=match):
        adjudication.extract(template, returned, out)
    assert not out.exists()
    assert (template.read_bytes(), returned.read_bytes()) == originals


@pytest.mark.parametrize("change", ["duplicate", "missing food", "missing sheet", "extra sheet"])
def test_changed_food_or_sheet_sets_are_refused(books, change):
    template, returned, _ = books
    wb = load_workbook(returned)
    ws = wb["Discordâncias"]
    if change == "duplicate":
        ws.append([c.value for c in ws[2]])
    elif change == "missing food":
        ws.delete_rows(2)
    elif change == "missing sheet":
        del wb["Instruções"]
    else:
        wb.create_sheet("Extra")
    wb.save(returned)
    wb.close()
    with pytest.raises(ValueError):
        adjudication.read_adjudication(template, returned)


def test_duplicate_across_template_sheets_is_rejected(books):
    template, returned, _ = books
    for path in (template, returned):
        wb = load_workbook(path)
        wb["Acordos bloqueados"]["A2"] = 1
        wb.save(path)
        wb.close()
    with pytest.raises(ValueError, match="multiple adjudication sheets"):
        adjudication.read_adjudication(template, returned)
