# Checks of NICE-Food's NEVO subgraph

Generated on 2026-11-05 by `python scripts/check_nice_food.py --report analysis/nice_food_nevo_checks.md`
from `nevo21_graph.ttl` of NICE-Food v3 (https://doi.org/10.5281/zenodo.18450818) and the shapes in
[shapes/nice-food/nevo-shapes.ttl](../shapes/nice-food/nevo-shapes.ttl), validated with Jena's
SHACL engine. It counts results by check and by nutrient or unit, and holds no NEVO value.

| Check | Results |
| --- | ---: |
| Nutritional value without a CDNO class | 75903 |
| Measure whose unit is only a string, not an OM unit | 26010 |
| Two nutritional values of one nutrient for one food item | 7295 |
| NEVO's available carbohydrate (CHO) without CDNO's available carbohydrate class | 3314 |
| Food item without a FoodOn class | 357 |
| Nutrient whose code is nan: NEVO's code NA (sodium) read as not-a-number | 1 |

## Nutritional value without a CDNO class

58 nutrients or units; the 8 with most results:

| Nutrient or unit | Results |
| --- | ---: |
| Fat total (FAT) | 3314 |
| Energy kJ (ENERCJ) | 1669 |
| Energy kcal (ENERCC) | 1669 |
| Protein animal (PROTAN) | 1657 |
| Protein plant (PROTPL) | 1657 |
| Alcohol total (ALC) | 1657 |
| Iron haem (HAEM) | 1652 |
| Iron non-haem (NHAEM) | 1652 |

## Measure whose unit is only a string, not an OM unit

1 nutrients or units; the 1 with most results:

| Nutrient or unit | Results |
| --- | ---: |
| µg | 26010 |

## Two nutritional values of one nutrient for one food item

7 nutrients or units; the 7 with most results:

| Nutrient or unit | Results |
| --- | ---: |
| Fat total (FAT) | 1657 |
| Carbohydrate available (CHO) | 1657 |
| Protein total (PROT) | 1657 |
| Fibre dietary total (FIBT) | 1657 |
| Ash (ASH) | 643 |
| Energy kcal (ENERCC) | 12 |
| Energy kJ (ENERCJ) | 12 |

## NEVO's available carbohydrate (CHO) without CDNO's available carbohydrate class

1 nutrients or units; the 1 with most results:

| Nutrient or unit | Results |
| --- | ---: |
| Carbohydrate available (CHO) | 3314 |
