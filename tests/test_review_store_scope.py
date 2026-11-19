"""Regression checks for safe review updates in a store also containing TBCA."""
import importlib.util
from decimal import Decimal

from rdflib import RDF, XSD, Literal, URIRef

from taco_rdf.namespaces import ID, ROOT

spec = importlib.util.spec_from_file_location("review_store", ROOT / "verification/apply_review_store.py")
store = importlib.util.module_from_spec(spec)
spec.loader.exec_module(store)


def test_review_scope_excludes_tbca_nutrition_policy_and_lookalike_iris():
    for path in ("tbca/food/BRC0001E", "tbca/value/BRC0001E/proteina", "measurement/1/protein",
                 "nutrient/protein", "policy/attribution", "alignment-set-old", "conversion-other"):
        assert not store.MANAGED.match(str(ID) + path)
    assert not store.MANAGED.match("https://w3idXorg/taco-rdf/id/food/1")
    for path in ("food/1", "alignment/abc", "review/round-1", "build-input/source.csv",
                 "alignment-set", "conversion"):
        assert store.MANAGED.match(str(ID) + path)


def test_jena_string_and_decimal_serialization_does_not_create_nutrient_changes():
    subject, predicate = ID["measurement/1/protein"], URIRef("urn:value")
    before = {(subject, predicate, Literal("g")),
              (subject, predicate, Literal(Decimal("0.950000"), datatype=XSD.decimal))}
    after = {(subject, predicate, Literal("g", datatype=XSD.string)),
             (subject, predicate, Literal(Decimal("0.95"), datatype=XSD.decimal))}
    assert store.canonical(before) == store.canonical(after)
    different = {(subject, predicate, Literal(Decimal("0.950001"), datatype=XSD.decimal))}
    assert store.canonical(before) != store.canonical(different)


def test_projection_preserves_other_dataset_triples():
    tbca = (ID["tbca/food/BRC0001E"], RDF.type, URIRef("urn:food"))
    taco = (ID["food/1"], RDF.type, URIRef("urn:old"))
    replacement = (ID["food/1"], RDF.type, URIRef("urn:new"))
    current = {tbca, taco}
    managed = {t for t in current if store.MANAGED.match(str(t[0]))}
    removed, inserted = managed - {replacement}, {replacement} - managed
    assert (current - removed) | inserted == {tbca, replacement}
