"""Regression tests for destructive publication and ambiguous graph selection."""
from __future__ import annotations

import json

import pytest
from rdflib import Graph, Literal, URIRef

from taco_rdf import cli
from taco_rdf import publish as publisher
from taco_rdf.namespaces import ID, RDFS


def test_missing_explicit_graph_is_not_replaced(tmp_path, monkeypatch):
    def unexpected():
        pytest.fail("an explicit missing graph must never build default data")
    monkeypatch.setattr(cli, "build_graph", unexpected)
    missing = tmp_path / "typo.ttl"
    with pytest.raises(FileNotFoundError):
        cli.load_graph(missing)
    assert not missing.exists()


def test_no_graph_argument_builds_fresh_each_time(monkeypatch):
    graphs = [Graph(), Graph()]
    monkeypatch.setattr(cli, "build_graph", lambda: graphs.pop())
    assert cli.load_graph() is not cli.load_graph()
    assert not graphs


def test_explicit_snapshot_is_loaded_unchanged(tmp_path, monkeypatch, capsys):
    snapshot = tmp_path / "snapshot.ttl"
    snapshot.write_text('<urn:historic> <urn:value> "old" .', encoding="utf-8")
    def unexpected():
        pytest.fail("historical snapshots must not be silently rebuilt")
    monkeypatch.setattr(cli, "build_graph", unexpected)
    before = snapshot.read_bytes()
    g = cli.load_graph(snapshot)
    assert (URIRef("urn:historic"), URIRef("urn:value"), Literal("old")) in g
    assert snapshot.read_bytes() == before
    assert "SHA-256" in capsys.readouterr().err


@pytest.fixture
def tiny_renderer(monkeypatch):
    def render(g, out):
        (out / "index.html").write_text(str(len(g)), encoding="utf-8")
        return 1
    monkeypatch.setattr(publisher, "_render_site", render)


def test_publication_refuses_unowned_nonempty_directory(tmp_path, tiny_renderer):
    important = tmp_path / "notes.txt"
    important.write_text("keep me", encoding="utf-8")
    with pytest.raises(ValueError, match="non-empty"):
        publisher.publish(Graph(), tmp_path)
    assert important.read_text() == "keep me"
    assert list(tmp_path.iterdir()) == [important]


def test_repeat_publication_updates_owned_files(tmp_path, tiny_renderer):
    out = tmp_path / "site"
    publisher.publish(Graph(), out)
    graph = Graph().add((ID["dataset"], RDFS.label, Literal("new")))
    publisher.publish(graph, out)
    assert (out / "index.html").read_text() == "1"
    assert json.loads((out / publisher._MANIFEST).read_text())["generator"] == "taco-rdf"


@pytest.mark.parametrize("change", ["add", "edit", "remove"])
def test_publication_preserves_user_changes(tmp_path, tiny_renderer, change):
    out = tmp_path / "site"
    publisher.publish(Graph(), out)
    if change == "add":
        (out / "notes.txt").write_text("keep", encoding="utf-8")
    elif change == "edit":
        (out / "index.html").write_text("edited", encoding="utf-8")
    else:
        (out / "index.html").unlink()
    before = {p.name: p.read_bytes() for p in out.iterdir()}
    with pytest.raises(ValueError, match="added, removed or edited"):
        publisher.publish(Graph(), out)
    assert {p.name: p.read_bytes() for p in out.iterdir()} == before


def test_render_failure_keeps_previous_site(tmp_path, tiny_renderer, monkeypatch):
    out = tmp_path / "site"
    publisher.publish(Graph(), out)
    before = {p.name: p.read_bytes() for p in out.iterdir()}
    def fail(g, stage):
        (stage / "partial").write_text("partial")
        raise RuntimeError("render failed")
    monkeypatch.setattr(publisher, "_render_site", fail)
    with pytest.raises(RuntimeError, match="render failed"):
        publisher.publish(Graph(), out)
    assert {p.name: p.read_bytes() for p in out.iterdir()} == before


@pytest.mark.parametrize("path", ["../escape", "a/../../escape", "a\\escape", "C:/escape", "/absolute"])
def test_unsafe_resource_path_is_rejected(path):
    with pytest.raises(ValueError, match="unsafe"):
        publisher._resource_path(str(ID) + path)


def test_publication_rejects_symlink_destination(tmp_path, tiny_renderer):
    real = tmp_path / "real"
    real.mkdir()
    linked = tmp_path / "link"
    try:
        linked.symlink_to(real, target_is_directory=True)
    except OSError:
        pytest.skip("symlink creation is not permitted by this OS account")
    with pytest.raises(ValueError, match="links/junctions"):
        publisher.publish(Graph(), linked)
    assert not list(real.iterdir())
