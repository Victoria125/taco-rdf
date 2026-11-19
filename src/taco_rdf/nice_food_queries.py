"""The questions the project asks of TACO and NEVO together in NICE-Food, and the rows they give.

Each competency question names a kind of food by a FoodOn class and a nutrient by a CDNO class, the classes
both tables use, and lists for each table the foods richest in the nutrient. SHARED counts the FoodOn types
foods of both tables share. answers() runs them with NICE-Food's own protein queries (queries/nice-food/), so
that a change to the export or to the store can be checked to leave their rows as they were
(scripts/rebuild_nicefood.py, verification/taco_nevo_alignment_check.py).
"""

from __future__ import annotations

from .namespaces import NEVO_SOURCE, QUERIES_DIR, TACO_SOURCE
from .sparql import endpoint, prefixes, select

TACO = str(TACO_SOURCE)
NEVO = str(NEVO_SOURCE)
PREFIXES = prefixes("rdf", "rdfs", "skos", "fio", "om", "dcterms", "obo")
PROTEIN_QUERIES = ("protein_groups.rq", "protein_groups_cdno.rq")
# (question, FoodOn class of the kind of food, CDNO class of the nutrient)
QUESTIONS = [
    ("Which fruits have the most vitamin C?", "FOODON_00001057", "CDNO_0200192"),
    ("Which legumes have the most iron?", "FOODON_00001264", "CDNO_0200651"),
    ("Which dairy foods have the most calcium?", "FOODON_00001256", "CDNO_0200544"),
    ("Which nuts have the most magnesium?", "FOODON_00001172", "CDNO_0200570"),
]


def richest(kind: str, nutrient: str) -> str:
    """The foods of a kind with their largest value of a nutrient, by table, richest first."""
    return PREFIXES + f"""SELECT ?source ?name (MAX(?value) AS ?amount) (SAMPLE(?u) AS ?unit) WHERE {{
  ?type rdfs:subClassOf* obo:{kind} .
  ?food rdf:type fio:FoodItem ; rdf:type ?type ; dcterms:isVersionOf ?source ; skos:prefLabel ?name .
  FILTER (LANG(?name) = "en")
  ?food fio:hasNutritionalValue ?v . ?v rdf:type obo:{nutrient} ; om:hasValue ?m .
  ?m om:hasNumericalValue ?value .
  OPTIONAL {{ ?m om:hasUnit ?u FILTER isLiteral(?u) }}
}} GROUP BY ?source ?name ORDER BY ?source DESC(?amount) ?name
"""


SHARED = PREFIXES + f"""SELECT ?label (COUNT(DISTINCT ?t) AS ?taco) (COUNT(DISTINCT ?n) AS ?nevo) WHERE {{
  ?t rdf:type fio:FoodItem ; rdf:type ?type ; dcterms:isVersionOf <{TACO}> .
  ?n rdf:type fio:FoodItem ; rdf:type ?type ; dcterms:isVersionOf <{NEVO}> .
  FILTER STRSTARTS(STR(?type), "http://purl.obolibrary.org/obo/FOODON_")
  ?type rdfs:label ?label .
}} GROUP BY ?label ORDER BY DESC(?taco + ?nevo) ?label
"""


def queries() -> dict[str, str]:
    """Each query answers() runs, by name."""
    out = {q: (QUERIES_DIR / "nice-food" / q).read_text(encoding="utf-8") for q in PROTEIN_QUERIES}
    out.update({f"{kind}/{nutrient}": richest(kind, nutrient) for _, kind, nutrient in QUESTIONS})
    out["shared"] = SHARED
    return out


def answers(url: str | None = None) -> dict[str, list[tuple[str, ...]]]:
    """The rows the queries give: TACO's rows of NICE-Food's protein queries, the competency questions, and
    the classes TACO and NEVO share."""
    url = url or endpoint()
    names = {r["n"] for r in select(f"SELECT DISTINCT ?n WHERE {{ ?f <http://purl.org/dc/terms/isVersionOf> "
                                    f"<{TACO}> ; <http://www.w3.org/2004/02/skos/core#prefLabel> ?n "
                                    'FILTER(LANG(?n) = "en") }', url)}
    text = queries()
    out = {}
    for q in PROTEIN_QUERIES:
        rows = select(text[q], url)
        out[q] = sorted({(r["grouplabel"], r["foodname"], r["value"])
                         for r in rows if r["foodname"] in names})
    for _, kind, nutrient in QUESTIONS:
        out[f"{kind}/{nutrient}"] = sorted((r["source"], r["name"], r["amount"])
                                           for r in select(text[f"{kind}/{nutrient}"], url))
    out["shared"] = sorted((r["label"], r["taco"], r["nevo"]) for r in select(SHARED, url))
    return out
