# ruff: noqa: E501, RUF001
"""For each TACO nutrient that takes a NEVO code in TACO's NICE-Food export, whether TACO's value and NEVO's are
the same quantity; and which of TACO's own nutrients could take a NEVO code.

A shared nutrient code says that two tables measure the same thing. That holds when both give the same element
or compound, in the same unit, as the same kind of number. It does not hold when one table calculates a value
another way: TACO's carbohydrate is calculated by difference, NEVO's is the sum of sugars and starch. This script
puts together:

- what TACO declares for each nutrient: its INFOODS tagname (TACO, 4th edition, Quadro 6, PDF pages 20-21) and
  its method (pages 16-18), transcribed here and checked against the PDF by
  verification/nutrient_definitions_check.py;
- tests on the data, run on both tables: whether available carbohydrate is the sum of sugars and starch, whether
  energy follows the general EU factors, whether protein comes from nitrogen with one factor or with factors per
  food, whether retinol equivalents follow the same carotenoid rule, and whether fatty acids are per 100 g of food;
- the unit each table gives, and whether NEVO has values under the code at all.

It writes analysis/nutrient_definitions.md and analysis/data/nutrient_definitions.csv. Only counts and shares of
NEVO's values are written, never a value. The data are read from Fuseki's nicefood dataset (triplestore/README.md);
verification/nutrient_definitions_check.py reads them again from the files with rdflib.

    $env:PYTHONPATH = "src"; python scripts/nutrient_definitions.py
"""

from __future__ import annotations

import argparse
import csv
import statistics
import sys
from collections import defaultdict
from collections.abc import Callable, Iterable

from rdflib import Graph, Literal, URIRef

from taco_rdf import sparql
from taco_rdf.namespaces import DCTERMS, FIO, NEVO_SOURCE, OM, ROOT, TACO_SOURCE
from taco_rdf.namespaces import NEVONUT as NEVONUT_NS

ENDPOINT = sparql.endpoint()
MAPPING = ROOT / "data" / "alignment" / "taco_nevo_nutrients.csv"
OUT_MD = ROOT / "analysis" / "nutrient_definitions.md"
OUT_CSV = ROOT / "analysis" / "data" / "nutrient_definitions.csv"
NEVONUT = str(NEVONUT_NS)
TACOID = "https://w3id.org/taco-rdf/id/nutrient/"
SOURCES = {"TACO": str(TACO_SOURCE), "NEVO": str(NEVO_SOURCE)}
PDF = ROOT / "data" / "external" / "taco" / "taco_4_edicao_revisada_e_ampliada.pdf"
NICEKG_NOTEBOOK = "nevo_processing.ipynb"

# TACO's INFOODS tagnames, as Quadro 6 prints them (PDF page 20, and 21 for fatty acids and cholesterol).
TAGNAMES = {
    "moisture": "WATER", "energy_kcal": "ENERC", "energy_kj": "ENERC", "protein": "PROCNT", "lipids": "FAT",
    "carbohydrate": "CHOCDF", "ash": "ASH", "dietary_fiber": "FIBTG", "calcium": "CA", "iron": "FE",
    "magnesium": "MG", "phosphorus": "P", "potassium": "K", "sodium": "NA", "zinc": "ZN", "copper": "CU",
    "manganese": "MN", "retinol": "RETOL", "re": "VITA", "rae": "VITA", "vitamin_c": "VITC", "thiamin": "THIA",
    "riboflavin": "RIFB", "niacin": "NIA", "pyridoxine": "VITB6A", "tryptophan": "TRP_G",
    "sfa": "FASAT", "fa_12_0": "F12D0", "fa_14_0": "F14D0", "fa_16_0": "F16D0", "fa_18_0": "F18D0",
    "fa_20_0": "F20D0", "fa_22_0": "F22D0", "fa_24_0": "F24D0", "mufa": "FAMS", "fa_14_1": "F14D1C",
    "fa_16_1": "F16D1C", "fa_18_1": "F18D1CN9", "fa_20_1": "F20D1C", "pufa": "FAPU", "fa_18_2_n6": "F18D2CN6",
    "fa_18_3_n3": "F18D3CN3", "fa_20_4": "F20D4N6", "fa_20_5": "F20D5N3", "fa_22_5": "F22D5",
    "fa_22_6": "F22D6N3", "fa_18_1t": "F18D1T", "fa_18_2t": "F18D2TN6 F18D2TN9", "cholesterol": "CHOLE",
}
TAGNAME_PAGE = {k: 21 if k.startswith(("fa_", "sfa", "mufa", "pufa", "cholesterol")) else 20 for k in TAGNAMES}
# What TACO says of its methods: (PDF page, a phrase of the PDF, in short).
METHODS = {
    "protein": (16, "fatores de conversão recomendado por Jones", "nitrogen (Kjeldahl) times Jones's factors, 6.25 where a food has none"),
    "lipids": (16, "extração Soxhlet", "Soxhlet extraction, after acid hydrolysis where needed"),
    "carbohydrate": (16, "calculado pela diferença", "by difference: 100 minus water, protein, fat, ash and alcohol; includes fibre"),
    "dietary_fiber": (16, "enzimático gravimétrico", "enzymatic-gravimetric (AOAC, Prosky)"),
    "energy_kcal": (16, "coeficientes específicos", "Atwater system with specific coefficients; alcohol 6.93 kcal/g"),
    "vitamin_c": (17, "Vitamina C total", "total vitamin C: ascorbic acid oxidised to dehydroascorbic acid, by HPLC"),
    "niacin": (17, "A niacina foi determinada", "niacin by HPLC"),
    "re": (18, "1/6 µ g de trans  beta-caroteno", "retinol + 1/6 trans beta-carotene + 1/12 other provitamin A carotenoids"),
    "rae": (18, "1/12 µg de trans  beta-caroteno", "retinol + 1/12 trans beta-carotene + 1/24 other provitamin A carotenoids"),
    "sfa": (18, "g de ácido graxo por 100g de aliment", "fatty acids in g per 100 g of food"),
}
# TACO's own nutrients whose tagname, or the common name in Quadro 5 (PDF page 19), gives the form a NEVO code
# names: (NEVO code, the evidence, whether TACO's tagname says it, a caveat).
COULD_TAKE = {
    "fa_14_1": ("F14:1CIS", "tagname F14D1C (cis); Quadro 5: miristoléico", True, ""),
    "fa_16_1": ("F16:1CIS", "tagname F16D1C (cis); Quadro 5: palmitoléico", True, ""),
    "fa_20_1": ("F20:1CIS", "tagname F20D1C (cis); Quadro 5: gadoléico", True, ""),
    "fa_20_4": ("F20:4CN6", "tagname F20D4N6 (n-6); Quadro 5: araquidônico", True, ""),
    "fa_18_1": ("F18:1CIS", "tagname F18D1CN9 (cis n-9); Quadro 5: oléico", True,
                "TACO names the n-9 isomer, NEVO's code every cis 18:1"),
    "fa_22_5": ("F22:5CN3", "Quadro 5: DPA, clupanodônico (n-3)", False,
                "TACO's tagname F22D5 gives no series; only the common name does"),
}
# Same element or compound in both tables, so the same quantity whatever the analytical method.
BY_DEFINITION = {"moisture", "ash", "cholesterol", "calcium", "magnesium", "phosphorus", "iron", "potassium",
                 "copper", "zinc", "retinol", "alcohol"}
FATTY_ACIDS = {"sfa", "pufa", "fa_12_0", "fa_14_0", "fa_16_0", "fa_18_0", "fa_18_1t", "fa_18_2_n6", "fa_18_3_n3",
               "fa_20_0", "fa_20_5", "fa_22_0", "fa_22_6", "fa_24_0"}
# Which data test decides a nutrient.
TEST_OF = {"available_carbohydrate": "carbohydrate", "energy_kcal": "energy kcal", "energy_kj": "energy kJ",
           "protein": "protein", "re": "vitamin A", "rae": "vitamin A", **{k: "fatty acids" for k in FATTY_ACIDS}}
CODES = ["ENERCC", "ENERCJ", "PROT", "FAT", "CHO", "SUGAR", "STARCH", "FIBT", "ALC", "OA", "POLYL", "NT", "RETOL",
         "VITA_RE", "VITA_RAE", "FASAT", "carbohydrate"]
VERDICTS = ["same quantity, checked with data", "same quantity by definition", "same quantity in another unit",
            "calculated another way", "NEVO's values are under another code", "to confirm with NEVO's method"]

Foods = dict[str, dict[str, float]]


# Reading the data

def from_fuseki(endpoint: str, table: str) -> tuple[Foods, dict[str, set[str]], dict[str, int]]:
    """Per food, the numbers of the nutrients the tests use; per nutrient, its unit strings and its count of
    values with a number."""
    def rows(query: str) -> list[dict[str, str]]:
        return sparql.select(query, endpoint, timeout=1800)

    head = (f"PREFIX fio: <{FIO}> PREFIX om: <{OM}> SELECT {{}} WHERE {{{{ ?f <{DCTERMS.isVersionOf}> "
            f"<{SOURCES[table]}> ; fio:hasNutritionalValue ?n . ?n fio:hasNutrient ?nu ; om:hasValue ?m . "
            "?m om:hasNumericalValue ?x . {} }} {}")
    wanted = " ".join(f"<{NEVONUT}{c}>" if c.isupper() else f"<{TACOID}{c}>" for c in CODES)
    foods: Foods = defaultdict(dict)
    for r in rows(head.format("?f ?nu (MIN(?x) AS ?v)", f"VALUES ?nu {{ {wanted} }}", "GROUP BY ?f ?nu")):
        foods[r["f"]][local(r["nu"])] = float(r["v"])
    units: dict[str, set[str]] = defaultdict(set)
    counts: dict[str, int] = {}
    for r in rows(head.format("?nu ?u (COUNT(DISTINCT ?n) AS ?c)", "OPTIONAL { ?m om:hasUnit ?u FILTER isLiteral(?u) }",
                              "GROUP BY ?nu ?u")):
        if "u" in r:
            units[local(r["nu"])].add(r["u"])
        counts[local(r["nu"])] = counts.get(local(r["nu"]), 0) + int(r["c"])
    return dict(foods), dict(units), counts


def from_graph(g: Graph, table: str) -> tuple[Foods, dict[str, set[str]], dict[str, int]]:
    """The same as from_fuseki, read with rdflib from a graph."""
    foods: Foods = defaultdict(dict)
    units: dict[str, set[str]] = defaultdict(set)
    values: dict[str, set] = defaultdict(set)
    for f in g.subjects(DCTERMS.isVersionOf, URIRef(SOURCES[table])):
        for n in g.objects(f, FIO.hasNutritionalValue):
            for nu in g.objects(n, FIO.hasNutrient):
                for m in g.objects(n, OM.hasValue):
                    for x in g.objects(m, OM.hasNumericalValue):
                        name = local(str(nu))
                        values[name].add(n)
                        units[name].update(str(u) for u in g.objects(m, OM.hasUnit) if isinstance(u, Literal))
                        if name in CODES:
                            v = float(x)
                            foods[str(f)][name] = min(v, foods[str(f)].get(name, v))
    return dict(foods), dict(units), {k: len(v) for k, v in values.items()}


def local(iri: str) -> str:
    return iri.rsplit("#", 1)[-1] if iri.startswith(NEVONUT) else iri.rsplit("/", 1)[-1]


# Tests on the data

def share(foods: Iterable[dict[str, float]], keep: Callable[[dict[str, float]], bool],
          ok: Callable[[dict[str, float]], bool]) -> tuple[int, int]:
    """Of the foods keep selects, how many ok holds for."""
    kept = [r for r in foods if keep(r)]
    return sum(map(ok, kept)), len(kept)


def near(a: float, b: float, absolute: float, relative: float) -> bool:
    return abs(a - b) <= max(absolute, relative * abs(b))


def tests(taco: Foods, nevo: Foods) -> dict[str, dict[str, tuple[int, int]]]:
    """Each test, per table: (foods it holds for, foods tested)."""
    def g(r: dict[str, float], k: str) -> float:
        return r.get(k, 0.0)

    def eu_kcal(r: dict[str, float], cho: float) -> float:
        return 4 * g(r, "PROT") + 9 * g(r, "FAT") + 4 * cho + 2 * g(r, "FIBT") + 7 * g(r, "ALC") + 3 * g(r, "OA") + 2.4 * g(r, "POLYL")

    def eu_kj(r: dict[str, float], cho: float) -> float:
        return 17 * g(r, "PROT") + 37 * g(r, "FAT") + 17 * cho + 8 * g(r, "FIBT") + 29 * g(r, "ALC") + 13 * g(r, "OA") + 10 * g(r, "POLYL")

    def taco_cho(r: dict[str, float]) -> float:
        return max(g(r, "carbohydrate") - g(r, "FIBT"), 0.0)

    def has(*keys: str) -> Callable[[dict[str, float]], bool]:
        return lambda r: all(k in r for k in keys)

    def vitamin_a(r: dict[str, float]) -> bool:
        carotenoid_re, carotenoid_rae = r["VITA_RE"] - g(r, "RETOL"), r["VITA_RAE"] - g(r, "RETOL")
        return near(carotenoid_re, 2 * carotenoid_rae, 1.5, 0.05)

    with_carotenoids = lambda r: "VITA_RE" in r and "VITA_RAE" in r and r["VITA_RE"] - g(r, "RETOL") > 3  # noqa: E731
    with_nitrogen = lambda r: "PROT" in r and g(r, "NT") > 0.05  # noqa: E731
    return {
        "carbohydrate: available carbohydrate is the sum of sugars and starch": {
            "NEVO": share(nevo.values(), has("CHO", "SUGAR", "STARCH"), lambda r: near(r["CHO"], r["SUGAR"] + r["STARCH"], 0.15, 0)),
            "TACO": share(taco.values(), has("carbohydrate"), lambda r: False)},  # TACO has no sugars or starch
        "energy kcal: energy follows the general EU factors": {
            "NEVO": share(nevo.values(), has("ENERCC", "PROT", "FAT"), lambda r: near(eu_kcal(r, g(r, "CHO")), r["ENERCC"], 2, 0.02)),
            "TACO": share(taco.values(), has("ENERCC", "PROT", "FAT", "carbohydrate"), lambda r: near(eu_kcal(r, taco_cho(r)), r["ENERCC"], 2, 0.02))},
        "energy kJ: energy follows the general EU factors": {
            "NEVO": share(nevo.values(), has("ENERCJ", "PROT", "FAT"), lambda r: near(eu_kj(r, g(r, "CHO")), r["ENERCJ"], 8, 0.02)),
            "TACO": share(taco.values(), has("ENERCJ", "PROT", "FAT", "carbohydrate"), lambda r: near(eu_kj(r, taco_cho(r)), r["ENERCJ"], 8, 0.02))},
        "protein: protein is nitrogen times 6.25": {
            "NEVO": share(nevo.values(), with_nitrogen, lambda r: near(r["PROT"] / r["NT"], 6.25, 0.01, 0)),
            "TACO": (0, 0)},  # TACO gives no nitrogen; its PDF names Jones's factors
        "vitamin A: retinol equivalents count carotenoids twice as much as retinol activity equivalents": {
            "NEVO": share(nevo.values(), with_carotenoids, vitamin_a),
            "TACO": share(taco.values(), with_carotenoids, vitamin_a)},
        "fatty acids: saturated fatty acids are at most the fat, so per 100 g of food": {
            "NEVO": share(nevo.values(), has("FASAT", "FAT"), lambda r: r["FASAT"] <= r["FAT"] + 0.05),
            "TACO": share(taco.values(), has("FASAT", "FAT"), lambda r: r["FASAT"] <= r["FAT"] + 0.05)},
    }


def protein_ratios(nevo: Foods) -> tuple[int, float]:
    """How many distinct protein-to-nitrogen ratios NEVO has, to two decimals, and their median."""
    ratios = [r["PROT"] / r["NT"] for r in nevo.values() if "PROT" in r and r.get("NT", 0) > 0.05]
    return len({round(x, 2) for x in ratios}), statistics.median(ratios) if ratios else 0.0


def holds(n: tuple[int, int]) -> bool | None:
    """A test holds for a table when it holds for 95% of its foods, fails when for fewer than half."""
    ok, total = n
    if not total:
        return None
    return True if ok >= 0.95 * total else False if ok < 0.5 * total else None


def test_says(name: str, results: dict[str, dict[str, tuple[int, int]]], distinct_ratios: int) -> str:
    """What a data test says of a nutrient: 'same' or 'differs'."""
    r = next(v for k, v in results.items() if k.startswith(name + ":"))
    taco, nevo = holds(r["TACO"]), holds(r["NEVO"])
    if name == "protein":  # nitrogen times factors per food in NEVO, as Jones's factors in TACO
        return "same" if distinct_ratios > 10 and nevo is False else "differs"
    if name == "carbohydrate":
        return "differs" if nevo else "same"
    return "same" if taco is True and nevo is True else "differs" if nevo is True and taco is False else "unclear"


# The verdicts

def mapping() -> list[dict[str, str]]:
    with MAPPING.open(encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh))
    return [*rows, {"taco_nutrient": "available_carbohydrate", "nevo_code": "CHO",
                    "note": "written by the export: TACO's carbohydrate minus dietary fibre"}]


def verdict(key: str, nevo_values: int, taco_units: set[str], nevo_units: set[str], says: str | None) -> str:
    if not nevo_values:
        return VERDICTS[4]
    if taco_units != nevo_units:
        return VERDICTS[2]
    if says is not None:
        return VERDICTS[0] if says == "same" else VERDICTS[3]
    if key in BY_DEFINITION:
        return VERDICTS[1]
    return VERDICTS[5]


def classify(taco: tuple, nevo: tuple, results: dict, distinct_ratios: int) -> list[dict[str, str]]:
    _, taco_units, _ = taco
    _, nevo_units, nevo_counts = nevo
    out = []
    for r in mapping():
        key, code = r["taco_nutrient"], r["nevo_code"]
        if not code:
            continue
        taco_key = "carbohydrate" if key == "available_carbohydrate" else key
        test = TEST_OF.get(key)
        says = test_says(test, results, distinct_ratios) if test else None
        t_units = taco_units.get(code, set()) if key != "available_carbohydrate" else taco_units.get("CHO", set())
        n_units = nevo_units.get(code, set())
        tagname = "CHOCDF − FIBTG" if key == "available_carbohydrate" else TAGNAMES.get(taco_key, "")
        out.append({"taco_nutrient": key, "nevo_code": code, "taco_tagname": tagname,
                    "taco_unit": "/".join(sorted(t_units)), "nevo_unit": "/".join(sorted(n_units)),
                    "nevo_values": str(nevo_counts.get(code, 0)), "test": test or "",
                    "verdict": verdict(key, nevo_counts.get(code, 0), t_units, n_units, says)})
    return out


def own_nutrients(nevo_units: dict[str, set[str]]) -> list[dict[str, str]]:
    """TACO's nutrients without a NEVO code, with the NEVO code TACO's own declarations point to, if any."""
    out = []
    for r in mapping():
        if r["nevo_code"]:
            continue
        key = r["taco_nutrient"]
        code, evidence, tagname_says, caveat = COULD_TAKE.get(key, ("", "", False, ""))
        out.append({"taco_nutrient": key, "taco_tagname": TAGNAMES.get(key, ""), "nevo_code": code,
                    "nevo_has_it": str(bool(code) and code in nevo_units), "evidence": evidence,
                    "tagname_says_it": str(tagname_says), "caveat": caveat})
    return out


# Writing

def document(rows: list[dict[str, str]], own: list[dict[str, str]], results: dict, ratios: tuple[int, float],
             sodium: int) -> str:
    counts = {v: sum(r["verdict"] == v for r in rows) for v in VERDICTS}
    could = [o for o in own if o["nevo_code"] and o["nevo_has_it"] == "True"]
    lines = ["# Is TACO's value the same quantity as NEVO's?", "",
             "Generated by `python scripts/nutrient_definitions.py` from Fuseki's `nicefood` dataset and TACO's "
             "printed table (4th edition, PDF), and checked by `python verification/nutrient_definitions_check.py`. "
             "NEVO appears only as counts and shares, never as a value.", "",
             f"In TACO's NICE-Food export, {len(rows)} TACO nutrients take a NEVO nutrient code "
             "(`data/alignment/taco_nevo_nutrients.csv`). A shared code says the two tables measure the same thing. "
             "For each, this compares what TACO declares, its INFOODS tagname and method, with tests on both tables' "
             "data.", "", "## In short", ""]
    lines += [f"| {v} | {counts[v]} |" for v in VERDICTS]
    lines.insert(len(lines) - len(VERDICTS), "| Verdict | Nutrients |")
    lines.insert(len(lines) - len(VERDICTS), "| --- | ---: |")
    lines += ["", "## Tests on the data", "",
              "Each test is run on every food with the values it needs; it holds for a table when it holds for 95% "
              "of its foods.", "", "| Test | NEVO | TACO |", "| --- | --- | --- |"]
    for name, r in results.items():
        cells = [f"{ok:,} of {n:,} ({100 * ok / n:.0f}%)" if n else "not testable" for ok, n in (r["NEVO"], r["TACO"])]
        lines.append(f"| {name} | {cells[0]} | {cells[1]} |")
    lines += ["", f"NEVO's protein-to-nitrogen ratio takes {ratios[0]} different values (median {ratios[1]:.2f}), "
              "so NEVO uses a factor per food, as TACO uses Jones's factors (TACO, PDF page 16). TACO's carbohydrate "
              "is by difference and includes fibre (page 16), so TACO has no sum of sugars and starch: the export's "
              "available carbohydrate is carbohydrate minus fibre. TACO's energy uses Atwater's specific "
              "coefficients (page 16), NEVO's the general EU factors.", "",
              "## Each nutrient", "", "| TACO nutrient | NEVO code | TACO tagname | Unit, TACO / NEVO | Verdict |",
              "| --- | --- | --- | --- | --- |"]
    for r in rows:
        lines.append(f"| `{r['taco_nutrient']}` | `{r['nevo_code']}` | {r['taco_tagname'] or '–'} | "
                     f"{r['taco_unit']} / {r['nevo_unit'] or '–'} | {r['verdict']} |")
    lines += ["", "## What this means for the shared code", "",
              "- **Calculated another way** (carbohydrate, energy): the code is shared, the number is not "
              "comparable as it is. TACO's value keeps how it was calculated (`prov:wasDerivedFrom` and a "
              "description for available carbohydrate), but a query by the code does not see it.",
              f"- **NEVO's values are under another code** (sodium): NICE-Food's graph has {sodium:,} NEVO sodium "
              "values under `nevonut:nan`, labelled Sodium. Its notebook (`nevo_processing.ipynb`, "
              "rivm-syso/nicekg_processing) reads NEVO's file with `pandas.read_csv`, which reads the code `NA` as "
              "a missing value, and writes the IRI from `str(...)`, which gives `nan`. A query for sodium finds "
              "TACO under `nevonut:NA` and NEVO under `nevonut:nan`, never both. Reading the file with "
              "`keep_default_na=False` would keep `NA`.",
              "- **Another unit** (tryptophan): TACO gives g, NEVO mg. Each measure keeps its unit, so a query "
              "must convert before comparing.",
              "- **To confirm with NEVO's method**: the name, unit and INFOODS meaning agree, but NEVO's method "
              "is not in this repository (fat extraction, fibre method, the vitamins' methods).", "",
              "## TACO's own nutrients that could take a NEVO code", "",
              f"{len(own)} TACO nutrients keep TACO's own URI. TACO's own tagnames and Quadro 5 name the form of "
              f"{len(could)} of them as a NEVO code does, so they could take that code:", "",
              "| TACO nutrient | TACO tagname | NEVO code | Evidence | Caveat |", "| --- | --- | --- | --- | --- |"]
    for o in could:
        lines.append(f"| `{o['taco_nutrient']}` | {o['taco_tagname']} | `{o['nevo_code']}` | {o['evidence']} | "
                     f"{o['caveat'] or '–'} |")
    lines += ["", "The alignment file still gives these no NEVO code; changing it changes the export and is for "
              "the group to decide.", ""]
    return "\n".join(lines)


def build(endpoint: str) -> tuple[list[dict[str, str]], list[dict[str, str]], str]:
    taco, nevo = from_fuseki(endpoint, "TACO"), from_fuseki(endpoint, "NEVO")
    results = tests(taco[0], nevo[0])
    ratios = protein_ratios(nevo[0])
    rows = classify(taco, nevo, results, ratios[0])
    own = own_nutrients(nevo[1])
    return rows, own, document(rows, own, results, ratios, nevo[2].get("nan", 0))


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--endpoint", default=ENDPOINT)
    args = p.parse_args()
    rows, own, text = build(args.endpoint)
    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    with OUT_CSV.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]), lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    OUT_MD.write_text(text, encoding="utf-8", newline="\n")
    print(f"wrote {OUT_MD} and {OUT_CSV}")
    for v in VERDICTS:
        print(f"  {sum(r['verdict'] == v for r in rows):3}  {v}")
    print(f"  {sum(bool(o['nevo_code']) for o in own)} of TACO's {len(own)} own nutrients could take a NEVO code")
    return 0


if __name__ == "__main__":
    sys.exit(main())
