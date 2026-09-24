from __future__ import annotations

from pathlib import Path

from rdflib import Namespace
from rdflib.namespace import DCAT, DCTERMS, FOAF, OWL, PROV, RDF, RDFS, SKOS, XSD

BASE = "https://w3id.org/taco-rdf/"

TACO = Namespace(BASE + "vocab#")
ID = Namespace(BASE + "id/")

QUDT = Namespace("http://qudt.org/schema/qudt/")
UNIT = Namespace("http://qudt.org/vocab/unit/")
ODRL = Namespace("http://www.w3.org/ns/odrl/2/")
OBO = Namespace("http://purl.obolibrary.org/obo/")
SH = Namespace("http://www.w3.org/ns/shacl#")
FIO = Namespace("http://www.foodvoc.org/resource/fio#")

PREFIXES = {
    "taco": TACO,
    "tacoid": ID,
    "skos": SKOS,
    "dcterms": DCTERMS,
    "dcat": DCAT,
    "prov": PROV,
    "foaf": FOAF,
    "qudt": QUDT,
    "unit": UNIT,
    "odrl": ODRL,
    "obo": OBO,
    "fio": FIO,
    "owl": OWL,
    "rdfs": RDFS,
    "xsd": XSD,
}

ROOT = Path(__file__).resolve().parents[2]
RAW_XLS = ROOT / "data" / "raw" / "original-Taco_4a_edicao_2011.xls"
CORRECTIONS_DIR = ROOT / "data" / "corrections"
ALIGNMENTS_CSV = ROOT / "data" / "alignment" / "alignments.csv"
FOOD_NAMES_EN = ROOT / "data" / "labels" / "food_names_en.csv"
ONTOLOGY_TTL = ROOT / "ontology" / "taco.ttl"
FOODON_MODULE_TTL = ROOT / "ontology" / "imports" / "foodon-module.ttl"
SHAPES_DIR = ROOT / "shapes"
POLICY_TTL = ROOT / "policies" / "taco-attribution-policy.ttl"
QUERIES_DIR = ROOT / "queries"
BUILD_DIR = ROOT / "build"
GRAPH_TTL = BUILD_DIR / "taco.ttl"

__all__ = [
    "ALIGNMENTS_CSV",
    "BASE",
    "BUILD_DIR",
    "CORRECTIONS_DIR",
    "DCAT",
    "DCTERMS",
    "FIO",
    "FOAF",
    "FOODON_MODULE_TTL",
    "FOOD_NAMES_EN",
    "GRAPH_TTL",
    "ID",
    "OBO",
    "ODRL",
    "ONTOLOGY_TTL",
    "OWL",
    "POLICY_TTL",
    "PREFIXES",
    "PROV",
    "QUDT",
    "QUERIES_DIR",
    "RAW_XLS",
    "RDF",
    "RDFS",
    "ROOT",
    "SH",
    "SHAPES_DIR",
    "SKOS",
    "TACO",
    "UNIT",
    "XSD",
]
