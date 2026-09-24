"""Helpers for protein_sources.ipynb: running the queries, reading preparations, drawing the figures."""

from __future__ import annotations

import re
from collections import deque
from decimal import Decimal
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.ticker import MaxNLocator
from rdflib import Graph, URIRef
from rdflib.namespace import RDFS

from taco_rdf.queries import run_query

HERE = Path(__file__).resolve().parent
QUERIES = HERE / "queries"
DATA = HERE / "data"
FIGURES = HERE / "figures"


def select(g: Graph, name: str, folder: Path = QUERIES, **bindings: str) -> pd.DataFrame:
    """Run <folder>/<name>.rq and return the rows as a DataFrame of plain Python values."""
    header, rows = run_query(g, folder / f"{name}.rq", bindings)
    values = [[None if v is None else v.toPython() for v in row] for row in rows]
    frame = pd.DataFrame(values, columns=header)
    for column in frame.columns:
        present = frame[column].dropna()
        if len(present) and present.map(lambda v: isinstance(v, (int, float, Decimal))).all():
            frame[column] = pd.to_numeric(frame[column])
    return frame


STATES_PT = {
    "raw": r"\bcru(?:a|s|as)?\b",
    "cooked": r"(?<!pré-)\bcozid[oa]s?\b",
    "precooked": r"\bpré-cozid[oa]s?\b",
    "grilled": r"\bgrelhad[oa]s?\b",
    "roasted": r"\bassad[oa]s?\b|\btorrad[oa]s?\b",
    "fried": r"\bfrit[oa]s?\b",
    "breaded": r"\bà milanesa\b|\bcom farinha de trigo\b|\bempanad[oa]s?\b",
    "sauteed": r"\brefogad[oa]s?\b",
    "steamed": r"\bno vapor\b",
    "salted": r"(?<!biscoito, )\bsalgad[oa]s?\b|\bcharque\b",
    "dried": r"\bsec[oa]s?\b|\bdesidratad[oa]s?\b|\bcharque\b",
    "frozen": r"\bcongelad[oa]s?\b",
    "canned": r"\benlatad[oa]s?\b|\bem conserva\b|\bconserva em\b",
    "smoked": r"\bdefumad[oa]s?\b",
}
STATES_EN = {
    "raw": r"\braw\b",
    "cooked": r"\bcooked\b|\bboiled\b|\bsimmered\b|\bstewed\b",
    "precooked": r"\bprecooked\b|\bpar-?cooked\b",
    "grilled": r"\bgrilled\b|\bbroiled\b|\bbarbe(?:que|cue)d?\b",
    "roasted": r"\broasted\b|\bbaked\b|\broast cooked\b|\btoast\b",
    "fried": r"\bfried\b",
    "breaded": r"\bbreaded\b",
    "sauteed": r"\bsaut[eé]ed\b",
    "steamed": r"\bsteamed\b",
    "salted": r"\bsalted\b|\bsalt pork\b|\bcorned\b",
    "dried": r"\bdried\b|\bdehydrated\b|\bjerky\b",
    "frozen": r"\bfrozen\b",
    "canned": r"\bcanned\b|\btinned\b|\bin oil\b",
    "smoked": r"\bsmoked\b",
}
SPECIFIC_COOKING = {"grilled", "roasted", "fried", "sauteed", "steamed", "precooked"}


def states(text: str | None, patterns: dict[str, str]) -> frozenset[str]:
    if not isinstance(text, str):
        return frozenset()
    text = text.lower()
    found = {state for state, pattern in patterns.items() if re.search(pattern, text)}
    if found & SPECIFIC_COOKING:
        found.discard("cooked")
    return frozenset(found)


def compare_preparation(taco: frozenset[str], foodon: frozenset[str], linked: bool) -> str:
    """Lexical triage of the preparation words in the name and the class label; not a semantic check."""
    if not linked:
        return "no FoodOn link"
    if not taco:
        return "no preparation word in the name"
    if taco == foodon:
        return "same words"
    if not foodon:
        return "no preparation word in the label"
    generalised = {"cooked" if s in SPECIFIC_COOKING else s for s in taco}
    if foodon == generalised:
        return "label says only cooked"
    if foodon < taco:
        return "some words missing"
    return "different words"


def superclass_path(g: Graph, start: URIRef, goal: URIRef) -> list[URIRef] | None:
    """The shortest rdfs:subClassOf chain from start up to goal, or None when goal is not above start."""
    previous: dict[URIRef, URIRef | None] = {start: None}
    queue = deque([start])
    while queue:
        node = queue.popleft()
        if node == goal:
            path = []
            while node is not None:
                path.append(node)
                node = previous[node]
            return path[::-1]
        for parent in g.objects(node, RDFS.subClassOf):
            if isinstance(parent, URIRef) and parent not in previous:
                previous[parent] = node
                queue.append(parent)
    return None


def stacked_barh(counts: pd.DataFrame, colors: dict[str, str], title: str, path: Path,
                 xlabel: str = "foods") -> None:
    """One horizontal bar per row of ``counts``, stacked by its columns in the order of ``colors``."""
    counts = counts.reindex(columns=[c for c in colors if c in counts.columns], fill_value=0)
    fig, ax = plt.subplots(figsize=(9, 0.45 * len(counts) + 1.6), dpi=120)
    left = pd.Series(0, index=counts.index, dtype=float)
    for column in counts.columns:
        ax.barh(counts.index, counts[column], left=left, color=colors[column], label=column, height=0.7)
        left += counts[column]
    ax.invert_yaxis()
    ax.xaxis.set_major_locator(MaxNLocator(integer=True))
    ax.set_xlabel(xlabel)
    ax.set_title(title, loc="left", fontsize=12)
    ax.spines[["top", "right"]].set_visible(False)
    ax.legend(ncol=min(len(counts.columns), 3), frameon=False, loc="upper left", bbox_to_anchor=(0, -0.12))
    fig.tight_layout()
    FIGURES.mkdir(exist_ok=True)
    fig.savefig(path, bbox_inches="tight", metadata={"Date": None})
    plt.show()
