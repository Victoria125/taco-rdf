# Verification

The project's own tests check its code on examples. The checks here verify it in independent ways: a proof
in Lean 4, a second implementation, a second engine, randomly generated cases, and the published source of the
data. They were run on 2026-11-16; the numbers below are from that run.

| Check | What it compares | Result |
| --- | --- | --- |
| [lean/TacoRules.lean](lean/TacoRules.lean) | Proofs, in Lean 4 (core, no Mathlib), of properties of the numeric rules | 21 theorems proved |
| [differential.py](differential.py) | The Python rules against their Lean model, on the same 27,401 cases, many exactly on a limit | 0 differ (after the fix below) |
| [boundary_impact.py](boundary_impact.py) | Every real TACO x NEVO comparison, as the code computes it and in exact decimal arithmetic | 0 change (after the fix) |
| [test_properties.py](test_properties.py) | Hypothesis: random TACO foods through the NICE-Food export; Spearman and quartiles against SciPy and NumPy | 4 properties hold |
| [shacl_crosscheck.py](shacl_crosscheck.py) | The SHACL checks of TACO's NICE-Food subgraph, by Jena and by pySHACL | same focus nodes for all 4 checks |
| [sparql_crosscheck.py](sparql_crosscheck.py) | NICE-Food queries on Fuseki and on rdflib | same rows |
| [pdf_crosscheck.py](pdf_crosscheck.py) | The exported values against TACO's printed PDF (Table 1, first half of each page pair) | 6,259 values in 569 foods, all the same |
| [cdno_parents.py](cdno_parents.py) | The parents of the 96 CDNO classes in use, in the loaded FoodOn release and in CDNO itself | 1 differs (below) |
| [lean/TacoTyping.lean](lean/TacoTyping.lean) | Proofs, in Lean 4 with Mathlib (Aesop, Plausible, `linarith`), of the FoodOn typing policy: types are inherited along subclass chains, so an organism ancestor makes a food an organism; only `type` rows to pinned, non-organism classes are published; counts split | all proved; Plausible finds no counter-example |
| [taco_typing_state.py](taco_typing_state.py) | Which TACO foods have a FoodOn type: the rule applied afresh to `alignments.csv`, `build/taco.ttl`, Fuseki and the audit CSVs; Lean checks the counts claimed on the 597 foods | all four agree: 311 typed, 286 untyped (125 with a historical candidate, 161 without, 35 with only blocked ones, 90 in round 1) |
| [taco_candidates_check.py](taco_candidates_check.py) | `scripts/taco_foodon_candidates.py`: the sheet's foods, the rule recomputed, name matches against Fuseki, known answers (each typed food with its type hidden), and Lean on the counts and the rule | 0 differ; for 70% of the 311 typed foods the type is among the candidates, for 83% it or a parent or child is |
| [test_candidate_properties.py](test_candidate_properties.py) | Hypothesis: the candidate rules on generated names and class sets | 5 properties hold |
| [organism_block_check.py](organism_block_check.py) | Why classes with an organism or whole-plant ancestor are refused: for each of the 677 candidate classes, a chain search (checked edge by edge in Lean), the owlrl RDFS reasoner on a made-up food typed with it, and Fuseki's property path; FoodOn's disjointness axioms; the chains of the 4 foods FoodOn places under a plant | all three find the same 86 classes; no disjointness between food and organism, so typing would silently make the food an organism; 28 of the 35 held-back foods now have a usable candidate |
| [type_review_check.py](type_review_check.py) | Round 2 as prepared (protocol version 2): forms, sample per group, checksums, candidates, no NEVO name; scoring simulated with identical, differing and invalid answers; Lean on counts, exclusion of round 1 and the allocation | 0 problems; every group's sample within one of its exact quota |
| [skos_check.py](skos_check.py) | Why foods link to FoodOn by `rdf:type` and not SKOS: NICE-Food's own graph; NICE-Food's protein query by Jena's ARQ on TACO with `rdf:type` and, in a temporary copy, with `skos:closeMatch`, against Fuseki; owlrl's RDFS closure with the W3C SKOS axioms; what converting the 125 SKOS candidate rows would entail; Lean on their counts and the rule | NICE-Food: 1,300 foods typed by `rdf:type`, SKOS only for `prefLabel`, 0 SKOS links to FoodOn; the query finds 105 TACO foods with `rdf:type` (Fuseki: 105) and 0 with `skos:closeMatch`; the closure gives no food a type and makes all 311 foods, and 288 FoodOn classes, `skos:Concept`; the 125 rows are 114 `relatedMatch` and 11 `closeMatch`, 123 with a note on why they differ, and converting them would make 35 foods organisms or plants |
| [test_type_review_properties.py](test_type_review_properties.py) | Hypothesis: allocation and sampling of round 2; `cohen_kappa` against a second implementation in exact fractions | 4 properties hold |

The Lean files with data are generated in `build/verification/` and checked with `lake env lean` in a Lake project that has Mathlib built (`--lake-project`); [lean/lakefile.toml](lean/lakefile.toml) pins the Lean and Mathlib versions. Each of these scripts also runs mutation tests on the Lean file it generates (skip them with `--no-mutants`): it breaks the data on purpose and requires Lean to reject the result, since a proof that accepts broken data proves nothing. The mutants are a claimed count off by one, a food typed in one source only, a class with an organism ancestor among the usable ones, a step that is no FoodOn edge, a food taken out of round 2's sample, and a round-1 food put in round 2. A mutation that does not change the file is reported as a problem, not taken as a pass: an early manual run missed this because the files then had Windows line endings, so they are now always written with LF.

The full test suite also passed: 354 tests, 1 skipped (330 before the FoodOn typing work of 2026-11-17).

## What the Lean proofs say

- **Available carbohydrate** (`scripts/taco_to_nice_food.py`):
  - it is never negative, and never more than total carbohydrate when fibre is zero or more;
  - with fibre at most the total, available carbohydrate plus fibre is the total;
  - it is zero when fibre exceeds the total, and zero when the total is negative and fibre is not applicable
    or a trace;
  - it is derived exactly when fibre has a number, is not applicable or is a trace.
- **EU labelling tolerances** (`scripts/compare_taco_nevo.py`):
  - for protein, available carbohydrate, fibre and fatty acids, the three cases form one band that never
    narrows as TACO's value grows, so there is no gap at 4, 10 or 40 g;
  - every value is within its own tolerance.
  - For sodium, the band does narrow at 500 mg, from ±150 to ±100 mg. That is the guidance's own salt rule
    (±0.375 g below 1.25 g of salt, ±20 % from there), which the code copies; the proof gives the example.
- **The composition check** (`scripts/check_food_pairs.py`): the water, mineral and 20 % rules do not depend on
  which table comes first, and two equal values never disagree.

## What the checks found, and what changed

1. **Floating-point arithmetic moved values that lie exactly on a limit.**
   - 1.45 x 20 is 28.999999999999996 in floating point, and the median of 0.6 and 0.7 is 0.6499999999999999.
     `differential.py` found such cases, and `boundary_impact.py` found one in the real comparison: an iron
     value (TACO 1.0 mg, NEVO median 0.65 mg) lies exactly on the lower EU limit but was counted outside it.
   - The comparisons now round values to nine decimals and allow 10^-9 at each limit. That is a thousandth
     of the data's last decimal, so no real difference is absorbed.
   - The iron row of [analysis/taco_nevo_comparison.md](../analysis/taco_nevo_comparison.md) changed from 38 %
     to 40 % within the EU tolerance. Nothing else changed: no 20 % result and no flag of the composition
     check.
   - `tests/test_comparison_limits.py` keeps the cases.
2. **`analysis/comparison_helper.py` raised an error when every value on one side was the same.** Spearman's rho
   is undefined then. It is now left out, as `scripts/compare_taco_nevo.py` already did. No current result was
   affected; the full TBCA could have hit it.
3. **The loaded FoodOn release gives CDNO's carbohydrate class the wrong parent.**
   - In FoodOn's release of 2026-09-20, *concentration of carbohydrate* (CDNO_0200005) is a subclass of
     *concentration of ash* (CDNO_0200004).
   - CDNO itself (release 2026-06-10, still the latest) has it under *concentration of dietary chemical
     component* (CDNO_0200001).
   - FoodOn's definitions do not imply it either: no path leads from carbohydrate (CHEBI_16646) to ash
     (ENVO_02000090).
   - The project's queries use exact CDNO classes and are not affected. A query climbing CDNO's hierarchy in a
     store with this FoodOn would count carbohydrate as ash.
   - It sits next to the earlier FoodOn finding, cooked chicken under mammalian meat.

## What the checks did not do

- The Lean proofs are about a model of each rule. `differential.py` ties the model to the code case by case;
  it does not prove the code for every possible input.
- The PDF check reads 11 of the 26 columns of Table 1, and 569 of 597 foods: the PDF's text splits the other
  columns and rows too badly to read safely.
- The SPARQL check leaves FoodOn out of rdflib, so labels and queries over FoodOn's hierarchy are not compared;
  the comparison of four engines in [triplestore/README.md](../triplestore/README.md) covers those queries.
- None of this checks TACO's values against new analyses of the foods; see
  [analysis/taco_reliability.md](../analysis/taco_reliability.md).

## Running them

Hypothesis, SciPy and pypdf are not project dependencies; install them in a separate folder and add it to
`PYTHONPATH`. Lean 4 must be on the PATH, and Fuseki must be running for the SHACL, SPARQL and CDNO checks.

```powershell
pip install --target $env:TEMP\verifylibs hypothesis scipy pypdf
$env:PYTHONPATH = "src;$env:TEMP\verifylibs"
lean verification\lean\TacoRules.lean
python verification\differential.py
python verification\boundary_impact.py
python -m pytest verification\test_properties.py
python verification\shacl_crosscheck.py --jar path\to\fuseki-server.jar --java path\to\java.exe
python verification\sparql_crosscheck.py
python verification\pdf_crosscheck.py
python verification\cdno_parents.py --cdno path\to\cdno.owl
```
