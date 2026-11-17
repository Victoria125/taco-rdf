# TACO and NEVO food pairs whose composition disagrees

Generated on 2026-11-05 by `python scripts/check_food_pairs.py --report analysis/taco_nevo_food_pair_check.md`
from the pairs in `taco_nevo_same_foodon_class.csv`, written by `scripts/compare_taco_nevo.py`. NEVO's conditions of
use do not let this project redistribute NEVO values, so this report names TACO foods and FoodOn
classes only; the pairs with NEVO names stay in `build/nevo/suspect_food_pairs.csv`, which git
ignores.

## Rule

A TACO food and a NEVO food typed with the same FoodOn class are compared component by component.
A component disagrees strongly when:

- water differs by more than 15 g per 100 g, as between a raw and a cooked or a dry
  and a prepared food;
- protein, available carbohydrate or dietary fibre lies outside the tolerance the European
  Commission's guidance of December 2012 allows a value declared on a label, with TACO's value as
  the declared one;
- a mineral (calcium, magnesium, phosphorus, potassium, sodium, copper, iron, zinc) is at least 3 times
  higher in one table, and the higher value is more than a trace amount.

A pair with 3 or more strongly disagreeing components is flagged: one or two can
be natural variation, several point to a different product or state. A flag makes the pair a
candidate for human review; it does not show which table or which FoodOn type is wrong.

## Result

115 food pairs compared; 20 flagged, between 17 TACO foods.

| strongly disagreeing components | food pairs |
| ---: | ---: |
| 0 | 43 |
| 1 | 34 |
| 2 | 18 |
| 3 | 14 |
| 4 | 2 |
| 5 | 3 |
| 8 | 1 |

Six pairs had been judged not to be the same food by looking at the largest differences by hand,
before this check existed; 5 of the 6 pairs found by hand are flagged.

## Flagged TACO foods

| TACO food | TACO name | FoodOn class | NEVO foods flagged | strongly disagreeing components |
| ---: | --- | --- | ---: | --- |
| 455 | Leite, de vaca, achocolatado | chocolate milk (FOODON_03301816) | 1 of 3 | available carbohydrate, copper, dietary fibre, iron, magnesium, protein, water, zinc |
| 31 | Farinha, de arroz, enriquecida | rice flour (FOODON_00002207) | 2 of 2 | iron, magnesium, potassium, protein, zinc |
| 88 | Batata, doce, cozida | sweet potato (cooked) (FOODON_00004429) | 1 of 1 | available carbohydrate, iron, magnesium, phosphorus, sodium |
| 39 | Macarrão, instantâneo | instant noodle (FOODON_00002940) | 1 of 1 | available carbohydrate, dietary fibre, protein, water |
| 593 | Gergelim, semente | sesame seed (FOODON_03310306) | 1 of 1 | available carbohydrate, dietary fibre, protein, sodium |
| 52 | Pão, trigo, forma, integral | whole wheat bread (FOODON_03301119) | 3 of 14 | available carbohydrate, calcium, copper, protein |
| 53 | Pão, trigo, francês | french bread (loaf) (FOODON_03302686) | 1 of 2 | available carbohydrate, calcium, protein |
| 91 | Batata, inglesa, cozida | potato (cooked) (FOODON_03306100) | 1 of 1 | available carbohydrate, magnesium, sodium |
| 103 | Cará, cru | yam (raw) (FOODON_03307043) | 1 of 1 | available carbohydrate, dietary fibre, iron |
| 121 | Farinha, de mandioca, crua | cassava flour (FOODON_03310125) | 1 of 1 | dietary fibre, iron, potassium |
| 122 | Farinha, de mandioca, torrada | cassava flour (FOODON_03310125) | 1 of 1 | dietary fibre, iron, potassium |
| 133 | Manjericão, cru | basil leaf (raw) (FOODON_03301192) | 1 of 1 | available carbohydrate, iron, magnesium |
| 159 | Tomate, molho industrializado | tomato sauce (FOODON_03301217) | 1 of 1 | available carbohydrate, dietary fibre, water |
| 426 | Peru, congelado, cru | turkey meat (raw) (FOODON_03307208) | 1 of 1 | copper, protein, sodium |
| 503 | Glicose de milho | corn syrup (FOODON_03301061) | 1 of 1 | magnesium, potassium, protein |
| 523 | Leite, de coco | coconut milk (FOODON_03303084) | 1 of 1 | iron, phosphorus, sodium |
| 547 | Salpicão, de frango | chicken salad (FOODON_03306092) | 1 of 1 | available carbohydrate, protein, water |

## Limits

- The components are not independent: a large difference in water moves every other component too.
- Total fat is not compared: NICE-Food gives NEVO's total fat no CDNO class
  ([nice_food_nevo_checks.md](nice_food_nevo_checks.md)), so the comparison yields no pairs for it.
- The thresholds were set by hand and checked once against the six pairs found by hand; they have
  not been tuned or validated on independent data.
- Some flagged pairs may still be the same food, analysed in another season, variety or form.
