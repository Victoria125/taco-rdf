# Alignment review protocol, version 3: FoodOn types for every TACO food

Version 3. Effective 2026-11-18 for the review of FoodOn types, round 1. It follows [version 2](alignment-review-v2.md) in what a reviewer decides and how; it differs in which foods are reviewed, by whom, and what is measured.

## 1. This review

This is the review of TACO's FoodOn types: two reviewers, all 597 TACO foods, `rdf:type` only. An earlier pilot under [version 1](alignment-review.md), which judged mixed relations (types and SKOS mappings), was discarded when the project moved to `rdf:type` only ([docs/foodon-typing.md](foodon-typing.md)); its forms are not part of this review.

## 2. What the review measures

One question per food, as in version 2:

> Of which FoodOn class is this food, as TACO describes it, a member, if any?

Both reviewers answer every food. The review measures:

- coverage: how many foods get a FoodOn type;
- agreement: how often the two reviewers, working independently, reach the same decision, on every food;
- for the 311 foods that already have a type ([analysis/foodon_typing.md](../analysis/foodon_typing.md)), how often the reviewers' decisions confirm it.

## 3. What the review contains

`data/alignment/review/round-1/`, written by `python scripts/prepare_type_review.py` (protocol 3, the default) from the candidate sheet of `python scripts/taco_foodon_candidates.py --ols --all-foods`:

- `items.csv`: the 597 foods and their TACO group.
- `reviewer-1.csv` and `reviewer-2.csv`: the two forms, each with every food.
- `context.csv`: the columns of the forms that reviewers do not change.
- `manifest.json`: the protocol version, the checksums of the inputs and files, and the pinned FoodOn release.

Each form row gives the food's Portuguese and English names, its group, and candidate classes, as in version 2, section 2: only classes the build could publish, with their FoodOn labels and the sources that proposed them, and no NEVO food name.

The 311 typed foods are presented blind. Their form rows do not say that they have a type or which. Their candidates are searched as for any food, except that they get no history candidate, which is where their type came from, and that a food is never its own similar TACO food. Their current type is among the candidates only when a search finds it again. The current types are not in the review's folder; scoring reads them from `analysis/data/foodon_types.csv`.

## 4. The FoodOn release

As in version 2, section 3: the release pinned in [ontology/imports/foodon-classes.tsv](../ontology/imports/foodon-classes.tsv) (2026-09-20).

## 5. Reviewers

Two reviewers. Before either starts, `notes.md` records each reviewer's name, background, and any relation to the project's author, and who will adjudicate.

Independence, as in version 1, section 4, and also:

- each reviewer receives only their own form, this protocol and `context.csv`;
- the reviewers do not consult the repository, `analysis/data/foodon_types.csv` or the project's reports until both forms are complete, since these show the current types;
- an assistant helping one reviewer carries neither the other's answers nor the current types.

A third person, recorded in `notes.md`, adjudicates disagreements.

## 6. How to judge a food

As in version 2, section 5: the decision is the CURIE of one FoodOn class of the pinned release, or `none`; the most specific class TACO's description justifies; never a class of a whole organism or plant, or one FoodOn places under one; `none` with the terms searched. The answer columns are `decision`, `justification`, `searched_terms` and `unsure`. One row per food; no rows added or removed; the other columns are not changed.

## 7. Scoring and adjudication

`scripts/score_type_review.py` checks every decision as in version 2, section 6. With both forms complete it reports, over all 597 foods, exact agreement, Cohen's kappa and, with a SPARQL endpoint, near agreement, and writes `adjudication.csv` with the foods whose decisions differ. The adjudicator decides each, with a justification.

For the 311 typed foods, the agreed or adjudicated decision is then compared with the current type: the same class, an ancestor or descendant of it, another class, or `none`. That comparison is reported; it is computed once both forms are complete and is not shown to the reviewers.

## 8. Applying the round

Accepted decisions become `type` rows for food alignments. Where a decision differs from a current type, the current type changes only after adjudication, and the change is recorded with the review. Applying is outside this version of the scripts.

## 9. What the results say, and what they do not

As in version 2, section 8. Agreement on every food estimates how reproducible the decisions are, not that agreed decisions are right. That the reviewers confirm a current type supports it; that they do not is a case for review, not proof that it is wrong.
