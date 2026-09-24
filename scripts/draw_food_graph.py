from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch, Patch
from rdflib import Graph, Literal

from taco_rdf.cli import load_graph
from taco_rdf.namespaces import ID, OBO, QUDT, RDF, RDFS, ROOT, SKOS, TACO

DEFAULT_NUTRIENTS = "protein,moisture,calcium,niacin,cholesterol"
UNIT_SYMBOLS = {"GM": "g", "MilliGM": "mg", "MicroGM": "µg", "PERCENT": "%"}
MATCH_PREDICATES = (SKOS.closeMatch, SKOS.exactMatch, SKOS.relatedMatch, SKOS.narrowMatch, SKOS.broadMatch)

FILL = {
    "food": "#cfe0f5",
    "group": "#c9ebe5",
    "nutrient": "#e2d5f0",
    "category": "#efe8f7",
    "external": "#fde3c8",
    "Measured": "#d3ecd7",
    "Trace": "#fbe6b5",
    "NotApplicable": "#e0e0e0",
    "UnderReevaluation": "#f6cccc",
}

COL_FOOD, COL_MEASUREMENT, COL_NUTRIENT, COL_CATEGORY, COL_EXTERNAL = 0.0, 5.6, 11.0, 15.8, 20.2

TEXT = {
    "en": {
        "title": "TACO as an RDF graph", "food": "Food", "group": "Group", "measured": "Measured",
        "Measured": "Measurement: measured value", "Trace": "Measurement: trace (Tr)",
        "NotApplicable": "Measurement: not applicable (NA)", "trace_value": "Trace (not zero)",
        "nutrient": "Nutrient", "category": "Nutrient category",
        "external": "External ontology (FoodOn, ChEBI)",
        "caption": "Each box is an RDF resource and each arrow is a triple (subject, predicate, object).",
    },
    "pt": {
        "title": "TACO como grafo RDF", "food": "Alimento", "group": "Grupo", "measured": "Medido",
        "Measured": "Medição: valor medido", "Trace": "Medição: traço (Tr)",
        "NotApplicable": "Medição: não se aplica (NA)", "trace_value": "Traço (não é zero)",
        "nutrient": "Nutriente", "category": "Categoria de nutriente",
        "external": "Ontologia externa (FoodOn, ChEBI)",
        "caption": "Cada caixa é um recurso RDF e cada seta é uma tripla (sujeito, predicado, objeto).",
    },
}


@dataclass
class Box:
    x: float
    y: float
    w: float
    h: float
    title: str
    subtitle: str
    fill: str
    dashed: bool = False


def short(iri) -> str:
    text = str(iri)
    for base, prefix in ((str(ID), "tacoid:"), (str(OBO), "obo:")):
        if text.startswith(base):
            return prefix + text[len(base):]
    return text


def label(g: Graph, node, lang: str) -> str:
    for pred in (SKOS.prefLabel, RDFS.label):
        for obj in g.objects(node, pred):
            if isinstance(obj, Literal) and obj.language == lang:
                return str(obj)
    return short(node).rsplit("/", 1)[-1]


def predicate_name(g: Graph, pred) -> str:
    return g.namespace_manager.normalizeUri(pred)


def external_match(g: Graph, node, prefix: str):
    for pred in MATCH_PREDICATES:
        for obj in sorted(g.objects(node, pred)):
            if str(obj).startswith(str(OBO) + prefix):
                return pred, obj
    return None


def measurement_text(g: Graph, m, lang: str) -> tuple[str, str]:
    status = str(next(g.objects(m, TACO.valueStatus))).split("#")[-1]
    if status == "Measured":
        value = float(next(g.objects(m, QUDT.numericValue)))
        unit = str(next(g.objects(m, QUDT.unit))).rsplit("/", 1)[-1]
        return status, f"{TEXT[lang]['measured']}: {value:.2f} {UNIT_SYMBOLS.get(unit, unit)}"
    if status == "Trace":
        return status, TEXT[lang]["trace_value"]
    return status, status


def boundary(a: Box, b: Box) -> tuple[float, float]:
    dx, dy = b.x - a.x, b.y - a.y
    sx = (a.w / 2) / abs(dx) if dx else float("inf")
    sy = (a.h / 2) / abs(dy) if dy else float("inf")
    s = min(sx, sy)
    return a.x + dx * s, a.y + dy * s


def draw_box(ax, box: Box) -> None:
    ax.add_patch(FancyBboxPatch(
        (box.x - box.w / 2, box.y - box.h / 2), box.w, box.h,
        boxstyle="round,pad=0.02,rounding_size=0.18",
        fc=box.fill, ec="#444444", lw=1.2, ls="--" if box.dashed else "-", zorder=2,
    ))
    ax.text(box.x, box.y + 0.15, box.title, ha="center", va="center",
            fontsize=10.5, fontweight="bold", zorder=3)
    ax.text(box.x, box.y - 0.22, box.subtitle, ha="center", va="center",
            fontsize=8, color="#444444", family="monospace", zorder=3)


def draw_edge(ax, a: Box, b: Box, text: str) -> None:
    start, end = boundary(a, b), boundary(b, a)
    ax.add_patch(FancyArrowPatch(start, end, arrowstyle="-|>", mutation_scale=14,
                                 lw=1.3, color="#555555", zorder=1))
    ax.text((start[0] + end[0]) / 2, (start[1] + end[1]) / 2, text, ha="center", va="center",
            fontsize=8, color="#222222",
            bbox=dict(boxstyle="round,pad=0.15", fc="white", ec="none"), zorder=4)


def build(g: Graph, food_number: int, keys: list[str], lang: str):
    food = ID[f"food/{food_number}"]
    if (food, RDF.type, TACO.Food) not in g:
        raise SystemExit(f"food {food_number} not found in the graph")

    boxes: list[Box] = []
    edges: list[tuple[Box, Box, str]] = []
    food_box = Box(COL_FOOD, 0.0, 3.2, 1.05, label(g, food, lang), short(food), FILL["food"])
    boxes.append(food_box)

    group = next(g.objects(food, TACO.inGroup), None)
    if group is not None:
        group_box = Box(COL_FOOD, 3.2, 3.2, 1.05, label(g, group, lang), short(group), FILL["group"])
        boxes.append(group_box)
        edges.append((food_box, group_box, predicate_name(g, TACO.inGroup)))
        match = external_match(g, group, "FOODON_")
        if match:
            pred, target = match
            ext = Box(COL_FOOD, 6.0, 3.6, 1.05, "FoodOn", short(target), FILL["external"], dashed=True)
            boxes.append(ext)
            edges.append((group_box, ext, predicate_name(g, pred)))

    present = [k for k in keys if (ID[f"measurement/{food_number}/{k}"], TACO.ofFood, food) in g]
    for k in keys:
        if k not in present:
            print(f"# no measurement of {k} for food {food_number}, skipped", file=sys.stderr)

    first_seen: dict = {}
    for k in present:
        first_seen.setdefault(next(g.objects(ID[f"nutrient/{k}"], SKOS.broader), None), len(first_seen))
    present.sort(key=lambda k: first_seen[next(g.objects(ID[f"nutrient/{k}"], SKOS.broader), None)])

    ys = [(len(present) - 1) - 2.0 * i for i in range(len(present))]
    slots = [ys[0] + 1.0 - 2.0 * i for i in range(len(ys) + 1)] if ys else []
    categories: dict = {}
    for key, y in zip(present, ys, strict=True):
        m, nutrient = ID[f"measurement/{food_number}/{key}"], ID[f"nutrient/{key}"]
        status, text = measurement_text(g, m, lang)
        m_box = Box(COL_MEASUREMENT, y, 3.4, 1.05, text, short(m), FILL[status])
        n_box = Box(COL_NUTRIENT, y, 2.8, 1.05, label(g, nutrient, lang), short(nutrient), FILL["nutrient"])
        boxes += [m_box, n_box]
        edges.append((m_box, food_box, predicate_name(g, TACO.ofFood)))
        edges.append((m_box, n_box, predicate_name(g, TACO.ofNutrient)))
        for cat in g.objects(nutrient, SKOS.broader):
            categories.setdefault(cat, []).append(n_box)
        match = external_match(g, nutrient, "CHEBI_")
        if match:
            pred, target = match
            ext = Box(COL_EXTERNAL, y, 3.0, 1.05, "ChEBI", short(target), FILL["external"], dashed=True)
            boxes.append(ext)
            edges.append((n_box, ext, predicate_name(g, pred)))

    for cat, members in sorted(categories.items(), key=lambda kv: -sum(b.y for b in kv[1]) / len(kv[1])):
        mean = sum(b.y for b in members) / len(members)
        y = min(slots, key=lambda s: (abs(s - mean), -s))
        slots.remove(y)
        c_box = Box(COL_CATEGORY, y, 3.0, 1.05, label(g, cat, lang), short(cat), FILL["category"])
        boxes.append(c_box)
        for n_box in members:
            edges.append((n_box, c_box, predicate_name(g, SKOS.broader)))

    return food, boxes, edges


def render(g: Graph, food_number: int, keys: list[str], output: Path, lang: str = "en") -> None:
    words = TEXT[lang]
    food, boxes, edges = build(g, food_number, keys, lang)

    fig, ax = plt.subplots(figsize=(22, 10.5))
    ax.set_xlim(-3.0, 23.0)
    ax.set_ylim(-6.2, 7.6)
    ax.axis("off")

    for a, b, text in edges:
        draw_edge(ax, a, b, text)
    for box in boxes:
        draw_box(ax, box)

    ax.set_title(f"{words['title']}: {label(g, food, lang)} ({short(food)})",
                 fontsize=16, fontweight="bold", loc="left")
    handles = [
        Patch(fc=FILL["food"], ec="#444444", label=words["food"]),
        Patch(fc=FILL["group"], ec="#444444", label=words["group"]),
        Patch(fc=FILL["Measured"], ec="#444444", label=words["Measured"]),
        Patch(fc=FILL["Trace"], ec="#444444", label=words["Trace"]),
        Patch(fc=FILL["NotApplicable"], ec="#444444", label=words["NotApplicable"]),
        Patch(fc=FILL["nutrient"], ec="#444444", label=words["nutrient"]),
        Patch(fc=FILL["category"], ec="#444444", label=words["category"]),
        Patch(fc=FILL["external"], ec="#444444", ls="--", label=words["external"]),
    ]
    ax.legend(handles=handles, loc="lower left", fontsize=9, ncol=2, frameon=True)
    fig.text(0.01, 0.01, words["caption"], fontsize=10, color="#333333")

    output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output, dpi=150, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"wrote {output}")


def main() -> int:
    p = argparse.ArgumentParser(description="Draw the RDF neighbourhood of one TACO food.")
    p.add_argument("--food", type=int, default=1)
    p.add_argument("--nutrients", default=DEFAULT_NUTRIENTS)
    p.add_argument("-o", "--output", default=str(ROOT / "docs" / "food-graph.png"))
    p.add_argument("--lang", choices=sorted(TEXT), default="en", help="language of the figure")
    args = p.parse_args()
    keys = [k.strip() for k in args.nutrients.split(",")]
    render(load_graph(), args.food, keys, Path(args.output), args.lang)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
