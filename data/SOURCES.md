# Data sources and terms

| File | What | Origin | Terms |
|---|---|---|---|
| `raw/original-Taco_4a_edicao_2011.xls` | The TACO 4th edition workbook, unmodified. **The graph is built from this file.** | NEPA-UNICAMP (Universidade Estadual de Campinas), as mirrored in `references/` of https://github.com/raulfdm/taco-api | **Verified 2026-09-23.** The official TACO 4th edition PDF (p. ii-iii), linked from https://nepa.unicamp.br/publicacoes/tabela-taco-pdf/, states: *"É permitida a reprodução parcial ou total desta obra, desde que citada a fonte"* (total or partial reproduction allowed, provided the source is cited). See `../LICENSE-DATA.md`. |
| `raw/food.csv`, `categories.csv`, `nutrients.csv`, `fatty-acids.csv`, `amino-acids.csv` | Hand-normalised version of the same workbook (`Tr` -> 0, `NA` and `*` -> blank) | https://github.com/raulfdm/taco-api (`references/csv/`) | MIT, see `raw/LICENSE-taco-api.md`. Used **only** as an independent check of the parser (`tests/test_crosscheck.py`), not as input. |
| `alignment/alignments.csv` | 581 links: TACO food groups (20) and foods (436) to FoodOn, nutrients to ChEBI (63) and to CDNO (62) | FoodOn and ChEBI links curated here by one annotator; CDNO links derived from the ChEBI links (see the README). `scripts/verify_alignments.py` checks that each target IRI exists in the EBI Ontology Lookup Service with the recorded label; it does not check that the target is the right one | CC BY 4.0 (this project). FoodOn and ChEBI are CC BY 4.0; CDNO is CC BY 3.0. |
| `corrections/` | Documented fixes for two defects in the workbook | this project | see `docs/validation-findings.md` |

Suggested citation of the source table (as used in the graph's provenance):

> NEPA-UNICAMP. Tabela brasileira de composição de alimentos - TACO. 4. ed. rev. e ampl. Campinas: NEPA-UNICAMP, 2011.
