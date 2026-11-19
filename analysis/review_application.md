# FoodOn review application: verified handover (19 November 2026)

This report records the **applied protocol-3 FoodOn typing decisions** for the 597 TACO foods and distinguishes currently observed CI results from earlier local verification results. It is an engineering/provenance report; it is **not** evidence of nutritional classification accuracy or independently established reviewer authorship.

## Final applied mapping

- 597/597 foods have one consolidated FoodOn class; 469 distinct FoodOn classes.
- 351 agreements were retained and 246 distinct adjudication decisions applied.
- The adjudication materials cover 197 original disagreements, 38 agreements changing the prior type, 13 supplemental uncertainty entries (three duplicating required cases), and one otherwise blocked agreement.
- Against the earlier 311 typed foods, 222 classes were retained and 89 changed; the remaining 286 foods were newly typed.
- Original agreement was 400/597 (67.00%); Cohen's kappa 0.669432428558178. Neither agreement nor full coverage is an accuracy estimate.
- The 597 food identifiers and final classes in the delivered handover workbook were independently reconstructed from the original reviewer-1 workbook and adjudication workbook, and matched all 597 id/class pairs in `data/alignment/review/round-1/reviewed-types.csv` (canonical `food_number|decision\n` CRC32 = `2842993818`). CRC32 is an inexpensive cross-check, **not** a cryptographic authenticity proof; the repository separately stores SHA-256 input manifests.
- Review session dates, assistance, independence, relationships to the author and permission to publish personal attribution remain unconfirmed in `data/alignment/review/round-1/notes.md`. Do not infer these from the forms.

## Repository evidence

- Decision table: [reviewed-types.csv](../data/alignment/review/round-1/reviewed-types.csv)
- Source and adjudication inputs: [round-1/](../data/alignment/review/round-1/)
- Application marker and input hashes: [application.json](../data/alignment/review/round-1/application.json)
- Review protocol: [alignment-review-v3.md](../docs/alignment-review-v3.md)
- Recorded earlier formal verification: [verification/README.md](../verification/README.md)
- NICE-Food comparison: [taco_nice_food.md](taco_nice_food.md) and [nutrient_definitions.md](nutrient_definitions.md)

## Verification (current clean CI)

GitHub Actions run [44575639962](https://github.com/Victoria125/taco-rdf/actions/runs/44575639962) on commit `f9280d2cf398693c83656158524888a80906a2db` **succeeded**:

- `ruff check src tests scripts`: passed.
- `pytest -q`: **427 passed, 3 skipped, 3 warnings**, 0 failures.
- The previous CI failure was a missing runtime dependency, `requests`; this was corrected by adding `requests>=2.31` to the main dependencies in `pyproject.toml`.
- CI currently tests Python code. Earlier documented Lean, Fuseki and SHACL checks are separate; the CI success does not imply those were rerun.

## Previously documented independent checks (not rerun in this handover)

The earlier local verifier reports 597 final mappings and their provenance matched across review data, alignments, native RDF, and NICE-Food export. It reports no change to 159,301 native and 178,860 NICE-Food nutritional triples relative to the frozen pre-application data, 9 general + 25 concrete Lean 4 theorems accepted by the kernel, and seven invalid certificates rejected. Those conclusions depend on the local baseline and data extraction; see [verification/README.md](../verification/README.md). The kernel does not establish the nutritional correctness of human choices.

The generator [verification/review_application_report.py](../verification/review_application_report.py) produces a Portuguese delivery report and XLSX, but expects the *local*, ignored `build/verification/review_application/` files and two pytest XML runs. Its published report-generation path is **not runnable from the GitHub checkout alone**. Do not represent this handover as a successful fresh run of that generator.

## Outstanding release-readiness items

1. Confirm/record provenance and publication authorization of review-form contributors. Preserve original signed/received evidence where available.
2. Re-run the review application verifier, SHACL and generated Lean certificates in a reproducible environment with the pinned external FoodOn release, baseline and local Fuseki datasets. Archive logs and input hashes.
3. Validate semantic nutrient comparability (seven method definitions remain to confirm), total-versus-available carbohydrate, energy computation conventions and sodium `NA` ingestion in the NEVO data.
4. Enable/configure GitHub Pages if site publication is desired: the separate [Pages workflow](https://github.com/Victoria125/taco-rdf/actions/runs/44575639862) failed on `deploy-pages` with HTTP 404 and suggested Settings > Pages.
5. Tag and cite a new release only after these provenance, quality and publication requirements are met; `CITATION.cff` currently describes v0.1.0.

## Scope of the integration

The local `nicefood` Fuseki dataset includes TACO, NEVO and the pinned FoodOn hierarchy; the unchanged NICE-Food protein query returns 185 TACO and 369 NEVO rows. This is a working interoperability demonstration, not production deployment into WUR's canonical NICE-Food service. NEVO individual values should not be redistributed through this repository.
