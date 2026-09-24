# Protein analysis

The notebooks follow NICE-Food's separation of SPARQL queries, small Python helpers and notebook tables and
figures. The references are its [protein query](https://github.com/rivm-syso/nicekg_analysis/blob/79fca6cda812b111d737f625e03e7f1ff134f2d4/analysis/queries/publication/protein_groups.rq),
[analysis notebook](https://github.com/rivm-syso/nicekg_analysis/blob/79fca6cda812b111d737f625e03e7f1ff134f2d4/analysis/use_case_nice_food.ipynb)
and [descriptive statistics helper](https://github.com/rivm-syso/nicekg_analysis/blob/79fca6cda812b111d737f625e03e7f1ff134f2d4/analysis/functions/analysis_helper.py).
The implementation here uses TACO identifiers, measurements and explicit reference bases. It does not assume
that the selected foods, nutrient methods or preparation states are equivalent between TACO and NEVO.

Install the analysis dependencies with `pip install -e ".[analysis]"` and run the notebooks from the `analysis`
directory. SPARQL retrieves food records; pandas groups the results; matplotlib produces the figures. FoodOn
class membership uses `rdf:type`, as in NICE-Food. Foods sharing a class retain their individual identifiers
and composition values. Statistics describe the selected table entries, not population consumption or causal
effects of cooking. Dry matter normalization is an arithmetic comparison using the published moisture values.

`data/foodon_lookup.csv` records searches and checks of curated candidate identifiers separately. Each new
search records its query, date, FoodOn release, limit and number of returned results. The default limit is five;
it is not an exhaustive examination of the ontology. Search statuses have the following meanings:

| Status | Meaning |
|---|---|
| `found` | The service returned one or more results; relevance still needs review. |
| `no_results` | The service returned no results for this query. |
| `not_recorded` | A historical search response was not retained; its outcome, date and release are unknown. |

Rows with `source=recorded` check a candidate identifier and use `found` or `not_found`; these rows do not show
that a search returned the candidate. Legacy gaps are marked `not_recorded` without invented dates or results.
Run `python foodon_lookup.py` from this directory to obtain a fresh log. A failed request or a changed release
leaves the previous log intact. Curated assessments in the two input CSV files still require human review
after a new search; the script does not automatically approve or reject a mapping.

The assessment `not found in documented searches` is limited to the retained search evidence. `search not
recorded` means the negative assessment cannot be substantiated from the log. A generic or taxonomic candidate
describes what was identified in this analysis; it is not a claim that no more specific class exists. Not finding
an exact named dish also does not establish that FoodOn cannot represent it through ingredients or other facets.

English food descriptions are drafts. Preparation details come from the TACO names or the official
[preparation protocols](https://nepa.unicamp.br/wp-content/uploads/sites/27/2023/10/taco_4_edicao_ampliada_e_revisada.pdf).
For example, the protocol for corn cuscuz on printed page 122 describes saucepan cooking with stirring and
does not specify steaming. Recipe summaries are evidence about the TACO preparation, not every regional
version of a dish.
