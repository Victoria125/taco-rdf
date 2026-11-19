# TACO as a NICE-Food subgraph

Updated on 2026-11-19 after applying the completed 597-food review. `scripts/taco_to_nice_food.py` wrote `build/taco_nice_food.ttl` from the TACO
snapshot `build/taco.ttl`. It was loaded into a Fuseki dataset, `nicefood`, with NEVO's subgraphs of
NICE-Food v3 (https://doi.org/10.5281/zenodo.18450818) and the FoodOn release this project pins
(2026-09-20), as [triplestore/README.md](../triplestore/README.md) describes. NEVO appears here in counts
only, since its conditions of use do not let this project redistribute its values.

## The subgraph

The subgraph writes TACO in the pattern of NICE-Food's `nevo21_graph.ttl`, in 183,043 triples:

- **Foods.** TACO's 597 foods are `fio:FoodItem`s with their Portuguese and English names. All 597 have
  a confirmed FoodOn class; the review uses 469 distinct classes. Each food is marked with `dcterms:isVersionOf`
  TACO's page, as NICE-Food marks NEVO's foods with NEVO's.
- **Values.** Each of TACO's 21,150 values is a `fio:NutritionalValue`, and 17,561 of them have a CDNO
  class. 17,564 values have a number, written as an `om:Measure` whose unit is an OM unit and a string, as
  in NEVO's subgraph. The other 3,586 are trace, not-applicable and under-re-evaluation cells: they keep
  TACO's `taco:valueStatus` and have no measure, since a trace is not zero.
- **Nutrients.** Where TACO and NEVO report the same component, the value names NEVO's code, e.g.
  `nevonut:PROT`; this covers 40 of TACO's 67 nutrients. The others name TACO's own nutrient.
  [data/alignment/taco_nevo_nutrients.csv](../data/alignment/taco_nevo_nutrients.csv) gives the code or
  the reason for every nutrient. For example, TACO does not say whether its 18:1 is cis or trans, and NEVO
  has a code for each.
- **Carbohydrate.** TACO's carbohydrate is total carbohydrate by difference, fibre included, which NEVO
  has no code for. NEVO's `CHO` is available carbohydrate. TACO's value keeps its own nutrient and CDNO's
  carbohydrate class (`CDNO_0200005`).
  - **Available carbohydrate added.** 570 foods also get available carbohydrate, carbohydrate minus
    dietary fibre, as `nevonut:CHO`. It is typed with CDNO's available carbohydrate class (`CDNO_0200033`)
    and linked by `prov:wasDerivedFrom` to both values.
  - **No fibre to subtract.** Where fibre is not applicable (204 foods, such as meat) or a trace (7), the
    available carbohydrate is the total.
  - **Below zero.** In 11 foods the result is below zero and is written as zero:
    - 7 where fibre exceeds total carbohydrate: pequi, lupin in brine, jurubeba, chicken stock cube,
      avocado, chives and curly lettuce;
    - 4 fish and meats whose total in TACO is itself slightly negative (−0.045 to −0.007 g).
  - **No derived value.** 27 foods have no number for carbohydrate or fibre and get no derived value.

## NICE-Food's own query

[queries/nice-food/protein_groups.rq](../queries/nice-food/protein_groups.rq) is the protein query of
NICE-Food's publication analysis, copied unchanged. Over `nicefood` it returns 554 rows, 185
of them TACO foods:

| FoodOn group | NEVO rows | TACO rows |
| --- | ---: | ---: |
| Fish food product | 56 | 27 |
| Legume food product | 66 | 19 |
| Mammalian meat food product | 117 | 33 |
| Plant fruit food product | 130 | 106 |
| **All** | **369** | **185** |

TACO's rows include lupin, peanut, lentil and red bean among the legumes, and tuna among the fish.

The query chooses protein by NEVO's code (`fio:hasNutrient nevonut:PROT`), so another table reaches it only
by writing NEVO's codes. [protein_groups_cdno.rq](../queries/nice-food/protein_groups_cdno.rq) changes that
one line: it chooses the value by its CDNO class, protein (`CDNO_0200040`). Over `nicefood` it returns the
same 554 rows; the complete result sets were compared and agree.

`tests/test_taco_to_nice_food.py` also checks a small graph using only TACO's own nutrient codes:
the CDNO query still finds its protein values, while the query requiring NEVO's code does not.

## The checks applied to NEVO

The shapes that [nice_food_nevo_checks.md](nice_food_nevo_checks.md) applies to NEVO were also applied to
TACO's subgraph (`scripts/check_nice_food.py --data build/taco_nice_food.ttl`):

| Check | TACO's subgraph | NEVO's (`nevo21_graph.ttl`) |
| --- | ---: | ---: |
| Nutritional value without a CDNO class | 3,589 of 21,720 (17%) | 75,903 of 185,272 (41%) |
| Nutritional value without exactly one measure | 3,586 | 0 |
| Measure whose unit is only a string, not an OM unit | 478 | 26,010 |
| Food item without a FoodOn class | 0 of 597 (0%) | 357 of 1,657 (22%) |
| Two nutritional values of one nutrient for one food item | 0 | 7,295 |
| Available carbohydrate (CHO) without CDNO's available carbohydrate class | 0 | 3,314 |
| Nutrient whose code is `nan` | 0 | 1 |

On TACO's side:

- The values without a CDNO class are energy, RE, RAE, alcohol, cystine and the fatty acids whose isomer
  TACO does not give.
- The values without one measure are the trace and not-applicable cells.
- The string-only units are micrograms, which NEVO's subgraph writes the same way.
- All 597 TACO foods have a reviewed FoodOn class. This is coverage, not an accuracy estimate.

## A FoodOn finding

In the pinned FoodOn release, *meat (whole or pieces)* (`FOODON_03317170`) is a subclass of *mammalian meat
food product* (`FOODON_00001006`):

*chicken breast (cooked)* → *meat (cooked)* → *meat (prepared)* → *meat (whole or pieces)* → *mammalian meat
food product*

This path can place poultry typed as *meat (cooked)* or *meat (prepared)* in the query's mammalian category.
The query follows the pinned ontology hierarchy. Human review of food membership does not repair upstream
ontology axioms. Whether another FoodOn release changes this path has not been checked.

## What adding TACO to NICE-Food would take

- **Licence.** TACO's terms allow reproduction with the source cited
  ([data/SOURCES.md](../data/SOURCES.md)), so the subgraph can be shared, unlike NEVO's values.
- **Nutrient codes.** NICE-Food would decide whether other tables write NEVO's codes for the same component,
  as this subgraph does, or whether queries choose values by CDNO class, as the one-line variant does. The
  CDNO choice needs no table to adopt another's codes.
- **Missing values.** The pattern has no place for trace and not-applicable values; this subgraph keeps
  TACO's status on them.
- **FoodOn coverage.** All 597 foods have a reviewed FoodOn class. The completed evidence, supplementary
  adjudications and application marker are in [data/alignment/review/round-1/](../data/alignment/review/round-1/).

## Limits

- NICE-Food's query returns food names, not IRIs, so a row is counted as TACO's when its name is a TACO
  food's English name.
- Both tables calculate energy from the composition; whether they use the same conversion factors has not
  been checked.
- A value named by NEVO's code means the same component, not the same method of analysis.

## Reproducing

```powershell
$env:PYTHONPATH = "src"
python scripts\taco_to_nice_food.py
python scripts\load_triplestore.py --endpoint http://localhost:3030/nicefood --graph build\taco_nice_food.ttl --foodon
python scripts\run_nice_food_query.py queries\nice-food\protein_groups.rq
python scripts\run_nice_food_query.py queries\nice-food\protein_groups_cdno.rq
python scripts\check_nice_food.py --jar path\to\fuseki-server.jar --java path\to\java.exe --data build\taco_nice_food.ttl
```
