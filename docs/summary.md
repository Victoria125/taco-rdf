# TACO in NICE-Food: summary

Generated on 2026-11-19 by `python scripts/describe_structure.py` from the same data as [docs/structure.md](https://github.com/Victoria125/taco-rdf/blob/main/docs/structure.md), the full description, and checked by `python verification/structure_check.py`.

TACO, the Brazilian food composition table (NEPA-UNICAMP, 4th edition, 2011), is written in the pattern NICE-Food uses for NEVO: 597 foods and 21,720 nutritional values in one Turtle file, [taco_nice_food.ttl](https://github.com/Victoria125/taco-rdf/blob/main/docs/taco-in-nice-food/files/knowledge-graph/taco_nice_food.ttl), with one food to read in [example_food_574.ttl](https://github.com/Victoria125/taco-rdf/blob/main/docs/taco-in-nice-food/files/knowledge-graph/example_food_574.ttl). Loaded next to NICE-Food's NEVO graphs and FoodOn, NICE-Food's own query `protein_groups.rq` runs unchanged and finds 185 TACO foods.

## What TACO shares with NEVO

- The same 15 terms: the classes `fio:FoodItem`, a FoodOn class, `fio:NutritionalValue`, a CDNO class, `fio:Nutrient`, `om:Measure`, `om:Unit`, and the properties `fio:hasNutritionalValue`, `fio:hasNutrient`, `om:hasValue`, `om:hasNumericalValue`, `om:hasUnit`, `dcterms:isVersionOf`, `dcterms:hasVersion`, `skos:prefLabel`.
- Foods typed with a FoodOn class by `rdf:type`, not linked by SKOS: 597 of 597 TACO foods. 135 TACO foods and 155 NEVO food items share a FoodOn class (114 classes).
- Values typed with a CDNO class: 18,131 of 21,720 TACO values, 110,480 of 187,275 NEVO values.
- Units as an OM unit and a string; the edition as `dcterms:hasVersion`, in each table's language.
- NEVO's nutrient URIs: 41 of TACO's 68 nutrients use them, 18,056 of 21,720 values.

## Where TACO differs, and why

| Difference | Why |
| --- | --- |
| TACO's URIs are under `https://w3id.org/taco-rdf/id/` | each table mints its own URIs |
| 27 nutrients have TACO's own URI | NEVO lacks some (manganese, amino acids but tryptophan, total carbohydrate) and has some fatty acids only in forms TACO does not tell apart; 6 could take NEVO's code, as TACO's own tagnames name NEVO's form |
| 3,586 values have `taco:valueStatus` instead of a number | TACO reports a trace, not applicable or under re-evaluation; a trace is not zero |
| 570 values have `prov:wasDerivedFrom` | available carbohydrate is calculated from TACO's carbohydrate and fibre |
| the food's number is `dcterms:identifier` | NEVO's `fio:hasNevoCode21` and `fio:hasNevoCode23` name NEVO |

## Is a shared nutrient code the same quantity?

Of the 41 codes TACO shares with NEVO ([analysis/nutrient_definitions.md](https://github.com/Victoria125/taco-rdf/blob/main/analysis/nutrient_definitions.md)), 29 are the same quantity (17 checked with the data, 12 the same element or compound), 1 is in another unit, 3 are calculated another way, 1 has NEVO's values under another code, and 7 are to confirm with NEVO's method.

- Carbohydrate: NEVO's available carbohydrate is sugars plus starch, TACO's is calculated by difference.
- Energy: NEVO's follows the general EU factors, TACO's Atwater's specific factors.
- Sodium: NICE-Food's graph writes NEVO's sodium as `nevonut:nan`, since pandas reads the code `NA` as a missing value, so TACO's sodium and NEVO's never meet in a query.
- Tryptophan: g in TACO, mg in NEVO.

## Points to agree on

1. Nutrient identity: NEVO's codes, which make NEVO the reference for every table, or a neutral one, such as a CDNO class with how the value was obtained, or INFOODS tagnames, which TACO already declares?
2. Values calculated another way: separate codes, or the method on each value?
3. Values without a number: one term for a trace, not applicable or under re-evaluation?
4. Food codes: one property for each table's own food code?
5. Releases: the shared graph pinned to FoodOn 2026-09-20 and CDNO 2026-06-10?

## More

- [docs/structure.md](https://github.com/Victoria125/taco-rdf/blob/main/docs/structure.md): namespaces, URIs, the schema, an example, NICE-Food's other datasets, foods in common.
- [analysis/nutrient_definitions.md](https://github.com/Victoria125/taco-rdf/blob/main/analysis/nutrient_definitions.md): each shared nutrient code, with TACO's INFOODS tagnames and the tests on both tables.
