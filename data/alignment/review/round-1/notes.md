# Review of FoodOn types, round 1 (protocol 3)

Protocol: [docs/alignment-review-v3.md](../../../../docs/alignment-review-v3.md). Forms prepared on 2026-11-18 by
`scripts/prepare_type_review.py`; checked by `verification/type_review_v3_check.py`.

## Reviewers

Filled in before either reviewer starts (protocol, section 5).

| Role | Name | Background | Relation to the project's author |
| --- | --- | --- | --- |
| Reviewer 1 (`reviewer-1.csv`) | Josandra Semedo | Nutritionist; master's student in nutrition, UECE | to record |
| Reviewer 2 (`reviewer-2.csv`) | Elizabete Wensel | BSc in nutrition, USP | to record |
| Adjudicator | Crislane Timbo | Nutritionist | to record |

Each reviewer received an Excel workbook made from her form by `scripts/review_workbook.py export`, with
instructions in Portuguese; returned workbooks go back into the forms with `scripts/review_workbook.py import`.

## What each reviewer receives

Only their own form, the protocol and `context.csv`. Not the other form, not `items.csv`, not
`analysis/data/foodon_types.csv` or the project's reports, until both forms are complete.

## Sessions

| Date | Reviewer | Foods answered | Helped by |
| --- | --- | --- | --- |

## Receipt and adjudicator assignment — 2026-11-19

Both completed workbooks were received locally in `C:/taco-rdf/revisao/respostas/`.
The author named Crislane Timbo, nutritionist, as the third-person adjudicator on 2026-11-19,
after receipt of both forms. This records the actual assignment date; it was not recorded before
the reviewers started as section 5 of the protocol requested.
The reviewers' working dates, any assistance, relations to the author, confirmation of independence,
and permission to publish personal attribution remain to be recorded; workbook contents do not establish them.

### Imported responses and preliminary results

Both forms now contain the 597 received answers, including their original justifications, searched terms,
and uncertainty flags (`sim` in Excel becomes `yes` in CSV). Context columns match the prepared forms.
The original workbooks were not edited. Their raw SHA-256 checksums are:

- Reviewer 1: `33928cec372fae4a89ad983d922045aaa555c9af74c3f52c62cff803e4334ff6`.
- Reviewer 2: `6809807c6dbc9cfecd1e911483c47e8576189c7ca4052364a2fb759bee7fb1d9`.

Raw exact agreement: 400/597 (67.0017%); Cohen's kappa: 0.669432428558178.
Same class or ancestor/descendant agreement: 424/597 (71.0218%), checked against the pinned local FoodOn
file, SHA-256 `b897bf64c1b265c422db9ee01e1235c10c0b809e7f02326ef810a52068347edf`.
No OWL inference was used; these are explicit transitive/reflexive `rdfs:subClassOf` paths.

These are received-response statistics, not accepted mappings. Nine choices across seven foods violate
the organism/plant rule: reviewer 1, foods 125, 162, 250, 314; reviewer 2, foods 108, 125, 250, 288, 298.
Food 250 (tamarind) is an exact agreement but still blocked. The received choices remain unchanged as evidence.

`adjudication.csv` holds the 197 disagreements produced by `score_type_review.py` without an endpoint;
that invocation does not check the hierarchy and must not be treated as final validation.
The complete adjudication queue has 236 distinct foods: those 197 disagreements, 38 agreements that
would change existing types (protocol section 8), and the additional blocked agreement on food 250.
Of the 311 existing types, 208 are confirmed by agreement, 38 have a different agreed proposal, and
65 await resolution of disagreement. Thirteen agreements also carry an uncertainty flag.

The local handoff is `C:/taco-rdf/revisao/analise-2026-11-19/TACO_FoodOn_desempate.xlsx`, prepared for
Crislane Timbo with empty final-decision and justification fields. The same directory holds `resumo.md`,
`resultados.json`, `ancestralidade.json`, `fila_completa.csv`, the detailed comparisons, and backups of the
empty forms in `formularios-antes/`. The workbook separates disagreements, changes to existing types,
and the additional blocked agreement, and includes the nine hierarchy warnings.

No reviewed decision has been applied to alignment inputs or RDF outputs. Preserve completed adjudication
before rerunning `score_type_review.py`, which overwrites `adjudication.csv`. The preparation checker
`verification/type_review_v3_check.py` expects empty forms; it is not a checker for returned answers.

The importer regression tests passed (17), as did the available type-review unit tests (5 passed,
2 skipped because the old round 2 is absent); targeted Ruff checks passed. A separate comparison
confirmed every imported answer against the received workbooks and verified 236 distinct foods with
empty final fields in the adjudication workbook. These checks do not certify semantic correctness.

## Completed adjudication

The author explicitly confirmed that Crislane Timbo authored and approved the returned decisions,
including the additional `Dúvidas com acordo` sheet. At the author's request, the incorrect AI/pending-review
attribution in the returned workbook's guide was corrected. The answer sheets and justifications are
unchanged; the original bytes and the four changed guide-cell addresses are retained locally in
`C:/taco-rdf/revisao/desempate-2026-11-19/arquivo-como-recebido/` and `correcao_identificacao.json`.

The workbook contains 236 required decisions and 13 supplementary opinions. Three supplementary items
(45, 341, 565) duplicate required items with identical decisions and justifications. The 246 distinct
confirmed decisions, plus 351 original reviewer agreements, give one consolidated class for all 597 foods.
All 469 distinct final classes are present in the pinned FoodOn index; no final class has a whole-organism
or plant ancestor in the checked hierarchy. The nine original hierarchy-blocked choices have been resolved.

`adjudication.csv` now records the 197 original disagreements. `adjudication-additional.csv` records
the remaining 49 decisions; `adjudication-all.csv` records all 246 with the source sheets and justifications.
`reviewed-types.csv` records all 597 consolidated decisions and retains both original reviewers' reasons,
search terms and uncertainty flags. `adjudication-receipt.json` records confirmation, checksums and counts.
The reviewer forms and the prepared-round manifest were not changed by consolidation.

Against the 311 previously typed foods, 222 retain their class and 89 change: 6 to an ancestor,
7 to a descendant and 76 to another class without an ancestry relation. The 286 previously untyped foods
have a class in the consolidated review. The original independent agreement remains 400/597 (67.0017%),
with kappa 0.669432428558178; adjudication does not replace that statistic with post-resolution agreement.

## Application on 2026-11-19

The protocol-3 application path is now implemented and the completed review is active through
`application.json`. All 597 food types were applied to alignments, the regenerated FoodOn module,
native RDF and NICE-Food export. Original audit inputs and alignment rows remain under `baseline/`;
the original forms, protocol hashes and adjudication receipt are preserved.

An independent verifier compared all 597 exact decisions and reviewer provenance, confirmed unchanged
nutritional triples, and checked the actual finite certificates in Lean 4. Nine general theorems and
25 data theorems passed; seven deliberately invalid certificates were rejected. Results are in
`build/verification/review_application/`. The delivery summary is
`C:/taco-rdf/revisao/aplicacao-2026-11-19/resumo.md`.

The older receipt's `alignment_inputs_updated=false` and `rdf_rebuilt=false` describe the earlier
consolidation stage. The separate activation marker records subsequent application without rewriting
that historical receipt.
