"""Run the Python rules and their Lean model (verification/lean/TacoRules.lean) on the same cases.

The Lean file proves properties of a model of each rule. This script checks, case by case, that the Python
code computes what the model computes, so that the proofs carry over to the code. Values are integers in
millionths, as in the Lean model; the Python functions get them as the decimals or floats they get from the
data. Many cases sit exactly on a rule's boundary, where floating-point arithmetic can differ from exact
arithmetic.

Run from the project folder with Lean 4 on the PATH:
    $env:PYTHONPATH = "src"; python verification/differential.py
"""

from __future__ import annotations

import importlib.util
import random
import re
import subprocess
import sys
import tempfile
from collections import Counter
from decimal import Decimal
from pathlib import Path

from rdflib import Graph, Literal

from taco_rdf.namespaces import ID, QUDT, ROOT, TACO, UNIT

S = 1_000_000
LEAN = ROOT / "verification" / "lean" / "TacoRules.lean"
CHUNK = 250


def load(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


nice = load("taco_to_nice_food")
compare = load("compare_taco_nevo")
pairs = load("check_food_pairs")


# --- cases -------------------------------------------------------------------------------------------------

def near(x: int) -> list[int]:
    return [x - 1, x, x + 1]


def band_cases(rng: random.Random, edges: list[int], width5) -> list[tuple[int, int]]:
    """Pairs (t, n) around each edge and at the band's exact limits; t multiples of 20 keep limits exact."""
    cases = []
    for edge in edges:
        for t in [*near(edge), edge - 20, edge + 20]:
            w = width5(t)
            if w % 5 == 0:
                for n in near(t + w // 5) + near(t - w // 5):
                    cases.append((t, n))
    for _ in range(1500):
        t = rng.randrange(0, 60 * S, 20) if rng.random() < 0.5 else rng.randrange(0, 60 * S)
        w = width5(t)
        if rng.random() < 0.5 and w % 5 == 0:
            n = t + rng.choice([1, -1]) * (w // 5) + rng.choice([-1, 0, 0, 1])
        else:
            n = t + rng.randrange(-w // 2 - 1, w // 2 + 2)
        cases.append((t, n))
    return cases


def macro_width5(t: int) -> int:
    return 10 * S if t < 10 * S else t if t <= 40 * S else 40 * S


def fat_width5(t: int) -> int:
    return 4 * S if t < 4 * S else t


def sodium_width5(t: int) -> int:
    return 750 * S if t < 500 * S else t


def percent_cases(rng: random.Random, low: int, high: int) -> list[tuple[int, int]]:
    """Pairs at exactly low % and high % of t, and next to them; t multiples of 20 keep them exact."""
    cases = []
    for _ in range(1200):
        t = rng.randrange(0, 2000 * S, 20)
        for n in near(t * low // 100) + near(t * high // 100):
            cases.append((t, n))
    return cases[:3000]


def within20_cases(rng: random.Random) -> list[tuple[int, int]]:
    cases = []
    for _ in range(1500):
        a = rng.randrange(0, 100 * S, 5)
        # b at exactly 20 % below or above the larger value, and next to it
        b_low = a - a // 5          # |a - b| = a / 5 = 0.2 * max
        cases += [(a, b) for b in near(b_low)]
        if (5 * a) % 4 == 0:
            b_high = a * 5 // 4     # |a - b| = b / 5 = 0.2 * max
            cases += [(a, b) for b in near(b_high)]
    return cases[:3000]


def mineral_cases(rng: random.Random, trace: int) -> list[tuple[int, int]]:
    cases = [(100_000, 300_000), (300_000, 100_000), (70_000, 210_000), (0, trace), (0, trace + 1)]
    for _ in range(1200):
        if rng.random() < 0.5:
            lo = rng.randrange(1, 500 * S)
        else:
            lo = rng.randrange(1, 10) * 10 ** rng.randrange(3, 7)  # one significant digit, e.g. 0.07 mg
        for hi in near(3 * lo):
            cases.append((lo, hi) if rng.random() < 0.5 else (hi, lo))
    for hi in near(trace):
        cases.append((0, hi))
    return cases[:3000]


def water_cases(rng: random.Random) -> list[tuple[int, int]]:
    cases = []
    for _ in range(1000):
        a = rng.randrange(0, 100 * S)
        cases += [(a, b) for b in near(a + 15 * S) + near(a - 15 * S)]
    return cases[:3000]


def available_cases(rng: random.Random) -> list[tuple[int, str, int]]:
    """(total, fibre status, fibre amount) with totals and fibres around zero and around each other."""
    cases = []
    for _ in range(600):
        t = rng.randrange(-100_000, 100 * S)
        for f in [rng.randrange(0, 40 * S), *near(t), 0]:
            cases.append((t, "measured", max(f, 0)))
        cases += [(t, "notApplicable", 0), (t, "trace", 0), (t, "noNumber", 0)]
    cases += [(t, "notApplicable", 0) for t in (-45_000, -26_667, -1, 0, 1)]
    return cases


# --- Python ------------------------------------------------------------------------------------------------

def dec(x: int) -> Decimal:
    return Decimal(x).scaleb(-6)


def python_available(total: int, status: str, amount: int) -> int | None:
    taco, g = Graph(), Graph()
    food, carb, fibre = ID["food/1"], ID["measurement/1/carbohydrate"], ID["measurement/1/dietary_fiber"]
    taco.add((carb, QUDT.numericValue, Literal(dec(total))))
    taco.add((carb, QUDT.unit, UNIT.GM))
    if status == "measured":
        taco.add((fibre, QUDT.numericValue, Literal(dec(amount))))
        taco.add((fibre, TACO.valueStatus, TACO.Measured))
    else:
        taco.add((fibre, TACO.valueStatus, {"notApplicable": TACO.NotApplicable, "trace": TACO.Trace,
                                            "noNumber": TACO.UnderReevaluation}[status]))
    nice.available_carbohydrate(g, taco, food, carb, fibre)
    node = ID["measurement/1/available_carbohydrate"]
    measure = g.value(node, nice.OM.hasValue)
    if measure is None:
        return None
    value = g.value(measure, nice.OM.hasNumericalValue).toPython()
    return int(Decimal(value).scaleb(6))


def tolerance(code: str, unit: str):
    return lambda t, n: compare.within_eu_tolerance(compare.CDNO + code, unit, t / S, n / S)


def disagrees(code: str, unit: str, name: str):
    return lambda a, b: name in pairs.disagreeing({code: (a / S, b / S, unit)})


RULES = {
    # name: (Lean expression, Python function)
    "withinMacro": ("withinMacro", tolerance("0200040", "g")),
    "withinFattyAcid": ("withinFattyAcid", tolerance("0200458", "g")),
    "withinSodium": ("withinSodium", tolerance("0200599", "mg")),
    "withinMineral": ("withinMineral", tolerance("0200544", "mg")),
    "withinVitamin": ("withinVitamin", tolerance("0200185", "mg")),
    "within20": ("within20", lambda t, n: compare.within_20_percent(t / S, n / S)),
    "waterDisagrees": ("waterDisagrees", disagrees(pairs.WATER, "g", "water")),
    "calciumDisagrees": ("mineralDisagrees (20 * S)", disagrees("0200544", "mg", "calcium")),
    "copperDisagrees": ("mineralDisagrees (100000)", disagrees("0200642", "mg", "copper")),
}


# --- Lean --------------------------------------------------------------------------------------------------

def lean_program(cases: dict[str, list[tuple[int, int]]], available: list[tuple[int, str, int]]) -> str:
    lines = [LEAN.read_text(encoding="utf-8"), "", "open TacoRules", ""]
    for name, rows in cases.items():
        expr = RULES[name][0]
        for i in range(0, len(rows), CHUNK):
            chunk = ", ".join(f"({t}, {n})" for t, n in rows[i:i + CHUNK])
            lines.append(f'#eval IO.println ("{name}:" ++ ",".intercalate (([{chunk}] : List (Prod Int Int))'
                         f".map (fun (p : Prod Int Int) => toString ({expr} p.1 p.2))))")
    for i in range(0, len(available), CHUNK):
        chunk = ", ".join(f"({t}, {fibre(status, f)})" for t, status, f in available[i:i + CHUNK])
        lines.append('#eval IO.println ("available:" ++ ",".intercalate (([' + chunk
                     + "] : List (Prod Int Fibre)).map (fun (p : Prod Int Fibre) => "
                     'match availableCarbohydrate p.1 p.2 with | some v => toString v | none => "none")))')
    return "\n".join(lines) + "\n"


def fibre(status: str, amount: int) -> str:
    return f"Fibre.measured ({amount})" if status == "measured" else f"Fibre.{status}"


def run_lean(program: str) -> dict[str, list[str]]:
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "Vectors.lean"
        path.write_text(program, encoding="utf-8")
        done = subprocess.run(["lean", str(path)], capture_output=True, text=True, encoding="utf-8")
    if done.returncode != 0:
        sys.exit(f"Lean failed:\n{done.stdout[-3000:]}\n{done.stderr[-3000:]}")
    out: dict[str, list[str]] = {}
    for line in done.stdout.splitlines():
        m = re.match(r"^(\w+):(.*)$", line)
        if m:
            out.setdefault(m.group(1), []).extend(m.group(2).split(","))
    return out


# --- main --------------------------------------------------------------------------------------------------

def main() -> int:
    rng = random.Random(20261116)
    cases = {
        "withinMacro": band_cases(rng, [10 * S, 40 * S], macro_width5),
        "withinFattyAcid": band_cases(rng, [4 * S], fat_width5),
        "withinSodium": band_cases(rng, [500 * S], sodium_width5),
        "withinMineral": percent_cases(rng, 65, 145),
        "withinVitamin": percent_cases(rng, 65, 150),
        "within20": within20_cases(rng),
        "waterDisagrees": water_cases(rng),
        "calciumDisagrees": mineral_cases(rng, 20 * S),
        "copperDisagrees": mineral_cases(rng, 100_000),
    }
    available = available_cases(rng)
    lean = run_lean(lean_program(cases, available))
    total_mismatches = 0
    print(f"{'rule':<18}{'cases':>7}{'agree':>8}{'differ':>8}")
    for name, rows in cases.items():
        expected = [v == "true" for v in lean[name]]
        assert len(expected) == len(rows), (name, len(expected), len(rows))
        python = [bool(RULES[name][1](t, n)) for t, n in rows]
        differ = [(r, e, p) for r, e, p in zip(rows, expected, python, strict=True) if e != p]
        total_mismatches += len(differ)
        print(f"{name:<18}{len(rows):>7}{len(rows) - len(differ):>8}{len(differ):>8}")
        kinds = Counter(f"Lean {e}, Python {p}" for _, e, p in differ)
        for kind, k in kinds.items():
            examples = [r for r, e, p in differ if f"Lean {e}, Python {p}" == kind][:3]
            shown = "; ".join(f"({a / S:g}, {b / S:g})" for a, b in examples)
            print(f"    {k} x {kind}, e.g. {shown}")
    expected_av = [None if v == "none" else int(v) for v in lean["available"]]
    python_av = [python_available(*c) for c in available]
    differ_av = [(c, e, p) for c, e, p in zip(available, expected_av, python_av, strict=True) if e != p]
    total_mismatches += len(differ_av)
    print(f"{'available':<18}{len(available):>7}{len(available) - len(differ_av):>8}{len(differ_av):>8}")
    for c, e, p in differ_av[:5]:
        print(f"    {c}: Lean {e}, Python {p}")
    print(f"\n{sum(map(len, cases.values())) + len(available)} cases, {total_mismatches} differ")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
