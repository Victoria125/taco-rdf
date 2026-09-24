from __future__ import annotations

import csv
import hashlib
import json
from dataclasses import asdict, dataclass
from decimal import Decimal
from pathlib import Path

from rdflib import Graph, Literal, URIRef

from . import __version__
from . import metadata as meta
from .groups import GROUP_LABELS_EN
from .namespaces import (
    ALIGNMENTS_CSV,
    DCAT,
    DCTERMS,
    FIO,
    FOAF,
    FOOD_NAMES_EN,
    FOODON_MODULE_TTL,
    ID,
    OBO,
    ODRL,
    ONTOLOGY_TTL,
    POLICY_TTL,
    PREFIXES,
    PROV,
    QUDT,
    RDF,
    RDFS,
    SKOS,
    TACO,
    UNIT,
    XSD,
)
from .nutrients import BY_KEY, CATEGORIES
from .parse import Status, Table

_MATCH = {
    "closeMatch": SKOS.closeMatch,
    "narrowMatch": SKOS.narrowMatch,
    "broadMatch": SKOS.broadMatch,
    "relatedMatch": SKOS.relatedMatch,
    "exactMatch": SKOS.exactMatch,
    "type": RDF.type,
}

_FOODON = str(OBO) + "FOODON_"
_ORGANISM_ROOTS = (OBO.COB_0000022, OBO.PO_0000003)

_ORIGIN = {
    "footnote": TACO.LegendFootnote,
    "cell_corrected": TACO.DocumentedCorrection,
    "id_corrected": TACO.DocumentedCorrection,
}

CITATION = (
    "NEPA-UNICAMP. Tabela brasileira de composição de alimentos - TACO. "
    "4. ed. rev. e ampl. Campinas: NEPA-UNICAMP, 2011."
)


@dataclass(frozen=True)
class Alignment:
    source_type: str
    source_key: str
    predicate: str
    target_iri: str
    target_label: str
    target_ontology: str
    note: str


def load_alignments(path: Path = ALIGNMENTS_CSV) -> list[Alignment]:
    with open(path, newline="", encoding="utf-8") as fh:
        return [Alignment(**row) for row in csv.DictReader(fh)]


@dataclass(frozen=True)
class FoodName:
    """The English name given to a TACO food. TACO publishes Portuguese names only."""

    name_pt: str
    name_en: str
    status: str
    note: str


NAME_STATUSES = ("draft", "reviewed")


def load_food_names_en(path: Path = FOOD_NAMES_EN) -> dict[int, FoodName]:
    with open(path, newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    names = {}
    for row in rows:
        food = int(row.pop("food_number"))
        if food in names:
            raise ValueError(f"food {food} has two English names in {Path(path).name}")
        names[food] = FoodName(**row)
        if names[food].status not in NAME_STATUSES or not names[food].name_en.strip():
            raise ValueError(f"food {food}: English name missing or status not in {NAME_STATUSES}")
    return names


def sha256_of(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def group_iri(group_id: int) -> URIRef:
    return ID[f"group/{group_id}"]


def food_iri(food_id: int) -> URIRef:
    return ID[f"food/{food_id}"]


def nutrient_iri(key: str) -> URIRef:
    return ID[f"nutrient/{key}"]


def measurement_iri(food_id: int, key: str) -> URIRef:
    return ID[f"measurement/{food_id}/{key}"]


def build_graph(
    table: Table,
    alignments: list[Alignment],
    *,
    source_file: Path,
    food_names_en: dict[int, FoodName] | None = None,
    include_ontology: bool = True,
    include_policy: bool = True,
) -> Graph:
    if food_names_en is not None:
        _check_food_names(table, food_names_en)
    g = Graph()
    for prefix, ns in PREFIXES.items():
        g.bind(prefix, ns)
    if include_ontology:
        g.parse(ONTOLOGY_TTL, format="turtle")
        g.parse(FOODON_MODULE_TTL, format="turtle")
    if include_policy:
        g.parse(POLICY_TTL, format="turtle")

    missing = [n for n in table.groups if n not in GROUP_LABELS_EN]
    if missing:
        raise ValueError(f"no English label for groups: {missing}")

    _add_dataset_metadata(g, source_file, table)
    _add_categories_and_nutrients(g)
    _add_groups(g, table)
    _add_foods(g, table, food_names_en or {})
    _add_measurements(g, table)
    _add_alignments(g, alignments, table)
    return g


def _add_dataset_metadata(g: Graph, source_file: Path, table: Table) -> None:
    dataset, source = ID["dataset"], ID["source"]
    nepa, software, activity = ID["agent/nepa-unicamp"], ID["agent/taco-rdf"], ID["conversion"]
    creator = ID["agent/vitoria-maia"]

    g.add((dataset, RDF.type, DCAT.Dataset))
    g.add((dataset, RDF.type, PROV.Entity))
    g.add((dataset, DCTERMS.title, Literal(meta.TITLE, lang="en")))
    g.add((dataset, DCTERMS.description, Literal(
        "The Brazilian Food Composition Table (TACO), 4th edition, converted to RDF: 597 foods in 15 "
        "groups, with proximate composition, minerals, vitamins, fatty acids and amino acids per 100 g "
        "of edible portion. Foods are Food Item Ontology (FIO) food items typed with FoodOn classes; "
        "nutrients are aligned to ChEBI and CDNO. Food names are TACO's Portuguese names, with English "
        "translations made for this project.", lang="en")))
    g.add((dataset, DCTERMS.language, Literal("pt")))
    g.add((dataset, DCTERMS.language, Literal("en")))
    g.add((dataset, DCTERMS.conformsTo, URIRef(str(TACO)[:-1])))
    g.add((dataset, PROV.wasDerivedFrom, source))
    g.add((dataset, PROV.wasGeneratedBy, activity))
    g.add((dataset, ODRL.hasPolicy, ID["policy/attribution"]))
    g.add((dataset, DCTERMS.license, URIRef(meta.DATA_LICENSE)))
    g.add((dataset, DCTERMS.rights, Literal(
        "Graph, vocabulary, shapes and alignments: CC BY 4.0. The nutrient values come from TACO, whose "
        "terms allow total or partial reproduction provided the source is cited (see the source's "
        "dcterms:rights).", lang="en")))
    g.add((dataset, DCTERMS.creator, creator))
    g.add((dataset, DCTERMS.publisher, creator))
    g.add((dataset, DCTERMS.hasVersion, Literal(__version__)))
    g.add((dataset, DCAT.landingPage, URIRef(meta.SITE_URL)))
    g.add((dataset, FOAF.page, URIRef(meta.REPO_URL)))
    for keyword in meta.KEYWORDS:
        g.add((dataset, DCAT.keyword, Literal(keyword, lang="en")))
    if meta.DOI:
        g.add((dataset, DCTERMS.identifier, Literal(f"https://doi.org/{meta.DOI}", datatype=XSD.anyURI)))
    for file_name, (media_type, label) in meta.DUMPS.items():
        dist = ID[f"distribution/{file_name.rsplit('.', 1)[1]}"]
        g.add((dataset, DCAT.distribution, dist))
        g.add((dist, RDF.type, DCAT.Distribution))
        g.add((dist, DCTERMS.title, Literal(f"Full graph as {label}", lang="en")))
        g.add((dist, DCAT.downloadURL, URIRef(meta.SITE_URL + file_name)))
        g.add((dist, DCAT.mediaType, URIRef(f"https://www.iana.org/assignments/media-types/{media_type}")))
        g.add((dist, DCTERMS.license, URIRef(meta.DATA_LICENSE)))

    g.add((creator, RDF.type, FOAF.Person))
    g.add((creator, RDF.type, PROV.Agent))
    g.add((creator, FOAF.name, Literal(meta.CREATOR)))
    g.add((creator, FOAF.mbox, URIRef(f"mailto:{meta.CREATOR_EMAIL}")))

    g.add((source, RDF.type, DCAT.Dataset))
    g.add((source, RDF.type, PROV.Entity))
    g.add((source, DCTERMS.title, Literal(
        "Tabela Brasileira de Composição de Alimentos (TACO), 4ª edição revisada e ampliada", lang="pt")))
    g.add((source, DCTERMS.title, Literal(
        "Brazilian Food Composition Table (TACO), 4th revised and expanded edition", lang="en")))
    g.add((source, DCTERMS.publisher, nepa))
    g.add((source, DCTERMS.issued, Literal("2011", datatype=XSD.gYear)))
    g.add((source, DCTERMS.bibliographicCitation, Literal(CITATION)))
    g.add((source, DCTERMS.rights, Literal(meta.SOURCE_TERMS, lang="pt")))
    g.add((source, DCTERMS.rights, Literal(meta.SOURCE_TERMS_EN, lang="en")))
    g.add((source, DCAT.landingPage, URIRef(meta.SOURCE_LANDING_PAGE)))
    g.add((source, FOAF.page, URIRef(meta.SOURCE_PDF)))
    g.add((source, TACO.sourceFile, Literal(Path(source_file).name)))
    g.add((source, TACO.sha256, Literal(sha256_of(source_file))))

    g.add((nepa, RDF.type, FOAF.Organization))
    g.add((nepa, RDF.type, PROV.Agent))
    g.add((nepa, FOAF.name, Literal(
        "NEPA-UNICAMP (Núcleo de Estudos e Pesquisas em Alimentação, Universidade Estadual de Campinas)")))

    g.add((software, RDF.type, PROV.SoftwareAgent))
    g.add((software, RDFS.label, Literal(f"taco-rdf {__version__}")))

    g.add((activity, RDF.type, PROV.Activity))
    g.add((activity, RDFS.label, Literal("Conversion of the TACO workbook to RDF", lang="en")))
    g.add((activity, PROV.used, source))
    g.add((activity, PROV.wasAssociatedWith, software))
    g.add((activity, PROV.wasAssociatedWith, creator))


def _add_categories_and_nutrients(g: Graph) -> None:
    scheme_cat, scheme_nut = TACO.NutrientCategoryScheme, TACO.NutrientScheme
    for key, (pt, en) in CATEGORIES.items():
        c = ID[f"category/{key}"]
        g.add((c, RDF.type, SKOS.Concept))
        g.add((c, SKOS.inScheme, scheme_cat))
        g.add((c, SKOS.prefLabel, Literal(pt, lang="pt")))
        g.add((c, SKOS.prefLabel, Literal(en, lang="en")))
        g.add((c, SKOS.topConceptOf, scheme_cat))

    for n in BY_KEY.values():
        iri = nutrient_iri(n.key)
        g.add((iri, RDF.type, TACO.Nutrient))
        g.add((iri, RDF.type, FIO.Nutrient))
        g.add((iri, SKOS.inScheme, scheme_nut))
        g.add((iri, SKOS.notation, Literal(n.key)))
        g.add((iri, SKOS.prefLabel, Literal(n.label_pt, lang="pt")))
        g.add((iri, SKOS.prefLabel, Literal(n.label_en, lang="en")))
        g.add((iri, SKOS.broader, ID[f"category/{n.category}"]))
        g.add((iri, TACO.unit, UNIT[n.qudt_unit]))


def _add_groups(g: Graph, table: Table) -> None:
    for gid, name in enumerate(table.groups, start=1):
        iri = group_iri(gid)
        g.add((iri, RDF.type, TACO.FoodGroup))
        g.add((iri, SKOS.inScheme, TACO.FoodGroupScheme))
        g.add((iri, SKOS.notation, Literal(str(gid))))
        g.add((iri, SKOS.prefLabel, Literal(name, lang="pt")))
        g.add((iri, SKOS.prefLabel, Literal(GROUP_LABELS_EN[name], lang="en")))


def _check_food_names(table: Table, names: dict[int, FoodName]) -> None:
    """The English names must cover exactly the foods of the workbook, under their workbook names."""
    missing = sorted(set(table.foods) - set(names))
    unknown = sorted(set(names) - set(table.foods))
    renamed = [fid for fid, n in sorted(names.items())
               if fid in table.foods and n.name_pt != table.foods[fid].name]
    if missing or unknown or renamed:
        raise ValueError(f"English food names do not match the workbook: missing {missing[:5]}, "
                         f"unknown {unknown[:5]}, Portuguese name differs for {renamed[:5]}")


def _add_foods(g: Graph, table: Table, names_en: dict[int, FoodName]) -> None:
    for food in table.foods.values():
        iri = food_iri(food.id)
        g.add((iri, RDF.type, TACO.Food))
        g.add((iri, RDF.type, FIO.FoodItem))
        g.add((iri, TACO.foodNumber, Literal(food.id)))
        g.add((iri, RDFS.label, Literal(food.name, lang="pt")))
        g.add((iri, SKOS.prefLabel, Literal(food.name, lang="pt")))
        if food.id in names_en:
            g.add((iri, SKOS.prefLabel, Literal(names_en[food.id].name_en, lang="en")))
        g.add((iri, TACO.inGroup, group_iri(food.group_id)))
        if food.footnote is not None:
            g.add((iri, TACO.footnoteMarker, Literal(food.footnote)))


def _add_measurements(g: Graph, table: Table) -> None:
    basis = ID["reference/edible-portion-100g"]
    g.add((basis, RDF.type, TACO.ReferenceBasis))
    g.add((basis, RDF.type, QUDT.QuantityValue))
    g.add((basis, RDFS.label, Literal("100 g of edible portion", lang="en")))
    g.add((basis, QUDT.numericValue, Literal(Decimal("100.0"), datatype=XSD.decimal)))
    g.add((basis, QUDT.unit, UNIT.GM))
    g.add((basis, TACO.foodPortion, TACO.EdiblePortion))
    for obs in table.observations:
        nutrient = BY_KEY[obs.nutrient]
        m = measurement_iri(obs.food_id, obs.nutrient)
        g.add((m, RDF.type, TACO.NutrientMeasurement))
        g.add((m, TACO.ofFood, food_iri(obs.food_id)))
        g.add((m, TACO.ofNutrient, nutrient_iri(obs.nutrient)))
        g.add((m, TACO.valueStatus, TACO[obs.status.value]))
        g.add((m, TACO.referenceBasis, basis))
        if obs.status is Status.MEASURED:
            g.add((m, QUDT.numericValue, Literal(obs.value, datatype=XSD.decimal)))
            g.add((m, QUDT.unit, UNIT[nutrient.qudt_unit]))
        origin = _ORIGIN.get(obs.origin)
        if origin is not None:
            g.add((m, TACO.valueOrigin, origin))
        if obs.note:
            g.add((m, SKOS.editorialNote, Literal(obs.note, lang="en")))


def _add_alignments(g: Graph, alignments: list[Alignment], table: Table) -> None:
    rows = sorted(json.dumps(asdict(a), sort_keys=True, ensure_ascii=False) for a in alignments)
    source = ID["alignment-set"]
    g.add((source, RDF.type, PROV.Entity))
    g.add((source, DCTERMS.title, Literal("TACO alignment assertions supplied to this build", lang="en")))
    g.add((source, TACO.sha256, Literal(hashlib.sha256("\n".join(rows).encode()).hexdigest())))
    g.add((source, SKOS.editorialNote, Literal(
        "Checksum of sorted, newline-joined JSON rows (UTF-8, sorted keys, ensure_ascii=False). "
        "Original annotation dates, individual annotator identities and target ontology releases "
        "were not recorded. Independent semantic review is pending.", lang="en")))
    g.add((source, DCTERMS.publisher, ID["agent/vitoria-maia"]))
    g.add((ID["conversion"], PROV.used, source))
    foodon = None
    for a in alignments:
        if a.source_type == "group":
            if not 1 <= int(a.source_key) <= len(table.groups):
                raise ValueError(f"alignment refers to unknown group {a.source_key}")
            subject = group_iri(int(a.source_key))
        elif a.source_type == "nutrient":
            if a.source_key not in BY_KEY:
                raise ValueError(f"alignment refers to unknown nutrient {a.source_key}")
            subject = nutrient_iri(a.source_key)
        elif a.source_type == "food":
            if int(a.source_key) not in table.foods:
                raise ValueError(f"alignment refers to unknown food {a.source_key}")
            subject = food_iri(int(a.source_key))
        else:
            raise ValueError(f"unknown alignment source_type {a.source_type!r}")
        target = URIRef(a.target_iri)
        if a.predicate == "type":
            foodon = foodon if foodon is not None else Graph().parse(FOODON_MODULE_TTL, format="turtle")
            _check_food_typing(foodon, a, target)
        g.add((subject, _MATCH[a.predicate], target))
        g.add((target, RDFS.label, Literal(a.target_label, lang="en")))
        identity = "\n".join((str(subject), str(_MATCH[a.predicate]), str(target)))
        record = ID["alignment/" + hashlib.sha256(identity.encode()).hexdigest()]
        g.add((subject, TACO.alignment, record))
        g.add((record, RDF.type, TACO.AlignmentAssertion))
        g.add((record, RDF.type, RDF.Statement))
        g.add((record, RDF.type, PROV.Entity))
        g.add((record, RDF.subject, subject))
        g.add((record, RDF.predicate, _MATCH[a.predicate]))
        g.add((record, RDF.object, target))
        g.add((record, PROV.wasDerivedFrom, source))
        g.add((record, TACO.reviewStatus, TACO.Unreviewed))
        g.add((record, TACO.targetOntology, Literal(a.target_ontology)))
        g.add((record, TACO.ontologyVersionStatus, TACO.NotRecorded))
        if a.note:
            g.add((record, SKOS.editorialNote, Literal(a.note, lang="en")))


def _check_food_typing(foodon: Graph, a: Alignment, target: URIRef) -> None:
    """Refuse an rdf:type the FoodOn module cannot back: unknown class, or a class of whole organisms."""
    where = f"{a.source_type} {a.source_key} rdf:type {target}"
    if a.source_type != "food" or not str(target).startswith(_FOODON):
        raise ValueError(f"only foods can be typed, and only with FoodOn classes: {where}")
    if (target, RDFS.label, None) not in foodon:
        raise ValueError(f"FoodOn class missing from {FOODON_MODULE_TTL.name}; re-run "
                         f"scripts/extract_foodon_module.py: {where}")
    ancestors = set(foodon.transitive_objects(target, RDFS.subClassOf))
    if ancestors & set(_ORGANISM_ROOTS):
        raise ValueError(f"FoodOn class is a class of whole organisms, not of food: {where}")
