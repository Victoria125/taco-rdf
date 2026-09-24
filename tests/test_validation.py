from __future__ import annotations

import re
from decimal import Decimal

import pytest
from rdflib import Literal, URIRef
from rdflib.namespace import XSD

from taco_rdf import graph as graphmod
from taco_rdf.namespaces import DCAT, DCTERMS, FIO, ID, OBO, ODRL, QUDT, RAW_XLS, RDF, SHAPES_DIR, TACO, UNIT
from taco_rdf.parse import Food, Observation, Status, Table
from taco_rdf.validate import validate


def _foods(report, needle):
    out = set()
    for f in report.findings:
        if needle in f.message:
            out.add(int(re.search(r"(?:food|measurement)/(\d+)", f.message).group(1)))
    return out


def test_real_graph_has_no_violations(report):
    assert report.conforms_strict, report.details()


def test_known_source_data_warnings(report):
    assert {f.severity for f in report.findings} == {"Warning"}
    assert _foods(report, "negative") == {288, 322, 337, 400}
    assert _foods(report, "Proximate") == {282, 290, 297, 319, 338, 348, 364, 370, 435, 437}
    assert _foods(report, "fatty acids") == {368, 388, 434, 485, 501, 587, 594}
    assert len(report.findings) == 21


def test_energy_units_agree_everywhere(report):
    assert not any("Energy of" in f.message for f in report.findings)


def test_governance_rules_pass_on_the_real_graph(report):
    assert not any(f.shape in {"DatasetShape", "SourceShape", "PolicyShape"} for f in report.findings)


@pytest.fixture()
def mini():
    table = Table(groups=["Cereais e derivados"], foods={1: Food(1, "Alimento de teste", 1)})
    values = {
        "moisture": "70", "energy_kcal": "100", "energy_kj": "418.4",
        "protein": "10", "lipids": "5", "carbohydrate": "14", "ash": "1",
    }
    table.observations = [
        Observation(1, k, Status.MEASURED, Decimal(v)) for k, v in values.items()
    ]
    return graphmod.build_graph(table, [], source_file=RAW_XLS)


def run(g):
    return validate(g, SHAPES_DIR)


def m(key):
    return graphmod.measurement_iri(1, key)


def shapes_hit(report, severity):
    return {f.shape for f in report.findings if f.severity == severity}


def test_baseline_mini_graph_is_clean(mini):
    assert run(mini).findings == []


def test_measured_without_a_number_is_a_violation(mini):
    mini.remove((m("protein"), QUDT.numericValue, None))
    rep = run(mini)
    assert "NutrientMeasurementShape" in shapes_hit(rep, "Violation")


def test_trace_with_a_number_is_a_violation(mini):
    mini.set((m("protein"), TACO.valueStatus, TACO.Trace))
    assert "NutrientMeasurementShape" in shapes_hit(run(mini), "Violation")


def test_unknown_status_is_a_violation(mini):
    mini.set((m("protein"), TACO.valueStatus, TACO.Approximately))
    assert "NutrientMeasurementShape" in shapes_hit(run(mini), "Violation")


def test_wrong_unit_is_a_violation(mini):
    mini.set((m("protein"), QUDT.unit, UNIT.MilliGM))
    rep = run(mini)
    assert any("is in unit" in f.message for f in rep.findings if f.severity == "Violation")


def test_more_than_100_g_per_100_g_is_a_violation(mini):
    mini.set((m("protein"), QUDT.numericValue, Literal(Decimal("150"), datatype=XSD.decimal)))
    rep = run(mini)
    assert any("exceeds 100 g" in f.message for f in rep.findings if f.severity == "Violation")


def test_duplicate_measurement_is_a_violation(mini):
    dup = URIRef(str(ID) + "measurement/1/protein-duplicate")
    for p, o in list(mini.predicate_objects(m("protein"))):
        mini.add((dup, p, o))
    rep = run(mini)
    assert any("measurements of nutrient" in f.message for f in rep.findings if f.severity == "Violation")


def test_inconsistent_energy_is_a_violation(mini):
    mini.set((m("energy_kj"), QUDT.numericValue, Literal(Decimal("300"), datatype=XSD.decimal)))
    rep = run(mini)
    assert any("Energy of" in f.message for f in rep.findings if f.severity == "Violation")


def test_energy_within_tolerance_is_accepted(mini):
    mini.set((m("energy_kj"), QUDT.numericValue, Literal(Decimal("420.0"), datatype=XSD.decimal)))
    assert run(mini).findings == []


def test_implausible_composition_is_a_warning_not_a_violation(mini):
    mini.set((m("lipids"), QUDT.numericValue, Literal(Decimal("15"), datatype=XSD.decimal)))
    rep = run(mini)
    assert rep.conforms_strict
    assert any("Proximate composition" in f.message for f in rep.findings if f.severity == "Warning")


def test_food_without_a_group_is_a_violation(mini):
    mini.remove((graphmod.food_iri(1), TACO.inGroup, None))
    assert "FoodShape" in shapes_hit(run(mini), "Violation")


def test_food_that_is_not_a_fio_food_item_is_a_violation(mini):
    mini.remove((graphmod.food_iri(1), RDF.type, FIO.FoodItem))
    assert "FoodShape" in shapes_hit(run(mini), "Violation")


def test_food_typed_with_a_food_class_is_accepted(mini):
    mini.add((graphmod.food_iri(1), RDF.type, OBO.FOODON_00004678))
    assert "FoodOnTypingShape" not in shapes_hit(run(mini), "Violation")


def test_food_typed_with_an_organism_class_is_a_violation(mini):
    mini.add((graphmod.food_iri(1), RDF.type, OBO.FOODON_03413876))
    assert "FoodOnTypingShape" in shapes_hit(run(mini), "Violation")


def test_food_with_two_foodon_types_is_a_violation(mini):
    mini.add((graphmod.food_iri(1), RDF.type, OBO.FOODON_00004678))
    mini.add((graphmod.food_iri(1), RDF.type, OBO.FOODON_00004679))
    assert "FoodOnTypingShape" in shapes_hit(run(mini), "Violation")


def test_food_without_a_portuguese_label_is_a_violation(mini):
    from rdflib.namespace import RDFS

    mini.set((graphmod.food_iri(1), RDFS.label, Literal("test food", lang="en")))
    assert "FoodShape" in shapes_hit(run(mini), "Violation")


def test_food_with_two_english_names_is_a_violation(mini):
    from rdflib.namespace import SKOS

    mini.add((graphmod.food_iri(1), SKOS.prefLabel, Literal("test food", lang="en")))
    assert run(mini).findings == []
    mini.add((graphmod.food_iri(1), SKOS.prefLabel, Literal("another name", lang="en")))
    assert "FoodShape" in shapes_hit(run(mini), "Violation")


def _permission(g):
    policy = ID["policy/attribution"]
    return next(g.objects(policy, ODRL.permission))


def test_reuse_permission_without_attribution_duty_is_a_violation(mini):
    perm = _permission(mini)
    duty = next(mini.objects(perm, ODRL.duty))
    mini.remove((perm, ODRL.duty, duty))
    rep = run(mini)
    assert any("no attribution duty" in f.message for f in rep.findings if f.severity == "Violation")


def test_a_duty_with_another_action_does_not_count_as_attribution(mini):
    perm = _permission(mini)
    duty = next(mini.objects(perm, ODRL.duty))
    mini.set((duty, ODRL.action, ODRL.compensate))
    assert "PolicyShape" in shapes_hit(run(mini), "Violation")


def test_read_only_permission_needs_no_duty(mini):
    perm = _permission(mini)
    duty = next(mini.objects(perm, ODRL.duty))
    mini.remove((perm, ODRL.duty, duty))
    for action in (ODRL.reproduce, ODRL.distribute, ODRL.derive):
        mini.remove((perm, ODRL.action, action))
    assert run(mini).findings == []


def test_dataset_without_policy_is_a_violation(mini):
    mini.remove((ID["dataset"], ODRL.hasPolicy, None))
    assert "DatasetShape" in shapes_hit(run(mini), "Violation")


def test_source_without_checksum_is_a_violation(mini):
    mini.remove((ID["source"], TACO.sha256, None))
    assert "SourceShape" in shapes_hit(run(mini), "Violation")


def test_permission_must_target_a_dataset(mini):
    perm = _permission(mini)
    mini.set((perm, ODRL.target, URIRef("https://example.org/somewhere-else")))
    assert "PolicyShape" in shapes_hit(run(mini), "Violation")


def test_dataset_without_licence_is_a_violation(mini):
    mini.remove((ID["dataset"], DCTERMS.license, None))
    assert "DatasetShape" in shapes_hit(run(mini), "Violation")


def test_dataset_without_distribution_is_a_violation(mini):
    mini.remove((ID["dataset"], DCAT.distribution, None))
    assert "DatasetShape" in shapes_hit(run(mini), "Violation")


def test_source_without_terms_of_use_is_a_violation(mini):
    mini.remove((ID["source"], DCTERMS.rights, None))
    assert "SourceShape" in shapes_hit(run(mini), "Violation")


@pytest.mark.parametrize("status", [TACO.Trace, TACO.NotApplicable, TACO.UnderReevaluation])
def test_nonnumeric_status_cannot_carry_a_unit(mini, status):
    mini.set((m("protein"), TACO.valueStatus, status))
    mini.remove((m("protein"), QUDT.numericValue, None))
    assert "NutrientMeasurementShape" in shapes_hit(run(mini), "Violation")
    mini.remove((m("protein"), QUDT.unit, None))
    assert run(mini).conforms_strict


def test_missing_reference_basis_is_a_violation(mini):
    mini.remove((m("protein"), TACO.referenceBasis, None))
    assert "NutrientMeasurementShape" in shapes_hit(run(mini), "Violation")


def test_wrong_reference_mass_is_a_violation(mini):
    basis = mini.value(m("protein"), TACO.referenceBasis)
    mini.set((basis, QUDT.numericValue, Literal(Decimal("1.0"), datatype=XSD.decimal)))
    assert "ReferenceBasisShape" in shapes_hit(run(mini), "Violation")
