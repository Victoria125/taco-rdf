"""scripts/review_workbook.py: a reviewer's workbook carries answers back to the form, and nothing else."""

from __future__ import annotations

import csv
import importlib.util

import pytest
from openpyxl import load_workbook

from taco_rdf.namespaces import ROOT

spec = importlib.util.spec_from_file_location("review_workbook", ROOT / "scripts" / "review_workbook.py")
assert spec is not None and spec.loader is not None
wbk = importlib.util.module_from_spec(spec)
spec.loader.exec_module(wbk)

FOODS = [("1", "Arroz, integral, cozido", "Rice, brown, cooked", "Cereais e derivados",
          "FOODON_00004320 rice (cooked) [name] | FOODON_00004678 brown rice kernel (cooked) [OLS]"),
         ("2", "Açaí, polpa, congelada", "Açaí, pulp, frozen", "Frutas e derivados", ""),
         ("3", "Mel, de abelha", "Honey", "Produtos açucarados", "FOODON_00001178 honey [name]")]


@pytest.fixture
def form(tmp_path):
    path = tmp_path / "reviewer-1.csv"
    with path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh, lineterminator="\r\n")
        w.writerow(wbk.CONTEXT + wbk.ANSWERS)
        w.writerows([*f, "", "", "", ""] for f in FOODS)
    classes = tmp_path / "classes.tsv"
    classes.write_text("# release\nFOODON_00004320\trice (cooked)\nFOODON_00001178\thoney\n",
                       encoding="utf-8")
    return path, classes


def export(form, tmp_path):
    path, classes = form
    out = tmp_path / "revisora.xlsx"
    wbk.export(path, out, "Revisora 1", classes)
    return out


def test_the_workbook_has_instructions_an_example_the_form_and_the_classes(form, tmp_path):
    wb = load_workbook(export(form, tmp_path))
    assert wb.sheetnames == ["Instruções", "Exemplo", "Formulário", "Classes FoodOn"]
    sheet = wb["Formulário"]
    assert [c.value for c in sheet[1]] == wbk.HEADERS
    assert [sheet.cell(row=i, column=1).value for i in (2, 3, 4)] == [1, 2, 3]
    assert sheet.protection.sheet
    assert all(sheet.cell(row=2, column=j).protection.locked for j in range(1, 6))
    assert not any(sheet.cell(row=2, column=j).protection.locked for j in range(6, 10))
    assert wb["Classes FoodOn"].max_row == 3
    assert "Revisora 1" in wb["Instruções"]["A1"].value


def test_answers_come_back_and_the_context_stays_the_form_s(form, tmp_path):
    out = export(form, tmp_path)
    wb = load_workbook(out)
    sheet = wb["Formulário"]
    sheet["F2"], sheet["G2"], sheet["I2"] = "FOODON_00004678", "brown rice, cooked", "sim"
    sheet["F3"], sheet["H3"] = "none", "acai; açaí berry"
    sheet["B4"] = "changed in Excel"  # a context cell changed by mistake does not reach the form
    wb.save(out)
    path, _ = form
    assert wbk.import_(path, out) == 0
    with path.open(encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh))
    assert [r["decision"] for r in rows] == ["FOODON_00004678", "none", ""]
    assert rows[0]["unsure"] == "yes" and rows[1]["searched_terms"] == "acai; açaí berry"
    assert [tuple(r[k] for k in wbk.CONTEXT) for r in rows] == FOODS
    assert path.read_bytes().count(b"\r\n") == 4


@pytest.mark.parametrize("change", ["drop a food", "bad CURIE", "bad unsure"])
def test_a_workbook_with_a_food_missing_or_a_malformed_answer_is_refused(form, tmp_path, change):
    out = export(form, tmp_path)
    wb = load_workbook(out)
    sheet = wb["Formulário"]
    if change == "drop a food":
        sheet.delete_rows(3)
    elif change == "bad CURIE":
        sheet["F2"] = "FOODON_123"
    else:
        sheet["I2"] = "talvez"
    wb.save(out)
    path, _ = form
    before = path.read_bytes()
    assert wbk.import_(path, out) == 1
    assert path.read_bytes() == before


def test_empty_formatted_columns_and_rows_do_not_change_the_import(form, tmp_path):
    out = export(form, tmp_path)
    wb = load_workbook(out)
    sheet = wb["Formulário"]
    sheet["F2"] = "FOODON_00004678"
    sheet["G2"] = "brown rice, cooked"
    sheet["Z20"].number_format = "0.00"  # Excel's used range can include empty, formatted cells.
    wb.save(out)
    wb.close()
    assert wbk.answers_in(out) == {
        1: {"decision": "FOODON_00004678", "justification": "brown rice, cooked",
            "searched_terms": "", "unsure": ""},
        2: dict.fromkeys(wbk.ANSWERS, ""),
        3: dict.fromkeys(wbk.ANSWERS, ""),
    }
    assert wbk.import_(form[0], out) == 0


@pytest.mark.parametrize(("cell", "value", "message"), [
    ("J1", "extra header", "columns changed"),
    ("J2", "extra answer", "data outside"),
    ("Z20", "extra answer", "data outside"),
    ("G20", "answer without an ID", "no food number"),
    ("A3", 1, "occurs more than once"),
    ("A2", 1.5, "non-integer food number"),
    ("A2", True, "non-integer food number"),
    ("A2", "1.5", "non-integer food number"),
    ("A2", "food 1", "non-integer food number"),
])
def test_ambiguous_rows_or_extra_data_are_refused_without_changing_the_form(
        form, tmp_path, cell, value, message):
    out = export(form, tmp_path)
    wb = load_workbook(out)
    wb["Formulário"][cell] = value
    wb.save(out)
    wb.close()
    before = form[0].read_bytes()
    with pytest.raises(ValueError, match=message):
        wbk.import_(form[0], out)
    assert form[0].read_bytes() == before


@pytest.mark.parametrize("invalid", [False, True])
def test_the_read_only_workbook_is_closed_even_if_rejected(form, tmp_path, monkeypatch, invalid):
    out = export(form, tmp_path)
    wb = load_workbook(out, read_only=True)
    closed = []
    close = wb.close

    def close_and_record():
        close()
        closed.append(True)

    monkeypatch.setattr(wb, "close", close_and_record)
    monkeypatch.setattr(wbk, "load_workbook", lambda *args, **kwargs: wb)
    if invalid:
        monkeypatch.setattr(wbk, "HEADERS", ["changed"])
        with pytest.raises(ValueError, match="columns changed"):
            wbk.answers_in(out)
    else:
        wbk.answers_in(out)
    assert closed == [True]
