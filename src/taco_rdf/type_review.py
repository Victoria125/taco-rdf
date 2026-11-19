"""Validate and activate a completed type-only review without rewriting its evidence.

Application is distinct from receipt: a completed CSV alone never changes a build.
The application marker pins every decision/evidence file and records who reviewed it.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import re
from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from rdflib import OWL, RDF, RDFS, Graph, URIRef

from .namespaces import OBO, ROOT

CONTEXT = ("food_number", "name_pt", "name_en", "group", "candidates")
ANSWERS = ("decision", "justification", "searched_terms", "unsure")
FILES = (
    "manifest.json",
    "context.csv",
    "items.csv",
    "reviewer-1.csv",
    "reviewer-2.csv",
    "adjudication.csv",
    "adjudication-additional.csv",
    "adjudication-all.csv",
    "reviewed-types.csv",
    "adjudication-receipt.json",
)
AUDITS = {"analysis/data/foodon_types.csv", "analysis/data/foodon_typing_gaps.csv"}
FORMAT = "taco-type-review-application-v1"
CURIE = re.compile(r"FOODON_[0-9]{8}\Z")
ORGANISM_ROOTS = {str(OBO.COB_0000022), str(OBO.PO_0000003)}


def digest(path: Path, *, normalized: bool = True) -> str:
    data = path.read_bytes()
    return hashlib.sha256(data.replace(b"\r\n", b"\n") if normalized else data).hexdigest()


def input_path(folder: Path, relative: str, root: Path = ROOT) -> Path:
    """Frozen pre-review audit inputs, live source inputs for everything else."""
    snapshot = folder / "baseline" / relative
    return snapshot if relative in AUDITS and snapshot.is_file() else root / relative


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    if any(None in row or None in row.values() for row in rows):
        raise ValueError(f"{path.name}: missing or extra columns")
    return rows


def receipt_matches(path: Path, expected: str | None) -> bool:
    """Receipt bytes, with Git's text newline conversion allowed for the exported CSVs."""
    if digest(path, normalized=False) == expected:
        return True
    rows = read_rows(path)
    if not rows:
        return False
    return hashlib.sha256(csv_bytes(rows, list(rows[0]), "\r\n")).hexdigest() == expected


def indexed(rows: list[dict[str, str]], name: str) -> dict[int, dict[str, str]]:
    result = {}
    for row in rows:
        value = row.get("food_number", "")
        if not re.fullmatch(r"[1-9][0-9]*", value):
            raise ValueError(f"{name}: invalid food number {value!r}")
        number = int(value)
        if number in result:
            raise ValueError(f"{name}: duplicate food {number}")
        result[number] = row
    return result


def class_index(path: Path) -> tuple[dict[str, str], dict[str, str]]:
    metadata, lines = {}, []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("# "):
            key, _, value = line[2:].partition(":")
            metadata[key.strip()] = value.strip()
        else:
            lines.append(line)
    labels = {row["class"]: row["label"] for row in csv.DictReader(lines, delimiter="\t")}
    return metadata, labels


def valid_decision(value: str, labels: dict[str, str]) -> bool:
    return value == "none" or bool(CURIE.fullmatch(value) and value in labels)


@dataclass(frozen=True)
class TypeReview:
    manifest: dict
    receipt: dict
    rows: dict[int, dict[str, str]]
    adjudicated: dict[int, dict[str, str]]
    labels: dict[str, str]
    foodon: dict[str, str]
    application: dict | None


def validate(folder: Path, *, root: Path = ROOT, require_application: bool = False) -> TypeReview:
    """Recompute consolidation from the received forms, refusing stale or incomplete evidence."""
    folder = Path(folder)
    manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
    if (manifest.get("protocol_version"), manifest.get("hash_format")) != (3, "sha256-lf-v1"):
        raise ValueError("not a protocol-3 review with sha256-lf-v1 checksums")
    changed = [
        name
        for name, expected in manifest["inputs"].items()
        if digest(input_path(folder, name, root)) != expected
    ]
    for name in ("context", "items"):
        if digest(folder / f"{name}.csv") != manifest[f"{name}_sha256"]:
            changed.append(f"{name}.csv")
    if changed:
        raise ValueError("review inputs differ from the manifest: " + ", ".join(changed))
    foodon, labels = class_index(root / "ontology/imports/foodon-classes.tsv")
    if manifest["foodon_release"] not in (foodon["release"], foodon["release"].split("/")[-2]):
        raise ValueError("review and pinned FoodOn releases differ")
    context = indexed(read_rows(folder / "context.csv"), "context.csv")
    expected_foods = set(range(1, manifest["foods"] + 1))
    if set(context) != expected_foods or manifest["foods"] != manifest["sample_size"]:
        raise ValueError("protocol 3 must review every food once in both forms")
    items = indexed(read_rows(folder / "items.csv"), "items.csv")
    if set(items) != expected_foods or any(row["in_sample"] != "True" for row in items.values()):
        raise ValueError("items.csv does not include every food in the second review")
    forms = []
    for number in (1, 2):
        name = f"reviewer-{number}.csv"
        form = indexed(read_rows(folder / name), name)
        if set(form) != expected_foods:
            raise ValueError(f"{name}: foods differ from context")
        for n, row in form.items():
            if any(row.get(k) != context[n][k] for k in CONTEXT):
                raise ValueError(f"{name}: food {n} context changed")
            if (
                not valid_decision(row.get("decision", ""), labels)
                or not row.get("justification", "").strip()
            ):
                raise ValueError(f"{name}: food {n} has an invalid or incomplete answer")
            if row["decision"] == "none" and not row.get("searched_terms", "").strip():
                raise ValueError(f"{name}: food {n} has none without searched terms")
            if row.get("unsure") not in ("", "yes"):
                raise ValueError(f"{name}: food {n} has an invalid uncertainty flag")
        forms.append(form)
    receipt = json.loads((folder / "adjudication-receipt.json").read_text(encoding="utf-8"))
    if receipt.get("human_confirmed_by_user") is not True or not receipt.get("adjudicator", "").strip():
        raise ValueError("the adjudication receipt has no confirmed human adjudicator")
    date.fromisoformat(receipt["processed_on"])
    recorded = {
        name.replace("\\", "/").rsplit("/", 1)[-1]: value for name, value in receipt["outputs_sha256"].items()
    }
    for name in (
        "reviewed-types.csv",
        "adjudication-all.csv",
        "adjudication.csv",
        "adjudication-additional.csv",
    ):
        if not receipt_matches(folder / name, recorded.get(name)):
            raise ValueError(f"{name}: differs from the confirmed adjudication receipt")
    adjudicated = indexed(read_rows(folder / "adjudication-all.csv"), "adjudication-all.csv")
    if not set(adjudicated) <= expected_foods:
        raise ValueError("adjudication includes a food outside the review")
    for n, row in adjudicated.items():
        if (
            row.get("name_pt") != context[n]["name_pt"]
            or not valid_decision(row.get("adjudicated", ""), labels)
            or not row.get("justification", "").strip()
            or not row.get("source_sheet", "").strip()
        ):
            raise ValueError(f"adjudication for food {n} is invalid or incomplete")
    disagreements = {n for n in expected_foods if forms[0][n]["decision"] != forms[1][n]["decision"]}
    official = indexed(read_rows(folder / "adjudication.csv"), "adjudication.csv")
    additional = indexed(read_rows(folder / "adjudication-additional.csv"), "adjudication-additional.csv")
    if set(official) != disagreements or set(additional) != set(adjudicated) - disagreements:
        raise ValueError("adjudication files do not partition all confirmed decisions")
    for n, row in official.items():
        if (row["reviewer_1"], row["reviewer_2"]) != (forms[0][n]["decision"], forms[1][n]["decision"]):
            raise ValueError(f"adjudication.csv: original decisions changed for food {n}")
    for name, subset in (("adjudication.csv", official), ("adjudication-additional.csv", additional)):
        for n, row in subset.items():
            if any(
                row.get(key) != adjudicated[n].get(key) for key in ("name_pt", "adjudicated", "justification")
            ):
                raise ValueError(f"{name}: food {n} differs from complete adjudication")
    rows = indexed(read_rows(folder / "reviewed-types.csv"), "reviewed-types.csv")
    if set(rows) != expected_foods:
        raise ValueError("reviewed-types.csv does not cover every food exactly once")
    for n, row in rows.items():
        a, b = forms[0][n], forms[1][n]
        adj = adjudicated.get(n)
        if adj is None and a["decision"] != b["decision"]:
            raise ValueError(f"food {n}: disagreement without adjudication")
        decision = adj["adjudicated"] if adj else a["decision"]
        expected = {
            "decision": decision,
            "decision_label": labels.get(decision, "nenhuma classe"),
            "decision_source": "adjudication" if adj else "reviewer_agreement",
            "adjudicator": receipt["adjudicator"] if adj else "",
            "adjudication_sheet": adj["source_sheet"] if adj else "",
            "adjudication_justification": adj["justification"] if adj else "",
            **{key: context[n][key] for key in ("food_number", "name_pt", "name_en", "group")},
        }
        for number, answer in enumerate((a, b), 1):
            expected.update({f"reviewer_{number}_{key}": answer[key] for key in ANSWERS})
        if any(row.get(key) != value for key, value in expected.items()):
            raise ValueError(f"reviewed-types.csv: food {n} differs from its review evidence")
    baseline = indexed(
        read_rows(input_path(folder, "analysis/data/foodon_types.csv", root)), "baseline types"
    )
    for n, previous in baseline.items():
        if rows[n]["decision"] != previous["target_iri"].rsplit("/", 1)[-1] and n not in adjudicated:
            raise ValueError(f"food {n}: changing an existing type requires adjudication")
    counts = {
        "foods": len(rows),
        "adjudicated": len(adjudicated),
        "original_agreements_retained": len(rows) - len(adjudicated),
        "with_class": sum(r["decision"] != "none" for r in rows.values()),
        "none": sum(r["decision"] == "none" for r in rows.values()),
        "unique_classes": len({r["decision"] for r in rows.values()} - {"none"}),
    }
    if any(receipt.get(key) != value for key, value in counts.items()):
        raise ValueError("receipt counts differ from the consolidated evidence")
    marker = folder / "application.json"
    application = json.loads(marker.read_text(encoding="utf-8")) if marker.is_file() else None
    if require_application and application is None:
        raise ValueError("the type review has not been applied")
    if application is not None:
        if (application.get("format"), application.get("status")) != (FORMAT, "applied"):
            raise ValueError("invalid application marker")
        if application.get("files") != {name: digest(folder / name) for name in FILES}:
            raise ValueError("applied review evidence changed since application")
        if (application.get("foodon_release"), application.get("foodon_sha256")) != (
            foodon["release"],
            foodon["sha256"],
        ):
            raise ValueError("application uses a different FoodOn release")
        reviewers = application.get("reviewers", {})
        if (
            not reviewers.get("reviewer_1")
            or not reviewers.get("reviewer_2")
            or len(set(reviewers.values())) != 3
            or reviewers.get("adjudicator") != receipt["adjudicator"]
        ):
            raise ValueError("application reviewers are incomplete or not distinct")
        if (application.get("protocol"), application.get("protocol_sha256")) != (
            manifest["protocol"],
            manifest["inputs"][manifest["protocol"]],
        ):
            raise ValueError("application protocol differs from the prepared review")
        if application.get("decision_recorded_on") != receipt["processed_on"]:
            raise ValueError("application decision date differs from receipt")
    return TypeReview(manifest, receipt, rows, adjudicated, labels, foodon, application)


def check_hierarchy(review: TypeReview, path: Path) -> None:
    """Check selected classes against the actual hash-pinned OWL, including inherited prohibitions."""
    if digest(path, normalized=False) != review.foodon["sha256"]:
        raise ValueError("FoodOn file does not match the pinned SHA-256")
    graph = Graph().parse(path, format="xml")
    children = defaultdict(set)
    for child, parent in graph.subject_objects(RDFS.subClassOf):
        children[parent].add(child)
    forbidden, stack = set(), [URIRef(root) for root in ORGANISM_ROOTS]
    while stack:
        node = stack.pop()
        if node in forbidden:
            continue
        forbidden.add(node)
        stack.extend(children[node] - forbidden)
    for n, row in review.rows.items():
        if row["decision"] == "none":
            continue
        term = URIRef(str(OBO) + row["decision"])
        if (
            (term, RDF.type, OWL.Class) not in graph
            or term in forbidden
            or any(bool(v.toPython()) for v in graph.objects(term, OWL.deprecated))
        ):
            raise ValueError(f"food {n}: final class is absent, deprecated or under organism/plant")


def marker_for(
    review: TypeReview,
    folder: Path,
    *,
    applied_on: str,
    reviewer_1: str,
    reviewer_2: str,
    alignments_data: bytes,
) -> dict:
    date.fromisoformat(applied_on)
    reviewers = {
        "reviewer_1": reviewer_1.strip(),
        "reviewer_2": reviewer_2.strip(),
        "adjudicator": review.receipt["adjudicator"],
    }
    if any(not name for name in reviewers.values()) or len(set(reviewers.values())) != 3:
        raise ValueError("two distinct reviewers and a different adjudicator are required")
    return {
        "format": FORMAT,
        "status": "applied",
        "protocol_version": 3,
        "protocol": review.manifest["protocol"],
        "protocol_sha256": review.manifest["inputs"][review.manifest["protocol"]],
        "files": {name: digest(folder / name) for name in FILES},
        "foodon_release": review.foodon["release"],
        "foodon_sha256": review.foodon["sha256"],
        "applied_on": applied_on,
        "decision_recorded_on": review.receipt["processed_on"],
        "reviewers": reviewers,
        "foods": len(review.rows),
        "adjudicated": len(review.adjudicated),
        "original_agreements": len(review.rows) - len(review.adjudicated),
        "alignments_sha256": hashlib.sha256(alignments_data.replace(b"\r\n", b"\n")).hexdigest(),
    }


def csv_bytes(rows: list[dict[str, str]], fields: list[str], newline: str = "\n") -> bytes:
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=fields, lineterminator=newline)
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue().encode("utf-8")
