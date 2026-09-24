"""Publication metadata shared by the graph, the site and the citation files."""

from __future__ import annotations

TITLE = "TACO 4th edition as an RDF knowledge graph"
CREATOR = "Vitória Maia"
CREATOR_EMAIL = "vitoriamaia19@gmail.com"

REPO_URL = "https://github.com/Victoria125/taco-rdf"
SITE_URL = "https://victoria125.github.io/taco-rdf/"
DOI: str | None = "10.5281/zenodo.22920219"

DATA_LICENSE = "https://creativecommons.org/licenses/by/4.0/"
CODE_LICENSE = "https://spdx.org/licenses/MIT.html"

KEYWORDS = (
    "food composition", "TACO", "Brazil", "nutrition", "knowledge graph", "RDF", "FoodOn", "ChEBI",
    "CDNO", "Food Item Ontology", "QUDT", "SHACL", "ODRL", "FAIR data",
)

SOURCE_TERMS = "É permitida a reprodução parcial ou total desta obra, desde que citada a fonte."
SOURCE_TERMS_EN = "Partial or total reproduction of this work is permitted, provided the source is cited."
SOURCE_LANDING_PAGE = "https://nepa.unicamp.br/publicacoes/tabela-taco-pdf/"
SOURCE_PDF = "https://nepa.unicamp.br/wp-content/uploads/sites/27/2023/10/taco_4_edicao_ampliada_e_revisada.pdf"

DUMPS = {
    "taco.ttl": ("text/turtle", "Turtle"),
    "taco.nt": ("application/n-triples", "N-Triples"),
}
