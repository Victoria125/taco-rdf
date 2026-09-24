from __future__ import annotations

from dataclasses import replace
from decimal import Decimal

import pytest
from rdflib import Literal, URIRef
from rdflib.namespace import DCTERMS, PROV, RDF, RDFS, SKOS, XSD

from taco_rdf import graph as graphmod
from taco_rdf.namespaces import ID, QUDT, RAW_XLS, TACO, UNIT


def count(g, cls):
    return len(set(g.subjects(RDF.type, cls)))


def test_resource_counts(graph, table):
    assert count(graph, TACO.Food) == 597
    assert count(graph, TACO.FoodGroup) == 15
    assert count(graph, TACO.Nutrient) == 67
    assert count(graph, TACO.NutrientMeasurement) == len(table.observations) == 21150


def test_every_food_is_in_exactly_one_group(graph):
    for food in graph.subjects(RDF.type, TACO.Food):
        assert len(list(graph.objects(food, TACO.inGroup))) == 1


def test_measured_value_has_decimal_and_unit(graph):
    m = graphmod.measurement_iri(1, "moisture")
    assert graph.value(m, QUDT.numericValue) == Literal(Decimal("70.138667"), datatype=XSD.decimal)
    assert graph.value(m, QUDT.unit) == UNIT.PERCENT
    assert graph.value(m, TACO.valueStatus) == TACO.Measured
    assert graph.value(m, TACO.ofFood) == graphmod.food_iri(1)


def test_trace_is_a_status_without_a_number(graph):
    m = graphmod.measurement_iri(1, "fa_14_0")
    assert graph.value(m, TACO.valueStatus) == TACO.Trace
    assert graph.value(m, QUDT.numericValue) is None
    assert graph.value(m, QUDT.unit) is None


def test_not_applicable_and_under_reevaluation_exist(graph):
    statuses = {graph.value(m, TACO.valueStatus) for m in graph.subjects(RDF.type, TACO.NutrientMeasurement)}
    assert statuses == {TACO.Measured, TACO.Trace, TACO.NotApplicable, TACO.UnderReevaluation}


def test_units_follow_the_nutrient(graph):
    expected = {
        "protein": UNIT.GM, "moisture": UNIT.PERCENT, "energy_kcal": UNIT.KiloCAL,
        "energy_kj": UNIT.KiloJ, "iron": UNIT.MilliGM, "retinol": UNIT.MicroGM,
    }
    for key, unit in expected.items():
        assert graph.value(graphmod.nutrient_iri(key), TACO.unit) == unit


def test_labels_are_language_tagged(graph):
    label = graph.value(graphmod.food_iri(1), RDFS.label)
    assert label == Literal("Arroz, integral, cozido", lang="pt")
    g3 = graphmod.group_iri(3)
    labels = {str(label) for label in graph.objects(g3, SKOS.prefLabel)}
    assert labels == {"Frutas e derivados", "Fruits and derivatives"}


def test_every_food_has_its_taco_name_and_an_english_name(graph, table):
    for food in table.foods.values():
        names = graph.objects(graphmod.food_iri(food.id), SKOS.prefLabel)
        labels = {name.language: str(name) for name in names}
        assert labels["pt"] == food.name
        assert labels.get("en"), f"food {food.id} has no English name"
    assert (graphmod.food_iri(1), SKOS.prefLabel, Literal("Rice, brown, cooked", lang="en")) in graph


def test_english_names_that_do_not_match_the_workbook_are_refused(table, alignments, food_names_en):
    renamed = {**food_names_en, 1: replace(food_names_en[1], name_pt="Arroz, outro")}
    with pytest.raises(ValueError, match="Portuguese name differs for \\[1\\]"):
        graphmod.build_graph(table, alignments, source_file=RAW_XLS, food_names_en=renamed)
    missing = {fid: name for fid, name in food_names_en.items() if fid != 2}
    with pytest.raises(ValueError, match="missing \\[2\\]"):
        graphmod.build_graph(table, alignments, source_file=RAW_XLS, food_names_en=missing)


def test_english_names_file_is_checked_when_read(tmp_path):
    path = tmp_path / "names.csv"
    header = "food_number,name_pt,name_en,status,note\n"
    path.write_text(header + '1,"Arroz, integral, cozido","Rice, brown, cooked",final,\n', encoding="utf-8")
    with pytest.raises(ValueError, match="status"):
        graphmod.load_food_names_en(path)
    path.write_text(header + '1,"Arroz, integral, cozido",A,draft,\n1,"Arroz, integral, cozido",B,draft,\n',
                    encoding="utf-8")
    with pytest.raises(ValueError, match="two English names"):
        graphmod.load_food_names_en(path)


def test_documented_corrections_are_visible_in_the_graph(graph):
    corrected = set(graph.subjects(TACO.valueOrigin, TACO.DocumentedCorrection))
    assert graphmod.measurement_iri(373, "pyridoxine") in corrected
    assert graphmod.measurement_iri(504, "tryptophan") in corrected
    assert len(corrected) == 19
    assert set(graph.subjects(TACO.valueOrigin, TACO.LegendFootnote)) == {
        graphmod.measurement_iri(472, "alcohol"), graphmod.measurement_iri(474, "alcohol"),
    }


def test_all_groups_are_aligned_to_foodon(graph):
    for gid in range(1, 16):
        targets = set()
        for p in (SKOS.closeMatch, SKOS.narrowMatch, SKOS.broadMatch, SKOS.relatedMatch):
            targets |= set(graph.objects(graphmod.group_iri(gid), p))
        assert targets, f"group {gid} has no alignment"
        assert all(str(t).startswith("http://purl.obolibrary.org/obo/FOODON_") for t in targets)


def test_nutrient_alignments_to_chebi_and_cdno_and_the_documented_gaps(graph):
    unaligned = {"CHEBI": set(), "CDNO": set()}
    for n in graph.subjects(RDF.type, TACO.Nutrient):
        targets = [
            str(t) for p in (SKOS.closeMatch, SKOS.narrowMatch, SKOS.broadMatch, SKOS.relatedMatch)
            for t in graph.objects(n, p)
        ]
        assert all(t.startswith(("http://purl.obolibrary.org/obo/CHEBI_",
                                 "http://purl.obolibrary.org/obo/CDNO_")) for t in targets)
        for prefix, missing in unaligned.items():
            if not any(t.startswith(f"http://purl.obolibrary.org/obo/{prefix}_") for t in targets):
                missing.add(str(n).rsplit("/", 1)[1])
    assert unaligned["CHEBI"] == {"dietary_fiber", "ash", "energy_kcal", "energy_kj"}
    assert unaligned["CDNO"] == {"energy_kcal", "energy_kj", "alcohol", "fa_20_1", "fa_18_2t"}


def test_external_targets_carry_a_label(graph, alignments):
    for a in alignments:
        assert (URIRef(a.target_iri), RDFS.label, Literal(a.target_label, lang="en")) in graph


def test_provenance_is_complete(graph):
    src = ID["source"]
    assert (ID["dataset"], PROV.wasDerivedFrom, src) in graph
    assert graph.value(src, TACO.sha256) == Literal(graphmod.sha256_of(RAW_XLS))
    assert "NEPA-UNICAMP" in str(graph.value(src, DCTERMS.bibliographicCitation))


def test_build_is_deterministic(table, alignments, food_names_en, graph):
    again = graphmod.build_graph(table, alignments, source_file=RAW_XLS, food_names_en=food_names_en)
    assert len(again) == len(graph)
    def ground(g):
        return {t for t in g if not any(hasattr(x, "n3") and x.n3().startswith("_:") for x in t)}

    assert ground(again) == ground(graph)


def test_alignment_rows_reference_existing_resources(table, alignments):
    for a in alignments:
        assert a.predicate in {"type", "closeMatch", "narrowMatch", "broadMatch", "relatedMatch",
                               "exactMatch"}
        assert a.predicate != "type" or a.source_type == "food"
        if a.source_type == "group":
            assert 1 <= int(a.source_key) <= len(table.groups)
        elif a.source_type == "food":
            assert int(a.source_key) in table.foods


def test_all_measurements_have_an_explicit_edible_portion_basis(graph):
    for m in graph.subjects(RDF.type, TACO.NutrientMeasurement):
        basis = graph.value(m, TACO.referenceBasis)
        assert graph.value(basis, QUDT.numericValue).toPython() == Decimal("100")
        assert graph.value(basis, QUDT.unit) == UNIT.GM
        assert graph.value(basis, TACO.foodPortion) == TACO.EdiblePortion


def test_alignment_rationales_are_exported_without_claiming_review(graph, alignments, reviewed):
    records = list(graph.subjects(RDF.type, TACO.AlignmentAssertion))
    assert len(records) == len(alignments)
    reviewed_foods = {ID[f"food/{food}"] for food in reviewed}
    for record in records:
        subject = graph.value(record, RDF.subject)
        predicate = graph.value(record, RDF.predicate)
        target = graph.value(record, RDF.object)
        assert (subject, predicate, target) in graph
        assert (subject, TACO.alignment, record) in graph
        assert (record, PROV.wasDerivedFrom, ID["alignment-set"]) in graph
        if subject in reviewed_foods:
            assert graph.value(record, TACO.reviewStatus) == TACO.Reviewed
            continue
        assert graph.value(record, TACO.reviewStatus) == TACO.Unreviewed
        assert graph.value(record, TACO.ontologyVersionStatus) == TACO.NotRecorded
        assert graph.value(record, PROV.wasDerivedFrom) == ID["alignment-set"]
    notes = {str(n) for r in records for n in graph.objects(r, SKOS.editorialNote)}
    assert {a.note for a in alignments if a.note} == notes
