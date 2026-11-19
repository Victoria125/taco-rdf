# QUDT versus OM for TACO-RDF / NICE-Food: verified engineering decision

**Decision (19 November 2026): retain QUDT in the canonical TACO graph and use the existing OM-based NICE-Food export. Do not perform a global unit-vocabulary replacement.**

This is an evidence-backed software architecture decision, not a claim that one ontology is intrinsically superior, a certification of nutrient comparability, or a change to WUR's canonical NICE-Food data.

## Where the two representations actually occur

| Layer | Numeric representation | Purpose |
| --- | --- | --- |
| TACO-RDF native graph | `qudt:numericValue`, `qudt:unit`, `taco:referenceBasis` | Preserve the source measurement (including its original unit distinction), plus explicit reference basis and nonnumeric statuses |
| TACO NICE-Food export | `fio:NutritionalValue` linked via `om:hasValue` to `om:Measure`, which has `om:hasNumericalValue` and `om:hasUnit` | Follow the same graph pattern used by NICE-Food's NEVO data |
| NICE-Food/NEVO processing | FIO + FoodOn + CDNO + OM | Query food and nutrient classes and units in a joint knowledge graph |

The bridge is implemented in `src/taco_rdf/nice_food.py`. Unlike a naive property rename, it changes the graph shape from an inline quantity on a source measurement to a `fio:NutritionalValue` with a separate `om:Measure` node. The source describes measurements on 100 g of edible food; the export encodes units as per 100 g.

| Native QUDT unit | NICE-Food OM unit | Unit string |
| --- | --- | --- |
| `unit:GM` | `om:gramPerHectogram` | g |
| `unit:PERCENT` | `om:gramPerHectogram` | g |
| `unit:MilliGM` | `om:milligramPerHectogram` | mg |
| `unit:MicroGM` | no OM unit IRI in the *current compatible export* | µg |
| `unit:KiloCAL` | `om:kilocaloriePerHectogram` | kcal |
| `unit:KiloJ` | `om:kilojoulePerHectogram` | kJ |

The percent/gram pair maps to the same per-100-g representation; the raw source-unit distinction cannot be reconstructed from the OM unit alone. This is a **design tradeoff**, not a declaration of a TACO source error. A full switch to OM as canonical storage would need an additional unambiguous preservation mechanism for the original unit and a deliberate policy for µg.

## Evidence from running the actual project

- [Lean 4 model](../verification/lean/UnitBridgeProof.lean), compiled with the pinned Lean 4 v4.36.0-rc2, proves (1) an arbitrary measured value is unchanged by the bridge, (2) trace/not applicable/under reevaluation have no number, (3) gram and percent share a target, (4) the mapping has no lossless inverse, and (5) microgram is string-only in the modeled contract. The proof is generic in the numeric value type. It models the production mapping; [Python tests](../tests/test_om_bridge.py) cross-check the mapping against the actual code.
- [Python regression tests](../tests/test_om_bridge.py): **6 passed** in the dedicated [GitHub Action](https://github.com/Victoria125/taco-rdf/actions/runs/44589807504). They rebuild the actual 597-food TACO graph, export it, and verify **all 17,564 measured values** numerically equal their originals, **3,586 nonnumeric statuses** carry no OM measure, and the 570 derived available-carbohydrate values yield **18,134 OM measures** in the **21,720-value** export. Both native QUDT predicates remain intact; exported nutritional records use OM and do not leak QUDT measurement predicates.
- [SHACL shape](../verification/om_measure_shapes.ttl): a valid exported OM measure passes; deleting its numeric value makes validation fail. Changing the mg to g mapping also makes the Python contract fail.
- The export retains FoodOn membership as `rdf:type`, FIO nutritional links, CDNO measurement types and `skos:prefLabel` for names, with no SKOS food-to-FoodOn equivalence mappings.
- Tests are independent of the report's prose. They *do not* test correctness of the original food composition table, chemical comparability between nutrients, or the canonical WUR production database.

## What to do about other ontologies

| Vocabulary | Use in TACO-RDF | Role in NICE-Food | Decision |
| --- | --- | --- | --- |
| **FoodOn** | Food categories as `rdf:type` | Used by NEVO and the integrated graph | Keep for integration |
| **CDNO** | Nutrient value classes | Used in NEVO | Keep for integration |
| **FIO** | Food items and nutritional values in export | Used by NEVO | Keep for integration |
| **OM** | Units/numbers in NICE-Food export | Used by NEVO | Keep in export |
| **QUDT** | Native measurement values and source units | Not identified as NEVO's measurement pattern | Keep canonical; export to OM |
| **ChEBI** | Chemical nutrient mappings | Used for contaminants in the NICE-Food KAP processing notebook; not part of the required NEVO nutrient join | Keep where semantically appropriate; do not describe as mandatory for NEVO integration |
| **PROV-O** | Provenance of derived carbohydrate and other provenance | Not identified in the inspected NEVO processing notebook | Keep as useful additional provenance |
| **DCAT** | Dataset-level metadata | Not identified as a required NEVO food/value field in the inspected processing notebook | Keep for FAIR publication |
| **SKOS** | Food/nutrient/group labels and non-food mappings | NEVO uses `skos:prefLabel` | Keep labels; do not use `skos:closeMatch` as food-type assertion |
| **SHACL** | Checks constraints | Independent data-quality validation | Keep |
| **Dublin Core** | Source/edition | NEVO and export use `dcterms:isVersionOf`, `dcterms:hasVersion` | Keep |

Source for the target model: [NICE-Food NEVO processing](https://github.com/rivm-syso/nicekg_processing/blob/main/nevo_processing.ipynb), [KAP processing](https://github.com/rivm-syso/nicekg_processing/blob/main/kap_processing.ipynb), and the actual [TACO native-to-NICE-Food adapter](../src/taco_rdf/nice_food.py). Absence from the inspected processing code must **not** be interpreted as proof that a vocabulary never appears anywhere in every NICE-Food graph or later version.

## Reasons against a destructive replacement now

A native OM-only migration would require coordinated changes to `ontology/taco.ttl`, `src/taco_rdf/graph.py`, parsing-unit definitions, native SHACL, SPARQL queries, static publishing, fixtures and tests. Since the export already matches the NICE-Food model and passes tested numerical-preservation rules, there is no demonstrated integration benefit that offsets this additional migration risk. Keep the two models deliberately separated and add a non-destructive inverse-context annotation only if a future interoperability requirement demands it.

**Research claim that is supported:** TACO-RDF can export its dataset using the NEVO-compatible FIO/OM/FoodOn/CDNO structural pattern without changing measured numeric values, as demonstrated by executable Python, RDF and Lean tests. This is *not* a proof that TACO's nutrient definitions and NEVO's are equivalent or that production integration has been approved.
