# NICE-Food queries

Queries of NICE-Food's analysis, run over the `nicefood` Fuseki dataset, which holds NEVO's subgraphs,
FoodOn and the TACO subgraph of `scripts/taco_to_nice_food.py` (see [triplestore/README.md](../../triplestore/README.md)).

| File | What it is |
| --- | --- |
| `protein_groups.rq` | NICE-Food's query, copied unchanged from [rivm-syso/nicekg_analysis](https://github.com/rivm-syso/nicekg_analysis), `analysis/queries/publication/protein_groups.rq` (EUPL-1.2). It names protein by NEVO's code, `nevonut:PROT`. |
| `protein_groups_cdno.rq` | The same query with one line changed: the nutritional value is chosen by its CDNO class, protein (`obo:CDNO_0200040`), instead of by NEVO's code. |
| `cdno_coverage.rq` | What choosing values by CDNO class finds in each table, for protein, lipid, carbohydrate, available carbohydrate and tryptophan: NEVO's fat and tryptophan have no CDNO class, and NEVO's available carbohydrate has CDNO's general carbohydrate class, the class of TACO's total carbohydrate. |
| `chicken_as_mammalian_meat.rq` | The path in FoodOn's hierarchy by which `protein_groups.rq` counts TACO's cooked chicken breast as mammalian meat (see [analysis/taco_nice_food.md](../../analysis/taco_nice_food.md)). |

Run either with

```sh
python scripts/run_nice_food_query.py queries/nice-food/protein_groups.rq
```

which counts the rows by food group and by table. The query returns food names only, so a row counts as
TACO's when its name is the English name of a TACO food.
