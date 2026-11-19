"""Validate a returned adjudication workbook against its template and extract its answers.

This checks workbook integrity and answer syntax, not FoodOn membership or ancestry.
It never applies decisions to the graph or overwrites a previous extract.
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
from pathlib import Path

from openpyxl import load_workbook

FIELDS = ["food_number", "name_pt", "source_sheet", "adjudicated", "justification"]
DECISION, JUSTIFICATION = "Decisão final", "Justificativa final"
CURIE = re.compile(r"FOODON_[0-9]{8}")


def _rows(sheet) -> list[tuple]:
    """Ignore only empty rows and trailing empty cells; reject formulas anywhere."""
    rows = []
    for cells in sheet.iter_rows():
        if any(c.data_type == "f" for c in cells):
            raise ValueError(f"{sheet.title}: formulas are not allowed")
        values = [None if c.value in (None, "") else c.value for c in cells]
        while values and values[-1] is None:
            values.pop()
        if values:
            rows.append(tuple(values))
    return rows


def _number(value, where: str) -> int:
    valid = (isinstance(value, int)
             or (isinstance(value, float) and value.is_integer())
             or (isinstance(value, str) and re.fullmatch(r"[0-9]+", value.strip())))
    if isinstance(value, bool) or not valid or int(value) < 1:
        raise ValueError(f"{where}: invalid food number {value!r}")
    return int(value)


def _items(rows: list[tuple], width: int, where: str) -> dict[int, tuple]:
    items = {}
    for row in rows:
        if len(row) > width:
            raise ValueError(f"{where}: data outside the form's columns")
        number = _number(row[0], where)
        if number in items:
            raise ValueError(f"{where}: duplicate food {number}")
        items[number] = row + (None,) * (width - len(row))
    return items


def _same(first: tuple, second: tuple) -> bool:
    """Keep booleans distinct from numeric cells (True must not equal 1)."""
    return len(first) == len(second) and all(
        type(a) is type(b) and a == b for a, b in zip(first, second, strict=True))


def read_adjudication(template: Path, workbook: Path) -> list[dict[str, str]]:
    """Require all final decisions, intact context, and the template's exact food sets."""
    expected = load_workbook(template, read_only=True, data_only=False)
    try:
        returned = load_workbook(workbook, read_only=True, data_only=False)
        try:
            if set(expected.sheetnames) != set(returned.sheetnames):
                raise ValueError("workbook sheets differ from the template")
            answers = []
            seen = set()
            for name in expected.sheetnames:
                before, after = _rows(expected[name]), _rows(returned[name])
                if not before:
                    if after:
                        raise ValueError(f"{name}: an empty template sheet changed")
                    continue
                heads = before[0]
                if DECISION not in heads and JUSTIFICATION not in heads:
                    if len(before) != len(after) or any(
                            not _same(a, b) for a, b in zip(before, after, strict=True)):
                        raise ValueError(f"{name}: read-only sheet changed")
                    continue
                if heads.count(DECISION) != 1 or heads.count(JUSTIFICATION) != 1:
                    raise ValueError(f"{name}: ambiguous final-answer columns")
                if not after or not _same(heads, after[0]):
                    raise ValueError(f"{name}: column headers changed")
                decision, justification = heads.index(DECISION), heads.index(JUSTIFICATION)
                original = _items(before[1:], len(heads), f"template {name}")
                received = _items(after[1:], len(heads), name)
                if original.keys() != received.keys():
                    raise ValueError(f"{name}: foods differ from the template")
                for number, context in original.items():
                    if number in seen:
                        raise ValueError(f"food {number} occurs in multiple adjudication sheets")
                    seen.add(number)
                    row = received[number]
                    fixed = [i for i in range(1, len(heads)) if i not in (decision, justification)]
                    if not _same(tuple(context[i] for i in fixed), tuple(row[i] for i in fixed)):
                        raise ValueError(f"{name}: food {number} context changed")
                    if context[decision] is not None or context[justification] is not None:
                        raise ValueError(f"{name}: template already has a final answer for food {number}")
                    answer = str(row[decision] or "").strip()
                    reason = str(row[justification] or "").strip()
                    if answer != "none" and not CURIE.fullmatch(answer):
                        raise ValueError(f"{name}: food {number} has an invalid or missing decision")
                    if not isinstance(row[justification], str) or not reason:
                        raise ValueError(f"{name}: food {number} needs a written justification")
                    answers.append({"food_number": str(number), "name_pt": str(context[1]),
                                    "source_sheet": name, "adjudicated": answer, "justification": reason})
            if not answers:
                raise ValueError("template has no adjudication items")
            return answers
        finally:
            returned.close()
    finally:
        expected.close()


def extract(template: Path, workbook: Path, out: Path) -> int:
    answers = read_adjudication(template, workbook)
    with out.open("x", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=FIELDS, lineterminator="\r\n")
        writer.writeheader()
        writer.writerows(answers)
    return len(answers)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--template", type=Path, required=True)
    parser.add_argument("--workbook", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    try:
        count = extract(args.template, args.workbook, args.out)
    except (ValueError, OSError) as error:
        print(error, file=sys.stderr)
        return 1
    print(f"wrote {args.out}: {count} adjudicated foods; FoodOn validation is still required")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
