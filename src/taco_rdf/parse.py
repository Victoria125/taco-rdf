from __future__ import annotations

import csv
import re
import unicodedata
from dataclasses import dataclass, field, replace
from decimal import Decimal
from enum import Enum
from pathlib import Path

import xlrd

from .nutrients import ALCOHOL, NUTRIENTS, Nutrient


class Status(str, Enum):
    MEASURED = "Measured"
    TRACE = "Trace"
    NOT_APPLICABLE = "NotApplicable"
    UNDER_REEVALUATION = "UnderReevaluation"


_TOKENS = {
    "tr": Status.TRACE,
    "na": Status.NOT_APPLICABLE,
    "*": Status.UNDER_REEVALUATION,
}


@dataclass(frozen=True)
class Food:
    id: int
    name: str
    group_id: int
    footnote: int | None = None


@dataclass(frozen=True)
class Observation:
    food_id: int
    nutrient: str
    status: Status
    value: Decimal | None
    origin: str = "table"
    note: str | None = None


@dataclass
class Table:
    groups: list[str] = field(default_factory=list)
    foods: dict[int, Food] = field(default_factory=dict)
    observations: list[Observation] = field(default_factory=list)
    legend: list[str] = field(default_factory=list)


class TacoParseError(ValueError):
    pass


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", unicodedata.normalize("NFC", str(text))).strip()


def _to_decimal(x: float) -> Decimal:
    s = format(x, ".6f").rstrip("0").rstrip(".")
    return Decimal(s if s not in ("", "-0") else "0")


@dataclass
class Corrections:
    cells: dict[tuple[int, str], tuple[str, Decimal]] = field(default_factory=dict)
    ids: dict[tuple[int, int, str], int] = field(default_factory=dict)


def load_corrections(directory: str | Path) -> Corrections:
    directory = Path(directory)
    out = Corrections()
    with open(directory / "cells.csv", newline="", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            out.cells[(int(r["food_id"]), r["nutrient"])] = (r["raw_cell"], Decimal(r["corrected_value"]))
    with open(directory / "ids.csv", newline="", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            out.ids[(int(r["sheet"]), int(r["listed_id"]), _norm(r["listed_name"]))] = int(r["corrected_id"])
    return out


def _squash(text: str) -> str:
    return re.sub(r"\s+", "", text).casefold()


def _same_name(a: str, b: str) -> bool:
    return _squash(a) == _squash(b)


def _classify(cell) -> tuple[Status, Decimal | None] | None:
    if isinstance(cell, float):
        return Status.MEASURED, _to_decimal(cell)
    text = _norm(cell)
    if text == "":
        return None
    status = _TOKENS.get(text.lower())
    if status is None:
        raise TacoParseError(f"unexpected cell content {cell!r}")
    return status, None


def _is_food_row(row: list) -> bool:
    return (
        isinstance(row[0], float)
        and row[0] > 0
        and row[0] == int(row[0])
        and isinstance(row[1], str)
        and _norm(row[1]) != ""
    )


def _is_group_row(row: list) -> bool:
    return (
        isinstance(row[0], str)
        and _norm(row[0]) not in ("", "Legenda")
        and all(_norm(c) == "" for c in row[1:])
    )


def _check_headers(sheet: xlrd.sheet.Sheet, nutrients: list[Nutrient]) -> None:
    hdr1, hdr2 = sheet.row_values(1), sheet.row_values(2)
    for n in nutrients:
        got1, got2 = _norm(hdr1[n.col]), _norm(hdr2[n.col])
        if got1 != n.header or got2 != n.unit_header:
            raise TacoParseError(
                f"sheet {sheet.name!r} col {n.col}: expected header "
                f"{n.header!r} {n.unit_header!r} for {n.key}, found {got1!r} {got2!r}"
            )


def _legend_alcohol(legend: list[str]) -> list[tuple[str, Decimal]]:
    for line in legend:
        if "Teores alcoólicos" in line:
            seg = line.split("):", 1)[1]
            found = re.findall(r"[¹²³⁴]\s*([^:¹²³⁴]+?):\s*(\d+(?:,\d+)?)", seg)
            return [(_norm(name), Decimal(v.replace(",", "."))) for name, v in found]
    return []


def parse_workbook(path: str | Path, corrections: Corrections | None = None) -> Table:
    corrections = corrections or Corrections()
    book = xlrd.open_workbook(str(path))
    if book.nsheets != 3:
        raise TacoParseError(f"expected 3 sheets, found {book.nsheets}")

    table = Table()
    by_sheet: dict[int, list[Nutrient]] = {0: [], 1: [], 2: []}
    for n in NUTRIENTS:
        by_sheet[n.sheet].append(n)

    group_ids: dict[str, int] = {}
    names_seen: dict[int, str] = {}

    for sheet_idx in (0, 1, 2):
        sheet = book.sheet_by_index(sheet_idx)
        nutrients = by_sheet[sheet_idx]
        _check_headers(sheet, nutrients)
        current_group: int | None = None

        for r in range(3, sheet.nrows):
            row = sheet.row_values(r)
            if _norm(row[0]) == "Legenda":
                if sheet_idx == 0:
                    table.legend = [
                        _norm(" ".join(str(c) for c in sheet.row_values(i) if _norm(c)))
                        for i in range(r + 1, sheet.nrows)
                        if any(_norm(c) for c in sheet.row_values(i))
                    ]
                break

            if _is_group_row(row):
                if sheet_idx == 0:
                    name = _norm(row[0])
                    if name not in group_ids:
                        group_ids[name] = len(group_ids) + 1
                        table.groups.append(name)
                    current_group = group_ids[name]
                continue

            if not _is_food_row(row):
                continue

            listed_id, fname = int(row[0]), _norm(row[1])
            fid = corrections.ids.get((sheet_idx, listed_id, fname), listed_id)
            id_note = (
                f"listed under food number {listed_id} in sheet {sheet.name!r}; "
                f"reassigned to {fid} (data/corrections/ids.csv)"
                if fid != listed_id
                else None
            )
            if sheet_idx == 0:
                if current_group is None:
                    raise TacoParseError(f"food {fid} appears before any group")
                if fid in table.foods:
                    raise TacoParseError(f"duplicate food id {fid}")
                table.foods[fid] = Food(fid, fname, current_group)
                names_seen[fid] = fname
            else:
                if fid not in table.foods:
                    raise TacoParseError(f"sheet {sheet_idx}: unknown food id {fid}")
                if not _same_name(names_seen[fid], fname):
                    raise TacoParseError(
                        f"sheet {sheet_idx}: food {fid} is {fname!r}, sheet 0 says {names_seen[fid]!r}"
                    )

            for n in nutrients:
                cell = row[n.col]
                fix = corrections.cells.get((fid, n.key))
                if fix is not None and isinstance(cell, str) and cell == fix[0]:
                    note = f"source cell text {cell!r} corrected to {fix[1]} (data/corrections/cells.csv)"
                    table.observations.append(
                        Observation(fid, n.key, Status.MEASURED, fix[1], "cell_corrected", note)
                    )
                    continue
                try:
                    cls = _classify(cell)
                except TacoParseError as exc:
                    raise TacoParseError(f"food {fid} {n.key}: {exc}") from None
                if cls is not None:
                    origin = "id_corrected" if id_note else "table"
                    table.observations.append(Observation(fid, n.key, *cls, origin, id_note))

    for name, value in _legend_alcohol(table.legend):
        matches = [
            f for f in table.foods.values() if re.fullmatch(re.escape(name) + r" [1-4]", f.name)
        ]
        if len(matches) != 1:
            raise TacoParseError(f"alcohol footnote for {name!r} matches {len(matches)} foods")
        food = matches[0]
        table.foods[food.id] = replace(food, name=name, footnote=int(food.name[-1]))
        table.observations.append(
            Observation(food.id, ALCOHOL.key, Status.MEASURED, value, origin="footnote")
        )

    return table
