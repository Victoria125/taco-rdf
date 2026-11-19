"""Where the project's Fuseki is, and one way to ask it.

The scripts load TACO, NICE-Food's NEVO graphs and FoodOn into a local Apache Jena Fuseki
(triplestore/README.md) and ask it with SPARQL over HTTP. Fuseki's address comes from the environment
variable TACO_FUSEKI (default http://localhost:3030), so they run against another store without editing
them; each dataset is a name under it.
"""

from __future__ import annotations

import os

import requests
from rdflib import Graph

from .namespaces import DCTERMS, FIO, ID, NEVONUT, OBO, OM, PROV, RDF, RDFS, SKOS, TACO, XSD

FUSEKI = os.environ.get("TACO_FUSEKI", "http://localhost:3030").rstrip("/")
NICEFOOD = "nicefood"  # TACO's NICE-Food export, NICE-Food's NEVO graphs and FoodOn
TACO_NEVO = "taco_nevo"  # TACO-RDF's own graph and NICE-Food's NEVO graphs
NAMESPACES = {"rdf": RDF, "rdfs": RDFS, "xsd": XSD, "skos": SKOS, "dcterms": DCTERMS, "prov": PROV,
              "obo": OBO, "fio": FIO, "om": OM, "nevonut": NEVONUT, "taco": TACO, "tacoid": ID}


def dataset(name: str = NICEFOOD) -> str:
    """A Fuseki dataset's address, under which /sparql, /update and /data answer."""
    return f"{FUSEKI}/{name}"


def endpoint(name: str = NICEFOOD) -> str:
    """A Fuseki dataset's SPARQL query endpoint."""
    return f"{dataset(name)}/sparql"


def prefixes(*names: str) -> str:
    """PREFIX declarations for the given prefixes (all of NAMESPACES if none is given)."""
    return "".join(f"PREFIX {n}: <{NAMESPACES[n]}> " for n in (names or NAMESPACES))


def _post(query: str, url: str | None, accept: str, timeout: float) -> requests.Response:
    r = requests.post(url or endpoint(), data={"query": query}, headers={"Accept": accept}, timeout=timeout)
    r.raise_for_status()
    return r


def select(query: str, url: str | None = None, timeout: float = 900) -> list[dict[str, str]]:
    """The rows of a SELECT query, each a dict from variable to the value's string; unbound variables are
    left out."""
    r = _post(query, url, "application/sparql-results+json", timeout)
    return [{k: v["value"] for k, v in b.items()} for b in r.json()["results"]["bindings"]]


def ask(query: str, url: str | None = None, timeout: float = 600) -> bool:
    return bool(_post(query, url, "application/sparql-results+json", timeout).json()["boolean"])


def construct(query: str, url: str | None = None, timeout: float = 900) -> Graph:
    """The graph a CONSTRUCT query gives. Turtle is UTF-8; Fuseki names no charset, and decoding the response
    as text would read it as Latin-1, so the bytes go to rdflib."""
    return Graph().parse(data=_post(query, url, "text/turtle", timeout).content, format="turtle")
