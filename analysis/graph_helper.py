"""Draw the subgraph around one FoodOn class, from the edges queries/nevo/taco_nevo_food_graph.rq returns.

NICE-Food's analysis makes its figures with networkx and matplotlib (rivm-syso/nicekg_analysis).
edges_to_graph turns the query's rows into a networkx graph, one node per food, class or value;
draw_food_graph draws it in rows, one colour per kind of node, so the NICE-Food pattern shows: foods typed
with a FoodOn class, values typed with a CDNO class.
"""

from __future__ import annotations

import textwrap

import matplotlib.pyplot as plt
import networkx as nx
import pandas as pd

COLOURS = {"TACO food": "#2a9d8f", "NEVO food": "#e76f51", "FoodOn class": "#457b9d", "CDNO class": "#8e7dbe",
           "value": "#cfcfcf"}
ROWS = {"TACO food": 2, "NEVO food": 2, "value": 3, "CDNO class": 4}
NODE_SIZE = 2400


def node_label(label: str, kind: str) -> str:
    if kind == "value":
        try:
            return f"{float(label):.3g}"
        except ValueError:
            return label
    return label


def edges_to_graph(edges: pd.DataFrame) -> nx.DiGraph:
    """A directed graph with each node's label and kind and each edge's relation.

    A food's name comes with its rdf:type edge; its value edges carry only the IRI, which a name replaces.
    """
    g = nx.DiGraph()
    for e in edges.itertuples(index=False):
        for node, label, kind in ((e.s, e.source_label, e.s_kind), (e.o, e.target_label, e.o_kind)):
            if g.nodes.get(node, {}).get("label") in (None, node):
                g.add_node(node, label=node_label(label, kind), kind=kind)
        g.add_edge(e.s, e.o, relation=e.p)
    return g


def row(g: nx.DiGraph, node: str) -> int:
    """The row a node is drawn in: superclasses, the FoodOn class, foods, values, then the CDNO class."""
    kind = g.nodes[node]["kind"]
    if kind == "FoodOn class":
        return 1 if any(g.edges[u, node]["relation"] == "rdf:type" for u in g.predecessors(node)) else 0
    return ROWS[kind]


def layered_positions(g: nx.DiGraph) -> dict[str, tuple[float, float]]:
    """Rows from top to bottom; TACO foods come first among the foods, and each value sits under its food."""
    rows: dict[int, list[str]] = {}
    for node in sorted(g, key=lambda n: (g.nodes[n]["kind"] != "TACO food", g.nodes[n]["label"])):
        rows.setdefault(row(g, node), []).append(node)
    foods = rows.get(2, [])

    def food_position(value: str) -> int:
        return min((foods.index(u) for u in g.predecessors(value) if u in foods), default=len(foods))

    rows[3] = sorted(rows.get(3, []), key=food_position)
    return {node: ((i + 1) / (len(nodes) + 1), -r)
            for r, nodes in rows.items() for i, node in enumerate(nodes)}


def draw_food_graph(g: nx.DiGraph, ax: plt.Axes | None = None, width: int = 18) -> plt.Axes:
    """Draw the graph in rows by kind of node, one colour per kind and the relation on each edge."""
    ax = ax or plt.gca()
    pos = layered_positions(g)
    kinds = nx.get_node_attributes(g, "kind")
    for kind, colour in COLOURS.items():
        nodes = [n for n, k in kinds.items() if k == kind]
        if nodes:
            nx.draw_networkx_nodes(g, pos, nodelist=nodes, node_color=colour, node_size=NODE_SIZE, ax=ax,
                                   label=kind)
    nx.draw_networkx_edges(g, pos, ax=ax, arrowstyle="-|>", arrowsize=12, edge_color="#8a8a8a",
                           node_size=NODE_SIZE)
    labels = {n: textwrap.fill(d["label"], width) for n, d in g.nodes(data=True)}
    nx.draw_networkx_labels(g, pos, labels=labels, font_size=7, ax=ax,
                            bbox={"facecolor": "white", "edgecolor": "none", "alpha": 0.8, "pad": 1})
    nx.draw_networkx_edge_labels(g, pos, edge_labels=nx.get_edge_attributes(g, "relation"), font_size=6,
                                 font_color="#555555", ax=ax)
    ax.legend(fontsize=8, loc="upper left", bbox_to_anchor=(1.0, 1.0), markerscale=0.3, frameon=False)
    ax.margins(x=0.08, y=0.12)
    ax.axis("off")
    return ax
