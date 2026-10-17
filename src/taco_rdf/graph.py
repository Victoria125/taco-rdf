from __future__ import annotations

import csv
import hashlib
import json
from collections import defaultdict
from dataclasses import asdict, dataclass
from decimal import Decimal
from pathlib import Path

from rdflib import Graph, Literal, URIRef

from . import __version__
from . import metadata as meta
from .groups import GROUP_LABELS_EN
from .namespaces import (
    ALIGNMENTS_CSV,
    CDNO_MODULE_TTL,
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
    OWL,
    POLICY_TTL,
    PREFIXES,
    PROV,
    QUDT,
    RDF,
    RDFS,
    REVIEW_DIR,
    ROOT,
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
_CDNO = str(OBO) + "CDNO_"
_ORGANISM_ROOTS = (OBO.COB_0000022, OBO.PO_0000003)
_FOOD_MATERIAL = OBO.FOODON_00002403

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
    """Read curation inputs, including historical food SKOS candidates that are not published."""
    with open(path, newline="", encoding="utf-8") as fh:
        return [Alignment(**row) for row in csv.DictReader(fh)]


def is_foodon_food_link(a: Alignment) -> bool:
    """A food's link to a FoodOn class: the mapping that review rounds judge.

    A food may also link to items of other datasets (a NEVO code, say); those links are outside
    the FoodOn review, so they neither take part in it nor carry its review status.
    """
    return a.source_type == "food" and a.target_iri.startswith(_FOODON)


def is_published_alignment(a: Alignment) -> bool:
    """A food is linked to FoodOn only by class membership, as NICE-Food types its food items.

    Keep legacy SKOS candidates to FoodOn in the input so ongoing review rounds retain their
    original evidence. They are neither asserted nor promoted to rdf:type. SKOS links from a
    food to another dataset's item (NICE-Food links LCA items to NEVO codes with
    skos:closeMatch) and the group and nutrient SKOS mappings are published.
    """
    return not is_foodon_food_link(a) or a.predicate == "type"


def cdno_measurement_types(alignments: list[Alignment]) -> dict[str, URIRef]:
    """The CDNO class that types every measurement of a nutrient, by nutrient key.

    NICE-Food types each NEVO nutritional value with its annotated CDNO class. Here that class
    comes from the nutrient's closeMatch or exactMatch to CDNO; a relatedMatch (one isomer for an
    unspecified position, vitamin A for retinol equivalents, cysteine for cystine) types nothing.
    """
    types: dict[str, URIRef] = {}
    for a in alignments:
        if a.source_type != "nutrient" or a.predicate not in ("closeMatch", "exactMatch"):
            continue
        if not a.target_iri.startswith(_CDNO):
            continue
        if a.source_key in types:
            raise ValueError(f"nutrient {a.source_key} has more than one close CDNO class")
        types[a.source_key] = URIRef(a.target_iri)
    return types


@dataclass(frozen=True)
class ReviewRound:
    """A scored round of alignment review: its SSSOM export and the manifest it was prepared under."""

    name: str
    sssom: Path
    protocol_sha256: str
    foodon_release: str


@dataclass(frozen=True)
class ReviewedMapping:
    """A food's mapping as a review round left it; an empty target means no FoodOn class fits."""

    food: int
    predicate: str
    target_iri: str
    reviewers: tuple[str, ...]
    reviewed_on: str
    round: ReviewRound


_SSSOM_PREDICATE = {"rdf:type": "type", "skos:closeMatch": "closeMatch", "skos:exactMatch": "exactMatch",
                    "skos:narrowMatch": "narrowMatch", "skos:broadMatch": "broadMatch",
                    "skos:relatedMatch": "relatedMatch"}


def read_review_round(folder: Path) -> list[ReviewedMapping]:
    """The mappings of one scored round, from its reviewed.sssom.tsv."""
    folder = Path(folder)
    manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
    review = ReviewRound(folder.name, folder / "reviewed.sssom.tsv", manifest["protocol_sha256"],
                         manifest["foodon_release"])
    with open(review.sssom, newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader((line for line in fh if not line.startswith("#")), delimiter="\t"))
    mappings = []
    for row in rows:
        subject, target = row["subject_id"], row["object_id"]
        if not subject.startswith("tacoid:food/"):
            raise ValueError(f"{review.sssom}: not a TACO food: {subject}")
        if target != "sssom:NoTermFound" and not target.startswith("FOODON:"):
            raise ValueError(f"{review.sssom}: {subject} is mapped outside FoodOn: {target}")
        if row["object_source_version"] != review.foodon_release:
            raise ValueError(f"{review.sssom}: {subject} was reviewed against another FoodOn release")
        unmapped = target == "sssom:NoTermFound"
        mappings.append(ReviewedMapping(
            food=int(subject.removeprefix("tacoid:food/")),
            predicate="" if unmapped else _SSSOM_PREDICATE[row["predicate_id"]],
            target_iri="" if unmapped else _FOODON + target.removeprefix("FOODON:"),
            reviewers=tuple(r.strip() for r in row["author_label"].split(";") if r.strip()),
            reviewed_on=row["mapping_date"], round=review))
    return mappings


def _round_number(folder: Path) -> int:
    number = folder.name.removeprefix("round-")
    if not number.isdigit():
        raise ValueError(f"a scored review round must be named round-<number>: {folder}")
    return int(number)


def load_reviewed_mappings(review_dir: Path = REVIEW_DIR) -> dict[int, ReviewedMapping]:
    """The latest reviewed mapping of each food, over every scored round.

    Later rounds supersede earlier ones.
    """
    reviewed: dict[int, ReviewedMapping] = {}
    folders = [f for f in Path(review_dir).glob("round-*") if (f / "reviewed.sssom.tsv").is_file()]
    for folder in sorted(folders, key=_round_number):
        for mapping in read_review_round(folder):
            reviewed[mapping.food] = mapping
    return reviewed


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
    reviewed: dict[int, ReviewedMapping] | None = None,
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
        g.parse(CDNO_MODULE_TTL, format="turtle")
    if include_policy:
        g.parse(POLICY_TTL, format="turtle")

    missing = [n for n in table.groups if n not in GROUP_LABELS_EN]
    if missing:
        raise ValueError(f"no English label for groups: {missing}")

    _add_dataset_metadata(g, source_file)
    _add_categories_and_nutrients(g)
    _add_groups(g, table)
    _add_foods(g, table, food_names_en or {})
    _add_measurements(g, table, cdno_measurement_types(alignments))
    _add_alignments(g, alignments, table, reviewed or {})
    return g


def _add_dataset_metadata(g: Graph, source_file: Path) -> None:
    dataset, source = ID["dataset"], ID["source"]
    nepa, software, activity = ID["agent/nepa-unicamp"], ID["agent/taco-rdf"], ID["conversion"]
    creator = ID["agent/vitoria-maia"]

    g.add((dataset, RDF.type, DCAT.Dataset))
    g.add((dataset, RDF.type, PROV.Entity))
    g.add((dataset, DCTERMS.title, Literal(meta.TITLE, lang="en")))
    g.add((dataset, DCTERMS.description, Literal(
        "The Brazilian Food Composition Table (TACO), 4th edition, converted to RDF: 597 foods in 15 "
        "groups, with proximate composition, minerals, vitamins, fatty acids and amino acids per 100 g "
        "of edible portion. Foods are Food Item Ontology (FIO) food items; FoodOn class membership, "
        "where supported, is expressed only with rdf:type. "
        "nutrients are aligned to ChEBI and CDNO, and their measurements are typed with the closely "
        "matching CDNO class. Food names are TACO's Portuguese names, with English "
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


def _decimal_literal(value: Decimal) -> Literal:
    """An xsd:decimal whose lexical form has a decimal point, as Turtle writes it.

    rdflib writes an integral decimal such as "953" as 953.0 in Turtle, which parses back as a different
    literal; with the point already there, the graph, taco.ttl and taco.nt carry the same terms.
    """
    text = format(value, "f")
    return Literal(text if "." in text else text + ".0", datatype=XSD.decimal)


def _add_measurements(g: Graph, table: Table, cdno_types: dict[str, URIRef]) -> None:
    """Add every measurement, typed with its nutrient's CDNO class whatever its value status.

    The CDNO class says which concentration the measurement is about; taco:valueStatus says
    what TACO reports for it.
    """
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
        if obs.nutrient in cdno_types:
            g.add((m, RDF.type, cdno_types[obs.nutrient]))
        g.add((m, TACO.ofFood, food_iri(obs.food_id)))
        g.add((m, TACO.ofNutrient, nutrient_iri(obs.nutrient)))
        g.add((m, TACO.valueStatus, TACO[obs.status.value]))
        g.add((m, TACO.referenceBasis, basis))
        if obs.status is Status.MEASURED:
            if obs.value is None:
                raise ValueError(f"food {obs.food_id} {obs.nutrient}: measured, but no value")
            g.add((m, QUDT.numericValue, _decimal_literal(obs.value)))
            g.add((m, QUDT.unit, UNIT[nutrient.qudt_unit]))
        origin = _ORIGIN.get(obs.origin)
        if origin is not None:
            g.add((m, TACO.valueOrigin, origin))
        if obs.note:
            g.add((m, SKOS.editorialNote, Literal(obs.note, lang="en")))


def _check_reviews(alignments: list[Alignment], reviewed: dict[int, ReviewedMapping], table: Table) -> None:
    """Refuse to build while a food's FoodOn mapping differs from the one its latest review arrived at.

    Only FoodOn links are compared; a food's links to other datasets' items are left alone.
    """
    current: dict[int, set[tuple[str, str]]] = defaultdict(set)
    for a in alignments:
        if is_foodon_food_link(a):
            current[int(a.source_key)].add((a.predicate, a.target_iri))
    stale = []
    for food, review in sorted(reviewed.items()):
        if food not in table.foods:
            raise ValueError(f"{review.round.name} reviewed unknown food {food}")
        expected = {(review.predicate, review.target_iri)} if review.target_iri else set()
        if current.get(food, set()) != expected:
            stale.append(f"{food} ({review.round.name})")
    if stale:
        raise ValueError("alignments.csv differs from the reviewed mapping of foods " + ", ".join(stale)
                         + "; apply the round with scripts/apply_alignment_review.py")


def _add_review_rounds(g: Graph, reviewed: dict[int, ReviewedMapping]) -> dict[str, URIRef]:
    rounds = {}
    for review in sorted({r.round for r in reviewed.values()}, key=lambda r: r.name):
        node = ID["review/" + review.name]
        g.add((node, RDF.type, TACO.ReviewRound))
        g.add((node, RDF.type, PROV.Entity))
        g.add((node, DCTERMS.title, Literal(f"TACO alignment review, {review.name}", lang="en")))
        path = review.sssom.resolve()
        g.add((node, TACO.sourceFile, Literal(
            path.relative_to(ROOT).as_posix() if path.is_relative_to(ROOT) else path.name)))
        g.add((node, TACO.sha256, Literal(sha256_of(review.sssom))))
        g.add((node, TACO.ontologyVersion, URIRef(review.foodon_release)))
        g.add((node, SKOS.editorialNote, Literal(
            "Dual independent review with adjudication of disagreements, under docs/alignment-review.md "
            f"(SHA-256 {review.protocol_sha256} of the protocol as the round was prepared).", lang="en")))
        rounds[review.name] = node
    return rounds


def _add_alignment_set(g: Graph, alignments: list[Alignment],
                       reviewed: dict[int, ReviewedMapping]) -> URIRef:
    """Checksum every curation input, while counting only published assertions as mappings."""
    rows = sorted(json.dumps(asdict(a), sort_keys=True, ensure_ascii=False) for a in alignments)
    published = [a for a in alignments if is_published_alignment(a)]
    confirmed = sum(1 for a in published if is_foodon_food_link(a) and int(a.source_key) in reviewed)
    source = ID["alignment-set"]
    g.add((source, RDF.type, PROV.Entity))
    g.add((source, DCTERMS.title, Literal(
        "TACO alignment curation inputs supplied to this build", lang="en")))
    g.add((source, TACO.sha256, Literal(hashlib.sha256("\n".join(rows).encode()).hexdigest())))
    g.add((source, SKOS.editorialNote, Literal(
        "Checksum of sorted, newline-joined JSON rows (UTF-8, sorted keys, ensure_ascii=False). "
        f"The {len(alignments)} input rows yield {len(published)} published assertions; "
        f"{len(alignments) - len(published)} historical food-to-FoodOn SKOS candidates are withheld. "
        "Food-to-FoodOn mappings are published only as rdf:type; withheld candidates remain review evidence. "
        "Original annotation dates, individual annotator identities and target ontology releases "
        f"were not recorded. {confirmed} of the {len(published)} assertions have since been independently "
        "reviewed (taco:Reviewed); independent semantic review of the others is pending.", lang="en")))
    g.add((source, DCTERMS.publisher, ID["agent/vitoria-maia"]))
    g.add((ID["conversion"], PROV.used, source))
    return source


def _alignment_subject(a: Alignment, table: Table) -> URIRef:
    """The group, nutrient or food an alignment is about; one the workbook does not have is refused."""
    if a.source_type == "group":
        if not 1 <= int(a.source_key) <= len(table.groups):
            raise ValueError(f"alignment refers to unknown group {a.source_key}")
        return group_iri(int(a.source_key))
    if a.source_type == "nutrient":
        if a.source_key not in BY_KEY:
            raise ValueError(f"alignment refers to unknown nutrient {a.source_key}")
        return nutrient_iri(a.source_key)
    if a.source_type == "food":
        if int(a.source_key) not in table.foods:
            raise ValueError(f"alignment refers to unknown food {a.source_key}")
        return food_iri(int(a.source_key))
    raise ValueError(f"unknown alignment source_type {a.source_type!r}")


def _add_review_status(g: Graph, record: URIRef, review: ReviewedMapping | None,
                       rounds: dict[str, URIRef]) -> None:
    if review is None:
        g.add((record, TACO.reviewStatus, TACO.Unreviewed))
        g.add((record, TACO.ontologyVersionStatus, TACO.NotRecorded))
    else:
        g.add((record, TACO.reviewStatus, TACO.Reviewed))
        g.add((record, TACO.ontologyVersionStatus, TACO.Recorded))
        g.add((record, TACO.ontologyVersion, URIRef(review.round.foodon_release)))
        g.add((record, PROV.wasDerivedFrom, rounds[review.round.name]))
        g.add((record, DCTERMS.date, Literal(review.reviewed_on, datatype=XSD.date)))
        for name in review.reviewers:
            g.add((record, TACO.reviewer, Literal(name)))


def _add_alignments(g: Graph, alignments: list[Alignment], table: Table,
                    reviewed: dict[int, ReviewedMapping]) -> None:
    _check_reviews(alignments, reviewed, table)
    rounds = _add_review_rounds(g, reviewed)
    source = _add_alignment_set(g, alignments, reviewed)
    modules: dict[Path, Graph] = {}
    for a in alignments:
        subject = _alignment_subject(a, table)
        if a.predicate not in _MATCH:
            raise ValueError(f"unknown alignment predicate {a.predicate!r}")
        if not is_published_alignment(a):
            continue
        target = URIRef(a.target_iri)
        _check_target(a, target, modules)
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
        g.add((record, TACO.targetOntology, Literal(a.target_ontology)))
        review = reviewed.get(int(a.source_key)) if is_foodon_food_link(a) else None
        _add_review_status(g, record, review, rounds)
        if a.note:
            g.add((record, SKOS.editorialNote, Literal(a.note, lang="en")))


def _check_target(a: Alignment, target: URIRef, modules: dict[Path, Graph]) -> None:
    """Check a published target against the pinned module it must come from, parsing each module once."""
    def module(path: Path) -> Graph:
        if path not in modules:
            modules[path] = Graph().parse(path, format="turtle")
        return modules[path]

    if a.predicate == "type":
        _check_food_typing(module(FOODON_MODULE_TTL), a, target)
    if a.target_iri.startswith(_CDNO):
        _check_cdno_class(module(CDNO_MODULE_TTL), a, target)


def _check_cdno_class(cdno: Graph, a: Alignment, target: URIRef) -> None:
    """Refuse a CDNO target the pinned module lacks: it would type measurements with an unchecked class."""
    if (target, RDF.type, OWL.Class) not in cdno or (target, RDFS.label, None) not in cdno:
        where = f"{a.source_type} {a.source_key} {a.predicate} {target}"
        raise ValueError(f"CDNO class missing from {CDNO_MODULE_TTL.name}; re-run "
                         f"scripts/extract_cdno_module.py: {where}")


def foodon_typing_obstacle(foodon: Graph, target: URIRef) -> str:
    """Why the FoodOn module cannot back rdf:type with this class; empty when it can.

    ``organism_class`` is a class of whole organisms or plants. ``foodon_axiom_conflict`` is a
    food material class that FoodOn also places under whole organisms or plants (bean pod is_a
    bean sprout is_a bean plant): FoodOn has a class for the food, but typing with it would
    entail that the food is an organism. NICE-Food's notebooks type food items without this check.
    """
    if (target, RDF.type, OWL.Class) not in foodon or (target, RDFS.label, None) not in foodon:
        return "missing_class"
    if any(value.toPython() is True for value in foodon.objects(target, OWL.deprecated)):
        return "deprecated_class"
    ancestors = set(foodon.transitive_objects(target, RDFS.subClassOf))
    if not ancestors & set(_ORGANISM_ROOTS):
        return ""
    return "foodon_axiom_conflict" if _FOOD_MATERIAL in ancestors else "organism_class"


def _check_food_typing(foodon: Graph, a: Alignment, target: URIRef) -> None:
    """Refuse an rdf:type the FoodOn module cannot back: unknown class, or one under whole organisms."""
    where = f"{a.source_type} {a.source_key} rdf:type {target}"
    if a.source_type != "food" or not str(target).startswith(_FOODON):
        raise ValueError(f"only foods can be typed, and only with FoodOn classes: {where}")
    obstacle = foodon_typing_obstacle(foodon, target)
    if obstacle == "missing_class":
        raise ValueError(f"FoodOn class missing from {FOODON_MODULE_TTL.name}; re-run "
                         f"scripts/extract_foodon_module.py: {where}")
    if obstacle == "deprecated_class":
        raise ValueError(f"FoodOn class is deprecated: {where}")
    if obstacle == "organism_class":
        raise ValueError(f"FoodOn class is a class of whole organisms, not of food: {where}")
    if obstacle == "foodon_axiom_conflict":
        raise ValueError("FoodOn places this food class under whole organisms or plants, so rdf:type "
                         f"would make the food an organism; report the axiom to FoodOn: {where}")
