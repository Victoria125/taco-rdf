# Running the TACO × NEVO queries in Fuseki

`scripts/compare_taco_nevo.py` runs the queries in `queries/nevo/` with rdflib, in memory, which takes about
fifteen minutes for every CDNO class. NICE-Food's analysis queries a local
[Apache Jena Fuseki](https://jena.apache.org/documentation/fuseki2/) from Jupyter notebooks instead
([rivm-syso/nicekg_analysis](https://github.com/rivm-syso/nicekg_analysis)), and the same queries run
unchanged there.

Fuseki holds NEVO values once loaded, so keep it local: NEVO's conditions of use do not let this project
redistribute them ([data/SOURCES.md](../data/SOURCES.md)).

## Starting Fuseki

1. Download `apache-jena-fuseki-6.2.0.zip` from the [Jena download page](https://jena.apache.org/download/),
   check it against its `.sha512` file and unzip it. Fuseki 6 needs Java 21.
2. Create an empty folder for the database and start the server with a dataset called `taco_nevo`:

   ```powershell
   java -jar fuseki-server.jar --tdb2 --loc=C:\path\to\fuseki-db --update /taco_nevo
   ```

3. Load the TACO snapshot and the NEVO subgraphs of NICE-Food (see `scripts/fetch_nice_food.py`) into the
   dataset's default graph. NICE-Food uploads its Turtle files through the Fuseki page at
   <http://localhost:3030>; this script does the same with the SPARQL Graph Store Protocol. `--foodon` also
   loads the FoodOn release this project pins, downloaded if missing and checked against its SHA-256, which
   the queries over FoodOn's hierarchy need:

   ```powershell
   $env:PYTHONPATH = "src"; python scripts\load_triplestore.py --foodon
   ```

The database folder keeps the data, so a restarted Fuseki needs no new load. The SPARQL endpoint is
<http://localhost:3030/taco_nevo/sparql>, and the Fuseki page has a query editor. With FoodOn loaded the
store holds 2,168,066 triples.

## Querying

`analysis/endpoint_helper.py` follows NICE-Food's `functions/wrapper_helper.py`: `open_query` reads an `.rq`
file and `sparql_query_to_dataframe` sends it with SPARQLWrapper and returns a pandas DataFrame. `bind`
fixes variables with a `VALUES` clause, as `--bind` does for rdflib; `substitute` writes the values into the
query instead, for queries made of UNIONs, into which Fuseki does not carry a `VALUES` clause.
`analysis/taco_nevo_triplestore.ipynb` uses them as NICE-Food's `use_case_nice_food.ipynb` does. Install the
dependencies with `pip install -e ".[analysis]"`, and do not commit the notebook with its outputs, which hold
NEVO values.

The notebook:

- draws the graph around one FoodOn class (`queries/nevo/taco_nevo_food_graph.rq`, `analysis/graph_helper.py`,
  with networkx): its superclasses, the TACO and NEVO foods typed with it, and their values typed with one
  CDNO class;
- compares protein for the foods of the same FoodOn class, and runs the comparison of every CDNO class at once;
- pairs foods whose FoodOn classes are one step apart in FoodOn's hierarchy
  (`queries/nevo/taco_nevo_related_foodon_class.rq`) and compares their protein
  (`analysis/comparison_helper.py`).

On the store of 2026-11-04 the hierarchy adds 257 food pairs, and 54 TACO foods get their first NEVO food.
For protein, each TACO food against the median of its NEVO foods:

| Pair | TACO foods | Spearman | TACO/NEVO median | Quartiles |
| --- | ---: | ---: | ---: | --- |
| Same FoodOn class | 83 | 0.94 | 0.95 | 0.80 to 1.10 |
| NEVO class a direct subclass of TACO's | 13 | 0.98 | 0.88 | 0.81 to 0.96 |
| TACO class a direct subclass of NEVO's | 81 | 0.88 | 0.97 | 0.81 to 1.53 |

Where TACO's class is the more specific one, NEVO's is often a broad class such as *margarine food product*
or *cow food product*, and the spread is wider: those pairs are candidates to check, not comparisons as good
as those of one class.

## TACO in a NICE-Food dataset

`scripts/taco_to_nice_food.py` writes TACO in NICE-Food's own pattern, `build/taco_nice_food.ttl`. That file
reuses the IRIs of `build/taco.ttl`, so it goes into a second dataset, `nicefood`, which holds what NICE-Food's
store holds, NEVO and FoodOn, plus TACO. The `taco_nevo` dataset and the notebook stay as they are. With
Fuseki running, create the dataset and load it:

```powershell
Invoke-RestMethod -Uri 'http://localhost:3030/$/datasets' -Method Post -Body @{dbName="nicefood"; dbType="tdb2"}
$env:PYTHONPATH = "src"; python scripts\taco_to_nice_food.py
python scripts\load_triplestore.py --endpoint http://localhost:3030/nicefood --graph build\taco_nice_food.ttl --foodon
```

After a change to the files, or to the store by hand, rebuild the dataset from the files in one step;
`scripts/rebuild_nicefood.py` records the store first and checks that the rebuilt one has the same triples by
property and gives the same rows to NICE-Food's queries (its records go to `build/verification/`):

```powershell
$env:PYTHONPATH = "src"; python scripts\rebuild_nicefood.py --fuseki-home path\to\apache-jena-fuseki
```

The scripts find Fuseki at `http://localhost:3030` unless the environment variable `TACO_FUSEKI` gives
another address (`src/taco_rdf/sparql.py`). The checks that run Jena's ARQ or SHACL engine take Java and
Fuseki's jar from `TACO_JAVA` and `TACO_FUSEKI_JAR`, or look for them on the PATH, under `JAVA_HOME`, in the
usual install folders and beside the project (`src/taco_rdf/tools.py`). The NICE-Food export runs as
`taco-rdf nice-food` or `python scripts\taco_to_nice_food.py`.

`scripts/run_nice_food_query.py` runs NICE-Food's queries in `queries/nice-food/` over it and counts their
rows by table. [analysis/taco_nice_food.md](../analysis/taco_nice_food.md) has the results.

## Why Fuseki

On one Windows laptop on 2026-11-04, with the TACO snapshot `build/taco.ttl` and NICE-Food v3's
`nevo21_graph.ttl` and `nevo23_graph.ttl` (1,768,284 triples), Fuseki was compared with rdflib and with
the stores of SoilWise (Virtuoso) and of a fast embedded engine (Oxigraph). All returned the same pairs: 111
for protein, and 2,214 for every CDNO class plus 80 for available carbohydrate, the 2,294 of
`scripts/compare_taco_nevo.py`.

| Store | Load | Protein | Every CDNO class | Available carbohydrate |
| --- | ---: | ---: | ---: | ---: |
| rdflib 7.6, in memory (`compare_taco_nevo.py`) | about 1 min | 23–74 s | about 15 min, one query per class | 57 s |
| Fuseki 6.2.0, TDB2 | 44 s | 2.0 s | 3.8 s | 0.2 s |
| Virtuoso 7.2.17, Docker, bulk loader | 15 s | 26 s | 270 s | 25 s |
| Oxigraph 0.5.13 (pyoxigraph), in memory | 12 s | 22 s | 252 s | 7.2 s |

Virtuoso also returned each row two to four times despite `SELECT DISTINCT`, and gave NEVO's `xsd:float`
values in single precision (21.3 as 21.299999237060546875). GraphDB 11.5.2 was not measured: it refuses data
without a licence, also for its free edition.
