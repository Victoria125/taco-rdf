# Proposed release 0.2.0 — draft (not tagged or published)

## Proposed scope

This release candidate documents the applied protocol-3 FoodOn review and the NICE-Food interoperability snapshot dated 19 November 2026.

### Included in the working tree

- Final FoodOn classification for all 597 TACO foods using 469 distinct classes.
- 246 adjudicated decisions and 351 retained agreements; original review inputs, provenance receipts and frozen baseline retained.
- NICE-Food-compatible TACO export that follows FIO + FoodOn + CDNO + OM structure and is queryable alongside a locally loaded NEVO graph.
- Code-based and CDNO-based protein queries with documented equality of 554 rows (369 NEVO + 185 TACO in the recorded run).
- Independent verification scripts and Lean core proofs; an additional Lean proof-check GitHub workflow is being introduced.
- Fix for the missing Python `requests` runtime dependency (commit f9280d2), with clean CI on that commit: 427 tests passed and 3 skipped.
- A complete, conservatively scoped application/handover report in [analysis/review_application.md](../analysis/review_application.md).

### Release blockers (must not be silently marked complete)

1. Confirm review-session dates, assistance, independence and publication permission for named contributors. The workbook alone does not establish these facts.
2. Archive an up-to-date complete application report from `verification/review_application_report.py` with verified local inputs, the two pytest XML runs, native and NICE-Food RDF, and Lean-generated data certificates.
3. The standalone [Lean 4 core CI job](https://github.com/Victoria125/taco-rdf/actions/runs/44580362375) passed for `TacoRules.lean` and `TypeReviewApplication.lean`. Still rerun the full data-specific certificate when its pinned external inputs are present.
4. Decide on the seven nutrient-method equivalences, carbohydrate and energy semantics, and NEVO sodium `NA` ingestion.
5. Enable GitHub Pages via repository settings if website deployment is desired; current job returns HTTP 404.
6. After scientific and publication sign-off, synchronously update `pyproject.toml`, the module version, `ontology/taco.ttl`, `CITATION.cff`, `.zenodo.json`, changelog/tag and Zenodo metadata. Do not reuse an earlier DOI as if it denoted the new data release without checking the publication process.

## Important limits

- The CI suite is Python tests, not an ontology or nutritional accuracy proof.
- A FoodOn type match is not a statement that foods have identical measured composition.
- Recorded Lean proofs check specified formal properties and certificates, not reviewer independence or the appropriateness of the reviewer-selected class.
- The official WUR NICE-Food production graph has not been changed by this repository.
- NEVO values remain outside the redistributable repo.

**Status: draft for research-team discussion; not a formal release or citable new version.**
