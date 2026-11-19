# ruff: noqa: E501, RUF001
"""Build docs/taco-in-nice-food: four images of the knowledge graph, a PDF overview and the files shared.

Images are drawn as SVG and rendered to PNG, and the overview printed to PDF, by Microsoft Edge in headless
mode. The CDNO classes in use are read from the nicefood Fuseki dataset. The shared files are copies of the
project's files without comments; the copy of the TACO subgraph is ignored by git, as build/ is.

    $env:PYTHONPATH = "src"; python scripts/build_taco_in_nice_food.py
"""

from __future__ import annotations

import argparse
import csv
import shutil
import subprocess
import tempfile
import textwrap
from html import escape
from pathlib import Path

from rdflib import Graph, Literal, URIRef

from taco_rdf import sparql
from taco_rdf.namespaces import FIO, ID, OBO, OM, RDF, RDFS, ROOT, SKOS

REPO = ROOT
OUT = ROOT / "docs" / "taco-in-nice-food"
ENDPOINT = sparql.endpoint()
EDGE = ""
CDNO_CLASSES = sparql.prefixes("fio", "dcterms", "rdfs") + """
SELECT ?cdno (SAMPLE(STR(?l)) AS ?label)
  (COUNT(DISTINCT IF(?t = "TACO", ?f, ?none)) AS ?taco_foods) (COUNT(DISTINCT IF(?t = "NEVO", ?f, ?none)) AS ?nevo_foods)
  (GROUP_CONCAT(DISTINCT IF(?t = "TACO", ?code, ""); separator=" ") AS ?taco_codes)
  (GROUP_CONCAT(DISTINCT IF(?t = "NEVO", ?code, ""); separator=" ") AS ?nevo_codes)
WHERE {
  ?f dcterms:isVersionOf ?src ; fio:hasNutritionalValue ?nv .
  ?nv a ?cdno ; fio:hasNutrient ?n . FILTER STRSTARTS(STR(?cdno), "http://purl.obolibrary.org/obo/CDNO_")
  BIND (IF(CONTAINS(STR(?src), "rivm"), "NEVO", "TACO") AS ?t)
  BIND (REPLACE(STR(?n), "^.*[#/]", "") AS ?code)
  OPTIONAL { ?cdno rdfs:label ?l }
} GROUP BY ?cdno
"""


def edge_path() -> str:
    """Microsoft Edge, as Windows registers it."""
    import winreg  # Windows only; imported here so that the rest of the module loads elsewhere

    key = r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\msedge.exe"
    with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key) as k:
        return winreg.QueryValue(k, None)


def cdno_rows(endpoint: str) -> list[list[str]]:
    """The CDNO classes values in the store are typed with, and the foods and codes of each table."""
    rows = []
    for b in sparql.select(CDNO_CLASSES, endpoint):
        label = b["label"].removeprefix("concentration of ").removesuffix(" in material entity")
        rows.append([b["cdno"].rsplit("/", 1)[-1], label, b["taco_foods"], b["nevo_foods"],
                     " ".join(sorted(b["taco_codes"].split())), " ".join(sorted(b["nevo_codes"].split()))])
    both = lambda r: int(r[2]) > 0 and int(r[3]) > 0  # noqa: E731
    return sorted(rows, key=lambda r: (not both(r), r[1]))

STYLE = """<style>
.n{fill:#ffffff;stroke:#c9d3d0;stroke-width:1.2}.k{fill:#e0f0ec;stroke:#0b6e63;stroke-width:1.4}
.t{font:600 13px 'Segoe UI',Arial,sans-serif;fill:#17201e}.s{font:400 11px Consolas,'Courier New',monospace;fill:#56635f}
.l{font:400 11px 'Segoe UI',Arial,sans-serif;fill:#56635f}.lk{font:600 11px 'Segoe UI',Arial,sans-serif;fill:#0b6e63}
.h{font:600 12px 'Segoe UI',Arial,sans-serif;fill:#56635f;letter-spacing:.06em}
.e{stroke:#17201e;stroke-width:1.3;fill:none}.ek{stroke:#0b6e63;stroke-width:2;fill:none}.d{stroke-dasharray:6 4}
.m{fill:#17201e}.mk{fill:#0b6e63}
</style>
<defs><marker id="a" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path class="m" d="M0,0 L10,5 L0,10 z"/></marker>
<marker id="ak" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path class="mk" d="M0,0 L10,5 L0,10 z"/></marker></defs>
<rect width="100%" height="100%" fill="#ffffff"/>"""


def svg(w, h, body, label):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}" role="img" '
            f'aria-label="{label}">{STYLE}{body}</svg>')


def box(x, y, w, h, title, sub, cls="n"):
    cx = x + w / 2
    lines = textwrap.wrap(str(title), width=max(18, int(w / 7))) or [""]
    title_y = y + h / 2 - 4 - 6 * (len(lines) - 1)
    title_svg = "".join(f'<tspan x="{cx}" y="{title_y + i * 12}">{escape(line)}</tspan>'
                        for i, line in enumerate(lines))
    return (f'<rect class="{cls}" x="{x}" y="{y}" width="{w}" height="{h}" rx="5"/>'
            f'<text class="t" text-anchor="middle" style="font-size:11px">{title_svg}</text>'
            f'<text class="s" x="{cx}" y="{y + h / 2 + 14}" text-anchor="middle">{escape(str(sub))}</text>')


def arrow(x1, y1, x2, y2, key=False, dash=False):
    cls = ("ek" if key else "e") + (" d" if dash else "")
    return f'<line class="{cls}" x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" marker-end="url(#{"ak" if key else "a"})"/>'


def label(x, y, text, key=False, anchor="middle"):
    return f'<text class="{"lk" if key else "l"}" x="{x}" y="{y}" text-anchor="{anchor}">{escape(str(text))}</text>'


# Figure 1: the pattern
f1 = "".join([
    box(20, 30, 160, 56, "Source table", "TACO or NEVO page"), box(300, 30, 180, 56, "Food item", "fio:FoodItem"),
    box(600, 30, 180, 56, "FoodOn class", "food class IRI", "k"), box(900, 30, 160, 56, "FoodOn superclass", "parent class IRI"),
    arrow(300, 58, 183, 58), label(241, 50, "dcterms:isVersionOf"), arrow(480, 58, 597, 58, True), label(539, 50, "rdf:type", True),
    arrow(780, 58, 897, 58), label(839, 50, "rdfs:subClassOf"), label(690, 104, "pairs foods across tables", True),
    arrow(390, 86, 390, 167), label(398, 131, "fio:hasNutritionalValue", anchor="start"),
    box(20, 170, 160, 56, "Nutrient code", "nevonut:PROT"), box(300, 170, 180, 56, "Nutritional value", "fio:NutritionalValue"),
    box(600, 170, 180, 56, "CDNO class", "CDNO_0200040", "k"), box(900, 170, 160, 56, "CDNO superclass", "CDNO_0200001"),
    arrow(300, 198, 183, 198), label(241, 190, "fio:hasNutrient"), arrow(480, 198, 597, 198, True), label(539, 190, "rdf:type", True),
    arrow(780, 198, 897, 198), label(839, 190, "rdfs:subClassOf"), label(690, 244, "pairs values across tables", True),
    arrow(390, 226, 390, 307), label(398, 271, "om:hasValue", anchor="start"),
    arrow(300, 220, 184, 309, dash=True), label(208, 258, "taco:valueStatus,", anchor="end"), label(208, 271, "instead of a measure", anchor="end"),
    box(20, 310, 160, 56, "Trace, not applicable", "no number, no zero"), box(300, 310, 180, 56, "Measure", "om:Measure"),
    box(600, 310, 180, 56, "22.17 g per 100 g", "om:gramPerHectogram"),
    arrow(480, 338, 597, 338), label(539, 318, "om:hasNumericalValue"), label(539, 330, "om:hasUnit"),
])
FIG1 = svg(1080, 390, f1, "The NICE-Food pattern as TACO-RDF writes it")

def food_figure(source: Graph, module: Graph, number: int = 574) -> str:
    """Draw the current export's food, values and a path of asserted FoodOn superclass edges."""
    food = ID[f"food/{number}"]
    names = sorted(str(n) for n in source.objects(food, SKOS.prefLabel) if n.language == "pt")
    types = sorted(t for t in source.objects(food, RDF.type) if str(t).startswith(str(OBO) + "FOODON_"))
    if len(types) != 1 or not names:
        raise ValueError(f"food {number} needs one FoodOn type and a Portuguese name")
    chain = [types[0]]
    while len(chain) < 3:
        parents = sorted(t for t in module.objects(chain[-1], RDFS.subClassOf)
                         if isinstance(t, URIRef) and str(t).startswith(str(OBO) + "FOODON_")
                         and t not in chain)
        if not parents:
            break
        chain.append(parents[0])
    parts = [box(20, 170, 200, 64, names[0], f"TACO food {number}"),
             '<polyline class="ek" points="120,170 120,48 297,48" marker-end="url(#ak)"/>',
             label(210, 40, "rdf:type", True)]
    for i, cls in enumerate(chain):
        labels = sorted(str(n) for n in module.objects(cls, RDFS.label))
        parts.append(box(300 + i * 260, 20, 230, 56, labels[0] if labels else cls.rsplit("/", 1)[-1],
                         cls.rsplit("/", 1)[-1], "k" if i == 0 else "n"))
        if i:
            parts += [arrow(270 + i * 260, 48, 297 + i * 260, 48),
                      label(285 + i * 260, 90, "subClassOf")]
    nodes = {str(v).rsplit("/", 1)[-1]: v for v in source.objects(food, FIO.hasNutritionalValue)}

    def value(key):
        node = nodes[key]
        measure = source.value(node, OM.hasValue)
        number_value = source.value(measure, OM.hasNumericalValue)
        units = sorted(str(u) for u in source.objects(measure, OM.hasUnit) if isinstance(u, Literal))
        classes = sorted(str(c).rsplit("/", 1)[-1] for c in source.objects(node, RDF.type)
                         if str(c).startswith(str(OBO) + "CDNO_"))
        nutrient = str(source.value(node, FIO.hasNutrient)).replace("#", "/").rsplit("/", 1)[-1]
        if number_value is None or not units or len(classes) != 1:
            raise ValueError(f"food {number}, {key}: missing number, unit or CDNO class")
        return f"{number_value.toPython():.2f}", units[0], f"{classes[0]} · {nutrient}"

    parts += ['<polyline class="e" points="220,202 260,202"/><line class="e" x1="260" y1="138" x2="260" y2="298"/>',
              label(240, 100, "fio:hasNutritionalValue", anchor="start")]
    for i, (key, title) in enumerate((("protein", "Protein"), ("carbohydrate", "Carbohydrate"),
                                     ("dietary_fiber", "Dietary fibre"))):
        number_text, unit, description = value(key)
        parts += [arrow(260, 138 + 80 * i, 297, 138 + 80 * i),
                  box(300, 110 + 80 * i, 260, 56, f"{title} {number_text} {unit}", description)]
    available, unit, description = value("available_carbohydrate")
    parts += [box(680, 222, 300, 74, f"Available carbohydrate {available} {unit}", description, "k"),
              label(830, 317, "Total minus fibre; values rounded for display"),
              arrow(680, 244, 563, 220, True, True), arrow(680, 276, 563, 298, True, True),
              label(621, 214, "prov:wasDerivedFrom", True),
              '<polyline class="e" points="120,234 120,380 830,380 830,299" marker-end="url(#a)"/>',
              label(475, 372, "fio:hasNutritionalValue")]
    return svg(1080, 400, "".join(parts), f"TACO food {number}, read from the current export and FoodOn module")

# Figure 3: CDNO classes that link TACO and NEVO values
ROWS = [("Umidade (moisture)", "water", "CDNO_0200002", "WATER"), ("Proteína (protein)", "protein", "CDNO_0200040", "PROT"),
        ("Fibra alimentar (fibre)", "dietary fibre", "CDNO_0200035", "FIBT"), ("Cinzas (ash)", "ash", "CDNO_0200004", "ASH"),
        ("Colesterol", "cholesterol", "CDNO_0200123", "CHORL"), ("Cálcio", "dietary calcium", "CDNO_0200544", "CA"),
        ("Ferro", "dietary iron", "CDNO_0200651", "FE"), ("Potássio", "dietary potassium", "CDNO_0200592", "K"),
        ("Zinco", "dietary zinc", "CDNO_0200670", "ZN"), ("Riboflavina", "riboflavin", "CDNO_0200185", "RIBF"),
        ("Vitamina C", "vitamin C", "CDNO_0200192", "VITC"), ("Ácidos graxos saturados", "saturated fatty acid", "CDNO_0200458", "FASAT")]
parts = ['<text class="h" x="150" y="34" text-anchor="middle">TACO VALUE</text>',
         '<text class="h" x="520" y="34" text-anchor="middle">CDNO CLASS</text>',
         '<text class="h" x="860" y="34" text-anchor="middle">NEVO VALUE</text>']
for i, (taco, cdno, cid, nevo) in enumerate(ROWS):
    y = 50 + i * 48
    parts += [f'<rect class="n" x="20" y="{y}" width="260" height="38" rx="5"/><text class="t" x="150" y="{y + 24}" text-anchor="middle">{taco}</text>',
              f'<rect class="k" x="370" y="{y}" width="300" height="38" rx="5"/><text class="t" x="460" y="{y + 24}" text-anchor="middle">{cdno}</text>'
              f'<text class="s" x="600" y="{y + 24}" text-anchor="middle">{cid}</text>',
              f'<rect class="n" x="760" y="{y}" width="200" height="38" rx="5"/><text class="s" x="860" y="{y + 24}" text-anchor="middle">nevonut:{nevo}</text>',
              arrow(280, y + 19, 367, y + 19, True), arrow(760, y + 19, 673, y + 19, True)]
h3 = 50 + len(ROWS) * 48 + 36
parts += [label(325, 46, "rdf:type", True), label(715, 46, "rdf:type", True),
          f'<text class="l" x="490" y="{h3 - 14}" text-anchor="middle">Examples of shared CDNO classes; the complete current counts are in cdno_classes_used.csv</text>']
FIG3 = svg(980, h3, "".join(parts), "CDNO classes that type both TACO and NEVO values")

# Figure 4: what was compared
STEPS = [("Pair foods", "same FoodOn class", ["match asserted food types", "hierarchy comparison:", "one subclass step apart", "reported separately"]),
         ("Pair values", "same CDNO class and unit", ["match nutrient definitions", "available carbohydrate:", "TACO total − fibre vs NEVO"]),
         ("One value per food", "median of its NEVO foods", ["each TACO food counts", "once, however broad", "its FoodOn class"]),
         ("Agreement", "rank, ratio, bands", ["Spearman's rho, TACO/NEVO", "ratio, within 20 %", "current counts and results:", "comparison report"])]
parts = []
for i, (title, key, lines) in enumerate(STEPS):
    x = 20 + i * 265
    parts += [f'<rect class="{"k" if i < 2 else "n"}" x="{x}" y="20" width="225" height="150" rx="5"/>',
              f'<text class="t" x="{x + 16}" y="48">{i + 1}. {title}</text>', f'<text class="lk" x="{x + 16}" y="68">{key}</text>']
    parts += [f'<text class="l" x="{x + 16}" y="{98 + j * 18}">{line}</text>' for j, line in enumerate(lines)]
    if i < 3:
        parts.append(arrow(x + 227, 95, x + 263, 95))
FIG4 = svg(1080, 190, "".join(parts), "How TACO and NEVO values were compared")

FIGS = {"1_graph_pattern": (FIG1, 1080, 390),
        "3_cdno_classes_shared": (FIG3, 980, h3), "4_what_was_compared": (FIG4, 1080, 190)}

DOC = """<!doctype html><html lang="en"><head><meta charset="utf-8"><title>TACO in NICE-Food</title><style>
@page { size: A4; margin: 16mm 15mm; }
body { font: 10.5pt/1.5 'Segoe UI', Arial, sans-serif; color: #17201e; }
h1 { font-size: 21pt; margin: 0 0 4pt; } h2 { font-size: 13.5pt; margin: 18pt 0 6pt; color: #0b6e63; }
p, li { margin: 0 0 6pt; } .meta { color: #56635f; font-size: 9pt; } code { font: 9pt Consolas, monospace; }
img { width: 100%; margin: 6pt 0 2pt; } .cap { color: #56635f; font-size: 9pt; margin-bottom: 10pt; }
table { border-collapse: collapse; width: 100%; font-size: 9.5pt; margin: 4pt 0 8pt; }
th, td { border-bottom: 1px solid #d3dcd9; padding: 4pt 6pt; text-align: left; vertical-align: top; }
th { color: #56635f; font-weight: 600; } .num { text-align: right; } .pb { page-break-before: always; }
</style></head><body>
<h1>TACO in NICE-Food</h1>
<p class="meta">How the TACO-RDF knowledge graph was built, the ontologies it uses and why, and what was compared with NEVO. Vitória Maia, November 2026.</p>
<p>TACO, the Brazilian food composition table (NEPA-UNICAMP, 4th edition, 2011), is written as a knowledge graph in NICE-Food's own pattern: 597 foods and 21,720 values. All 597 food classifications were reviewed by Josandra Semedo and Elizabete Wensel, with adjudication by Crislane Timbo, and applied on 19 November 2026. Loaded beside NEVO and FoodOn, NICE-Food's own query <code>protein_groups.rq</code> runs unchanged. Current query counts are in the accompanying subgraph report.</p>

<h2>Ontologies and vocabularies, and why</h2>
<table><tr><th>Vocabulary</th><th>Used for</th><th>Why</th></tr>
<tr><td>FIO</td><td>Food items, nutritional values, nutrients</td><td>NICE-Food's own pattern for NEVO, so TACO loads beside NEVO and NICE-Food's queries read it unchanged.</td></tr>
<tr><td>FoodOn</td><td>What kind of food each item is (<code>rdf:type</code>)</td><td>Pairs a TACO food with NEVO foods of the same class; its hierarchy pairs classes one step apart. All 597 foods carry a reviewed class; the decisions use 469 distinct classes.</td></tr>
<tr><td>CDNO</td><td>What each value is a concentration of (<code>rdf:type</code>)</td><td>Pairs values across tables whatever each table calls its nutrients. Each class is defined as a concentration (PATO) of a ChEBI entity.</td></tr>
<tr><td>OM</td><td>Units</td><td>NICE-Food's unit vocabulary: g and mg per 100 g, with the unit also as a string.</td></tr>
<tr><td>PROV-O</td><td>Derived values</td><td>Available carbohydrate is calculated, so it points to the values it comes from.</td></tr>
<tr><td>DCTERMS, SKOS</td><td>Source table; food names</td><td><code>dcterms:isVersionOf</code> tells the tables apart in one store; <code>skos:prefLabel</code> gives Portuguese and English names.</td></tr></table>
<p>Foods and values are linked to FoodOn and CDNO with <code>rdf:type</code>, as NICE-Food links NEVO's, not with SKOS mappings: a food item is an instance of a food class, not a SKOS concept.</p>

<h2>The graph</h2>
<img src="images/1_graph_pattern.svg"><p class="cap">Figure 1. Every value hangs on two links: the FoodOn class of its food and its own CDNO class. A trace or a not-applicable cell keeps TACO's status instead of a measure, because a trace is not zero.</p>
<img src="images/2_one_food_red_beans.svg"><p class="cap">Figure 2. One food through the graph. TACO publishes total carbohydrate, fibre included; the graph keeps it and adds available carbohydrate, total minus fibre, linked with <code>prov:wasDerivedFrom</code> to the two values it comes from.</p>

<h2 class="pb">CDNO: what makes the two tables comparable</h2>
<p>A value typed with a CDNO class says what it is a concentration of, independently of the table's own nutrient codes. TACO's values use 54 CDNO classes and NEVO's 75; 33 classes type values of both, and those are the classes the comparison pairs values by.</p>
<img src="images/3_cdno_classes_shared.svg"><p class="cap">Figure 3. CDNO classes that type both TACO and NEVO values. Where TACO and NEVO report the same component, TACO's values also name NEVO's code (<code>nevonut:PROT</code>), so NICE-Food's queries find them. The list of all 96 classes in use is in <code>cdno/cdno_classes_used.csv</code>.</p>
<p>A query can choose protein by its CDNO class (<code>CDNO_0200040</code>) instead of NEVO's nutrient code. This permits a table to retain its own nutrient codes while participating in the query. The original and CDNO queries are included, with current counts in the subgraph report.</p>

<h2>What was compared</h2>
<img src="images/4_what_was_compared.svg"><p class="cap">Figure 4. TACO and NEVO foods are paired by FoodOn class and their values by CDNO class and unit; each TACO food then counts once, against the median of its NEVO foods.</p>
<p>The comparison is regenerated after the completed classification review. Current counts, rank correlations and ratio distributions are in <code>comparison/taco_nevo_comparison.md</code>. Shared class membership permits comparison but does not establish nutritional equivalence.</p>

<h2>How it was checked</h2>
<ul><li>SHACL shapes for the NICE-Food pattern, run with two engines (Jena and pySHACL) with the same result: no duplicate values, one nutrient per value.</li>
<li>The exported values against TACO's printed PDF: 6,259 values of 569 foods, all identical.</li>
<li>Automated regression tests and independent verification compare all 597 decisions against original review evidence, RDF exports and preserved nutritional triples. Lean 4 checks resolution rules and concrete certificates; deliberate incorrect inputs test error detection. See the accompanying review verification report.</li></ul>

<h2>Files</h2>
<table><tr><th>File</th><th>What it is</th></tr>
<tr><td><code>knowledge-graph/taco_nice_food.ttl</code></td><td>TACO's subgraph in NICE-Food's pattern (Turtle). TACO may be reproduced with the source cited.</td></tr>
<tr><td><code>ontology/</code></td><td>TACO-RDF's vocabulary and the CDNO and FoodOn modules it uses</td></tr>
<tr><td><code>cdno/</code></td><td>The 96 CDNO classes in use, with foods per table; TACO's 67 nutrients and their NEVO codes</td></tr>
<tr><td><code>queries/</code></td><td>NICE-Food's query, its CDNO version, and the comparison queries</td></tr>
<tr><td><code>comparison/</code></td><td>The TACO × NEVO comparison by nutrient (counts and statistics only)</td></tr>
<tr><td><code>scripts/taco_to_nice_food.py</code></td><td>The script that writes the subgraph</td></tr></table>
</body></html>"""

FILES = {
    "review/application.json": "data/alignment/review/round-1/application.json",
    "review/verification.json": "build/verification/review_application/result.json",
    "review/verification.md": "verification/README.md",
    "review/reviewed-types.csv": "data/alignment/review/round-1/reviewed-types.csv",
    "knowledge-graph/taco_nice_food.ttl": "build/taco_nice_food.ttl",
    "ontology/taco.ttl": "ontology/taco.ttl",
    "ontology/cdno-module.ttl": "ontology/imports/cdno-module.ttl",
    "ontology/foodon-module.ttl": "ontology/imports/foodon-module.ttl",
    "cdno/taco_nevo_nutrients.csv": "data/alignment/taco_nevo_nutrients.csv",
    "queries/protein_groups.rq": "queries/nice-food/protein_groups.rq",
    "queries/protein_groups_cdno.rq": "queries/nice-food/protein_groups_cdno.rq",
    "queries/one_taco_food.rq": "queries/nice-food/one_taco_food.rq",
    "queries/taco_nevo_same_foodon_class.rq": "queries/nevo/taco_nevo_same_foodon_class.rq",
    "queries/taco_nevo_available_carbohydrate.rq": "queries/nevo/taco_nevo_available_carbohydrate.rq",
    "comparison/taco_nevo_comparison.md": "analysis/taco_nevo_comparison.md",
    "comparison/taco_nice_food.md": "analysis/taco_nice_food.md",
    "scripts/taco_to_nice_food.py": "scripts/taco_to_nice_food.py",
    "scripts/taco_rdf/nice_food.py": "src/taco_rdf/nice_food.py",
    "scripts/taco_rdf/namespaces.py": "src/taco_rdf/namespaces.py",
}


def strip_python(text):
    """Python source without comments and docstrings; checked to have the same syntax tree otherwise."""
    import ast
    import io
    import tokenize
    tree = ast.parse(text)
    doc_lines = set()
    for node in [tree, *ast.walk(tree)]:
        body = getattr(node, "body", None)
        if isinstance(body, list) and body and isinstance(body[0], ast.Expr) \
                and isinstance(body[0].value, ast.Constant) and isinstance(body[0].value.value, str):
            doc_lines.update(range(body[0].lineno, body[0].end_lineno + 1))
    comments = {}
    for tok in tokenize.generate_tokens(io.StringIO(text).readline):
        if tok.type == tokenize.COMMENT:
            comments[tok.start[0]] = tok.start[1]
    out = []
    for i, line in enumerate(text.splitlines(), start=1):
        if i in doc_lines:
            continue
        if i in comments:
            line = line[:comments[i]].rstrip()
            if not line.strip():
                continue
        out.append(line.rstrip())
    cleaned = []
    for line in out:
        if line == "" and cleaned and cleaned[-1] == "":
            continue
        cleaned.append(line)
    result = "\n".join(cleaned).strip("\n") + "\n"

    def shape(t):
        tree = ast.parse(t)
        for node in ast.walk(tree):
            body = getattr(node, "body", None)
            if isinstance(body, list) and body and isinstance(body[0], ast.Expr) \
                    and isinstance(body[0].value, ast.Constant) and isinstance(body[0].value.value, str):
                node.body = body[1:] or [ast.Pass()]
        return ast.dump(tree)
    assert shape(result) == shape(text), "stripping changed the code"
    return result


def strip_hash_lines(text):
    """SPARQL or Turtle without whole-line # comments (a # inside an IRI is kept)."""
    lines = [line for line in text.splitlines() if not line.lstrip().startswith("#")]
    cleaned = []
    for line in lines:
        if line.strip() == "" and cleaned and cleaned[-1].strip() == "":
            continue
        cleaned.append(line.rstrip())
    return "\n".join(cleaned).strip("\n") + "\n"


def copy_without_comments(source, target):
    text = source.read_text(encoding="utf-8")
    if source.suffix == ".py":
        text = strip_python(text)
    elif source.suffix == ".rq":
        text = strip_hash_lines(text)
        from rdflib.plugins.sparql import prepareQuery
        prepareQuery(text)
    elif source.suffix == ".ttl":
        stripped = strip_hash_lines(text)
        from rdflib import Graph
        from rdflib.compare import isomorphic
        assert isomorphic(Graph().parse(data=text, format="turtle"), Graph().parse(data=stripped, format="turtle")), source
        text = stripped
    target.write_text(text, encoding="utf-8", newline="\n")


def edge(*args):
    with tempfile.TemporaryDirectory() as profile:
        subprocess.run([EDGE, "--headless=new", "--disable-gpu", "--hide-scrollbars", "--no-first-run",
                        f"--user-data-dir={profile}", *args], check=True, timeout=120)


def main() -> int:
    global OUT, EDGE
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--out", type=Path, default=OUT, help=f"folder to write (default {OUT})")
    p.add_argument("--endpoint", default=ENDPOINT, help=f"SPARQL endpoint (default {ENDPOINT})")
    args = p.parse_args()
    OUT, EDGE = args.out.resolve(), edge_path()
    rows = cdno_rows(args.endpoint)
    if OUT.exists():
        shutil.rmtree(OUT)
    (OUT / "images").mkdir(parents=True)
    source = Graph().parse(REPO / "build/taco_nice_food.ttl")
    module = Graph().parse(REPO / "ontology/imports/foodon-module.ttl")
    figures = {**FIGS, "2_one_food_red_beans": (food_figure(source, module), 1080, 400)}
    for name, (text, w, h) in figures.items():
        svg_path = OUT / "images" / f"{name}.svg"
        svg_path.write_text(text, encoding="utf-8")
        edge("--force-device-scale-factor=2", "--default-background-color=FFFFFFFF", f"--window-size={w},{h}",
             f"--screenshot={OUT / 'images' / (name + '.png')}", svg_path.as_uri())
    doc = OUT / "TACO_in_NICE-Food.html"
    doc.write_text(DOC, encoding="utf-8")
    edge("--no-pdf-header-footer", "--print-to-pdf-no-header", f"--print-to-pdf={OUT / 'TACO_in_NICE-Food.pdf'}",
         doc.as_uri())
    doc.unlink()
    files = OUT / "files"
    from example_food_rdf import VALUES, example
    example_graph = example(source, ID["food/574"], VALUES)
    (files / "knowledge-graph").mkdir(parents=True)
    example_graph.serialize(files / "knowledge-graph/example_food_574.ttl", format="turtle")
    (files / "cdno").mkdir(parents=True)
    with (files / "cdno" / "cdno_classes_used.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(["cdno_class", "label", "taco_foods", "nevo_foods", "taco_nutrient_codes", "nevo_nutrient_codes"])
        w.writerows(rows)
    for target, source in FILES.items():
        (files / target).parent.mkdir(parents=True, exist_ok=True)
        if Path(source).suffix in (".py", ".rq", ".ttl"):
            copy_without_comments(REPO / source, files / target)
        else:
            shutil.copyfile(REPO / source, files / target)
    for path in sorted(OUT.rglob("*")):
        if path.is_file():
            print(f"{path.relative_to(OUT)}  {path.stat().st_size // 1024} KB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
