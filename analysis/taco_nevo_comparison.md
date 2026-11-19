# TACO and NEVO values for foods typed with the same FoodOn class

Generated on 2026-11-19 by
`python scripts/compare_taco_nevo.py --report analysis/taco_nevo_comparison.md`
from the local Fuseki graph after the completed 597-food review and the NEVO subgraphs of NICE-Food v3 (NEVO-Online 2021 7.0,
https://doi.org/10.5281/zenodo.18450818). NEVO's conditions of use do not let this project
redistribute NEVO values ([data/SOURCES.md](../data/SOURCES.md)), so this report holds aggregates
only; the matched values stay in `build/nevo/`, which git ignores.

## What the comparison can show

A pair is a TACO food and a NEVO food typed with the same FoodOn class, with values typed with the
same CDNO class in the same unit. Only identical classes match, a class can be broad, and every
FoodOn class can cover foods with different compositions. Review provenance is recorded in the
TACO graph; reviewed class membership does not establish nutritional equivalence.
The pairs show where the tables can be
compared. Agreement suggests that the shared typing brings comparable foods and nutrients together;
disagreement can come from the typing, from varieties, fortification, sampling, analytical methods
or table conventions, and does not say which table is wrong. Neither tests whether two foods or two
tables are equivalent.

## Coverage

3701 value pairs between 135 TACO foods and 155 NEVO foods (183 food pairs) in 114 shared FoodOn classes and 33 CDNO classes.

## Agreement by nutrient

Each TACO food counts once: its value is compared with the median value of the NEVO foods of its
FoodOn class. Spearman's rho says whether the two tables rank the foods alike; the TACO/NEVO ratio,
over the foods with both values above zero, says how far apart the values are (1.00: equal, 0.50:
TACO's value is half NEVO's). A nutrient with fewer than 10 TACO foods gets counts only.
`value pairs` counts every TACO-NEVO pair before the median.

| CDNO class | NEVO nutrient | unit | TACO foods | value pairs | Spearman rho | TACO/NEVO median | TACO/NEVO quartiles | foods with a zero |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| concentration of dietary calcium in material entity | Calcium | mg | 129 | 175 | 0.82 | 0.75 | 0.53 to 1.10 | 1 |
| concentration of protein in material entity | Protein total | g | 129 | 175 | 0.93 | 0.96 | 0.80 to 1.24 | 2 |
| concentration of water in material entity | Water total | g | 129 | 175 | 0.93 | 1.00 | 0.92 to 1.03 | 1 |
| concentration of dietary phosphorus in material entity | Phosphorus | mg | 127 | 173 | 0.89 | 0.87 | 0.68 to 1.12 | 0 |
| concentration of dietary iron in material entity | Iron total | mg | 126 | 169 | 0.74 | 0.77 | 0.49 to 1.03 | 2 |
| concentration of dietary potassium in material entity | Potassium | mg | 126 | 172 | 0.63 | 0.83 | 0.66 to 1.07 | 0 |
| concentration of dietary magnesium in material entity | Magnesium | mg | 121 | 167 | 0.64 | 0.88 | 0.67 to 1.19 | 0 |
| concentration of dietary sodium in material entity | Sodium | mg | 115 | 160 | 0.79 | 0.77 | 0.29 to 1.38 | 1 |
| concentration of dietary zinc in material entity | Zinc | mg | 115 | 161 | 0.92 | 0.84 | 0.64 to 1.02 | 0 |
| concentration of dietary copper in material entity | Copper | mg | 107 | 151 | 0.58 | 0.98 | 0.67 to 1.53 | 1 |
| concentration of linoleic acid in material entity | C18:2 n-6 (linoleic acid) | g | 95 | 137 | 0.81 | 0.91 | 0.51 to 1.49 | 7 |
| concentration of hexadecanoic acid in material entity | C16:0 | g | 94 | 136 | 0.81 | 1.01 | 0.73 to 1.64 | 6 |
| concentration of saturated fatty acid in material entity | Fatty acids saturated total | g | 94 | 137 | 0.87 | 1.00 | 0.67 to 1.47 | 7 |
| concentration of octadecanoic acid in material entity | C18:0 | g | 91 | 133 | 0.89 | 1.02 | 0.74 to 1.71 | 7 |
| concentration of polyunsaturated fatty acid in material entity | Fatty acids total polyunsaturated total | g | 90 | 133 | 0.78 | 0.85 | 0.50 to 1.21 | 6 |
| concentration of monounsaturated fatty acid in material entity | Fatty acids monounsaturated cis total | g | 87 | 130 | 0.85 | 1.04 | 0.68 to 1.51 | 6 |
| concentration of α-linolenic acid in material entity | C18:3 n-3 cis (ALA) | g | 82 | 123 | 0.72 | 0.85 | 0.50 to 2.00 | 15 |
| concentration of available carbohydrate in material entity | Carbohydrate available | g | 79 | 110 | 0.88 | 0.94 | 0.62 to 1.17 | 3 |
| concentration of dietary fibre in material entity | Fibre dietary total | g | 79 | 110 | 0.60 | 1.20 | 0.85 to 1.82 | 1 |
| concentration of riboflavin in material entity | Riboflavin (Vit B2) | mg | 70 | 109 | 0.56 | 0.58 | 0.40 to 0.95 | 0 |
| concentration of tetradecanoic acid in material entity | C14:0 | g | 68 | 105 | 0.75 | 0.94 | 0.71 to 2.06 | 3 |
| concentration of icosanoic acid in material entity | C20:0 | g | 65 | 97 | 0.70 | 1.00 | 0.79 to 1.73 | 16 |
| concentration of nicotinic acid in material entity | Niacin (Vit B3) | mg | 59 | 79 | 0.57 | 0.92 | 0.54 to 1.40 | 1 |
| concentration of pyridoxine in material entity | Pyridoxin (Vit B6) | mg | 58 | 81 | 0.07 | 0.69 | 0.40 to 1.37 | 0 |
| concentration of cholesterol in material entity | Cholesterol | mg | 55 | 82 | 0.66 | 1.19 | 0.95 to 1.91 | 0 |
| concentration of ash in material entity | Ash | g | 48 | 74 | 0.71 | 0.98 | 0.84 to 1.24 | 0 |
| concentration of vitamin C in material entity | Ascorbic acid (Vit C) | mg | 47 | 60 | 0.60 | 1.07 | 0.64 to 2.02 | 4 |
| concentration of docosanoic acid in material entity | C22:0 | g | 39 | 63 | 0.64 | 1.00 | 0.50 to 1.49 | 9 |
| concentration of dodecanoic acid in material entity | C12:0 | g | 28 | 45 | 0.79 | 0.74 | 0.50 to 1.37 | 2 |
| concentration of retinol in material entity | Retinol | µg | 26 | 36 | 0.85 | 0.61 | 0.33 to 1.24 | 0 |
| concentration of tetracosanoic acid in material entity | C24:0 | g | 21 | 25 | 0.79 | 1.00 | 0.70 to 1.38 | 5 |
| concentration of docosahexaenoic acid in material entity | C22:6 n-3 cis (DHA) | g | 8 | 10 | - | - | - | 5 |
| concentration of icosapentaenoic acid in material entity | C20:5 n-3 cis (EPA) | g | 7 | 8 | - | - | - | 3 |

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
| concentration of dietary calcium in material entity | 129 | 29% | 53% |
| concentration of protein in material entity | 129 | 50% | 80% |
| concentration of water in material entity | 129 | 86% | - |
| concentration of dietary phosphorus in material entity | 127 | 43% | 65% |
| concentration of dietary iron in material entity | 126 | 27% | 46% |
| concentration of dietary potassium in material entity | 126 | 37% | 58% |
| concentration of dietary magnesium in material entity | 121 | 34% | 57% |
| concentration of dietary sodium in material entity | 115 | 20% | 74% |
| concentration of dietary zinc in material entity | 115 | 42% | 58% |
| concentration of dietary copper in material entity | 107 | 30% | 49% |
| concentration of linoleic acid in material entity | 95 | 22% | - |
| concentration of hexadecanoic acid in material entity | 94 | 31% | - |
| concentration of saturated fatty acid in material entity | 94 | 34% | 64% |
| concentration of octadecanoic acid in material entity | 91 | 31% | - |
| concentration of polyunsaturated fatty acid in material entity | 90 | 29% | 76% |
| concentration of monounsaturated fatty acid in material entity | 87 | 29% | 52% |
| concentration of α-linolenic acid in material entity | 82 | 16% | - |
| concentration of available carbohydrate in material entity | 79 | 39% | 58% |
| concentration of dietary fibre in material entity | 79 | 30% | 76% |
| concentration of riboflavin in material entity | 70 | 11% | 31% |
| concentration of tetradecanoic acid in material entity | 68 | 28% | - |
| concentration of icosanoic acid in material entity | 65 | 26% | - |
| concentration of nicotinic acid in material entity | 59 | 25% | 51% |
| concentration of pyridoxine in material entity | 58 | 14% | 29% |
| concentration of cholesterol in material entity | 55 | 40% | - |
| concentration of ash in material entity | 48 | 56% | - |
| concentration of vitamin C in material entity | 47 | 21% | 36% |
| concentration of docosanoic acid in material entity | 39 | 31% | - |
| concentration of dodecanoic acid in material entity | 28 | 18% | - |
| concentration of retinol in material entity | 26 | 12% | 27% |
| concentration of tetracosanoic acid in material entity | 21 | 33% | - |
| concentration of docosahexaenoic acid in material entity | 8 | 0% | - |
| concentration of icosapentaenoic acid in material entity | 7 | 0% | - |

## FoodOn classes

TACO food numbers and the number of NEVO foods for each shared class, the classes that give the
most pairs first.

| FoodOn class | label | TACO foods | NEVO foods |
| --- | --- | --- | ---: |
| FOODON_03301119 | whole wheat bread | 52 | 14 |
| FOODON_02000203 | beef rib | 335, 337, 342, 347 | 2 |
| FOODON_00002729 | pork sausage | 422, 423 | 3 |
| FOODON_03317605 | yogurt (fruit flavored) | 450, 452 | 3 |
| FOODON_03303588 | dark chocolate | 498 | 5 |
| FOODON_03301502 | yogurt (plain) | 448 | 4 |
| FOODON_03305289 | soybean milk | 582 | 4 |
| FOODON_00002800 | chicken egg (boiled) | 488 | 3 |
| FOODON_02000146 | beef sirloin (raw) | 367, 380, 382 | 1 |
| FOODON_03301816 | chocolate milk | 455 | 3 |
| FOODON_03304779 | beef stew | 528, 537, 553 | 1 |
| FOODON_03310125 | cassava flour | 121, 122, 123 | 1 |
| FOODON_03401689 | 10005834 - chicken sausages - prepared/processed (gs1 gpc) | 418, 419, 420 | 1 |
| FOODON_00001692 | cassava food product | 131, 552 | 1 |
| FOODON_00002207 | rice flour | 31 | 2 |
| FOODON_00004677 | white rice (cooked) | 3, 5 | 1 |
| FOODON_03301121 | chicken (whole or pieces, raw) | 402, 405 | 1 |
| FOODON_03301192 | basil leaf (raw) | 81, 133 | 1 |
| FOODON_03301449 | potato (raw) | 92 | 2 |
| FOODON_03301453 | tomato | 161 | 2 |
| FOODON_03302101 | ground beef patty (cooked) | 416, 417 | 1 |
| FOODON_03302200 | wheat bread | 54 | 2 |
| FOODON_03302946 | custard | 509 | 2 |
| FOODON_03303567 | meatball (cooked) | 331 | 2 |
| FOODON_03306809 | pea (canned) | 560 | 2 |
| FOODON_03309927 | tomato (raw) | 157 | 2 |
| FOODON_03310126 | plantain (raw) | 175, 181 | 1 |
| FOODON_03311076 | pork chop (raw) | 427 | 2 |
| FOODON_03311121 | white rice (raw) | 4, 6 | 1 |
| FOODON_03311654 | beef (cured, cooked) | 338, 384 | 1 |
| FOODON_00002570 | pork loin | 432 | 1 |
| FOODON_00002922 | red cabbage head | 151 | 1 |
| FOODON_00002940 | instant noodle | 39 | 1 |
| FOODON_00003012 | yellow bell pepper (raw) | 143 | 1 |
| FOODON_00003247 | parmesan cheese food product | 464 | 1 |
| FOODON_00003410 | cauliflower floret | 118 | 1 |
| FOODON_00004137 | beetroot (raw) | 98 | 1 |
| FOODON_00004138 | zucchini squash (raw) | 71 | 1 |
| FOODON_00004387 | kiwifruit | 207 | 1 |
| FOODON_00004429 | sweet potato (cooked) | 88 | 1 |
| FOODON_00004678 | brown rice kernel (cooked) | 1 | 1 |
| FOODON_00004679 | brown rice kernel (raw) | 2 | 1 |
| FOODON_02000189 | beef brisket | 378 | 1 |
| FOODON_02000190 | beef brisket (raw) | 379 | 1 |
| FOODON_02000197 | beef shank | 371 | 1 |
| FOODON_02000198 | beef shank (raw) | 372 | 1 |
| FOODON_02000284 | pork leg (raw) | 436 | 1 |
| FOODON_02020240 | chicken drumstick (with skin, raw) | 397 | 1 |
| FOODON_02020913 | beef liver | 356 | 1 |
| FOODON_02021057 | goat milk | 454 | 1 |
| FOODON_03000019 | red leaf lettuce (raw) | 80 | 1 |
| FOODON_03000021 | welsh onion (raw) | 108 | 1 |
| FOODON_03000026 | amaranth leaf | 104 | 1 |
| FOODON_03000124 | crisphead lettuce (raw) | 77 | 1 |
| FOODON_03000125 | butterhead lettuce (raw) | 79 | 1 |
| FOODON_03000447 | endive leaf | 111 | 1 |
| FOODON_03301061 | corn syrup | 503 | 1 |
| FOODON_03301073 | sugar (granulated) | 492 | 1 |
| FOODON_03301179 | chicken liver (raw) | 400 | 1 |
| FOODON_03301217 | tomato sauce | 159 | 1 |
| FOODON_03301271 | peach (canned) | 245 | 1 |
| FOODON_03301279 | plum (canned) | 173 | 1 |
| FOODON_03301440 | mayonnaise | 524 | 1 |
| FOODON_03301474 | corn oil | 270 | 1 |
| FOODON_03301545 | cucumber (raw) | 142 | 1 |
| FOODON_03301570 | carrot root (raw) | 110 | 1 |
| FOODON_03301697 | pumpkin (raw) | 67 | 1 |
| FOODON_03301704 | onion (raw) | 107 | 1 |
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
| FOODON_03305263 | vegetable oil | 271 | 1 |
| FOODON_03306092 | chicken salad | 547 | 1 |
| FOODON_03306100 | potato (cooked) | 91 | 1 |
| FOODON_03306255 | toast | 63 | 1 |
| FOODON_03306698 | swiss chard leaf (raw) | 74 | 1 |
| FOODON_03306726 | sweet green bell pepper (raw) | 144 | 1 |
| FOODON_03306732 | sweet red bell pepper (raw) | 145 | 1 |
| FOODON_03307043 | yam (raw) | 103 | 1 |
| FOODON_03308329 | sardine in oil (canned) | 319 | 1 |
| FOODON_03309709 | eggplant (raw) | 96 | 1 |
| FOODON_03309715 | eggplant (cooked) | 95 | 1 |
| FOODON_03309738 | beef (cooked) | 361 | 1 |
| FOODON_03310232 | palm oil | 259 | 1 |
| FOODON_03310257 | cornmeal | 43 | 1 |
| FOODON_03310296 | peanut candy | 579 | 1 |
| FOODON_03310306 | sesame seed | 593 | 1 |
| FOODON_03310357 | sunflower seed oil | 269 | 1 |
| FOODON_03310623 | pork sausage (raw) | 421 | 1 |
| FOODON_03310641 | lentil | 577 | 1 |
| FOODON_03310717 | fish (fried) | 308 | 1 |
| FOODON_03310938 | beef tongue (raw) | 366 | 1 |
| FOODON_03311100 | carrot (cooked) | 109 | 1 |
| FOODON_03311420 | broccoli (cooked) | 100 | 1 |
| FOODON_03311618 | shrimp (boiled) | 284 | 1 |
| FOODON_03311757 | leek (raw) | 83 | 1 |
| FOODON_03316339 | pumpkin (cooked) | 68 | 1 |
| FOODON_03317254 | beetroot | 97 | 1 |
| FOODON_03541129 | 11290 - brazil nuts (efsa foodex2) | 589 | 1 |
| FOODON_03543891 | 38910 - french fries from cut potato (efsa foodex2) | 93 | 1 |
