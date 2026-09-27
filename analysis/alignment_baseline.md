# FoodOn alignment baseline

This is a reproducible screening of the current CSV inputs, not a human assessment of mapping
quality.
Coverage counts foods with at least one FoodOn link. Relation columns count links, so their sum can
exceed the number of linked foods. No precision, accuracy or cultural adequacy is inferred.

436 of 597 TACO foods have a FoodOn link (73.0%). 161 have no link.

| Group | Foods | Linked | Unlinked | Coverage |
| --- | ---: | ---: | ---: | ---: |
| Cereais e derivados | 63 | 52 | 11 | 82.5% |
| Verduras, hortaliças e derivados | 99 | 83 | 16 | 83.8% |
| Frutas e derivados | 96 | 73 | 23 | 76.0% |
| Gorduras e óleos | 14 | 13 | 1 | 92.9% |
| Pescados e frutos do mar | 50 | 30 | 20 | 60.0% |
| Carnes e derivados | 123 | 75 | 48 | 61.0% |
| Leite e derivados | 24 | 20 | 4 | 83.3% |
| Bebidas (alcoólicas e não alcoólicas) | 14 | 11 | 3 | 78.6% |
| Ovos e derivados | 7 | 5 | 2 | 71.4% |
| Produtos açucarados | 20 | 15 | 5 | 75.0% |
| Miscelâneas | 9 | 7 | 2 | 77.8% |
| Outros alimentos industrializados | 5 | 5 | 0 | 100.0% |
| Alimentos preparados | 32 | 12 | 20 | 37.5% |
| Leguminosas e derivados | 30 | 26 | 4 | 86.7% |
| Nozes e sementes | 11 | 9 | 2 | 81.8% |
| TOTAL | 597 | 436 | 161 | 73.0% |

## Preparation screening (22 flagged links)

The screen checks only explicit Portuguese preparation terms against the English FoodOn label:
`cru` versus `cooked`, and `cozido`, `assado`, `frito`, `refogado` or `grelhado` versus `raw`.
It also flags a prepared TACO name when the target label lacks an explicit preparation term.
A flag is a review priority, not a demonstrated mapping error. The target class definition,
relationship (`relatedMatch` may describe a different preparation), and TACO context still matter.
The screen misses many mismatches because it does not interpret synonyms or ontology definitions.
The full flagged list is in `data/preparation_conflicts.csv`.

- preparation not explicit in FoodOn label: 18 links
- prepared TACO name / raw FoodOn label: 4 links

The prepared round in `../data/alignment/review/round-1/` contains 86 randomly sampled foods
plus targeted cases. Its two reviewer forms are empty. The scientific question about mapping
correctness and loss of Brazilian food distinctions requires the independent reviews, adjudication
and scoring described in `../docs/alignment-review.md`.

Reproduce with `python scripts/audit_alignment_baseline.py` from the repository root.
