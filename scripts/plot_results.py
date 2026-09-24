from __future__ import annotations

import argparse
import math
import textwrap
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Patch, PathPatch
from matplotlib.path import Path as MPath

from taco_rdf.cli import load_graph
from taco_rdf.namespaces import ID, QUERIES_DIR, RDF, ROOT, SKOS, TACO
from taco_rdf.queries import run_query

SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK_SECONDARY = "#52514e"
MUTED = "#898781"
GRID = "#e1e0d9"
AXIS = "#c3c2b7"
SERIES = "#2a78d6"
STATUS_COLORS = ("#2a78d6", "#eb6834", "#1baf7a")

UNIT_SYMBOLS = {"GM": "g", "MilliGM": "mg", "MicroGM": "µg", "PERCENT": "%"}

NBSP = "\u00a0"

SOURCE = {
    "en": "Source: TACO 4th edition (NEPA-UNICAMP, 2011), taco-rdf RDF graph, SPARQL query {query}",
    "pt": "Fonte: TACO 4ª edição (NEPA-UNICAMP, 2011), grafo RDF taco-rdf, consulta SPARQL {query}",
}
TEXT = {
    "en": {
        "top_title": "The {n} foods richest in {nutrient}",
        "top_subtitle": "{first} leads with {value} {unit} per 100 g, {ratio}x the second. "
                        "Values in {unit} per 100 g of edible portion.",
        "range": "{mean} ({low} to {high})",
        "mean": "Group mean",
        "min_max": "Minimum to maximum across foods",
        "protein_title": "Protein by food group",
        "protein_subtitle": "Highest mean: {first} ({first_mean} g per 100 g). "
                            "Lowest: {last} ({last_mean} g). Label: mean (minimum to maximum). "
                            "In brackets after the name: foods with measured protein.",
        "status": ("Tr: trace (not zero)", "NA: not applicable", "*: under re-evaluation"),
        "status_title": "Not every TACO value is a number",
        "status_subtitle": "{first}: {n} of the {foods} foods ({pct}%) have Tr, not a value. "
                           "A plain CSV would turn every Tr into 0 and every NA into an empty cell. "
                           "Entries that are not numbers, for the {rows} nutrients with the most Tr.",
    },
    "pt": {
        "top_title": "Os {n} alimentos mais ricos em {nutrient}",
        "top_subtitle": "{first} lidera com {value} {unit} por 100 g, {ratio}x o segundo colocado. "
                        "Valores em {unit} por 100 g de parte comestível.",
        "range": "{mean} ({low} a {high})",
        "mean": "Média do grupo",
        "min_max": "Mínimo a máximo entre os alimentos",
        "protein_title": "Proteína por grupo de alimentos",
        "protein_subtitle": "Maior média: {first} ({first_mean} g por 100 g). Menor: {last} ({last_mean} g). "
                            "Rótulo: média (mínimo a máximo). Entre parênteses no nome: alimentos com "
                            "proteína medida.",
        "status": ("Tr: traço (não é zero)", "NA: não se aplica", "*: em reavaliação"),
        "status_title": "Nem todo valor da TACO é um número",
        "status_subtitle": "{first}: {n} dos {foods} alimentos ({pct}%) trazem Tr, não um valor. "
                           "Um CSV comum trocaria cada Tr por 0 e cada NA por célula vazia. "
                           "Medições que não são número, nos {rows} nutrientes com mais Tr.",
    },
}

plt.rcParams["font.family"] = ["Segoe UI", "DejaVu Sans"]


def fmt(value: float, lang: str, digits: int = 1) -> str:
    text = f"{value:.{digits}f}"
    return text.replace(".", ",") if lang == "pt" else text


def nice_step(top: float) -> int:
    for step in (1, 2, 5, 10, 20, 25, 50, 100, 200):
        if top / step <= 6:
            return step
    return 500


def label(g, node, lang: str) -> str:
    for obj in g.objects(node, SKOS.prefLabel):
        if getattr(obj, "language", None) == lang:
            return str(obj)
    return str(node).rsplit("/", 1)[-1]


def new_figure(width: float, height: float, top: float, bottom: float, left: float, right: float):
    fig = plt.figure(figsize=(width, height), dpi=150, facecolor=SURFACE)
    rect: tuple[float, float, float, float] = (
        left / width,
        bottom / height,
        (width - left - right) / width,
        (height - top - bottom) / height,
    )
    ax = fig.add_axes(rect, facecolor=SURFACE)  # type: ignore[reportUnknownMemberType]
    for side in ("top", "right", "bottom"):
        ax.spines[side].set_visible(False)
    ax.spines["left"].set_color(AXIS)
    ax.spines["left"].set_linewidth(1)
    ax.tick_params(axis="both", length=0, labelsize=9.5, labelcolor=MUTED)
    ax.set_yticks([])
    ax.set_axisbelow(True)
    ax.xaxis.grid(True, color=GRID, linewidth=0.8, linestyle="-")
    return fig, ax


def set_header(fig, title: str, subtitle: str, source: str, margin_in: float = 0.4) -> None:
    width, height = fig.get_size_inches()
    x = margin_in / width
    fig.text(x, 1 - 0.32 / height, title, fontsize=17, fontweight="bold", color=INK, ha="left", va="top")
    fig.text(x, 1 - 0.78 / height, textwrap.fill(subtitle, 120), fontsize=10.5, color=INK_SECONDARY,
             ha="left", va="top", linespacing=1.35)
    fig.text(x, 0.3 / height, source, fontsize=8.5, color=MUTED, ha="left", va="bottom")


def units_per_inch(ax) -> tuple[float, float]:
    fig_w, fig_h = ax.figure.get_size_inches()
    pos = ax.get_position()
    x_lo, x_hi = ax.get_xlim()
    y_lo, y_hi = ax.get_ylim()
    return (x_hi - x_lo) / (pos.width * fig_w), abs(y_hi - y_lo) / (pos.height * fig_h)


def rounded_bar(ax, y: float, value: float, thickness_pt: float = 15, radius_pt: float = 3,
                start: float = 0.0, color: str = SERIES, round_end: bool = True) -> None:
    if value <= start:
        return
    x_per_in, y_per_in = units_per_inch(ax)
    half = thickness_pt / 72 / 2 * y_per_in
    rx = min(radius_pt / 72 * x_per_in, value - start) if round_end else 0.0
    ry = radius_pt / 72 * y_per_in if round_end else 0.0
    top, bottom = y - half, y + half
    verts = [(start, top), (value - rx, top), (value, top), (value, top + ry), (value, bottom - ry),
             (value, bottom), (value - rx, bottom), (start, bottom), (start, top)]
    codes = [MPath.MOVETO, MPath.LINETO, MPath.CURVE3, MPath.CURVE3, MPath.LINETO,
             MPath.CURVE3, MPath.CURVE3, MPath.LINETO, MPath.CLOSEPOLY]
    ax.add_patch(PathPatch(MPath(verts, codes), fc=color, ec="none", zorder=2))


def row_labels(ax, labels: list[str], wrap: int, size: float = 10.5) -> None:
    transform = ax.get_yaxis_transform()
    for i, text in enumerate(labels):
        ax.text(-0.015, i, "\n".join(textwrap.wrap(text, wrap)), transform=transform, ha="right",
                va="center", fontsize=size, color=INK, linespacing=1.15)


def finish_axis(ax, count: int, top_value: float, xmax: float) -> None:
    step = nice_step(top_value)
    ticks = list(range(0, math.ceil(top_value / step) * step + 1, step))
    ax.set_xlim(0, xmax)
    ax.set_ylim(count - 0.5, -0.5)
    ax.set_xticks(ticks)


def plot_top_nutrient(g, key: str, output: Path, lang: str) -> None:
    _, rows = run_query(g, QUERIES_DIR / "richest_in.rq", {"key": key})
    names = [str(r[5] if lang == "en" and r[5] is not None else r[1]) for r in rows]
    values = [float(r[3]) for r in rows]
    unit = UNIT_SYMBOLS.get(str(rows[0][4]), str(rows[0][4]))
    nutrient = label(g, ID[f"nutrient/{key}"], lang).lower()
    text = TEXT[lang]

    fig, ax = new_figure(11, 6.6, top=1.45, bottom=0.85, left=3.3, right=0.6)
    finish_axis(ax, len(rows), values[0], values[0] * 1.16)
    for i, value in enumerate(values):
        rounded_bar(ax, i, value)
        ax.text(value + values[0] * 0.012, i, fmt(value, lang), ha="left", va="center", fontsize=10.5,
                color=INK, fontweight="bold", zorder=3)
    row_labels(ax, names, 38)

    ratio = values[0] / values[1]
    set_header(
        fig,
        text["top_title"].format(n=len(rows), nutrient=nutrient),
        text["top_subtitle"].format(first=names[0], value=fmt(values[0], lang), unit=unit,
                                    ratio=fmt(ratio, lang)),
        SOURCE[lang].format(query="richest_in"),
    )
    save(fig, output)


def plot_protein_by_group(g, output: Path, lang: str) -> None:
    query = (QUERIES_DIR / "group_protein_summary.rq").read_text(encoding="utf-8")
    if 'LANG(?group) = "en"' not in query:
        raise SystemExit("group_protein_summary.rq no longer filters groups by English label")
    rows = [tuple(r) for r in g.query(query.replace('LANG(?group) = "en"', f'LANG(?group) = "{lang}"'))]
    text = TEXT[lang]
    groups = [str(r[0]) for r in rows]
    foods = [int(r[1]) for r in rows]
    mean = [float(r[2]) for r in rows]
    low = [float(r[3]) for r in rows]
    high = [float(r[4]) for r in rows]

    fig, ax = new_figure(11, 8.8, top=1.8, bottom=0.85, left=3.3, right=0.6)
    top_value = max(high)
    finish_axis(ax, len(rows), top_value, math.ceil(top_value * 1.5 / 10) * 10)
    for i in range(len(rows)):
        rounded_bar(ax, i, mean[i])
        ax.plot([low[i], high[i]], [i, i], color=INK, linewidth=1.6, solid_capstyle="round", zorder=3)
        for x in (low[i], high[i]):
            ax.plot([x], [i], marker="o", markersize=6.5, markerfacecolor=INK,
                    markeredgecolor=SURFACE, markeredgewidth=1.5, linestyle="none", zorder=4,
                    clip_on=False)
        value_range = text["range"].format(mean=fmt(mean[i], lang), low=fmt(low[i], lang),
                                           high=fmt(high[i], lang))
        ax.text(high[i] + top_value * 0.03, i, value_range,
                ha="left", va="center", fontsize=9.5, color=INK_SECONDARY, zorder=3)
    row_labels(ax, [f"{name}{NBSP}({n})" for name, n in zip(groups, foods, strict=True)], 36, size=10)

    width, height = fig.get_size_inches()
    handles = [
        Patch(fc=SERIES, ec="none", label=text["mean"]),
        Line2D([0], [0], color=INK, linewidth=1.6, marker="o", markersize=6.5, label=text["min_max"]),
    ]
    fig.legend(handles=handles, loc="lower left", bbox_to_anchor=(0.4 / width, 1 - 1.5 / height),
               ncol=2, frameon=False, fontsize=10, labelcolor=INK_SECONDARY, handlelength=1.6)

    set_header(
        fig,
        text["protein_title"],
        text["protein_subtitle"].format(first=groups[0], first_mean=fmt(mean[0], lang), last=groups[-1],
                                        last_mean=fmt(mean[-1], lang)),
        SOURCE[lang].format(query="group_protein_summary"),
    )
    save(fig, output)


def plot_value_status(g, output: Path, lang: str) -> None:
    query = (QUERIES_DIR / "value_status_summary.rq").read_text(encoding="utf-8")
    if 'LANG(?nutrient) = "en"' not in query:
        raise SystemExit("value_status_summary.rq no longer filters nutrients by English label")
    rows = [tuple(r) for r in g.query(query.replace('LANG(?nutrient) = "en"',
                                                    f'LANG(?nutrient) = "{lang}"'))]
    text = TEXT[lang]
    names = [str(r[0]) for r in rows]
    counts = [tuple(int(v) for v in r[1:4]) for r in rows]
    totals = [sum(c) for c in counts]
    food_count = sum(1 for _ in g.subjects(RDF.type, TACO.Food))

    fig, ax = new_figure(11, 7.4, top=1.8, bottom=0.85, left=3.3, right=0.6)
    finish_axis(ax, len(rows), max(totals), max(totals) * 1.55)
    x_per_in, _ = units_per_inch(ax)
    gap = 1.5 / 72 * x_per_in
    for i, parts in enumerate(counts):
        drawn = [(v, c) for v, c in zip(parts, STATUS_COLORS, strict=True) if v > 0]
        cum = 0.0
        for j, (v, color) in enumerate(drawn):
            first, last = j == 0, j == len(drawn) - 1
            a = cum + (0 if first or v <= gap else gap / 2)
            b = cum + v - (0 if last or v <= gap else gap / 2)
            rounded_bar(ax, i, b, start=a, color=color, round_end=last)
            cum += v
        labels = [f"{v} {tag}" for v, tag in zip(parts, ("Tr", "NA", "*"), strict=True) if v > 0]
        ax.text(totals[i] + max(totals) * 0.015, i, ", ".join(labels), ha="left", va="center",
                fontsize=9.5, color=INK_SECONDARY, zorder=3)
    row_labels(ax, names, 38)

    width, height = fig.get_size_inches()
    status_labels = text["status"]
    handles = [Patch(fc=color, ec="none", label=label)
               for color, label in zip(STATUS_COLORS, status_labels, strict=True)]
    fig.legend(handles=handles, loc="lower left", bbox_to_anchor=(0.4 / width, 1 - 1.5 / height),
               ncol=3, frameon=False, fontsize=10, labelcolor=INK_SECONDARY, handlelength=1.6)

    pct = round(100 * counts[0][0] / food_count)
    set_header(
        fig,
        text["status_title"],
        text["status_subtitle"].format(first=names[0], n=counts[0][0], foods=food_count, pct=pct,
                                       rows=len(rows)),
        SOURCE[lang].format(query="value_status_summary"),
    )
    save(fig, output)


def save(fig, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output, dpi=150, facecolor=SURFACE)
    plt.close(fig)
    print(f"wrote {output}")


def main() -> int:
    p = argparse.ArgumentParser(description="Plot results of the SPARQL queries over the TACO graph.")
    p.add_argument("--nutrient", default="iron", help="nutrient key for the top-10 chart (skos:notation)")
    p.add_argument("--outdir", default=str(ROOT / "docs"))
    p.add_argument("--lang", choices=sorted(TEXT), default="en", help="language of the charts")
    args = p.parse_args()
    out = Path(args.outdir)
    g = load_graph()
    plot_top_nutrient(g, args.nutrient, out / f"chart-{args.nutrient}-top10.png", args.lang)
    plot_protein_by_group(g, out / "chart-protein-by-group.png", args.lang)
    plot_value_status(g, out / "chart-value-status.png", args.lang)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
