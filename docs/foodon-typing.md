# FoodOn typing policy

Effective 2026-10-08.

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

A FoodOn axiom conflict is a different case. Some food classes are placed by FoodOn under whole plants: in the pinned release, `scallion (raw)` is_a `scallion` is_a `scallion plant`, and `bean pod` is_a `bean sprout` is_a `bean plant`. Foods 108, 125, 162 and 250 keep such classes as `closeMatch` candidates. FoodOn has a class for them, so they are not ontology gaps; but typing with it would entail that the food is a plant, so the build withholds it. The audit marks these candidates `foodon_axiom_conflict`, separately from candidates that are organism classes (`organism_class`), and the conflicting axioms should be reported to FoodOn.

The absence of a published type initially means unresolved coverage. It becomes evidence of an ontology gap only after a documented search fails to find a defensible class. Missing data about the TACO food and unfinished review can also explain an unresolved item. No automatic conversion of `closeMatch`, `relatedMatch`, `narrowMatch`, `broadMatch` or `exactMatch` to `type` is permitted.

## Publication and retained evidence

`data/alignment/alignments.csv` retains the original food candidate rows because the ongoing review round checksums this input. Food rows with `predicate=type` produce a direct `rdf:type` triple and its `taco:AlignmentAssertion`. SKOS food rows to FoodOn classes produce neither a direct food mapping nor an alignment assertion in the published graph. Group and nutrient SKOS mappings retain their existing roles, and a SKOS food row to another dataset's item would be published like them.

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

## Compatibility with round 1

`docs/alignment-review.md` is version 1 of the review protocol. Round 1 records its checksum, the source alignment checksum and the checksums of its context, sample, names, ontology inputs and corrections. Those files and the reviewer answers are not rewritten to adopt the publication policy.

Round 1 continues to assess its historical mixed-relation baseline under its original protocol. Its agreement and precision estimates must be reported as results for that baseline, not as the accuracy of the current published `rdf:type` subset. A new assessment under a type-only protocol requires a separately versioned protocol and newly prepared round; the current preparation command still uses version 1.

Reviewer A's proposed replacements are individual judgements. Reviewer B's independent answers and adjudication are required before the existing workflow can score and apply a completed round. The publication change does not apply Reviewer A's proposed classes automatically or label them as independently reviewed.

After a completed historical round is applied, its `type` outcomes can be published with review provenance. SKOS outcomes remain unpublished evidence. A `none` outcome leaves no FoodOn type. An `unsure` outcome does not establish an ontology gap. The build still requires the source rows to agree with the latest completed review, including candidates excluded from publication, so review results cannot be silently overwritten.
