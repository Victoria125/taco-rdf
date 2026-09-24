"""The FAIR plumbing: dataset metadata, the static site behind the w3id IRIs, and the SPARQL endpoint."""

from __future__ import annotations

import json
import re
import threading
import urllib.error
import urllib.parse
import urllib.request
from http.server import ThreadingHTTPServer

import pytest
from rdflib import Graph, Literal, URIRef

from taco_rdf import metadata as meta
from taco_rdf.namespaces import DCAT, DCTERMS, ID, RDFS, TACO
from taco_rdf.publish import publish
from taco_rdf.serve import make_handler


def test_dataset_declares_licence_distributions_and_source_terms(graph):
    dataset = ID["dataset"]
    assert (dataset, DCTERMS.license, URIRef(meta.DATA_LICENSE)) in graph
    urls = {str(graph.value(d, DCAT.downloadURL)) for d in graph.objects(dataset, DCAT.distribution)}
    assert urls == {meta.SITE_URL + f for f in meta.DUMPS}
    assert (ID["source"], DCTERMS.rights, Literal(meta.SOURCE_TERMS, lang="pt")) in graph


@pytest.fixture(scope="module")
def site(graph, tmp_path_factory):
    out = tmp_path_factory.mktemp("site")
    count = publish(graph, out)
    return out, count


def test_every_resource_but_measurements_gets_three_documents(site, graph):
    out, count = site
    base = str(ID)
    expected = {str(s)[len(base):] for s in graph.subjects()
                if isinstance(s, URIRef) and str(s).startswith(base) and "/measurement/" not in str(s)}
    assert count == len(expected)
    for path in expected:
        for ext in (".ttl", ".jsonld", ".html"):
            assert (out / "id" / (path + ext)).is_file(), path + ext
    assert not (out / "id" / "measurement").exists()


def test_food_document_carries_the_food_and_its_measurements(site, graph):
    out, _ = site
    doc = Graph().parse(out / "id" / "food" / "1.ttl", format="turtle")
    food = ID["food/1"]
    assert (food, RDFS.label, Literal("Arroz, integral, cozido", lang="pt")) in doc
    measurements = set(graph.subjects(TACO.ofFood, food))
    assert measurements and measurements <= set(doc.subjects())
    jsonld = Graph().parse(out / "id" / "food" / "1.jsonld", format="json-ld")
    assert len(jsonld) == len(doc)


def test_vocabulary_and_dumps_are_published(site, graph):
    out, _ = site
    vocab = Graph().parse(out / "vocab.ttl", format="turtle")
    assert (URIRef("https://w3id.org/taco-rdf/vocab#Food"), None, None) in vocab
    assert 'id="Food"' in (out / "vocab.html").read_text(encoding="utf-8")
    for name in meta.DUMPS:
        assert (out / name).stat().st_size > 1_000_000


def test_landing_page_has_schema_org_dataset_markup(site):
    out, _ = site
    page = (out / "index.html").read_text(encoding="utf-8")
    block = re.search(r'<script type="application/ld\+json">(.*?)</script>', page, re.S).group(1)
    data = json.loads(block)
    assert data["@type"] == "Dataset"
    assert data["license"] == meta.DATA_LICENSE
    assert {d["contentUrl"] for d in data["distribution"]} == {meta.SITE_URL + f for f in meta.DUMPS}


def test_sparql_endpoint_answers_queries_and_refuses_updates(graph):
    server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(graph))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{server.server_address[1]}/sparql"
    try:
        q = "SELECT (COUNT(?f) AS ?n) WHERE { ?f a <https://w3id.org/taco-rdf/vocab#Food> }"
        with urllib.request.urlopen(url + "?" + urllib.parse.urlencode({"query": q})) as resp:
            assert resp.headers["Content-Type"].startswith("application/sparql-results+json")
            assert json.load(resp)["results"]["bindings"][0]["n"]["value"] == "597"

        ask = urllib.request.Request(url, data=b"ASK { ?s ?p ?o }", headers={
            "Content-Type": "application/sparql-query", "Accept": "text/csv"})
        with urllib.request.urlopen(ask) as resp:
            assert json.load(resp)["boolean"] is True

        update = urllib.request.Request(url, data=b"update=CLEAR+ALL", headers={
            "Content-Type": "application/x-www-form-urlencoded"})
        with pytest.raises(urllib.error.HTTPError) as err:
            urllib.request.urlopen(update)
        assert err.value.code == 403
    finally:
        server.shutdown()
        server.server_close()
