# Alignment review protocol, version 2: FoodOn types only

Version 2. Effective 2026-11-17 for round 2. Version 1 ([alignment-review.md](alignment-review.md)) still governs round 1, which assesses the historical mixed-relation baseline.

## 1. What round 2 measures

Since [the FoodOn typing policy](foodon-typing.md), a TACO food is linked to FoodOn by `rdf:type` only. 286 of TACO's 597 foods have no type ([analysis/foodon_typing.md](../analysis/foodon_typing.md)). Round 1 sampled 90 of them; they stay with round 1 until it is adjudicated. Round 2 covers the other 196, and asks one question per food:

> Of which FoodOn class is this food, as TACO describes it, a member, if any?

Round 2 gives each food a reviewed decision, and on a sample it measures how often two reviewers working independently reach the same one.

## 2. What the round contains

`data/alignment/review/round-2/`, written by `scripts/prepare_type_review.py`:

- `items.csv`: the 196 foods, their TACO group, and whether the second reviewer's sample holds them.
- `reviewer-1.csv`: the form for the first reviewer, with every food.
- `reviewer-2.csv`: the form for the second reviewer, with the sample only.
- `manifest.json`: the protocol version and checksum, the checksums of the inputs, the pinned FoodOn release, the sample size and the random seed.

Each form row gives the food's Portuguese and English names, its group, and candidate classes. The candidates come from `scripts/taco_foodon_candidates.py`, which searches TACO's English name, similar typed TACO and NEVO foods, and EBI's Ontology Lookup Service. Only candidates the build could publish are listed: classes of the pinned release with no whole organism or plant among their ancestors. Each is shown with its FoodOn label and the sources that proposed it. The forms hold no NEVO food name.

A candidate is a suggestion, not an answer. The class chosen may be any class of the pinned release.

## 3. The FoodOn release

The release pinned in [ontology/imports/foodon-classes.tsv](../ontology/imports/foodon-classes.tsv) (2026-09-20). Classes are looked up in it, or in OLS with a check that the class is in the pinned release.

## 4. Reviewers

Two reviewers, as in version 1, section 4, including its independence rules: neither sees the other's form or notes before both are complete, and an assistant helping one reviewer must not carry the other's answers. The first reviewer answers every food; the second answers the sample. A third person adjudicates disagreements and is recorded in `notes.md`.

## 5. How to judge a food

### 5.1 The decision

`decision` is either the CURIE of one FoodOn class, such as `FOODON_03301449`, or `none`.

Choose a class when the food is a member of it: everything the class states holds for the food as TACO describes it (name, Portuguese and English, preparation in TACO's Appendix 2, and species in Quadro 7). Among such classes, choose the most specific one the description justifies. A more general class is right when no more specific one is justified. A class that requires a species, variety, preparation or ingredient that TACO does not state is not justified by similarity alone.

Never choose a class of a whole organism or plant, or a class FoodOn places under one: `rdf:type` is inherited along `rdfs:subClassOf`, so the food would become an organism (proved in [verification/lean/TacoTyping.lean](../verification/lean/TacoTyping.lean)). FoodOn places some food classes under plants by mistake (for example, `bean pod` is_a `bean sprout` is_a `bean plant`). For such a food, choose the nearest general food class that FoodOn does not place under a plant, and note the conflicting axiom so that it can be reported to FoodOn.

Choose `none` when no class of the pinned release is justified, and say which terms were searched.

### 5.2 The answer columns

| column | content |
| --- | --- |
| `decision` | a FoodOn CURIE, or `none` |
| `justification` | why the food is a member of the class, or why no class fits |
| `searched_terms` | the terms searched beyond the candidates; required for `none` |
| `unsure` | `yes` when the reviewer is unsure; empty otherwise |

### 5.3 Filling in the file

One row per food; no rows added or removed. The form is CSV in UTF-8. The other columns are not changed.

## 6. Scoring and adjudication

`scripts/score_type_review.py` checks every decision: a CURIE of the pinned release or `none`, and, given a SPARQL endpoint with FoodOn, no organism or plant ancestor. On the sample it reports:

- exact agreement: the share of foods with the same decision;
- Cohen's kappa over the decisions, computed as in version 1 (`taco_rdf.evaluation.cohen_kappa`);
- with an endpoint, near agreement: the decisions are the same class, or one is an ancestor of the other.

It writes `adjudication.csv` with the sample foods whose decisions differ. The adjudicator decides each, with a justification. For foods outside the sample, the first reviewer's decision stands.

## 7. Applying the round

Accepted decisions become `type` rows for food alignments. Round 1 records a checksum of `data/alignment/alignments.csv`, so round 2 is applied to it only after round 1 is scored and applied, or through a separate input that the build reads beside it. Applying is outside this version of the scripts.

## 8. What the results say, and what they do not

The number of foods typed is coverage, not accuracy. Agreement on the sample estimates how reproducible the decisions are; it does not show that agreed decisions are right. A `none` decision becomes evidence of a FoodOn gap only with its searched terms. The candidates' measured quality (for 70% of the 311 typed foods, their type is among the candidates; see [verification/README.md](../verification/README.md)) describes the candidate search, not the reviewed decisions.
