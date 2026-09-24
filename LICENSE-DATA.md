# Data licence

| What | Licence |
|---|---|
| Code (`src/`, `scripts/`, `tests/`) | MIT, see [`LICENSE`](LICENSE) |
| The RDF graph built by `taco-rdf build`, the vocabulary (`ontology/`), the SHACL shapes (`shapes/`), the ODRL policy (`policies/`), the SPARQL queries (`queries/`), the alignments (`data/alignment/`) and the corrections (`data/corrections/`) | [Creative Commons Attribution 4.0 International (CC BY 4.0)](https://creativecommons.org/licenses/by/4.0/) |
| The nutrient values and food names, which come from TACO | NEPA-UNICAMP's terms, below |
| `data/raw/*.csv` (independent transcription, used only in tests) | MIT, see [`data/raw/LICENSE-taco-api.md`](data/raw/LICENSE-taco-api.md) |

## Terms of the source table

The official TACO 4th edition (p. ii-iii) states:

> É permitida a reprodução parcial ou total desta obra, desde que citada a fonte.
>
> *(Total or partial reproduction of this work is allowed, provided the source is cited.)*

Source: <https://nepa.unicamp.br/wp-content/uploads/sites/27/2023/10/taco_4_edicao_ampliada_e_revisada.pdf>,
linked from <https://nepa.unicamp.br/publicacoes/tabela-taco-pdf/> (checked 2026-09-23).

The CC BY 4.0 attribution duty and NEPA's citation requirement point the same way. When you reuse the graph, cite both:

> NEPA-UNICAMP. Tabela brasileira de composição de alimentos - TACO. 4. ed. rev. e ampl. Campinas: NEPA-UNICAMP, 2011.

and this dataset (see [`CITATION.cff`](CITATION.cff)).
