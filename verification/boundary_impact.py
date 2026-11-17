"""Whether floating-point arithmetic changes any result of the TACO x NEVO comparison.

verification/differential.py shows that the Python rules, which use floats, differ from exact arithmetic
for values that sit exactly on a rule's limit: 1.45 * 20 is 28.999999999999996, so a NEVO value of 29 mg is
read as outside a tolerance it is exactly on. This script applies each rule to the real value pairs twice,
as the code does and with exact decimal arithmetic, and lists every result that changes:
- the EU labelling tolerance and the 20 % band, per TACO food against the median of its NEVO foods, as
  scripts/compare_taco_nevo.py reports them;
- the strongly disagreeing components and the flags of scripts/check_food_pairs.py.

    $env:PYTHONPATH = "src"; python verification/boundary_impact.py
"""

from __future__ import annotations

import importlib.util
import statistics
from collections import defaultdict
from decimal import Decimal

from taco_rdf.namespaces import ROOT


def load(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


compare = load("compare_taco_nevo")
pairs = load("check_food_pairs")
D = Decimal


def eu_exact(cdno: str, unit: str, t: Decimal, n: Decimal) -> bool | None:
    code = cdno.rsplit("CDNO_", 1)[-1]
    if code in compare.EU_MACRONUTRIENTS and unit == "g":
        return abs(n - t) <= (D(2) if t < 10 else D("0.2") * t if t <= 40 else D(8))
    if code in compare.EU_FATTY_ACIDS and unit == "g":
        return abs(n - t) <= (D("0.8") if t < 4 else D("0.2") * t)
    if code == compare.EU_SODIUM and unit == "mg":
        return abs(n - t) <= (D(150) if t < 500 else D("0.2") * t)
    if code in compare.EU_MINERALS:
        return D("0.65") * t <= n <= D("1.45") * t
    if code in compare.EU_VITAMINS:
        return D("0.65") * t <= n <= D("1.50") * t
    return None


def within20_exact(t: Decimal, n: Decimal) -> bool:
    return abs(t - n) <= D("0.2") * max(abs(t), abs(n))


def disagreeing_exact(values: dict[str, tuple[Decimal, Decimal, str]]) -> list[str]:
    found = []
    if pairs.WATER in values and abs(values[pairs.WATER][0] - values[pairs.WATER][1]) > D(15):
        found.append("water")
    for code, name in pairs.TOLERANCE.items():
        if code in values:
            t, n, unit = values[code]
            if eu_exact(compare.CDNO + code, unit, t, n) is False:
                found.append(name)
    for code, (name, trace) in pairs.MINERALS.items():
        if code in values and values[code][2] == "mg":
            low, high = sorted(values[code][:2])
            if high > D(str(trace)) and (low == 0 or high >= 3 * low):
                found.append(name)
    return found


def per_food_exact(rows):
    by_food = defaultdict(dict)
    for r in rows:
        key = (r["cdno_label"] or r["class"], r["class"], r["nevo_nutrient"], r["unit"])
        _, nevo = by_food[key].setdefault(r["taco_food"], (D(r["taco_value"]), []))
        nevo.append(D(r["nevo_value"]))
    return {key: {food: (t, statistics.median(n)) for food, (t, n) in foods.items()}
            for key, foods in by_food.items()}


def main() -> int:
    rows = compare.read_pairs(compare.OUT)
    print(f"{len(rows)} value pairs from {compare.OUT.name}\n")
    exact = per_food_exact(rows)
    # The code's own per-food values, as compare_taco_nevo.thresholds_table computes them.
    code = compare.per_food(rows)
    eu_flips, band_flips, compared = [], [], 0
    for key, foods in exact.items():
        label, cdno, _, unit = key
        float_values = code[key]
        exact_values = list(foods.values())
        assert len(float_values) == len(exact_values)
        for (tf, nf), (te, ne) in zip(float_values, exact_values, strict=True):
            compared += 1
            a, b = compare.within_eu_tolerance(cdno, unit, tf, nf), eu_exact(cdno, unit, te, ne)
            if a != b:
                eu_flips.append((label, te, ne, a, b))
            if compare.within_20_percent(tf, nf) != within20_exact(te, ne):
                band_flips.append((label, te, ne, compare.within_20_percent(tf, nf), within20_exact(te, ne)))
    print(f"TACO food x nutrient values compared: {compared}")
    print(f"  EU tolerance results that change with exact arithmetic: {len(eu_flips)}")
    for f in eu_flips:
        print(f"    {f[0]}: TACO {f[1]}, NEVO median {f[2]}: code {f[3]}, exact {f[4]}")
    print(f"  within-20 % results that change with exact arithmetic: {len(band_flips)}")
    for f in band_flips:
        print(f"    {f[0]}: TACO {f[1]}, NEVO median {f[2]}: code {f[3]}, exact {f[4]}")

    checked = {(r["taco_food"], r["nevo_code"]): r for r in pairs.check(rows)}
    by_pair = defaultdict(dict)
    for r in rows:
        by_pair[(r["taco_food"], pairs.nevo_code(r["nevo_food"]))][r["class"].rsplit("_", 1)[-1]] = (
            D(r["taco_value"]), D(r["nevo_value"]), r["unit"])
    component_flips, flag_flips = [], []
    for key, values in by_pair.items():
        found = disagreeing_exact(values)
        code_found = checked[key]["disagreeing"].split(", ") if checked[key]["disagreeing"] else []
        if sorted(found) != sorted(code_found):
            component_flips.append((key, code_found, found))
        if (len(found) >= pairs.MIN_DISAGREEING) != (checked[key]["flagged"] == "True"):
            flag_flips.append(key)
    print(f"\nfood pairs in the composition check: {len(by_pair)}")
    print(f"  pairs whose disagreeing components change with exact arithmetic: {len(component_flips)}")
    for key, a, b in component_flips:
        print(f"    TACO {key[0]} x NEVO {key[1]}: code {a}, exact {b}")
    print(f"  pairs whose flag changes: {len(flag_flips)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
