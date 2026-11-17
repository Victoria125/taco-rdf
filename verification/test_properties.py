"""Property-based tests (Hypothesis) of the NICE-Food export and of the agreement statistics.

Hypothesis generates random TACO foods and value pairs, and each test states something that must hold for all
of them. When one fails, Hypothesis shrinks it to a smallest failing example.

- scripts/taco_to_nice_food.py keeps every TACO value: one nutritional value per measurement, its number
  unchanged, its status, its CDNO classes, NEVO's code exactly where the alignment file gives one, and
  available carbohydrate as carbohydrate minus fibre (zero below zero).
- analysis/comparison_helper.py computes Spearman's rho and the ratio quartiles as SciPy and NumPy do.

Hypothesis and SciPy are not dependencies of the project; install them where Python finds them, e.g.
    pip install --target <folder> hypothesis scipy;  $env:PYTHONPATH = "src;<folder>"
    python -m pytest verification/test_properties.py
"""

from __future__ import annotations

import csv
import importlib.util
import math
from decimal import Decimal

import numpy as np
import pandas as pd
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from rdflib import RDF, Graph, Literal
from scipy import stats

from taco_rdf.namespaces import ID, OBO, QUDT, ROOT, TACO, UNIT
from taco_rdf.nutrients import BY_KEY


def load(path):
    spec = importlib.util.spec_from_file_location(path.stem, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


nice = load(ROOT / "scripts" / "taco_to_nice_food.py")
helper = load(ROOT / "analysis" / "comparison_helper.py")
with nice.NUTRIENTS.open(encoding="utf-8", newline="") as fh:
    CODES = {r["taco_nutrient"]: r["nevo_code"] for r in csv.DictReader(fh) if r["nevo_code"]}

UNITS = [UNIT.GM, UNIT.PERCENT, UNIT.MilliGM, UNIT.MicroGM, UNIT.KiloCAL, UNIT.KiloJ]
STATUSES = [TACO.NotApplicable, TACO.Trace, TACO.UnderReevaluation]
CDNO_CLASSES = [OBO.CDNO_0200040, OBO.CDNO_0200005, OBO.CDNO_0200035, OBO.CDNO_0200544]
amounts = st.decimals(min_value=Decimal("-0.1"), max_value=Decimal("1000"), places=6, allow_nan=False)
measurement = st.one_of(
    st.tuples(st.just("number"), amounts, st.sampled_from(UNITS)),
    st.tuples(st.just("status"), st.sampled_from(STATUSES), st.none()),
)
classes = st.sets(st.sampled_from(CDNO_CLASSES), max_size=2)
food = st.dictionaries(st.sampled_from(sorted(BY_KEY)), st.tuples(measurement, classes),
                       min_size=1, max_size=12)


def taco_graph(foods: list[dict]) -> Graph:
    g = Graph()
    for i, nutrients in enumerate(foods, start=1):
        f = ID[f"food/{i}"]
        g.add((f, RDF.type, TACO.Food))
        g.add((f, TACO.foodNumber, Literal(i)))
        for key, ((kind, value, unit), classes) in nutrients.items():
            m = ID[f"measurement/{i}/{key}"]
            g.add((m, RDF.type, TACO.NutrientMeasurement))
            g.add((m, TACO.ofFood, f))
            g.add((m, TACO.ofNutrient, ID[f"nutrient/{key}"]))
            for c in classes:
                g.add((m, RDF.type, c))
            if kind == "number":
                g.add((m, QUDT.numericValue, Literal(value)))
                g.add((m, QUDT.unit, unit))
                g.add((m, TACO.valueStatus, TACO.Measured))
            else:
                g.add((m, TACO.valueStatus, value))
    return g


@settings(max_examples=300, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(st.lists(food, min_size=1, max_size=3))
def test_the_export_keeps_every_value_its_number_status_classes_and_code(foods):
    out, counts = nice.export(taco_graph(foods), CODES)
    for i, nutrients in enumerate(foods, start=1):
        f = ID[f"food/{i}"]
        for key, ((kind, value, unit), classes) in nutrients.items():
            m = ID[f"measurement/{i}/{key}"]
            assert (f, nice.FIO.hasNutritionalValue, m) in out
            assert set(out.objects(m, nice.FIO.hasNutrient)) == {
                nice.NEVONUT[CODES[key]] if key in CODES else ID[f"nutrient/{key}"]}
            assert {c for c in out.objects(m, RDF.type) if "CDNO_" in str(c)} == classes
            measure = out.value(m, nice.OM.hasValue)
            if kind == "number":
                assert out.value(measure, nice.OM.hasNumericalValue).toPython() == value
                om_unit, text = nice.UNITS[unit]
                units = set(out.objects(measure, nice.OM.hasUnit))
                assert Literal(text, datatype=nice.XSD.string) in units
                assert (om_unit in units) if om_unit is not None else len(units) == 1
            else:
                assert measure is None
                assert out.value(m, TACO.valueStatus) == value
    measured = sum(len(n) for n in foods)
    derived = sum(1 for v in out.subjects(RDF.type, nice.FIO.NutritionalValue)
                  if str(v).endswith("/available_carbohydrate"))
    assert counts["values"] == measured
    assert len(set(out.subjects(RDF.type, nice.FIO.NutritionalValue))) == measured + derived


@settings(max_examples=300, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(food)
def test_available_carbohydrate_is_carbohydrate_minus_fibre_or_zero(nutrients):
    out, _ = nice.export(taco_graph([nutrients]), CODES)
    node = ID["measurement/1/available_carbohydrate"]
    carb = nutrients.get("carbohydrate")
    fibre = nutrients.get("dietary_fiber")
    expected = None
    if carb is not None and carb[0][0] == "number":
        total = carb[0][1]
        if fibre is not None and fibre[0][0] == "number":
            expected = max(Decimal(0), total - fibre[0][1])
        elif fibre is not None and fibre[0][1] in (TACO.NotApplicable, TACO.Trace):
            expected = max(Decimal(0), total)
    measure = out.value(node, nice.OM.hasValue)
    if expected is None:
        assert measure is None
    else:
        assert out.value(measure, nice.OM.hasNumericalValue).toPython() == expected
        assert (node, nice.FIO.hasNutrient, nice.NEVONUT.CHO) in out


values = st.lists(st.tuples(st.integers(1, 40), st.integers(0, 50), st.integers(0, 50)),
                  min_size=3, max_size=60)
# Values all the same on one side, for which rho is undefined: random values above rarely produce them.
constant_values = st.integers(0, 50).flatmap(lambda c: st.lists(
    st.tuples(st.integers(1, 40), st.just(c), st.integers(0, 50)), min_size=3, max_size=30))


@settings(max_examples=200, deadline=None)
@given(constant_values)
def test_constant_values_give_no_spearman_instead_of_an_error(rows):
    pairs = pd.DataFrame(rows, columns=["food", "value", "other"]).astype({"value": float, "other": float})
    pairs["food"] = pairs["food"].astype(str)
    assert "Spearman" not in helper.paired_agreement(pairs, "food", "value", "other")
    pairs["relation"] = "same class"
    taco = dict.fromkeys(pairs.food, float(rows[0][1]))
    nevo = {f: v for f, v in zip(pairs.food, pairs.other, strict=True)}
    pairs = pairs.assign(taco_food=pairs.food, nevo_food=pairs.food)
    assert "Spearman" not in helper.agreement(pairs, taco, nevo).iloc[0].to_dict()


@settings(max_examples=500, deadline=None)
@given(values)
def test_spearman_and_quartiles_agree_with_scipy_and_numpy(rows):
    pairs = pd.DataFrame(rows, columns=["food", "value", "other"]).astype({"value": float, "other": float})
    pairs["food"] = pairs["food"].astype(str)
    foods: dict[str, tuple[float, list[float]]] = {}
    for f, v, o in zip(pairs.food, pairs.value, pairs.other, strict=True):
        foods.setdefault(f, (v, []))[1].append(o)
    a = [v for v, _ in foods.values()]
    b = [float(np.median(o)) for _, o in foods.values()]
    constant = len(set(a)) < 2 or len(set(b)) < 2
    row = helper.paired_agreement(pairs, "food", "value", "other")
    if len(foods) > 2 and not constant:
        rho = stats.spearmanr(a, b).statistic
        assert math.isclose(row["Spearman"], round(float(rho), 2), abs_tol=0.0100001)
    else:
        assert "Spearman" not in row
    ratios = [x / y for x, y in zip(a, b, strict=True) if x > 0 and y > 0]
    if len(ratios) >= 4:
        # statistics.quantiles' default ("exclusive") is NumPy's "weibull" method. The helper prints two
        # decimals, and a quartile that is exactly x.xx5 can round either way after a last-bit difference.
        q1, q2, q3 = np.percentile(ratios, [25, 50, 75], method="weibull")
        low, high = (float(x) for x in row["ratio quartiles"].split(" to "))
        for printed, exact in ((row["ratio median"], q2), (low, q1), (high, q3)):
            assert abs(printed - float(exact)) <= 0.005 + 1e-9
