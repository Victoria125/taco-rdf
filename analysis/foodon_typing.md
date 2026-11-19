# Published FoodOn typing and unresolved foods

597 of 597 TACO foods have a published FoodOn `rdf:type` (100.0%).
Published type assertions: 597. Foods without a FoodOn type: 0.
Of the untyped foods, 0 retain historical candidates and 0 have no candidate recorded in the alignment inputs.

These are coverage counts, not semantic accuracy estimates. Absence of a type does not prove
that FoodOn lacks a suitable class. The gap CSV is a review queue; a confirmed ontology gap
requires documented class search and review. A valid general class may be used even when
FoodOn does not express the food's more specific preparation or cultural identity.

## Candidates the FoodOn module cannot back

FoodOn axiom conflicts: 0 untyped foods (none) have a food class candidate that FoodOn also places
under whole organisms or plants. FoodOn has a class for them, but `rdf:type` would entail that
the food is an organism, so the build withholds it. These are not ontology gaps; the conflicting
axioms should be reported to FoodOn. NICE-Food's notebooks type food items without this check.

Organism classes only: 0 untyped foods retain only a class of whole organisms or
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
| reviewed_type | 597 | 0 |

## Coverage by TACO group

| Group | Foods | Typed | Untyped |
| --- | ---: | ---: | ---: |
| Cereais e derivados | 63 | 63 | 0 |
| Verduras, hortaliças e derivados | 99 | 99 | 0 |
| Frutas e derivados | 96 | 96 | 0 |
| Gorduras e óleos | 14 | 14 | 0 |
| Pescados e frutos do mar | 50 | 50 | 0 |
| Carnes e derivados | 123 | 123 | 0 |
| Leite e derivados | 24 | 24 | 0 |
| Bebidas (alcoólicas e não alcoólicas) | 14 | 14 | 0 |
| Ovos e derivados | 7 | 7 | 0 |
| Produtos açucarados | 20 | 20 | 0 |
| Miscelâneas | 9 | 9 | 0 |
| Outros alimentos industrializados | 5 | 5 | 0 |
| Alimentos preparados | 32 | 32 | 0 |
| Leguminosas e derivados | 30 | 30 | 0 |
| Nozes e sementes | 11 | 11 | 0 |

Reproduce with `python scripts/audit_foodon_typing.py` from the repository root.
