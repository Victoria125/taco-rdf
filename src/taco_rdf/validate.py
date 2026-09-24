from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from pyshacl import validate as _pyshacl_validate
from rdflib import Graph, URIRef

from .namespaces import SH

_SEVERITY = {SH.Violation: "Violation", SH.Warning: "Warning", SH.Info: "Info"}


@dataclass(frozen=True)
class Finding:
    severity: str
    shape: str
    focus: str
    message: str
    value: str | None


@dataclass
class Report:
    findings: list[Finding]

    @property
    def conforms_strict(self) -> bool:
        return not any(f.severity == "Violation" for f in self.findings)

    def counts(self) -> Counter:
        return Counter((f.severity, f.shape) for f in self.findings)

    def summary(self) -> str:
        by_sev = Counter(f.severity for f in self.findings)
        head = "CONFORMS (no violations)" if self.conforms_strict else "DOES NOT CONFORM"
        lines = [
            f"{head}: {by_sev.get('Violation', 0)} violation(s), "
            f"{by_sev.get('Warning', 0)} warning(s), {by_sev.get('Info', 0)} info"
        ]
        for (sev, shape), n in sorted(self.counts().items()):
            lines.append(f"  {sev:<9} {n:>4}  {shape}")
        return "\n".join(lines)

    def details(self, limit: int = 15) -> str:
        out, seen = [], Counter()
        for f in self.findings:
            key = (f.severity, f.shape)
            seen[key] += 1
            if seen[key] > limit:
                continue
            out.append(f"[{f.severity}] {f.shape}\n    {f.message}")
        return "\n".join(out)


def _short(iri) -> str:
    text = str(iri)
    return text.rsplit("#", 1)[-1] if "#" in text else text.rsplit("/", 1)[-1]


def load_shapes(shapes_dir: Path) -> Graph:
    shapes = Graph()
    for path in sorted(Path(shapes_dir).glob("*.ttl")):
        shapes.parse(path, format="turtle")
    return shapes


def _shape_name(shapes: Graph, shape) -> str:
    if isinstance(shape, URIRef):
        return _short(shape)
    parent = next(iter(shapes.subjects(SH.property, shape)), None)
    return _short(parent) if isinstance(parent, URIRef) else "(blank shape)"


def validate(data: Graph, shapes_dir: Path) -> Report:
    shapes = load_shapes(shapes_dir)
    _, results_graph, _ = _pyshacl_validate(
        data,
        shacl_graph=shapes,
        inference="none",
        allow_warnings=True,
        abort_on_first=False,
    )
    if not isinstance(results_graph, Graph):
        raise ValueError(f"invalid SHACL shapes in {shapes_dir}: {results_graph}")
    findings: list[Finding] = []
    for res in results_graph.subjects(SH.resultSeverity, None):
        sev = results_graph.value(res, SH.resultSeverity)
        shape = results_graph.value(res, SH.sourceShape)
        msg = results_graph.value(res, SH.resultMessage)
        focus = results_graph.value(res, SH.focusNode)
        value = results_graph.value(res, SH.value)
        findings.append(
            Finding(
                severity=_SEVERITY.get(sev, _short(sev)),
                shape=_shape_name(shapes, shape),
                focus=str(focus),
                message=str(msg) if msg else f"{_shape_name(shapes, shape)} failed for {focus}",
                value=str(value) if value is not None else None,
            )
        )
    findings.sort(key=lambda f: (f.severity, f.shape, f.focus, f.message))
    return Report(findings)
