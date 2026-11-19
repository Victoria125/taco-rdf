# Verification

## Completed review application — 2026-11-19

All 597 foods now carry their confirmed FoodOn type: 246 adjudicated decisions by Crislane Timbo and
351 original agreements between Josandra Semedo and Elizabete Wensel. The agreement before adjudication
was 400/597 (67.00%; kappa 0.66943); agreement is not an accuracy estimate.

`python verification/type_review_application_check.py` independently reads the original forms,
adjudications, alignments, audits, native RDF and both NICE-Food exports. It confirms the same 597 exact
food/class pairs and each native assertion's review provenance. It also compares 159,301 native
nutritional triples and 178,860 NICE-Food nutritional triples before and after: all unchanged.

Lean 4 v4.36.0-rc2 accepted 9 general theorems and 25 concrete certificate theorems using kernel reduction
(`decide +kernel`), with no `sorry`, added axioms or `native_decide`. A balanced membership tree avoids
quadratic certificate reduction; its contents are proved equal to the recorded class list, and positive
tree membership is proved to imply list membership. The hierarchy certificate contains 1,392 named
nodes and 1,951 edges from the hash-pinned FoodOn release. No selected class reaches a prohibited root.

Seven deliberately incorrect certificates were rejected: wrong class with unchanged count, missing food,
duplicate food, wrong provenance, altered original response, prohibited root, and changed nutritional
fingerprint. The valid certificate passes before negative tests are considered successful.

Results and compiler logs are in `build/verification/review_application/`; the proof source is
[lean/TypeReviewApplication.lean](lean/TypeReviewApplication.lean). Frozen inputs and the activation marker
are in `data/alignment/review/round-1/`. RDF parsing and certificate extraction are Python checks outside
Lean's kernel. The checks verify faithful application of completed human judgements, not nutritional
accuracy. See [the application report](../analysis/review_application.md) for the final delivery.

## Earlier verification runs

The project's own tests check its code on examples. The checks here verify it in independent ways: a proof
in Lean 4, a second implementation, a second engine, randomly generated cases, and the published source of the
data. They were run between 2026-11-16 and 2026-11-18; the numbers below are from those runs.

| Check | What it compares | Result |
| --- | --- | --- |
| [lean/TacoRules.lean](lean/TacoRules.lean) | Proofs, in Lean 4 (core, no Mathlib), of properties of the numeric rules | 21 theorems proved |
| [differential.py](differential.py) | The Python rules against their Lean model, on the same 27,401 cases, many exactly on a limit | 0 differ (after the fix below) |
| [boundary_impact.py](boundary_impact.py) | Every real TACO x NEVO comparison, as the code computes it and in exact decimal arithmetic | 0 change (after the fix) |
| [test_properties.py](test_properties.py) | Hypothesis: random TACO foods through the NICE-Food export (every value kept; every food item, and only a food item, has TACO's version once, in Portuguese); Spearman and quartiles against SciPy and NumPy | 5 properties hold; an export without the language tag, or with a food without its version, is caught |
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
| [structure_check.py](structure_check.py) | [docs/structure.md](../docs/structure.md) and the two-page [docs/summary.md](../docs/summary.md) against the data: generated again and compared; the summary at most 1,000 words; TACO's numbers counted again with rdflib from the export file; URI patterns; each arrow of the class diagram asked of Fuseki; each arrow of the instance diagram a triple of the file; the shared classes by another query; links on GitHub; 4 mutants of the document | all 8 pass; 11 class arrows and 12 instance arrows have data |
| [taco_nevo_alignment_check.py](taco_nevo_alignment_check.py) | TACO's export after it gained `dcterms:hasVersion`, as NEVO's food items have: the properties NEVO uses against TACO's (Fuseki, and rdflib on the file); one version per food, written as NICE-Food writes NEVO's; the export against the one published before (commit 5714556); NICE-Food's protein queries and the competency questions before and after; the predicates those queries read (rdflib's SPARQL parser); why 27 TACO nutrients keep TACO's own URI, from NEVO's nutrient labels and TACO's own tagnames; Lean 4 with Mathlib on all of it, with a theorem for all graphs: triples with a predicate a pattern does not name cannot change what it reads | NEVO's only properties TACO lacks are its own food codes (`fio:hasNevoCode21`, `fio:hasNevoCode23`); 597 of 597 foods have one version, `@pt` as NEVO's are `@nl`; 597 triples added, 0 removed; 7 of 7 queries give the same rows (105, 105, 186, 87, 173, 47, 83) and none reads the version; of the 27 nutrients NEVO lacks 18, has 3 only split or qualified where TACO does not say which form, and has a code for the form TACO names for 6, which could take it; 20 theorems proved; 6 mutants of the checks and 7 of the Lean file rejected |
| [nutrient_definitions_check.py](nutrient_definitions_check.py) | [analysis/nutrient_definitions.md](../analysis/nutrient_definitions.md), whether each of the 41 shared nutrient codes is the same quantity in TACO and NEVO: the tagnames and methods taken from TACO's PDF, found on their pages; the data tests (carbohydrate, energy in kcal and kJ, protein, vitamin A, fatty acids), units and counts read with rdflib from the files and from Fuseki; the verdict rule written again in the check and in Lean | 66 tagnames, phrases and names found; 0 differences between rdflib and Fuseki; 41 of 41 verdicts the same: 29 the same quantity (17 checked with data, 12 the same element or compound), 1 in another unit, 3 calculated another way, 1 with NEVO's values under another code, 7 to confirm with NEVO's method; 4 mutants of the checks and 4 of the Lean file rejected |
| [../scripts/rebuild_nicefood.py](../scripts/rebuild_nicefood.py) | Fuseki's `nicefood` dataset deleted and loaded again from its files, against the store as it was: triples by property and the rows of NICE-Food's queries | 2,181,281 triples in 79 properties and 7 of 7 queries the same: the store updated by hand was what the files say |

The Lean files with data are generated in `build/verification/` and checked with `lake env lean` in a Lake project that has Mathlib built (`--lake-project`); [lean/lakefile.toml](lean/lakefile.toml) pins the Lean and Mathlib versions. Each of these scripts also runs mutation tests on the Lean file it generates (skip them with `--no-mutants`): it breaks the data on purpose and requires Lean to reject the result, since a proof that accepts broken data proves nothing. The mutants are a claimed count off by one, a food typed in one source only, a class with an organism ancestor among the usable ones, a step that is no FoodOn edge, a food taken out of round 2's sample, and a round-1 food put in round 2. A mutation that does not change the file is reported as a problem, not taken as a pass: an early manual run missed this because the files then had Windows line endings, so they are now always written with LF. A file Lean rejects makes every mutant of it fail too, which proves nothing: `taco_nevo_alignment_check.py` first generated a file with a missing import, and its mutants were all "rejected". It now runs mutants only on a file Lean accepts; the other scripts still run them, but fail as a whole when Lean rejects the file.

The full test suite also passed: 363 tests, 1 skipped, on 2026-11-18 (330 before the FoodOn typing work of 2026-11-17).

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
4. **TACO's version was first written as a plain string; NEVO's is a string in Dutch.**
   - `taco_nevo_alignment_check.py` compared the two in Fuseki: NICE-Food's code writes NEVO's version as
     `Literal(..., lang="nl")` (`"NEVO-Online 2021 7.0"@nl`).
   - TACO's is now in its own language: `"TACO 4ª edição revisada e ampliada (NEPA-UNICAMP, 2011)"@pt`.
5. **The example file of food 574 had its Portuguese name garbled** (`FeijÃ£o`).
   - `scripts/example_food_rdf.py` read Fuseki's Turtle with `requests`' `.text`; Fuseki names no charset,
     so it was decoded as Latin-1. It now hands rdflib the bytes, which Turtle defines as UTF-8.
   - `skos_check.py` had the same call; its results compare structure, not names, so they did not change.
   - Read from the file and from Fuseki, foods 1, 300 and 574, with all their values, now give the same graph.
6. **TACO does say which form some of its fatty acids are.**
   - `data/alignment/taco_nevo_nutrients.csv` says TACO does not tell cis from trans for 14:1, 16:1, 18:1 and
     20:1, nor the series of 20:4 and 22:5. TACO's own INFOODS tagnames (Quadro 6) do: `F14D1C`, `F16D1C`,
     `F18D1CN9`, `F20D1C` (cis) and `F20D4N6` (n-6); its common names (Quadro 5) agree, and name 22:5 DPA (n-3).
   - Check 6 of `taco_nevo_alignment_check.py` had looked only at NEVO's labels, so it confirmed the note. It now
     also takes TACO's declarations: 6 nutrients could take NEVO's code. The mapping is unchanged until the group
     decides; for 18:1 TACO names the n-9 isomer and NEVO's code every cis 18:1.
7. **A shared code is not always the same quantity** (`nutrient_definitions_check.py`).
   - NEVO's available carbohydrate is sugars plus starch for 98% of its foods; TACO's is calculated by difference.
   - NEVO's energy follows the general EU factors for 99% of its foods; TACO's, for 36%: TACO uses Atwater's
     specific factors, as its PDF says.
8. **NICE-Food's graph writes NEVO's sodium as `nevonut:nan`.** `scripts/check_nice_food.py` already counted
   it among NICE-Food's cases ([analysis/nice_food_nevo_checks.md](../analysis/nice_food_nevo_checks.md)).
   `nutrient_definitions_check.py` adds the cause and the size: NICE-Food's notebook reads NEVO's file with
   pandas, which reads the code `NA` as missing, and the 1,672 values in NICE-Food's own file never meet
   TACO's `nevonut:NA`.
9. **The instance diagram of `docs/structure.md` depended on Fuseki's order.** After the store was rebuilt,
   Fuseki returned food 574's triples in another order, and the nodes were numbered differently;
   `structure_check.py`'s mutant, written for one numbering, no longer changed the document and said so. The
   triples are now sorted before drawing, and the mutant finds its arrow whatever the numbering.

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
python verification\structure_check.py --nicekg path\to\nicekg_processing
python verification\taco_nevo_alignment_check.py --save-baseline build\verification\baseline.json  # before a change
python verification\taco_nevo_alignment_check.py --baseline build\verification\baseline.json --lake-project path\to\lake\project
python verification\nutrient_definitions_check.py --lake-project path\to\lake\project
python scripts\rebuild_nicefood.py --fuseki-home path\to\apache-jena-fuseki
```
