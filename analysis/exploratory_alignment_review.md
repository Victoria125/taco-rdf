# Exploratory FoodOn alignment review

This is an AI-assisted desk assessment of the first 25 rows marked `sample` in
`data/alignment/review/round-1/items.csv`, in their recorded order. The source names and existing
links come from `context.csv`; candidate identifiers were checked against the pinned
`ontology/imports/foodon-classes.tsv`. The context's definitions and search candidates were
captured from OLS when the round was prepared and are aids, not proof of meaning in the pinned
release. The TACO workbook is the authority for the Portuguese names. The source publication is
available from [NEPA-UNICAMP](https://nepa.unicamp.br/tabela-brasileira-de-composicao-de-alimentos-4a-edicao/),
and [FoodOn's product hierarchy guidance](https://foodon.org/food-facets/food-product/) explains
its distinction between food items and product classes.

The assessment is **not** one of the two independent human reviews required by
`docs/alignment-review.md`. It does not fill either reviewer form, adjudicate a mapping,
change `alignments.csv`, estimate precision, or label a mapping `Reviewed`. The 25 rows are a
convenience subset of the prepared sample, not a new probability sample. A suggested class
must still be examined in the pinned ontology, including its definition and ancestors, before
adoption. `Needs checking` means the available evidence is insufficient for a verdict.

| TACO ID | Existing link | Preliminary assessment | Evidence and question for human review |
| ---: | --- | --- | --- |
| 591 | related → coconut water | Needs checking | TACO names a raw young coconut; the FoodOn definition describes its liquid. The relation expresses an association, but the reviewer should look for a class of the whole food. |
| 72 | related → zucchini squash (raw) | Needs checking | TACO says *refogada*; the target says raw. A related relation may be defensible, but a prepared zucchini class may be stronger. |
| 435 | related → pork sirloin tip roast | Needs checking | The target definition specifies an anatomical leg-tip cut. TACO says roasted *pernil* without specifying that cut. |
| 517 | no link → coarse salt | Needs checking | OLS candidates include `FOODON_03400134` (“salt or salt substitute”), whose disjunction does not establish an exact coarse-salt match. |
| 271 | no link → pequi oil | Needs checking | Generic edible vegetable oil candidates occur in the context, but their suitability and any pequi-specific class require ontology inspection. |
| 488 | no link → boiled whole chicken egg | **Candidate missed** | The pinned class index contains `FOODON_00005341` (“chicken egg (cooked)”). TACO specifies a chicken egg cooked for 10 minutes. Check the class definition and parents; if it allows a whole boiled egg, `type` is a candidate. |
| 514 | type → baker's yeast | Provisionally supported | The TACO name says biological yeast in tablet form; the class is baker's yeast. Confirm that the source identifies baker's yeast rather than another yeast preparation. |
| 577 | related → brown lentil (cooked) | **Relation needs checking** | The target definition explicitly requires a **brown** lentil. TACO says only cooked lentil. Under section 5.1 of the review protocol, an unspecified variety cannot justify `type` or `close`; `narrow` may describe the current target, or a generic cooked-lentil class may be better. |
| 457 | type → skim milk food product | Needs checking | TACO specifies skimmed cow milk treated by UHT. The target's captured definition mentions pasteurization; check whether its axioms include or exclude UHT sterilization. |
| 20 | no link → canjica with whole milk | Needs checking | The context has no candidate. Absence of an OLS candidate does not prove no suitable FoodOn class or compositional representation exists. |
| 490 | type → chicken egg (fried) | Provisionally supported | TACO specifies a whole fried chicken egg. The pinned module places this class under prepared chicken egg product and pan-fried food. |
| 521 | type → green olive (canned) | Needs checking | TACO says green olive in preserve (*conserva*), which does not by itself specify a can. The captured target definition permits a can, bottle or jar and mentions pickling; inspect source preservation details. |
| 160 | type → tomato puree | Provisionally supported | TACO says tomato purée, matching the pinned class label. Confirm the target's additional processing characteristics against the source. |
| 126 | type → yam (raw) | Needs checking | TACO says raw *inhame*. Confirm the plant meant in TACO before asserting the FoodOn yam class; the word can be used for different tubers. |
| 260 | type → olive oil (extra-virgin) | Provisionally supported | Both names specify extra-virgin olive oil. The captured FoodOn definition also states an acidity limit that is not stated in the TACO row, so the product classification should be confirmed. |
| 592 | no link → raw babassu mesocarp flour | Needs checking | A generic `flour` class appears in OLS candidates but is not present in the local module. Verify in the pinned release before proposing a type; a generic class may also lose the babassu distinction. |
| 466 | no link → strawberry petit-suisse cheese | **Candidate missed** | The pinned index contains `FOODON_03303550` (“petite suisse cheese”). Check whether its definition includes flavored products; a general class might permit `type` while losing the strawberry distinction. |
| 505 | no link → maria-mole with toasted coconut | Needs checking | No candidate was recorded. Search by dish ingredients and preparation in the pinned release; do not infer a class is absent from this blank result. |
| 588 | type → cashew nut (shell off, roasted) | Provisionally supported | TACO also says salted. A broader roasted cashew class may still contain salted cashews; salt is a distinction that the current class label does not capture. |
| 561 | type → pinto bean (cooked) | Needs checking | TACO says cooked *feijão carioca*. Verify the botanical/market variety equivalence to “pinto bean” before accepting the type. |
| 310 | type → weakfish (raw) | Needs checking | The raw state agrees, but *pescadinha* needs a source-backed species identification before a weakfish type is accepted. |
| 294 | close → croaker | Needs checking | TACO describes cooked *corvina grande*; verify species, whether the target denotes an organism or a food, and whether a cooked food class exists. |
| 515 | related → gelatine (EFSA FoodEx2) | Needs checking | The captured target definition describes purified collagen. TACO says flavored gelatin powder, possibly a prepared mix; inspect ingredients and the candidate “gelatin dessert food product”. |
| 280 | related → cod | **More specific candidate** | TACO says salted, sautéed cod. The pinned index contains `FOODON_03307021` (“codfish (salted)”). Compare both classes' definitions and processing claims before changing the link. |
| 462 | related → semihard cheese | **More specific candidate** | TACO says half-cured Minas cheese. The pinned index contains `FOODON_03601036` (“minas cheese”). Check whether that class permits the half-cured variety and whether `type` is warranted. |

Five rows contain a concrete candidate or relation question (488, 577, 466, 280, 462).
Five more are provisional supporting examples (514, 490, 160, 260, 588). The remaining
15 need source or ontology evidence before any decision. These counts describe this desk
assessment only; they are **not** mapping accuracy, error rate, reviewer agreement or a
statistical estimate for TACO.

For the actual experiment, two qualified people must independently complete the unchanged
`reviewer-a.csv` and `reviewer-b.csv` forms for all 141 foods and record their backgrounds in
`notes.md`. They should not use this assessment as an answer key, because it could anchor their
judgments. After both finish, run `python scripts/score_alignment_review.py
data/alignment/review/round-1`, adjudicate disagreements, and run it again. The resulting
sample-weighted estimate and qualitative error analysis can then answer the mapping question.
