# Alignment review protocol

Version 1, 2026-09-24.

This protocol governs every review round under `data/alignment/review/`. Each round's `manifest.json`
records the SHA-256 of this file as it was when the round was prepared, and the scorer refuses a round
whose protocol has changed since. Changing this file therefore means preparing a new round.

## 1. What a round measures

A round judges the links between TACO foods and FoodOn classes in `data/alignment/alignments.csv`:
whether each link is right, and whether an unmapped food should have had one. It answers:

- how many links are right (precision), estimated for all links from a random sample;
- which food groups and which kinds of link fail, and how;
- how far two reviewers working independently agree (Cohen's kappa).

It does not judge group or nutrient mappings, and it does not rank candidate classes against each other
beyond what section 5 asks.

## 2. What a round contains

`scripts/prepare_alignment_review.py` draws three parts, recorded in `items.csv`:

| part | how it is chosen | what it supports |
| --- | --- | --- |
| sample | at random, a fixed number of foods from every stratum of food group × current link (`type`, `closeMatch`, `relatedMatch`, `none`), from a recorded seed | estimates for all links, weighted by stratum size |
| problem case | foods listed on purpose in `problem_cases.csv` | only statements about those foods |
| prepared dish | every food of the group *Alimentos preparados* | only statements about that group |

A food drawn in the sample stays in the sample even if it is also a problem case. The forms do not say
which part a food belongs to, and the rows come in a random order, so that reviewers treat every food the
same way.

## 3. The FoodOn release

All judgements are made against one FoodOn release:

- versionIRI `http://purl.obolibrary.org/obo/foodon/releases/2026-09-20/foodon.owl`;
- that PURL does not resolve, because FoodOn created no `v2026-09-20` tag. The file declaring the
  versionIRI is FoodOn commit `cd73540243a84bcd511a500d9a497d12d7dc02f6`,
  <https://raw.githubusercontent.com/FoodOntology/foodon/cd73540243a84bcd511a500d9a497d12d7dc02f6/foodon.owl>,
  SHA-256 `b897bf64c1b265c422db9ee01e1235c10c0b809e7f02326ef810a52068347edf`.

`ontology/imports/foodon-classes.tsv` lists every class of that release that is not deprecated, with its
label. A proposed class must be in it; the scorer refuses any other. OLS (<https://www.ebi.ac.uk/ols4/>)
is convenient for browsing, but it shows the current FoodOn, which may differ: check a class you find there
against `foodon-classes.tsv`. The definitions and candidates in the form come from OLS; the candidates are
kept only when the pinned release has them.

## 4. Reviewers

- Two reviewers fill in `reviewer-a.csv` and `reviewer-b.csv`. At least one of them took no part in
  creating the mappings under review.
- Reviewers know Brazilian foods and can read FoodOn class definitions. Before starting, both read this
  protocol in full and work through section 6 together on foods **outside** the round.
- Write a `notes.md` in the round folder, before scoring, stating for each reviewer and adjudicator: name,
  background, whether they took part in creating the mappings, and the dates they worked.

### Independence

- Do not discuss any food of the round, or look at the other form, until both forms are complete.
- Do not change the context columns (`food_number` to `foodon_release`). The scorer compares them with
  `context.csv` and refuses a form that differs.
- Reviewers see the current link, which may anchor them. Judge the link on its merits, and search as
  section 5 says even when the link looks right.

## 5. How to judge a food

1. **Read the TACO food.** The Portuguese name is authoritative; the English name is a translation aid
   and may be wrong (say so in `evidence` if it misleads). Establish what the food is: the organism or
   plant and, where given, species or variety; the part (fillet, leg, leaf, kernel); processing (salted,
   smoked, canned, frozen, dried); preparation (raw, cooked, boiled, fried, roasted); whether it is a
   dish of several ingredients. What TACO does not state is unknown, not absent.
2. **Read the FoodOn class.** Its label, its definition and its parents. Note every characteristic it
   states, and whether FoodOn places it under whole organisms or plants.
3. **Decide which relation holds** between the TACO food and the class (5.1).
4. **Search for a stronger link.** Look at the candidates in the form and search OLS at least by the
   English name and by the species or main ingredient. A link is right only if no class of the release
   supports a stronger relation (5.1, strength).
5. **Fill in the answer** (5.2).

### 5.1 Relations

From the strongest to the weakest:

| relation | holds when |
| --- | --- |
| `type` | the TACO food is a member of the class: everything the class states is true of the food as TACO describes it. The class may be more general than the food. Not allowed for classes of whole organisms or plants, or classes FoodOn places under them; the build refuses these. |
| `exact` | the class is defined as exactly this food, with nothing added or left out. For a food that is a member of the class, prefer `type`. |
| `close` | the class and the food could be used interchangeably to find or group foods, but `type` cannot be asserted, typically because the class is an organism or plant class. |
| `narrow` | the class is a more specific kind of the food: it states a characteristic (variety, origin, processing, form) that the TACO name does not state and that foods of that name need not have. |
| `broad` | the class is more general than the food and `type` cannot be asserted. Whenever the food is a member of the class, use `type` instead. |
| `related` | the class is a different thing associated with the food: its source when not interchangeable with it, an ingredient, a product made from it, a different preparation or a similar food. Say in the justification what the association is. |

Strength: `type` and `exact` > `close` > `narrow` and `broad` > `related`. A more specific class with the
same relation is not stronger: if the current class is right and a more specific one is also right,
accept, and name the more specific class in `evidence` as `more specific: FOODON_…`.

Rules that apply throughout:

- A class that states something the TACO name contradicts (raw against cooked, fresh against dried,
  another species) is never `type`, `exact`, `close` or `narrow`.
- A class that states something the TACO name does not state is `narrow`, not `type`, unless the Brazilian
  name itself entails it; cite the source that shows it does.
- A dish is not a member of its main ingredient's class; at most, the two are `related`.
- An organism or plant class is at most `close` to a food made from it.

### 5.2 The answer columns

| column | what to write |
| --- | --- |
| `decision` | `accept`, `relation`, `class`, `none` or `unsure`, as below |
| `relation` | for `relation` and `class`: `type`, `exact`, `close`, `narrow`, `broad` or `related` |
| `class` | for `class`: the identifier, such as `FOODON_03309834` |
| `certainty` | `certain`, or `uncertain` when the decision rests on something TACO does not state or on a reading of FoodOn you are not sure of |
| `justification` | one or two sentences naming what decides it: the characteristic that holds, is missing or is contradicted |
| `evidence` | what you consulted: FoodOn identifiers and quoted definitions, TACO documentation, references (URL or DOI) for Brazilian names and species |
| `reviewer` | your full name, the same on every row |
| `reviewed_on` | the date, `YYYY-MM-DD` |

Decisions:

| decision | for a linked food | for an unmapped food |
| --- | --- | --- |
| `accept` | the relation holds and no class supports a stronger one | no class of the release fits (same as `none`) |
| `relation` | the class is right, but another relation is the one that holds, or the strongest that holds | not allowed |
| `class` | another class supports the right relation, or a stronger one; give `relation` and `class` | a class was missed; give `relation` and `class` |
| `none` | the link is wrong and no class of the release fits | no class of the release fits |
| `unsure` | you cannot decide after the search in section 5; say why. Always `uncertain` | same |

An `unsure` answer leaves the food out of the results and its link unreviewed. Use it rarely.

### 5.3 Filling in the file

The forms are UTF-8 CSV with commas. Spreadsheet programs set to a Portuguese locale often save with
semicolons or another encoding: use LibreOffice Calc (UTF-8, comma), Google Sheets (download as CSV) or a
text editor, and do not reorder, add or remove columns or rows.

## 6. Scoring and adjudication

1. When both forms are complete, run `python scripts/score_alignment_review.py data/alignment/review/round-N`.
   It refuses incomplete or inconsistent forms, and forms whose inputs have changed since preparation.
2. It writes `adjudication.csv` with every food on which the reviewers disagree, both answers side by side.
   Agreement means the same decision and, where given, the same relation and class; for an unmapped food,
   `accept` and `none` agree.
3. The two reviewers, or a third person, decide each disagreement in the answer columns of that file,
   under the same rules. `reviewer` names whoever adjudicated; `justification` says why the answer chosen
   prevails.
4. Run the scorer again. It writes `results.md`, `results.csv` and `reviewed.sssom.tsv`.
5. Commit the round folder: forms, adjudication, results and `notes.md`. Do not edit them afterwards; a
   correction is a new round.

## 7. Applying a round

1. `python scripts/apply_alignment_review.py data/alignment/review/round-N` gives every reviewed food the
   mapping the review arrived at in `alignments.csv`; `unsure` foods are left as they were.
2. If it reports classes missing from the module, run `python scripts/extract_foodon_module.py`.
3. Build and validate. The graph marks each reviewed mapping `taco:Reviewed`, with its reviewers, review
   date, round and FoodOn release; all others stay `taco:Unreviewed`. The build refuses a mapping that
   differs from its latest review.

A later round supersedes an earlier one for the foods it reviews; a food it leaves `unsure` keeps its earlier
review. Once applied, a round no longer matches
the current inputs, and its scorer refuses to run again; the round's own files keep what it found.

## 8. What the results say, and what they do not

- **Precision** is estimated from the sample only, each stratum weighted by its size, with 95% Wilson
  intervals on the effective sample size of the stratified design. *Strict* precision counts a link as
  right only if it was accepted; *right class* also counts links whose class was kept with another
  relation. With few foods per stratum, the intervals are wide.
- **Problem cases and prepared dishes** were not drawn at random; their results describe those foods only.
- **Agreement** is reported before adjudication. Kappa is on the decision codes; it is not estimable when
  both reviewers use one code only.
- Reviewers saw the current links, so agreement is not an independent gold standard. A reviewed mapping is
  accountable, not infallible.
