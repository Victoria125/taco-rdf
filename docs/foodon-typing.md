# FoodOn typing policy

Effective 2026-10-08; completed type-only review applied 2026-11-19.

The published TACO food-to-FoodOn relationship is `rdf:type`: the TACO food must be a member of the FoodOn class. This adopts the class-membership modelling approach used by NICE-Food in its [NEVO](https://github.com/rivm-syso/nicekg_processing/blob/main/nevo_processing.ipynb), [LEDA](https://github.com/rivm-syso/nicekg_processing/blob/main/leda_processing.ipynb), [KAP](https://github.com/rivm-syso/nicekg_processing/blob/main/kap_processing.ipynb) and [LCA](https://github.com/rivm-syso/nicekg_processing/blob/main/lca_processing.ipynb) processing notebooks (checked 2026-10-08). NICE-Food uses SKOS for other relationships, such as `skos:prefLabel` on NEVO items and `skos:closeMatch` from LCA items to NEVO codes. This policy concerns food-to-FoodOn links only: a SKOS link from a TACO food to an item of another dataset remains allowed.

The FoodOn target must be a non-deprecated class in the pinned release, and the build rejects classes that have whole organisms or plants among their ancestors, because `rdf:type` would make the food a member of every ancestor. NICE-Food's notebooks add the annotated class without this check; TACO-RDF is stricter on purpose.

For example, food 92 is published as follows. Like a NEVO item in NICE-Food's `nevo_processing.ipynb`, it is a `fio:FoodItem` and an instance of its FoodOn class:

```turtle
@prefix tacoid: <https://w3id.org/taco-rdf/id/> .
@prefix fio: <http://www.foodvoc.org/resource/fio#> .
@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .

tacoid:food/92
    rdf:type fio:FoodItem, <http://purl.obolibrary.org/obo/FOODON_03301449> ;
    rdfs:label "Batata, inglesa, crua"@pt .
```

`FOODON_03301449` is `potato (raw)`.

## Choosing a class

Every characteristic required by the class must hold for the food as described by TACO. A more general food-product class is acceptable; a more specific class that requires an unstated species, variety, preparation or ingredient is not justified by similarity alone.

A cooked fish food is not thereby an instance of a class describing the whole fish organism. A prepared dish is not thereby an instance of its main ingredient's class. Search for a defensible food-product class, including a more general one. If the search finds none, leave the food without a FoodOn type and record the searched terms, rejected candidates, pinned release and reason in the review evidence.

A FoodOn axiom conflict is a different case. Some food classes are placed by FoodOn under whole plants: in the pinned release, `scallion (raw)` is_a `scallion` is_a `scallion plant`, and `bean pod` is_a `bean sprout` is_a `bean plant`. These were historical candidate conflicts. The completed review chose permitted final classes; none of the 597 applied decisions reaches the organism or plant roots. The previous candidates remain in the frozen baseline and original reviewer evidence.

The absence of a published type initially means unresolved coverage. It becomes evidence of an ontology gap only after a documented search fails to find a defensible class. Missing data about the TACO food and unfinished review can also explain an unresolved item. No automatic conversion of `closeMatch`, `relatedMatch`, `narrowMatch`, `broadMatch` or `exactMatch` to `type` is permitted.

## Publication and retained evidence

`data/alignment/alignments.csv` now contains the 597 confirmed food type decisions. The original alignment and audit inputs are preserved in `data/alignment/review/round-1/baseline/`. Food rows with `predicate=type` produce a direct `rdf:type` triple and its `taco:AlignmentAssertion`. SKOS food rows to FoodOn classes produce neither a direct food mapping nor an alignment assertion in the published graph. Group and nutrient SKOS mappings retain their existing roles, and a SKOS food row to another dataset's item would be published like them.

The retained SKOS rows remain useful search evidence: they identify possible ingredients, organisms or preparations to investigate. Retaining a candidate does not assert that it is a valid FoodOn type, and suppressing it does not assert that no suitable class exists. The source CSV therefore must not be counted or distributed as an export of the published food mappings.

Run:

```bash
python scripts/audit_foodon_typing.py
```

This writes:

- `analysis/foodon_typing.md`: published typing coverage and unresolved-food counts;
- `analysis/data/foodon_types.csv`: the food-to-FoodOn mappings selected for publication;
- `analysis/data/foodon_typing_gaps.csv`: foods without a published type, with retained candidate evidence, why the FoodOn module cannot back each candidate (`candidate_obstacle`) and review status.

These outputs distinguish pending review from reviewed outcomes. Coverage counts are not accuracy estimates. The older `analysis/alignment_baseline.md` and its generation script describe the historical input rows, including SKOS candidates; their counts answer a different question.

## Completed type-only round 1

The active round uses `docs/alignment-review-v3.md`. Josandra Semedo and Elizabete Wensel each answered for all 597 foods. Their exact agreement was 400/597 (67.00%; kappa 0.66943). Crislane Timbo supplied 246 unique adjudications, including supplementary agreed cases. The remaining 351 decisions retain the independent agreement. The user confirmed Crislane's authorship and completion of all returned sheets.

The application validates source checksums, context, original answers, adjudication reasons, final decisions and the pinned FoodOn hierarchy before changing alignments. `application.json` activates the round. A later edit to the evidence or an applied class is rejected during a build. Frozen pre-review audit inputs keep the manifest reproducible after audits are regenerated.

All 597 foods now have one FoodOn type, using 469 distinct classes. Of the 311 previously typed foods, 222 retain the same type and 89 change; 286 previously untyped foods receive a type. Original forms, receipt and adjudication remain preserved. The discarded mixed-relation pilot is not the current review and its statistics must not be used for this completed round.

The independent checker `verification/type_review_application_check.py` compares each final food/class pair across evidence, alignments, audits and both RDF exports. Lean 4 checks resolution rules and finite certificates; deliberate mutations test whether the checks reject errors. These checks establish faithful application of the human decisions, not an independent nutritional judgement.
