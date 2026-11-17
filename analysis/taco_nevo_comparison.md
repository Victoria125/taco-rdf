# TACO and NEVO values for foods typed with the same FoodOn class

Generated on 2026-11-16 by
`python scripts/compare_taco_nevo.py --report analysis/taco_nevo_comparison.md`
from the pairs an earlier run wrote to `taco_nevo_same_foodon_class.csv` and the NEVO subgraphs of NICE-Food v3 (NEVO-Online 2021 7.0,
https://doi.org/10.5281/zenodo.18450818). NEVO's conditions of use do not let this project
redistribute NEVO values ([data/SOURCES.md](../data/SOURCES.md)), so this report holds aggregates
only; the matched values stay in `build/nevo/`, which git ignores.

## What the comparison can show

A pair is a TACO food and a NEVO food typed with the same FoodOn class, with values typed with the
same CDNO class in the same unit. Only identical classes match, a class can be broad, and every
FoodOn type in the TACO graph is still unreviewed. The pairs show where the two tables can be
compared. Agreement suggests that the shared typing brings comparable foods and nutrients together;
disagreement can come from the typing, from varieties, fortification, sampling, analytical methods
or table conventions, and does not say which table is wrong. Neither tests whether two foods or two
tables are equivalent.

## Coverage

2294 value pairs between 87 TACO foods and 111 NEVO foods (115 food pairs) in 83 shared FoodOn classes and 33 CDNO classes.

## Agreement by nutrient

Each TACO food counts once: its value is compared with the median value of the NEVO foods of its
FoodOn class. Spearman's rho says whether the two tables rank the foods alike; the TACO/NEVO ratio,
over the foods with both values above zero, says how far apart the values are (1.00: equal, 0.50:
TACO's value is half NEVO's). A nutrient with fewer than 10 TACO foods gets counts only.
`value pairs` counts every TACO-NEVO pair before the median.

| CDNO class | NEVO nutrient | unit | TACO foods | value pairs | Spearman rho | TACO/NEVO median | TACO/NEVO quartiles | foods with a zero |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| concentration of dietary calcium in material entity | Calcium | mg | 83 | 111 | 0.84 | 0.75 | 0.49 to 1.08 | 1 |
| concentration of dietary potassium in material entity | Potassium | mg | 83 | 111 | 0.74 | 0.84 | 0.67 to 1.09 | 0 |
| concentration of protein in material entity | Protein total | g | 83 | 111 | 0.94 | 0.95 | 0.80 to 1.10 | 2 |
| concentration of water in material entity | Water total | g | 83 | 111 | 0.97 | 1.00 | 0.95 to 1.05 | 1 |
| concentration of dietary iron in material entity | Iron total | mg | 81 | 106 | 0.74 | 0.70 | 0.45 to 1.00 | 0 |
| concentration of dietary magnesium in material entity | Magnesium | mg | 81 | 109 | 0.68 | 0.87 | 0.70 to 1.00 | 0 |
| concentration of dietary phosphorus in material entity | Phosphorus | mg | 81 | 109 | 0.90 | 0.89 | 0.69 to 1.08 | 0 |
| concentration of dietary zinc in material entity | Zinc | mg | 75 | 103 | 0.93 | 0.82 | 0.60 to 1.02 | 0 |
| concentration of dietary copper in material entity | Copper | mg | 71 | 98 | 0.50 | 1.02 | 0.68 to 1.83 | 1 |
| concentration of dietary sodium in material entity | Sodium | mg | 71 | 98 | 0.79 | 0.68 | 0.30 to 1.43 | 2 |
| concentration of available carbohydrate in material entity | Carbohydrate available | g | 57 | 80 | 0.94 | 0.97 | 0.68 to 1.18 | 0 |
| concentration of dietary fibre in material entity | Fibre dietary total | g | 57 | 80 | 0.67 | 1.26 | 0.86 to 1.90 | 1 |
| concentration of hexadecanoic acid in material entity | C16:0 | g | 56 | 82 | 0.93 | 0.91 | 0.72 to 1.28 | 3 |
| concentration of linoleic acid in material entity | C18:2 n-6 (linoleic acid) | g | 56 | 82 | 0.93 | 0.94 | 0.67 to 1.28 | 3 |
| concentration of saturated fatty acid in material entity | Fatty acids saturated total | g | 55 | 81 | 0.93 | 0.94 | 0.68 to 1.30 | 3 |
| concentration of octadecanoic acid in material entity | C18:0 | g | 54 | 80 | 0.92 | 1.01 | 0.77 to 1.56 | 3 |
| concentration of polyunsaturated fatty acid in material entity | Fatty acids total polyunsaturated total | g | 52 | 78 | 0.93 | 0.94 | 0.54 to 1.10 | 1 |
| concentration of monounsaturated fatty acid in material entity | Fatty acids monounsaturated cis total | g | 51 | 77 | 0.94 | 1.00 | 0.67 to 1.27 | 4 |
| concentration of α-linolenic acid in material entity | C18:3 n-3 cis (ALA) | g | 47 | 72 | 0.88 | 0.72 | 0.52 to 1.37 | 11 |
| concentration of pyridoxine in material entity | Pyridoxin (Vit B6) | mg | 43 | 62 | -0.10 | 0.67 | 0.35 to 1.27 | 0 |
| concentration of icosanoic acid in material entity | C20:0 | g | 37 | 59 | 0.86 | 1.11 | 0.93 to 1.83 | 6 |
| concentration of riboflavin in material entity | Riboflavin (Vit B2) | mg | 37 | 57 | 0.57 | 0.68 | 0.39 to 1.44 | 0 |
| concentration of tetradecanoic acid in material entity | C14:0 | g | 37 | 59 | 0.83 | 0.89 | 0.70 to 1.13 | 3 |
| concentration of vitamin C in material entity | Ascorbic acid (Vit C) | mg | 34 | 42 | 0.57 | 1.32 | 0.54 to 1.71 | 3 |
| concentration of nicotinic acid in material entity | Niacin (Vit B3) | mg | 33 | 40 | 0.68 | 0.93 | 0.58 to 2.29 | 0 |
| concentration of ash in material entity | Ash | g | 30 | 46 | 0.74 | 1.13 | 0.91 to 1.26 | 0 |
| concentration of cholesterol in material entity | Cholesterol | mg | 26 | 33 | 0.92 | 1.17 | 0.95 to 1.52 | 0 |
| concentration of docosanoic acid in material entity | C22:0 | g | 25 | 44 | 0.80 | 1.00 | 0.98 to 1.61 | 4 |
| concentration of retinol in material entity | Retinol | µg | 18 | 25 | 0.92 | 0.61 | 0.32 to 0.79 | 0 |
| concentration of dodecanoic acid in material entity | C12:0 | g | 17 | 24 | 0.97 | 0.58 | 0.49 to 0.75 | 1 |
| concentration of tetracosanoic acid in material entity | C24:0 | g | 15 | 16 | 0.85 | 1.00 | 0.73 to 1.45 | 2 |
| concentration of docosahexaenoic acid in material entity | C22:6 n-3 cis (DHA) | g | 6 | 6 | - | - | - | 3 |
| concentration of icosapentaenoic acid in material entity | C20:5 n-3 cis (EPA) | g | 2 | 2 | - | - | - | 1 |

## Exploratory: fixed thresholds

Share of TACO foods whose value lies within 20% of the median NEVO value (the difference at most
20% of the larger value), and within the tolerance the European Commission's guidance of December
2012 allows a nutrient value declared on a label, with TACO's value as the declared one. Those
tolerances were set to check a label against analyses of the same product; they are not a measure
of agreement between two food composition tables. They are wide for small amounts (±150 mg of
sodium below 500 mg, ±2 g of protein, carbohydrate or fibre below 10 g) and do not exist for water,
ash, cholesterol or single fatty acids. A share within them does not show that the tables agree,
and a value outside them is not an error.

| CDNO class | TACO foods | within 20% | within EU labelling tolerance |
| --- | ---: | ---: | ---: |
| concentration of dietary calcium in material entity | 83 | 31% | 51% |
| concentration of dietary potassium in material entity | 83 | 37% | 65% |
| concentration of protein in material entity | 83 | 57% | 87% |
| concentration of water in material entity | 83 | 86% | - |
| concentration of dietary iron in material entity | 81 | 21% | 40% |
| concentration of dietary magnesium in material entity | 81 | 36% | 63% |
| concentration of dietary phosphorus in material entity | 81 | 48% | 69% |
| concentration of dietary zinc in material entity | 75 | 37% | 57% |
| concentration of dietary copper in material entity | 71 | 27% | 48% |
| concentration of dietary sodium in material entity | 71 | 17% | 82% |
| concentration of available carbohydrate in material entity | 57 | 46% | 63% |
| concentration of dietary fibre in material entity | 57 | 28% | 81% |
| concentration of hexadecanoic acid in material entity | 56 | 34% | - |
| concentration of linoleic acid in material entity | 56 | 30% | - |
| concentration of saturated fatty acid in material entity | 55 | 36% | 71% |
| concentration of octadecanoic acid in material entity | 54 | 33% | - |
| concentration of polyunsaturated fatty acid in material entity | 52 | 35% | 73% |
| concentration of monounsaturated fatty acid in material entity | 51 | 35% | 65% |
| concentration of α-linolenic acid in material entity | 47 | 11% | - |
| concentration of pyridoxine in material entity | 43 | 14% | 30% |
| concentration of icosanoic acid in material entity | 37 | 30% | - |
| concentration of riboflavin in material entity | 37 | 8% | 32% |
| concentration of tetradecanoic acid in material entity | 37 | 41% | - |
| concentration of vitamin C in material entity | 34 | 9% | 35% |
| concentration of nicotinic acid in material entity | 33 | 18% | 42% |
| concentration of ash in material entity | 30 | 60% | - |
| concentration of cholesterol in material entity | 26 | 58% | - |
| concentration of docosanoic acid in material entity | 25 | 36% | - |
| concentration of retinol in material entity | 18 | 17% | 39% |
| concentration of dodecanoic acid in material entity | 17 | 12% | - |
| concentration of tetracosanoic acid in material entity | 15 | 33% | - |
| concentration of docosahexaenoic acid in material entity | 6 | 0% | - |
| concentration of icosapentaenoic acid in material entity | 2 | 0% | - |

## FoodOn classes

TACO food numbers and the number of NEVO foods for each shared class, the classes that give the
most pairs first.

| FoodOn class | label | TACO foods | NEVO foods |
| --- | --- | --- | ---: |
| FOODON_03301119 | whole wheat bread | 52 | 14 |
| FOODON_03301502 | yogurt (plain) | 448 | 4 |
| FOODON_03305289 | soybean milk | 582 | 4 |
| FOODON_03301816 | chocolate milk | 455 | 3 |
| FOODON_00002207 | rice flour | 31 | 2 |
| FOODON_00004677 | white rice (cooked) | 3, 5 | 1 |
| FOODON_02000210 | beef ribeye steak (raw) | 341 | 2 |
| FOODON_03301449 | potato (raw) | 92 | 2 |
| FOODON_03301959 | potato (french-fried) | 93 | 2 |
| FOODON_03302686 | french bread (loaf) | 53 | 2 |
| FOODON_03305639 | marshmallow | 504 | 2 |
| FOODON_03307043 | yam (raw) | 103, 126 | 1 |
| FOODON_03310125 | cassava flour | 121, 122 | 1 |
| FOODON_03311076 | pork chop (raw) | 427 | 2 |
| FOODON_03311121 | white rice (raw) | 4, 6 | 1 |
| FOODON_00002940 | instant noodle | 39 | 1 |
| FOODON_00003012 | yellow bell pepper (raw) | 143 | 1 |
| FOODON_00003247 | parmesan cheese food product | 464 | 1 |
| FOODON_00003661 | lime | 220 | 1 |
| FOODON_00004137 | beetroot (raw) | 98 | 1 |
| FOODON_00004138 | zucchini squash (raw) | 71 | 1 |
| FOODON_00004429 | sweet potato (cooked) | 88 | 1 |
| FOODON_00004678 | brown rice kernel (cooked) | 1 | 1 |
| FOODON_00004679 | brown rice kernel (raw) | 2 | 1 |
| FOODON_02000190 | beef brisket (raw) | 379 | 1 |
| FOODON_02000198 | beef shank (raw) | 372 | 1 |
| FOODON_02000284 | pork leg (raw) | 436 | 1 |
| FOODON_02021057 | goat milk | 454 | 1 |
| FOODON_03000019 | red leaf lettuce (raw) | 80 | 1 |
| FOODON_03000125 | butterhead lettuce (raw) | 79 | 1 |
| FOODON_03301061 | corn syrup | 503 | 1 |
| FOODON_03301073 | sugar (granulated) | 492 | 1 |
| FOODON_03301121 | chicken (whole or pieces, raw) | 402 | 1 |
| FOODON_03301179 | chicken liver (raw) | 400 | 1 |
| FOODON_03301192 | basil leaf (raw) | 133 | 1 |
| FOODON_03301217 | tomato sauce | 159 | 1 |
| FOODON_03301440 | mayonnaise | 524 | 1 |
| FOODON_03301474 | corn oil | 270 | 1 |
| FOODON_03301545 | cucumber (raw) | 142 | 1 |
| FOODON_03301570 | carrot root (raw) | 110 | 1 |
| FOODON_03301704 | onion (raw) | 107 | 1 |
| FOODON_03301713 | broccoli floret (raw) | 101 | 1 |
| FOODON_03301717 | sweet potato (raw) | 89 | 1 |
| FOODON_03301777 | butter (unsalted) | 262 | 1 |
| FOODON_03301804 | fig (raw) | 194 | 1 |
| FOODON_03301828 | okra (raw) | 147 | 1 |
| FOODON_03302142 | soybean flour | 581 | 1 |
| FOODON_03302643 | butter (salted) | 261 | 1 |
| FOODON_03302732 | cauliflower floret (raw) | 117 | 1 |
| FOODON_03302734 | beef liver (raw) | 355 | 1 |
| FOODON_03302776 | soybean oil | 272 | 1 |
| FOODON_03302908 | ricotta cheese | 469 | 1 |
| FOODON_03303084 | coconut milk | 523 | 1 |
| FOODON_03304384 | sweetened condensed milk | 453 | 1 |
| FOODON_03304656 | radish (raw) | 148 | 1 |
| FOODON_03304663 | ground beef patty (raw) | 415 | 1 |
| FOODON_03304685 | red cabbage head (raw) | 150 | 1 |
| FOODON_03305052 | chicken egg yolk (cooked) | 487 | 1 |
| FOODON_03305208 | garlic bulb (raw) | 82 | 1 |
| FOODON_03305444 | tuna (raw) | 278 | 1 |
| FOODON_03306092 | chicken salad | 547 | 1 |
| FOODON_03306100 | potato (cooked) | 91 | 1 |
| FOODON_03306255 | toast | 63 | 1 |
| FOODON_03306698 | swiss chard leaf (raw) | 74 | 1 |
| FOODON_03306726 | sweet green bell pepper (raw) | 144 | 1 |
| FOODON_03307208 | turkey meat (raw) | 426 | 1 |
| FOODON_03308329 | sardine in oil (canned) | 319 | 1 |
| FOODON_03309668 | tuna (solid pack, canned in oil) | 277 | 1 |
| FOODON_03309709 | eggplant (raw) | 96 | 1 |
| FOODON_03309715 | eggplant (cooked) | 95 | 1 |
| FOODON_03309827 | peanut (skin off, salted, roasted) | 558 | 1 |
| FOODON_03310126 | plantain (raw) | 175 | 1 |
| FOODON_03310232 | palm oil | 259 | 1 |
| FOODON_03310257 | cornmeal | 43 | 1 |
| FOODON_03310296 | peanut candy | 579 | 1 |
| FOODON_03310306 | sesame seed | 593 | 1 |
| FOODON_03310357 | sunflower seed oil | 269 | 1 |
| FOODON_03310623 | pork sausage (raw) | 421 | 1 |
| FOODON_03310938 | beef tongue (raw) | 366 | 1 |
| FOODON_03311100 | carrot (cooked) | 109 | 1 |
| FOODON_03311420 | broccoli (cooked) | 100 | 1 |
| FOODON_03311757 | leek (raw) | 83 | 1 |
| FOODON_03315233 | walnut (raw) | 597 | 1 |
