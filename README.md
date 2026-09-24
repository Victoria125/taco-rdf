# TACO-RDF

**A FAIR, provenance-aware RDF knowledge graph for the Brazilian Food Composition Table (TACO).**

TACO-RDF transforms the Brazilian Food Composition Table (**TACO — Tabela Brasileira de Composição de Alimentos**, 4th edition, NEPA-UNICAMP, 2011) into a structured, machine-readable RDF knowledge graph.

The project was designed to preserve the scientific meaning of the original food-composition data while enabling semantic querying, validation, ontology alignment, provenance tracking, reproducible transformation, and future integration with other nutrition and food data resources.

Unlike a direct spreadsheet-to-RDF conversion, TACO-RDF explicitly represents non-numeric values such as trace amounts, non-applicable measurements, values under re-evaluation, documented source corrections, measurement reference basis, and semantic alignment provenance.

The project combines:

* RDF and OWL for semantic representation;
* SKOS for controlled concepts and ontology mappings;
* FoodOn for food-related semantic alignment;
* ChEBI and CDNO for nutrient-related concepts;
* QUDT for quantities and measurement units;
* PROV-O for provenance;
* DCAT for dataset metadata;
* SHACL for graph validation;
* SPARQL for querying and analysis;
* SSSOM for interoperable ontology mapping exchange;
* automated Python tests for reproducibility and data-integrity verification.

> **Research status**
>
> TACO-RDF is an active research project. The transformation and structural validation of the original TACO data are extensively tested. External ontology mappings are being progressively evaluated and should not be interpreted as a manually validated gold standard unless explicitly marked as reviewed.

---

# Motivation

Food-composition databases are essential resources for nutrition, epidemiology, public health, clinical research, dietary assessment, food science, and computational nutrition.

However, national food-composition tables are commonly distributed as spreadsheets or relational datasets.

This creates several interoperability problems.

Food names may be expressed only in a local language. Nutrients may use database-specific identifiers. Missing and non-numeric values may have domain-specific meanings. Measurement units and reference bases may be implicit. Provenance may exist only in documentation, and the food entities themselves may not be connected to internationally recognized semantic resources.

TACO contains particularly valuable information about Brazilian foods, including:

* regional foods;
* traditional preparations;
* Brazilian meat cuts;
* native fruits;
* cereals and legumes;
* processed products;
* cooked foods;
* nutrient composition;
* fatty-acid composition;
* amino-acid composition.

The main objective of TACO-RDF is therefore not simply to convert a spreadsheet into triples.

The project investigates:

> **How can the scientific meaning of TACO be represented faithfully as a semantic knowledge graph while making its foods, nutrients, measurements, provenance, and ontology mappings machine-readable and reproducible?**

---

# Design principles

TACO-RDF follows several principles.

## 1. Preserve the source

The original TACO workbook remains the authoritative source for the transformation.

The project avoids silently changing source values during RDF generation.

---

## 2. Preserve semantic distinctions

Values such as:

```text
0
Tr
NA
*
blank
```

do not have the same meaning.

TACO-RDF therefore represents them differently.

---

## 3. Do not force ontology mappings

A TACO food is not assigned to an external ontology class simply because a vaguely similar concept exists.

Weak relationships remain weak relationships.

When no defensible external concept is available, the food may remain intentionally unmapped.

---

## 4. Separate source data from semantic interpretation

The transformation of TACO itself is separated from external ontology alignment.

This allows mappings to evolve without rewriting the original source representation.

---

## 5. Make transformations reproducible

Parsing, corrections, RDF generation, mappings, validation and publication are implemented as reproducible processes rather than manual one-off transformations.

---

## 6. Make uncertainty explicit

Ontology coverage is not treated as ontology accuracy.

A mapping may point to an existing external class and still be semantically incorrect.

Mapping review status and provenance are therefore treated as part of the data.

---

# Dataset overview

The current graph represents the fourth edition of TACO.

| Component             | Current representation |
| --------------------- | ---------------------: |
| Foods                 |                    597 |
| Food groups           |                     15 |
| Nutrient concepts     |                     67 |
| Nutrient observations |       more than 21,000 |
| Reference basis       |   100 g edible portion |
| Main source           |      TACO, 4th edition |
| Source year           |                   2011 |

The graph also contains semantic alignments for food groups, nutrients and individual foods.

Alignment statistics represent the current development state and may change as mappings are reviewed.

---

# Project architecture

The complete transformation follows this general pipeline:

```text
Original TACO workbook
        │
        ▼
Workbook integrity checks
        │
        ▼
Strict Python parser
        │
        ├── numeric values
        ├── trace values
        ├── non-applicable values
        ├── values under re-evaluation
        ├── blank cells
        └── documented corrections
        │
        ▼
Internal structured representation
        │
        ▼
RDF graph generation
        │
        ├── foods
        ├── food groups
        ├── nutrients
        ├── observations
        ├── quantities
        ├── units
        ├── reference basis
        ├── provenance
        └── external semantic alignments
        │
        ▼
SHACL validation
        │
        ▼
Automated tests
        │
        ▼
SPARQL queries and analysis
        │
        ▼
FAIR publication artifacts
```

The architecture deliberately keeps different responsibilities separate.

```text
Parsing
≠
RDF modelling
≠
ontology alignment
≠
validation
≠
publication
```

This separation makes it easier to identify whether an error originates in the source data, parser, semantic model, alignment layer or publication pipeline.

---

# Repository structure

```text
taco-rdf/
│
├── data/
│   ├── raw/
│   ├── corrections/
│   ├── alignment/
│   └── ...
│
├── ontology/
│   ├── taco.ttl
│   └── imports/
│
├── shapes/
│   └── SHACL validation rules
│
├── queries/
│   └── reusable SPARQL queries
│
├── analysis/
│   └── analysis-specific resources
│
├── scripts/
│   └── research and maintenance utilities
│
├── src/
│   └── taco_rdf/
│       ├── parse.py
│       ├── graph.py
│       ├── validate.py
│       ├── evaluation.py
│       ├── publish.py
│       └── ...
│
├── tests/
│   └── automated test suite
│
├── docs/
│   └── methodology and technical documentation
│
├── pyproject.toml
├── CITATION.cff
└── README.md
```

---

# Source data

TACO-RDF starts from the original TACO workbook rather than using a simplified CSV representation as its primary input.

The source workbook is stored under:

```text
data/raw/
```

This decision is important because spreadsheet cells can contain semantic information that may be lost during naïve conversion.

Examples include:

```text
Tr
NA
*
blank cells
merged headers
units
footnotes
```

The parser therefore works directly with the original workbook structure.

---

# Parsing strategy

The parser is intentionally strict.

It verifies expected:

* worksheets;
* columns;
* headers;
* nutrient positions;
* identifiers;
* units;
* value types.

Unexpected structures are treated as errors rather than guessed automatically.

This design is intended to prevent a modified workbook from being silently interpreted using assumptions developed for another version.

The main parser implementation is located in:

```text
src/taco_rdf/parse.py
```

---

# Representation of numeric and non-numeric values

One of the central modelling decisions in TACO-RDF is that the content of a nutrient cell is not always a number.

TACO contains several states.

## Numeric values

A numeric value represents a reported quantitative nutrient result.

For example:

```text
2.59 g protein / 100 g edible portion
```

Numeric values are represented using QUDT quantities and units.

---

## Trace values

TACO uses:

```text
Tr
```

to represent trace amounts.

A trace value is not converted to zero.

This is important because:

```text
trace ≠ zero
```

The source states that the substance is present at a trace level, not that it is absent.

---

## Not applicable

```text
NA
```

is represented separately.

It does not mean zero and does not necessarily mean that the value is unknown.

---

## Under re-evaluation

TACO also contains:

```text
*
```

for values marked for re-evaluation.

TACO-RDF preserves this status instead of converting it into a numeric or generic missing value.

---

## Blank cells

Blank cells are not automatically converted to zero or to a synthetic measurement.

The absence of a represented observation is kept distinct from an explicit value.

---

# RDF model

The graph contains resources representing:

```text
foods
food groups
nutrients
nutrient observations
value status
measurement units
reference basis
source provenance
semantic mappings
mapping assertions
```

A simplified relationship is:

```text
Food
 │
 ├── belongs to ─────────► Food Group
 │
 └── has observation ────► Nutrient Observation
                              │
                              ├── nutrient
                              ├── numeric value
                              ├── unit
                              ├── value status
                              ├── reference basis
                              └── provenance
```

---

# Example food

A food resource can be represented conceptually as:

```turtle
tacoid:food/1
    a taco:Food ;
    taco:foodNumber 1 ;
    skos:prefLabel "Arroz, integral, cozido"@pt ;
    taco:inGroup tacoid:group/1 .
```

Each food uses a stable project identifier based on its TACO identity.

---

# Nutrient observations

Nutrient measurements are represented as resources instead of placing every numeric literal directly on the food.

Conceptually:

```turtle
tacoid:measurement/1/protein
    a taco:NutrientMeasurement ;
    taco:ofFood tacoid:food/1 ;
    taco:ofNutrient tacoid:nutrient/protein ;
    taco:referenceBasis tacoid:reference/edible-portion-100g ;
    qudt:numericValue 2.59 ;
    qudt:unit unit:GM .
```

This structure allows additional information to be associated with the observation itself.

For example:

```text
status
provenance
reference basis
unit
source correction
future methodological metadata
```

A direct property such as:

```text
food → protein → 2.59
```

would make that information significantly harder to represent.

---

# Reference basis

Food-composition values are only meaningful when their basis is known.

TACO primarily reports composition per:

> **100 g of edible portion**

TACO-RDF represents this basis explicitly.

This prevents a downstream application from assuming that values reported:

```text
per 100 g
per serving
per 100 mL
per dry weight
```

are directly comparable.

---

# Why RDF?

RDF was chosen because the project represents relationships between heterogeneous concepts rather than only rectangular tabular data.

A relational or CSV representation is appropriate for storing the original numbers.

RDF adds another layer:

```text
food
    ↓
belongs to food group

food
    ↓
has nutrient observation

observation
    ↓
describes nutrient

nutrient
    ↓
mapped to external semantic concept

food
    ↓
mapped/classified using an external food ontology
```

This makes relationships explicit and queryable.

---

# Why OWL?

OWL is used to define the semantics of the TACO-RDF vocabulary.

The ontology is stored at:

```text
ontology/taco.ttl
```

It describes important concepts such as:

```text
Food
FoodGroup
Nutrient
NutrientMeasurement
ValueStatus
ReferenceBasis
AlignmentAssertion
```

OWL is used where formal semantic relationships are useful.

The project intentionally avoids adding stronger OWL axioms simply for convenience when those axioms could introduce incorrect inferences.

---

# Why SKOS?

SKOS is used for two main purposes.

First, it represents controlled conceptual structures such as nutrient categories.

Second, it allows mappings whose semantic strength differs.

Examples include:

```text
skos:closeMatch
skos:relatedMatch
skos:broadMatch
skos:narrowMatch
```

This is important because external ontology alignment is rarely binary.

For example, a Brazilian preparation may be related to an international food concept without being identical to it.

Using `owl:sameAs` in such cases would overstate the relationship.

---

# Why FoodOn?

**FoodOn** is an ontology designed specifically for food-related concepts.

It provides identifiers and semantic classes for areas including:

```text
food products
ingredients
food sources
preparations
food organisms
processed foods
```

TACO-RDF uses FoodOn to investigate semantic interoperability between Brazilian foods and internationally defined food concepts.

However, FoodOn is treated as an external semantic reference rather than as a replacement for the TACO classification system.

TACO food identities remain preserved.

When no sufficiently accurate FoodOn concept exists, the project does not force a mapping.

---

# Why ChEBI?

**ChEBI — Chemical Entities of Biological Interest** is used when a nutrient corresponds meaningfully to a chemical entity.

Examples can include:

```text
minerals
vitamins
amino acids
fatty acids
specific chemical compounds
```

However:

> a nutrient measurement concept is not always identical to a chemical entity.

For that reason, mapping relationships are chosen conservatively.

---

# Why CDNO?

The **Compositional Dietary Nutrition Ontology (CDNO)** provides semantic concepts associated with dietary and compositional nutrients.

It complements ChEBI.

The distinction is useful because:

```text
chemical identity
```

and

```text
nutritional measurement concept
```

are related but not always identical concepts.

Using more than one semantic resource allows the project to avoid forcing all nutrient semantics into a purely chemical interpretation.

---

# Why QUDT?

**QUDT — Quantities, Units, Dimensions and Data Types** is used to represent quantitative values and units.

For example:

```text
g
mg
µg
kJ
kcal
```

Using external unit identifiers is preferable to storing arbitrary strings such as:

```text
"mg"
```

because software can understand that multiple representations refer to formally defined measurement units.

---

# Why PROV-O?

Scientific data transformations need provenance.

**PROV-O** is used to describe information such as:

```text
source dataset
source file
transformation activity
generated graph
software
input checksums
processing relationships
```

This helps answer questions such as:

> Where did this RDF resource come from?

> Which source file generated it?

> Was the value taken directly from TACO or affected by a documented correction?

> Which transformation produced this version?

---

# Why DCAT?

**DCAT — Data Catalog Vocabulary** is used to provide machine-readable metadata about the published dataset.

This includes concepts such as:

```text
dataset
distribution
download artifact
media type
landing page
```

DCAT improves FAIR publication and dataset discovery.

---

# Why SHACL?

Valid RDF syntax does not guarantee a correct TACO graph.

For example, all of the following could still produce syntactically valid RDF:

```text
a food without a group
a numeric value without a unit
a duplicate nutrient observation
an invalid value status
an impossible ontology mapping
```

SHACL is therefore used to validate constraints on the graph.

Shapes are stored in:

```text
shapes/
```

Validation covers several categories.

## Structural constraints

Examples:

* required food identifiers;
* required labels;
* required food groups;
* correct value structures;
* unit requirements.

## Semantic constraints

Examples:

* valid alignment structures;
* valid target classes;
* controlled statuses.

## Consistency constraints

Examples:

* duplicate observations;
* incompatible combinations of status and numeric values.

## Plausibility checks

Some unusual values are treated as warnings rather than automatically changed.

This follows an important principle:

> A suspicious source value should be flagged, not silently rewritten.

---

# Documented corrections

The project contains explicit correction files under:

```text
data/corrections/
```

Corrections are deliberately kept outside of the parsing code.

This means a source correction is data, not an invisible conditional such as:

```python
if food == 123:
    value = ...
```

Each correction records enough information to identify what was expected and what should be substituted.

The parser also checks that the expected original value is actually present before applying a correction.

This protects against accidentally applying a correction to a different source release.

---

# Semantic alignment

External ontology mappings are stored separately from the core source data.

This separation is intentional.

A TACO value can be correct even when an ontology mapping is incorrect.

Therefore:

```text
source transformation
```

and

```text
semantic interpretation
```

must be independently inspectable.

Mappings may include:

```text
rdf:type
skos:closeMatch
skos:relatedMatch
skos:broadMatch
skos:narrowMatch
```

depending on the relationship being expressed.

---

# Mapping provenance

A plain triple such as:

```turtle
tacoid:food/123 skos:closeMatch foodon:XXXX .
```

does not answer questions such as:

```text
Who created the mapping?
When was it created?
Was it reviewed?
Which ontology release was used?
What evidence supported the decision?
Was it manually selected or automatically suggested?
```

For this reason, TACO-RDF also represents mappings as alignment assertions containing metadata about the mapping process.

This richer representation allows the direct mapping triple to remain queryable while preserving research provenance.

---

# Human review of ontology mappings

Ontology alignment is treated as an evaluation problem.

A target IRI existing in an ontology does **not** prove that the mapping is semantically correct.

The project therefore includes infrastructure for human review.

The review protocol is documented under:

```text
docs/alignment-review.md
```

A review round can record:

```text
food identifier
food name
existing mapping
candidate concept
mapping relation
decision
certainty
justification
evidence
reviewer
review date
ontology version
```

Two reviewers can evaluate the same sample independently, followed by adjudication of disagreements.

---

# Reproducible review rounds

Review rounds include manifests containing checksums of the inputs used to generate them.

Examples include hashes of:

```text
alignment tables
translated labels
review protocol
ontology module
sample context
```

This prevents a review from silently changing because one of its underlying files was modified halfway through the process.

The intended principle is:

> The exact inputs used in a scientific evaluation must remain identifiable after the evaluation has been completed.

---

# SSSOM

Reviewed mappings can be represented using:

**SSSOM — Simple Standard for Sharing Ontological Mappings.**

SSSOM provides a standardized tabular representation for ontology mappings and associated metadata.

This makes mappings easier to:

```text
exchange
review
compare
reuse
version
process automatically
```

while the RDF graph can retain a richer project-specific representation.

---

# Ontology versioning

Ontology mappings depend on external ontologies that evolve over time.

A mapping such as:

```text
TACO food → FOODON class
```

is therefore incomplete unless the target ontology version is known.

The project maintains a local FoodOn module containing the classes relevant to the current mapping set.

This allows important semantic checks to be reproduced without relying entirely on a remote API whose underlying ontology may change.

---

# Candidate generation

Automatic search is used to assist human annotation.

It is not considered authoritative.

The current workflow can use translated food descriptions to retrieve candidate ontology concepts.

Conceptually:

```text
TACO food
      │
      ▼
Portuguese description
      │
      ▼
English retrieval description
      │
      ▼
candidate generation
      │
      ▼
candidate ontology classes
      │
      ▼
semantic evaluation
      │
      ▼
mapping decision
```

Candidate generation should therefore be understood as:

> **information retrieval**

rather than:

> **automatic ontology truth assignment**.

---

# Cross-checking the source transformation

TACO-RDF includes tests comparing the parser output against an independent transcription of TACO.

The purpose is to detect errors such as:

```text
wrong spreadsheet column
incorrect row association
incorrect value parsing
incorrect nutrient assignment
incorrect fatty-acid parsing
incorrect amino-acid parsing
```

The independent transcription is not used to replace the original TACO workbook.

It serves as an external consistency check.

---

# Testing philosophy

The test suite is not limited to checking whether Python functions execute.

Tests cover several layers.

## Parsing tests

Verify correct interpretation of the source workbook.

## Data-integrity tests

Verify expected numbers of foods, nutrients and observations.

## Cross-check tests

Compare results against independently available structured data.

## RDF tests

Verify expected graph structures and semantic relationships.

## SHACL tests

Verify that correct graphs conform to the shapes.

## Mutation tests

Introduce deliberate errors and verify that validation actually detects them.

## Mapping tests

Verify assumptions involving external ontology identifiers and semantic classifications.

## Publication safety tests

Verify that publication tooling does not accidentally overwrite or remove unrelated user files.

## Review-integrity tests

Verify reproducibility of ontology-alignment evaluation rounds.

---

# SPARQL queries

The graph can be queried using SPARQL.

Queries are stored under:

```text
queries/
```

They support questions involving:

```text
foods
food groups
nutrients
nutrient composition
value statuses
amino acids
fatty acids
ontology mappings
provenance
reference basis
source corrections
alignment evidence
```

Example:

```bash
taco-rdf query richest_in --bind key=iron
```

SPARQL allows users to move beyond fixed tables and ask graph-oriented questions involving several types of resources simultaneously.

---

# Building the knowledge graph

Create a Python environment:

```bash
python -m venv .venv
```

Activate it.

Windows PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
```

Linux/macOS:

```bash
source .venv/bin/activate
```

Install the development environment:

```bash
pip install -e ".[dev]"
```

Build the graph:

```bash
taco-rdf build
```

The build command reads the source data, constructs the RDF graph, adds metadata and semantic alignments, and serializes the resulting dataset.

---

# Validation

Validate a generated graph with SHACL:

```bash
taco-rdf validate
```

Validation results distinguish between:

```text
violations
warnings
informational findings
```

A validation warning does not necessarily mean that TACO-RDF generated incorrect RDF.

It can instead identify a scientifically suspicious value already present in the original source.

---

# Running queries

Example:

```bash
taco-rdf query protein
```

or:

```bash
taco-rdf query richest_in --bind key=iron
```

Available queries can be inspected under:

```text
queries/
```

---

# Running tests

Run the complete automated test suite:

```bash
pytest
```

Run linting:

```bash
ruff check .
```

The project uses continuous integration so that these checks can also be executed automatically for repository changes.

---

# FAIR principles

TACO-RDF aims to improve the FAIR properties of TACO-derived semantic data.

## Findable

The project provides:

* persistent repository;
* dataset metadata;
* versioned releases;
* DOI support;
* machine-readable descriptions.

## Accessible

The generated graph can be distributed using standard RDF serializations and queried using standard Semantic Web tools.

## Interoperable

The project reuses established vocabularies instead of defining unnecessary local equivalents.

These include:

```text
RDF
RDFS
OWL
SKOS
QUDT
PROV-O
DCAT
FoodOn
ChEBI
CDNO
SSSOM
```

## Reusable

The project provides:

* explicit provenance;
* documented transformations;
* machine-readable metadata;
* validation rules;
* source checks;
* versioning;
* automated tests;
* mapping provenance.

---

# Important limitations

TACO-RDF deliberately documents what has **not** yet been established.

## Mapping coverage is not mapping accuracy

The existence of a FoodOn mapping does not prove that the selected semantic target is correct.

---

## Some foods do not have adequate external equivalents

Brazilian foods may contain cultural, culinary or ingredient distinctions not represented by available ontology classes.

The project prefers leaving such resources unmapped or weakly related instead of forcing false equivalence.

---

## English labels are project translations

English food names are provided to improve international accessibility and ontology retrieval.

They are not official translations published by NEPA-UNICAMP.

---

## Numeric provenance can be improved further

The current model distinguishes numeric values from non-numeric statuses, but future versions may provide a more detailed distinction between:

```text
analytically measured
calculated
derived
estimated
```

numeric values.

---

## Ontologies evolve

FoodOn, ChEBI, CDNO and other external semantic resources change over time.

Mappings should therefore always be interpreted together with their recorded target ontology version.

---

## The current software is primarily repository-oriented

The project is currently designed to run from a repository checkout containing the source data, ontology, SHACL shapes and supporting resources.

A future version may package these resources differently for standalone Python installation.

---

# What TACO-RDF does not do

TACO-RDF does not:

* replace the official TACO publication;
* claim ownership of the original TACO nutritional measurements;
* treat external ontology coverage as proof of semantic correctness;
* automatically convert trace values to zero;
* silently repair suspicious nutritional values;
* force every Brazilian food into an international ontology;
* treat approximate food concepts as exact equivalents;
* claim that translated English labels are official TACO terminology.

---

# Current research directions

Current work focuses on:

* systematic human validation of food ontology mappings;
* improving provenance for alignment decisions;
* evaluating mapping quality across different categories of Brazilian foods;
* distinguishing difficult regional and composite foods from straightforward mappings;
* improving semantic modelling of measured versus calculated values;
* formalizing competency questions;
* strengthening reference-basis modelling;
* improving reproducibility of ontology alignment;
* increasing interoperability without removing TACO-specific semantics.

A particularly important research question is:

> **To what extent can an international food ontology represent culturally specific foods from a Brazilian food-composition database without losing meaningful culinary and nutritional distinctions?**

---

# Citation

If you use TACO-RDF in academic work, please cite the project using the metadata provided in:

```text
CITATION.cff
```

or the DOI associated with the corresponding release.

---

# Source attribution

The nutritional data represented by this project originate from:

**NEPA — Núcleo de Estudos e Pesquisas em Alimentação.
Tabela Brasileira de Composição de Alimentos — TACO.
4th revised and expanded edition.
UNICAMP, Campinas, 2011.**

TACO-RDF is an independent semantic representation and software project.

It does not replace or modify the original publication.

Users should consult the original TACO documentation for authoritative information regarding its methodology, sampling, analytical procedures and source-data conditions.

---

# License

The project distinguishes between the software produced by TACO-RDF and source-derived data.

Software code is distributed under the license specified in:

```text
LICENSE
```

Semantic artifacts and project-generated data use the licensing information provided in the corresponding dataset metadata.

The original TACO content remains subject to the terms associated with its original publication.

---

# Author

**Vitória Maia**

Computer Science
Universidade Estadual do Ceará — UECE

Research interests:

* Artificial Intelligence
* Knowledge Graphs
* Semantic Web
* Machine Learning
* Health and Nutrition Data
* Explainable AI
* FAIR Data
* Semantic Interoperability

GitHub: [Victoria125](https://github.com/Victoria125)

---

# Acknowledgements

This project uses and builds upon open standards and community-maintained semantic resources including RDF, OWL, SKOS, SHACL, SPARQL, QUDT, PROV-O, DCAT, FoodOn, ChEBI, CDNO and SSSOM.

TACO-RDF also acknowledges the work of **NEPA-UNICAMP**, whose Brazilian Food Composition Table provides the scientific source data represented by this project.
