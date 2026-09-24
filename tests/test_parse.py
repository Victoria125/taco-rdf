from __future__ import annotations

from collections import Counter
from decimal import Decimal

import pytest
import xlrd

from taco_rdf.namespaces import CORRECTIONS_DIR, RAW_XLS
from taco_rdf.nutrients import NUTRIENTS
from taco_rdf.parse import (
    Status,
    TacoParseError,
    _check_headers,
    _classify,
    _is_food_row,
    _norm,
    _to_decimal,
    load_corrections,
    parse_workbook,
)


def test_shape_of_the_table(table):
    assert len(table.foods) == 597
    assert sorted(table.foods) == list(range(1, 598))
    assert len(table.groups) == 15
    assert table.groups[0] == "Cereais e derivados"
    assert table.groups[-1] == "Nozes e sementes"


def test_every_food_has_a_group_and_a_name(table):
    assert {f.group_id for f in table.foods.values()} == set(range(1, 16))
    assert all(f.name and f.name == f.name.strip() for f in table.foods.values())


def test_status_totals(table):
    counts = Counter(o.status for o in table.observations)
    assert counts == {
        Status.MEASURED: 17564,
        Status.TRACE: 2603,
        Status.NOT_APPLICABLE: 907,
        Status.UNDER_REEVALUATION: 76,
    }
    assert len(table.observations) == 21150


def test_status_counts_match_an_independent_scan_of_the_workbook(table):
    book = xlrd.open_workbook(str(RAW_XLS))
    wanted = {0: [], 1: [], 2: []}
    for n in NUTRIENTS:
        wanted[n.sheet].append(n.col)
    tokens = Counter()
    for si in (0, 1, 2):
        sh = book.sheet_by_index(si)
        for r in range(3, sh.nrows):
            row = sh.row_values(r)
            if isinstance(row[0], str) and row[0].strip() == "Legenda":
                break
            if not (isinstance(row[0], float) and isinstance(row[1], str) and row[1].strip()):
                continue
            for c in wanted[si]:
                cell = row[c]
                if isinstance(cell, str) and cell.strip().lower() in ("tr", "na", "*"):
                    tokens[cell.strip().lower()] += 1
    counts = Counter(o.status for o in table.observations)
    assert tokens["tr"] == counts[Status.TRACE]
    assert tokens["na"] == counts[Status.NOT_APPLICABLE]
    assert tokens["*"] == counts[Status.UNDER_REEVALUATION]


def test_only_measured_observations_carry_a_value(table):
    for o in table.observations:
        assert (o.value is not None) == (o.status is Status.MEASURED)


def test_trace_is_not_zero(value_of):
    o = value_of[(1, "fa_14_0")]
    assert o.status is Status.TRACE and o.value is None
    traces = [o for o in value_of.values() if o.status is Status.TRACE]
    assert traces and all(o.value is None for o in traces)


def test_cell_correction_is_applied_and_flagged(value_of):
    o = value_of[(373, "pyridoxine")]
    assert o.value == Decimal("0.02")
    assert o.origin == "cell_corrected"
    assert ",0,02" in o.note


def test_id_correction_moves_amino_acids_to_maria_mole(table, value_of):
    assert table.foods[504].name == "Maria mole"
    assert table.foods[468].name == "Queijo, requeijão, cremoso"
    assert (504, "tryptophan") in value_of and (468, "tryptophan") not in value_of
    assert value_of[(504, "tryptophan")].origin == "id_corrected"
    assert "468" in value_of[(504, "tryptophan")].note
    assert sum(1 for k in value_of if k[1] == "tryptophan") == 26


def test_defects_are_never_absorbed_silently():
    with pytest.raises(TacoParseError, match="unexpected cell content"):
        parse_workbook(RAW_XLS)

    corrections = load_corrections(CORRECTIONS_DIR)
    corrections.ids.clear()
    with pytest.raises(TacoParseError, match="food 468 is 'Maria mole'"):
        parse_workbook(RAW_XLS, corrections)


def test_a_correction_cannot_mask_a_different_value():
    corrections = load_corrections(CORRECTIONS_DIR)
    corrections.cells[(373, "pyridoxine")] = ("something else", Decimal("9"))
    with pytest.raises(TacoParseError, match="unexpected cell content"):
        parse_workbook(RAW_XLS, corrections)


def test_legend_footnotes_become_data(table, value_of):
    assert table.foods[472].name == "Cana, aguardente" and table.foods[472].footnote == 1
    assert table.foods[474].name == "Cerveja, pilsen" and table.foods[474].footnote == 2
    assert value_of[(472, "alcohol")].value == Decimal("31.1")
    assert value_of[(474, "alcohol")].value == Decimal("3.6")
    assert value_of[(472, "alcohol")].origin == "footnote"


def test_known_value_matches_the_printed_table(value_of):
    assert value_of[(1, "moisture")].value == Decimal("70.138667")
    assert round(value_of[(1, "energy_kcal")].value) == 124
    assert round(value_of[(1, "energy_kj")].value) == 517
    assert round(value_of[(1, "protein")].value, 1) == Decimal("2.6")


def test_nutrient_registry_is_consistent():
    keys = [n.key for n in NUTRIENTS]
    assert len(keys) == len(set(keys)) == 66
    per_sheet = Counter(n.sheet for n in NUTRIENTS)
    assert per_sheet == {0: 26, 1: 22, 2: 18}


def test_to_decimal_removes_float_noise():
    assert _to_decimal(70.13866666666667) == Decimal("70.138667")
    assert _to_decimal(100.0) == Decimal("100")
    assert _to_decimal(0.0) == Decimal("0")
    assert str(_to_decimal(0.5)) == "0.5"


@pytest.mark.parametrize("cell, expected", [
    ("Tr", (Status.TRACE, None)),
    (" tr ", (Status.TRACE, None)),
    ("NA", (Status.NOT_APPLICABLE, None)),
    ("*", (Status.UNDER_REEVALUATION, None)),
    ("", None),
    ("  ", None),
])
def test_classify_tokens(cell, expected):
    assert _classify(cell) == expected


def test_classify_rejects_garbage_instead_of_guessing():
    with pytest.raises(TacoParseError):
        _classify(",0,02")


def test_food_row_detection():
    assert _is_food_row([1.0, "Arroz", 70.1])
    assert not _is_food_row(["Número do", "", ""])
    assert not _is_food_row([1.5, "x", 0.0])
    assert not _is_food_row([1.0, "", 0.0])
    assert _norm("  a \n b ") == "a b"


def test_header_check_fails_loudly_on_layout_change():
    class FakeSheet:
        name = "fake"

        def row_values(self, i):
            row1 = [""] * 40
            row2 = [""] * 40
            return {1: row1, 2: row2}[i]

    with pytest.raises(TacoParseError, match="expected header"):
        _check_headers(FakeSheet(), [NUTRIENTS[0]])
