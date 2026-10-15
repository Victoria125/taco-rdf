# Published FoodOn typing and unresolved foods

311 of 597 TACO foods have a published FoodOn `rdf:type` (52.1%).
Published type assertions: 311. Foods without a FoodOn type: 286.
Of the untyped foods, 125 retain historical candidates and 161 have no candidate recorded in the alignment inputs.

These are coverage counts, not semantic accuracy estimates. Absence of a type does not prove
that FoodOn lacks a suitable class. The gap CSV is a review queue; a confirmed ontology gap
requires documented class search and review. A valid general class may be used even when
FoodOn does not express the food's more specific preparation or cultural identity.

## Candidates the FoodOn module cannot back

FoodOn axiom conflicts: 4 untyped foods (108, 125, 162, 250) have a food class candidate that FoodOn also places
under whole organisms or plants. FoodOn has a class for them, but `rdf:type` would entail that
the food is an organism, so the build withholds it. These are not ontology gaps; the conflicting
axioms should be reported to FoodOn. NICE-Food's notebooks type food items without this check.

Organism classes only: 31 untyped foods retain only a class of whole organisms or
plants as candidate. A food class, possibly a more general one, still has to be searched for.

## Reproducible exports

- `data/foodon_types.csv`: FoodOn types asserted in the graph built from current inputs.
- `data/foodon_typing_gaps.csv`: every food without a type, with historical candidate evidence.
  Multiple candidates, if present, use ` | ` in corresponding candidate columns.
  `candidate_obstacle` gives why the FoodOn module cannot back each candidate as a type
  (`foodon_axiom_conflict`, `organism_class`, `missing_class`, `deprecated_class`), or is empty.

The build checks class availability, organism ancestry and consistency with scored reviews before
the audit runs. Historical food SKOS candidates are not counted as published mappings and are
not automatically converted to `rdf:type`. Group and nutrient mappings are outside this report.

## Review status

Review metadata comes only from the latest scored round for each food. Incomplete rounds and
individual reviewer proposals do not change these exports. `pending_review` means no scored
decision is available; `reviewed_type` records an accepted type; `reviewed_no_type` records a
historical non-type decision; `reviewed_no_term` records `sssom:NoTermFound` in a scored round.
A historical non-type decision does not establish the absence of a defensible FoodOn type.

| Status | Typed foods | Untyped foods |
| --- | ---: | ---: |
| pending_review | 311 | 286 |

## Coverage by TACO group

| Group | Foods | Typed | Untyped |
| --- | ---: | ---: | ---: |
| Cereais e derivados | 63 | 42 | 21 |
| Verduras, hortaliças e derivados | 99 | 59 | 40 |
| Frutas e derivados | 96 | 48 | 48 |
| Gorduras e óleos | 14 | 13 | 1 |
| Pescados e frutos do mar | 50 | 13 | 37 |
| Carnes e derivados | 123 | 52 | 71 |
| Leite e derivados | 24 | 17 | 7 |
| Bebidas (alcoólicas e não alcoólicas) | 14 | 7 | 7 |
| Ovos e derivados | 7 | 5 | 2 |
| Produtos açucarados | 20 | 10 | 10 |
| Miscelâneas | 9 | 5 | 4 |
| Outros alimentos industrializados | 5 | 4 | 1 |
| Alimentos preparados | 32 | 4 | 28 |
| Leguminosas e derivados | 30 | 24 | 6 |
| Nozes e sementes | 11 | 8 | 3 |

Reproduce with `python scripts/audit_foodon_typing.py` from the repository root.
