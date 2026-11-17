"""Agreement between TACO and NEVO values of paired foods, by kind of pair.

As in scripts/compare_taco_nevo.py, each TACO food counts once, against the median of the NEVO foods paired
with it, because a broad FoodOn class can pair one TACO food with many NEVO foods. Spearman's rho says whether
the two tables rank the foods alike; the TACO/NEVO ratio, over values above zero, how far apart they lie.
Like NICE-Food's functions/analysis_helper.py, this keeps the statistics out of the notebook.
"""

from __future__ import annotations

import statistics

import pandas as pd


def values_by_food(values: pd.DataFrame, dataset: str) -> dict[str, float]:
    """One dataset's values from values_in_cdno_class.rq, by food."""
    rows = values[values.dataset == dataset]
    return dict(zip(rows.food, rows.value.astype(float), strict=True))


def paired_agreement(pairs: pd.DataFrame, food: str, value: str, other: str) -> dict[str, object]:
    """Agreement of one table's values (column value, per food in column food) with another's (column other).

    For the rows of a pair query such as tbca_nevo_candidate_class.rq: each food of the first table counts
    once, against the median of the values paired with it. Same reading as agreement below.
    """
    foods: dict[str, tuple[float, list[float]]] = {}
    for f, v, o in zip(pairs[food], pairs[value].astype(float), pairs[other].astype(float), strict=True):
        foods.setdefault(f, (v, []))[1].append(o)
    values = [(v, statistics.median(o)) for v, o in foods.values()]
    ratios = [a / b for a, b in values if a > 0 and b > 0]
    row: dict[str, object] = {"value pairs": len(pairs), "foods": len(values)}
    a, b = zip(*values, strict=True) if values else ((), ())
    if len(values) > 2 and len(set(a)) > 1 and len(set(b)) > 1:  # rho is undefined for constant values
        row["Spearman"] = round(statistics.correlation(a, b, method="ranked"), 2)
    if len(ratios) >= 4:
        q1, q2, q3 = statistics.quantiles(ratios, n=4)
        row["ratio median"] = round(q2, 2)
        row["ratio quartiles"] = f"{q1:.2f} to {q3:.2f}"
    return row


def identical_share(pairs: pd.DataFrame, value: str, other: str, tolerance: float = 0.005) -> float:
    """The share of value pairs that are the same within a relative tolerance, e.g. values copied over."""
    a, b = pairs[value].astype(float), pairs[other].astype(float)
    return float(((a - b).abs() <= tolerance * a.abs().clip(lower=0.01)).mean())


def agreement(pairs: pd.DataFrame, taco: dict[str, float], nevo: dict[str, float]) -> pd.DataFrame:
    """For each kind of pair (the relation column): TACO foods with a value on both sides, rho and ratios."""
    rows = []
    for relation, group in pairs.groupby("relation"):
        foods: dict[str, list[float]] = {}
        for taco_food, nevo_food in zip(group.taco_food, group.nevo_food, strict=True):
            if taco_food in taco and nevo_food in nevo:
                foods.setdefault(taco_food, []).append(nevo[nevo_food])
        values = [(taco[food], statistics.median(nevo_values)) for food, nevo_values in foods.items()]
        ratios = [t / n for t, n in values if t > 0 and n > 0]
        row: dict[str, object] = {"relation": relation, "food pairs": len(group), "TACO foods": len(values)}
        t, n = zip(*values, strict=True) if values else ((), ())
        if len(values) > 2 and len(set(t)) > 1 and len(set(n)) > 1:  # rho is undefined for constant values
            row["Spearman"] = round(statistics.correlation(t, n, method="ranked"), 2)
        if len(ratios) >= 4:
            q1, q2, q3 = statistics.quantiles(ratios, n=4)
            row["TACO/NEVO median"] = round(q2, 2)
            row["TACO/NEVO quartiles"] = f"{q1:.2f} to {q3:.2f}"
        rows.append(row)
    return pd.DataFrame(rows)
