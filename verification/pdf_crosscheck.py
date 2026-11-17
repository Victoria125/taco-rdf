"""Compare the TACO values written for NICE-Food with the values printed in TACO's own PDF.

The project reads TACO's spreadsheet; the PDF (NEPA-UNICAMP, 4th edition, 2011) is the published table, an
independent source for the same numbers. This script reads the first half of each pair of pages of the PDF's
Table 1: moisture, energy (kcal, kJ), protein, lipids, cholesterol, carbohydrate, dietary fibre, ash, calcium
and magnesium. The other half of each pair comes out of the PDF's text with numbers split apart and is not
used. A row whose numbers came out split is skipped and counted.

Each exported value, rounded to the decimals the PDF prints (half up), must equal the printed number; NA, Tr
and * must match the value's taco:valueStatus (not applicable, trace, under re-evaluation). A printed Tr also
agrees with a number that rounds to zero, which is how TACO defines a trace.

    $env:PYTHONPATH = "src;<folder with pypdf>"; python verification/pdf_crosscheck.py
"""

from __future__ import annotations

import argparse
import re
from collections import Counter
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

from pypdf import PdfReader
from rdflib import DCTERMS, Graph, Namespace

from taco_rdf.namespaces import BUILD_DIR, ROOT, TACO

FIO = Namespace("http://www.foodvoc.org/resource/fio#")
OM = Namespace("http://www.ontology-of-units-of-measure.org/resource/om-2/")
PDF = ROOT / "data" / "external" / "taco" / "taco_4_edicao_revisada_e_ampliada.pdf"
# The PDF's columns, in order, and the nutrient each is written under in the subgraph.
COLUMNS = ["WATER", "ENERCC", "ENERCJ", "PROT", "FAT", "CHORL", "carbohydrate", "FIBT", "ASH", "CA", "MG"]
PIECE = r"(?:[\d,]+|NA|Tr|\*)"
# A food row: its number, its name (ending in a character that is not a digit, space or comma), its pieces.
ROW = re.compile(rf"^(\d{{1,3}}) (.*?[^\d\s,]) ({PIECE}(?:\s+{PIECE})*)\s*$")
NUMBER = re.compile(r"^\d+(,\d+)?$")
STATUS = {"NA": TACO.NotApplicable, "Tr": TACO.Trace, "*": TACO.UnderReevaluation}


def first_three(pieces: list[str]) -> list[str] | None:
    """Moisture, kcal and kJ from pieces that the PDF's text may have split, e.g. 1974 kJ as '19 74'.

    Every way of joining neighbouring pieces into three numbers is tried, and kept only when the PDF agrees
    with itself: moisture at most 100 %, kcal and kJ whole numbers, kJ = kcal x 4.184 (TACO, p. 13) within
    rounding. The subgraph's values play no part, so they cannot steer the reading. None unless exactly one
    way fits.
    """
    if len(pieces) == 3 and any(p in STATUS for p in pieces):
        return pieces
    fits = []
    n = len(pieces)
    for i in range(1, n - 1):
        for j in range(i + 1, n):
            moisture, kcal, kj = "".join(pieces[:i]), "".join(pieces[i:j]), "".join(pieces[j:])
            if not (NUMBER.match(moisture) and kcal.isdigit() and kj.isdigit()):
                continue
            if float(moisture.replace(",", ".")) <= 100 and abs(int(kcal) * 4.184 - int(kj)) <= 2.5:
                fits.append([moisture, kcal, kj])
    return fits[0] if len(fits) == 1 else None


def pdf_rows(path: Path) -> tuple[dict[str, tuple[str, list[str]]], int, int]:
    """Food number to (name, its 11 printed values); how many rows were rejoined; how many were not read."""
    rows: dict[str, tuple[str, list[str]]] = {}
    rejoined = unread = 0
    for page in PdfReader(path).pages:
        text = page.extract_text() or ""
        if "Umidade" not in text or "Tabela 1" not in text:
            continue
        for line in text.splitlines():
            m = ROW.match(line.strip())
            if not m:
                if re.match(r"^\d{1,3} [A-ZÁÉÍÓÚÂÊÔÃÕÇ]", line.strip()):
                    unread += 1
                continue
            pieces = m.group(3).split()
            if len(pieces) < 11:
                unread += 1
                continue
            head = first_three(pieces[:-8])
            if head is None:
                unread += 1
                continue
            rejoined += len(pieces) > 11
            rows[m.group(1)] = (m.group(2), head + pieces[-8:])
    return rows, rejoined, unread


def exported(path: Path) -> dict[tuple[str, str], tuple[Decimal | None, str | None]]:
    """(food number, nutrient) to (number, status) in the NICE-Food subgraph."""
    g = Graph().parse(path, format="turtle")
    out = {}
    for food, number in g.subject_objects(DCTERMS.identifier):
        for value in g.objects(food, FIO.hasNutritionalValue):
            nutrient = str(g.value(value, FIO.hasNutrient)).rsplit("#", 1)[-1].rsplit("/", 1)[-1]
            measure = g.value(value, OM.hasValue)
            amount = g.value(measure, OM.hasNumericalValue) if measure is not None else None
            status = g.value(value, TACO.valueStatus)
            out[(str(number), nutrient)] = (Decimal(str(amount)) if amount is not None else None, status)
    return out


def check(printed: str, amount: Decimal | None, status) -> str:
    if printed in STATUS:
        if status == STATUS[printed]:
            return "same status"
        if printed == "Tr" and amount is not None and amount.quantize(Decimal("0.1"), ROUND_HALF_UP) == 0:
            return "Tr, number rounds to zero"
        return "differs"
    if amount is None:
        return "differs"
    want = Decimal(printed.replace(",", "."))
    places = Decimal(1).scaleb(want.as_tuple().exponent)
    if amount.quantize(places, ROUND_HALF_UP) == want:
        return "same number"
    if abs(amount.quantize(places, ROUND_HALF_UP) - want) <= places:
        return "last digit"
    return "differs"


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--pdf", type=Path, default=PDF)
    p.add_argument("--subgraph", type=Path, default=BUILD_DIR / "taco_nice_food.ttl")
    args = p.parse_args()
    rows, rejoined, unread = pdf_rows(args.pdf)
    values = exported(args.subgraph)
    outcome: Counter = Counter()
    by_column: dict[str, Counter] = {c: Counter() for c in COLUMNS}
    problems = []
    for number, (name, tokens) in sorted(rows.items(), key=lambda kv: int(kv[0])):
        for column, printed in zip(COLUMNS, tokens, strict=True):
            amount, status = values.get((number, column), (None, None))
            result = check(printed, amount, status)
            outcome[result] += 1
            by_column[column][result] += 1
            if result in ("differs", "last digit"):
                problems.append((number, name, column, printed, amount, status, result))
    print(f"PDF rows read: {len(rows)} of TACO's 597 foods; {rejoined} of them with numbers the PDF's text "
          f"had split, rejoined; {unread} rows not read")
    print(f"values compared: {sum(outcome.values())}")
    for result, n in outcome.most_common():
        print(f"  {n:6d}  {result}")
    print("\nby column (same / last digit / differs):")
    for column, c in by_column.items():
        same = c["same number"] + c["same status"] + c["Tr, number rounds to zero"]
        print(f"  {column:<13}{same:>5}{c['last digit']:>5}{c['differs']:>5}")
    if problems:
        print("\nvalues that are not the same:")
        for number, name, column, printed, amount, status, result in problems:
            st = str(status).rsplit("#", 1)[-1] if status is not None else ""
            print(f"  {number:>3} {name[:42]:<42} {column:<13} PDF {printed:<7} export {amount} {st} "
                  f"({result})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
