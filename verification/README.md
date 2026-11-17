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

The full test suite also passed: 330 tests, 1 skipped.

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
