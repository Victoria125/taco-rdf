"""Static site behind the w3id IRIs: Turtle, JSON-LD and HTML for every resource."""

from __future__ import annotations

import html
import json
import os
import re
import stat
import tempfile
from collections import defaultdict
from pathlib import Path

from rdflib import BNode, Graph, Literal, URIRef

from . import __version__
from . import metadata as meta
from .graph import CITATION, sha256_of
from .namespaces import BASE, DCTERMS, ID, ONTOLOGY_TTL, PREFIXES, RDFS, SKOS, TACO

_MEASUREMENT = str(ID) + "measurement/"
_LABELS = (SKOS.prefLabel, RDFS.label, DCTERMS.title)
_MANIFEST = ".taco-rdf-site.json"


def _reject_link(path: Path) -> None:
    """Reject symlinks and Windows junctions, including broken links."""
    if path.is_symlink() or (path.exists() and
            getattr(path.lstat(), "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT):
        raise ValueError(f"publication refuses links/junctions: {path}")


def _site_files(out: Path) -> dict[str, str]:
    files = {}
    pending = [out]
    while pending:
        directory = pending.pop()
        for child in directory.iterdir():
            _reject_link(child)
            if child.is_dir():
                pending.append(child)
            elif child.is_file():
                if child != out / _MANIFEST:
                    files[child.relative_to(out).as_posix()] = sha256_of(child)
            else:
                raise ValueError(f"publication refuses non-regular file: {child}")
    return files


def _check_destination(out: Path) -> dict[str, str]:
    for parent in (out, *out.parents):
        _reject_link(parent)
    if not out.exists():
        return {}
    if not out.is_dir():
        raise ValueError(f"publication destination is not a directory: {out}")
    if not any(out.iterdir()):
        return {}
    marker = out / _MANIFEST
    _reject_link(marker)
    if not marker.is_file():
        raise ValueError(f"refusing non-empty directory without {_MANIFEST}: {out}; use a new directory")
    manifest = json.loads(marker.read_text(encoding="utf-8"))
    if not isinstance(manifest, dict) or manifest.get("generator") != "taco-rdf" \
            or manifest.get("schema_version") != 1 or not isinstance(manifest.get("files"), dict):
        raise ValueError(f"invalid publication manifest: {marker}")
    actual = _site_files(out)
    if actual != manifest["files"]:
        raise ValueError(f"published files were added, removed or edited in {out}; use a new directory")
    return actual


def publish(g: Graph, out: Path) -> int:
    """Render the site in a staging directory, then move the files into place."""
    out = Path(os.path.abspath(out))
    previous = _check_destination(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".taco-rdf-stage-", dir=out.parent) as directory:
        stage = Path(directory)
        count = _render_site(g, stage)
        current = _site_files(stage)
        (stage / _MANIFEST).write_text(json.dumps({
            "generator": "taco-rdf", "schema_version": 1, "files": current,
        }, sort_keys=True, indent=2) + "\n", encoding="utf-8")
        if _check_destination(out) != previous:
            raise ValueError("publication destination changed while rendering")
        out.mkdir(parents=True, exist_ok=True)
        for name in current:
            target = out / name
            target.parent.mkdir(parents=True, exist_ok=True)
            (stage / name).replace(target)
        for name in previous.keys() - current.keys():
            (out / name).unlink()
        (stage / _MANIFEST).replace(out / _MANIFEST)
    return count


def _resource_path(iri: str) -> str:
    path = iri[len(str(ID)):]
    if not path or any(not re.fullmatch(r"[A-Za-z0-9_-]+(?:\.[A-Za-z0-9_-]+)*", part)
                       for part in path.split("/")):
        raise ValueError(f"unsafe resource IRI for publication: {iri}")
    return path


def _render_site(g: Graph, out: Path) -> int:
    (out / ".nojekyll").write_text("", encoding="utf-8")

    g.serialize(destination=str(out / "taco.ttl"), format="turtle")
    g.serialize(destination=str(out / "taco.nt"), format="nt", encoding="utf-8")

    vocab = Graph().parse(ONTOLOGY_TTL, format="turtle")
    _bind(vocab)
    _write_resource(out / "vocab", URIRef(BASE + "vocab"), vocab, g, subjects=_vocab_terms(vocab))

    measurements = defaultdict(list)
    for m, food in g.subject_objects(TACO.ofFood):
        measurements[food].append(m)

    count = 0
    for s in sorted({s for s in g.subjects() if isinstance(s, URIRef)}, key=str):
        iri = str(s)
        if not iri.startswith(str(ID)) or iri.startswith(_MEASUREMENT):
            continue
        subjects = [s, *sorted(measurements.get(s, []), key=str)]
        context = {o for node in subjects for p in (TACO.referenceBasis, TACO.alignment)
                   for o in g.objects(node, p)}
        subjects.extend(sorted(context - set(subjects), key=str))
        _write_resource(out / "id" / _resource_path(iri), s, _describe(g, subjects), g, subjects=subjects)
        count += 1

    (out / "index.html").write_text(_landing_page(g, count), encoding="utf-8")
    return count


def _bind(g: Graph) -> None:
    for prefix, ns in PREFIXES.items():
        g.bind(prefix, ns)


def _describe(g: Graph, subjects: list[URIRef]) -> Graph:
    """Concise bounded description of each subject: its triples, following blank nodes."""
    d = Graph()
    _bind(d)
    todo = list(subjects)
    seen = set()
    while todo:
        s = todo.pop()
        if s in seen:
            continue
        seen.add(s)
        for p, o in g.predicate_objects(s):
            d.add((s, p, o))
            if isinstance(o, BNode):
                todo.append(o)
    return d


def _vocab_terms(vocab: Graph) -> list[URIRef]:
    ontology = URIRef(BASE + "vocab")
    terms = sorted({s for s in vocab.subjects() if isinstance(s, URIRef) and s != ontology}, key=str)
    return [ontology, *terms]


def _write_resource(stem: Path, iri: URIRef, doc: Graph, full: Graph, *, subjects: list[URIRef]) -> None:
    stem.parent.mkdir(parents=True, exist_ok=True)
    doc.serialize(destination=str(stem) + ".ttl", format="turtle")
    doc.serialize(destination=str(stem) + ".jsonld", format="json-ld", encoding="utf-8")
    Path(str(stem) + ".html").write_text(_resource_page(iri, doc, full, subjects, stem.name),
                                         encoding="utf-8")


def _label(g: Graph, node) -> str | None:
    for p in _LABELS:
        values = list(g.objects(node, p))
        if values:
            en = [v for v in values if isinstance(v, Literal) and v.language == "en"]
            return str((en or values)[0])
    return None


def _href(iri: str) -> str:
    """Link our own IRIs to their page on the site, so browsing works before w3id resolves."""
    if iri.startswith(_MEASUREMENT):
        iri = str(ID) + "food/" + iri[len(_MEASUREMENT):].split("/")[0]
    if iri.startswith(str(ID)):
        return meta.SITE_URL + "id/" + iri[len(str(ID)):] + ".html"
    if iri.startswith(BASE + "vocab"):
        return meta.SITE_URL + "vocab.html" + (iri[len(BASE + "vocab"):] or "")
    return iri


def _term(node, full: Graph) -> str:
    if isinstance(node, URIRef):
        text = _label(full, node) or full.namespace_manager.normalizeUri(node)
        return f'<a href="{html.escape(_href(str(node)))}">{html.escape(text)}</a>'
    if isinstance(node, Literal):
        lang = f' <span class="tag">@{node.language}</span>' if node.language else ""
        return html.escape(str(node)) + lang
    return "<em>[blank node]</em>"


def _rows(doc: Graph, full: Graph, s) -> str:
    rows = []
    for p, o in sorted(doc.predicate_objects(s), key=lambda po: (str(po[0]), str(po[1]))):
        value = _term(o, full)
        if isinstance(o, BNode):
            inner = "".join(f"<li>{_term(p2, full)}: {_term(o2, full)}</li>"
                            for p2, o2 in doc.predicate_objects(o))
            value = f"<ul>{inner}</ul>"
        rows.append(f"<tr><th>{_term(p, full)}</th><td>{value}</td></tr>")
    return "\n".join(rows)


def _resource_page(iri: URIRef, doc: Graph, full: Graph, subjects: list[URIRef], name: str) -> str:
    title = _label(full, iri) or _label(doc, iri) or str(iri)
    sections = []
    for s in subjects:
        if not any(True for _ in doc.predicate_objects(s)):
            continue
        heading = "" if s == iri else f'<h2 id="{html.escape(str(s).rsplit("/", 1)[-1].split("#")[-1])}">' \
                                      f'{html.escape(_label(doc, s) or str(s))}</h2>'
        sections.append(f'{heading}<p class="iri">{html.escape(str(s))}</p>'
                        f"<table>{_rows(doc, full, s)}</table>")
    return _page(title, f"""
<p class="iri"><strong>{html.escape(str(iri))}</strong></p>
<p>Also as <a href="{html.escape(name)}.ttl">Turtle</a> and <a href="{html.escape(name)}.jsonld">JSON-LD</a>.
Part of the <a href="{meta.SITE_URL}">{html.escape(meta.TITLE)}</a> dataset.</p>
{"".join(sections)}""")


def _landing_page(g: Graph, resources: int) -> str:
    doi = f"https://doi.org/{meta.DOI}" if meta.DOI else None
    schema = {
        "@context": "https://schema.org/",
        "@type": "Dataset",
        "@id": str(ID["dataset"]),
        "name": meta.TITLE,
        "description": str(g.value(ID["dataset"], DCTERMS.description)),
        "url": meta.SITE_URL,
        "sameAs": [meta.REPO_URL] + ([doi] if doi else []),
        "identifier": doi or str(ID["dataset"]),
        "version": __version__,
        "license": meta.DATA_LICENSE,
        "keywords": list(meta.KEYWORDS),
        "inLanguage": ["pt", "en"],
        "isAccessibleForFree": True,
        "creator": {"@type": "Person", "name": meta.CREATOR},
        "isBasedOn": {"@type": "Dataset",
                      "name": "Tabela Brasileira de Composição de Alimentos (TACO), 4ª edição",
                      "citation": CITATION, "url": meta.SOURCE_LANDING_PAGE},
        "distribution": [{"@type": "DataDownload", "encodingFormat": media, "contentUrl": meta.SITE_URL + f}
                         for f, (media, _) in meta.DUMPS.items()],
    }
    doi_line = f'<p>DOI: <a href="{doi}">{doi}</a></p>' if doi else ""
    dumps = "".join(f'<li><a href="{f}">{f}</a> ({label})</li>' for f, (_, label) in meta.DUMPS.items())
    return _page(meta.TITLE, f"""
<script type="application/ld+json">{json.dumps(schema, ensure_ascii=False, indent=1)}</script>
<p>{html.escape(schema["description"])}</p>
{doi_line}
<ul>
<li>Dataset: <a href="{_href(str(ID["dataset"]))}">{ID["dataset"]}</a></li>
<li>Vocabulary: <a href="vocab.html">{BASE}vocab</a> (<a href="vocab.ttl">Turtle</a>)</li>
<li>Source code, SPARQL queries and SHACL shapes: <a href="{meta.REPO_URL}">{meta.REPO_URL}</a></li>
</ul>
<h2>Download</h2><ul>{dumps}</ul>
<p>{resources} resources (foods, groups, nutrients, provenance) each have a page, Turtle and JSON-LD
document under <code>id/</code>.</p>
<h2>Licence and citation</h2>
<p>The graph, vocabulary, shapes and alignments are released under
<a href="{meta.DATA_LICENSE}">CC BY 4.0</a>. The nutrient values come from TACO; its terms read:
<q lang="pt">{html.escape(meta.SOURCE_TERMS)}</q> ({html.escape(meta.SOURCE_TERMS_EN)})
Cite the source table:</p>
<blockquote>{html.escape(CITATION)}</blockquote>""")


def _page(title: str, body: str) -> str:
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)}</title>
<style>
:root {{ color-scheme: light dark; --muted: #666; --line: #ddd; }}
@media (prefers-color-scheme: dark) {{ :root {{ --muted: #aaa; --line: #444; }} }}
body {{ font: 16px/1.5 system-ui, sans-serif; max-width: 60rem; margin: 2rem auto; padding: 0 1rem; }}
table {{ border-collapse: collapse; width: 100%; margin-bottom: 1.5rem; }}
th, td {{ text-align: left; vertical-align: top; padding: .3rem .5rem;
          border-bottom: 1px solid var(--line); }}
th {{ width: 30%; font-weight: 500; }}
td ul {{ margin: 0; padding-left: 1rem; }}
.iri {{ font-family: ui-monospace, monospace; font-size: .85rem; color: var(--muted);
        overflow-wrap: anywhere; }}
.tag {{ color: var(--muted); font-size: .8rem; }}
</style></head>
<body><h1>{html.escape(title)}</h1>{body}
<footer class="iri">taco-rdf {__version__} | <a href="{meta.SITE_URL}">{meta.SITE_URL}</a></footer>
</body></html>
"""
