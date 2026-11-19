# ruff: noqa: RUF001
"""Independently verify application of protocol 3 and check its certificates in Lean 4.

Does not call the application/resolution code. It reads original review evidence,
alignment rows, RDF outputs and the pinned RDF/XML hierarchy separately. Graph
parses are sequential to limit memory. Lean uses core only and kernel reduction;
the Python RDF parser and certificate extraction remain outside Lean's kernel.
"""

from __future__ import annotations

import argparse
import copy
import csv
import gc
import hashlib
import json
import re
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path

from rdflib import DCTERMS, RDF, SKOS, BNode, Graph, Namespace, URIRef

from taco_rdf.namespaces import FIO

ROOT = Path(__file__).resolve().parents[1]
ROUND = ROOT / "data/alignment/review/round-1"
BEFORE = ROOT / "build/verification/review_application_before"
OUT = ROOT / "build/verification/review_application"
LEAN_BASE = ROOT / "verification/lean/TypeReviewApplication.lean"
OBO = "http://purl.obolibrary.org/obo/"
FOODON = OBO + "FOODON_"
ID = "https://w3id.org/taco-rdf/id/"
TACO = Namespace("https://w3id.org/taco-rdf/vocab#")
PROV = Namespace("http://www.w3.org/ns/prov#")
ROOTS = {OBO + "COB_0000022", OBO + "PO_0000003"}
CONTEXT = ("food_number", "name_pt", "name_en", "group", "candidates")
FOODS = list(range(1, 598))


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def sha(path: Path, *, lf: bool = False) -> str:
    data = path.read_bytes()
    return hashlib.sha256(data.replace(b"\r\n", b"\n") if lf else data).hexdigest()


def digest_lines(lines: list[str]) -> str:
    return hashlib.sha256("\n".join(sorted(lines)).encode("utf-8")).hexdigest()


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def indexed(rows: list[dict[str, str]], where: str) -> dict[int, dict[str, str]]:
    numbers = [int(r["food_number"]) for r in rows]
    require(len(numbers) == len(set(numbers)), f"{where}: duplicate food number")
    return dict(zip(numbers, rows, strict=True))


def class_number(curie: str) -> int:
    if curie == "none":
        return 0
    require(bool(re.fullmatch(r"FOODON_[0-9]{8}", curie)), f"malformed class: {curie}")
    return int(curie.removeprefix("FOODON_"))


def check_source_rows(first_rows, second_rows, final_rows, adjudication_rows, context_rows):
    """Re-resolve the review, independently of production helpers; retain raw evidence."""
    first, second, final, adjudicated, context = [
        indexed(rows, name)
        for rows, name in (
            (first_rows, "reviewer 1"),
            (second_rows, "reviewer 2"),
            (final_rows, "final decisions"),
            (adjudication_rows, "adjudication"),
            (context_rows, "context"),
        )
    ]
    for name, source in (
        ("reviewer 1", first),
        ("reviewer 2", second),
        ("final", final),
        ("context", context),
    ):
        require(sorted(source) == FOODS, f"{name}: not every food exactly once")
    require(len(adjudicated) == 246 and set(adjudicated) <= set(FOODS), "wrong adjudication scope")
    expected, source_rows = [], []
    for n in FOODS:
        a, b, result = first[n], second[n], final[n]
        for form in (a, b):
            require(all(form[k] == context[n][k] for k in CONTEXT), f"food {n}: context differs")
            require(bool(form["justification"].strip()), f"food {n}: missing original justification")
        require(bool(a["decision"]) and bool(b["decision"]), f"food {n}: incomplete originals")
        for i, form in ((1, a), (2, b)):
            for key in ("decision", "justification", "searched_terms", "unsure"):
                require(result[f"reviewer_{i}_{key}"] == form[key], f"food {n}: original evidence changed")
        if n in adjudicated:
            record = adjudicated[n]
            choice = record["adjudicated"]
            require(bool(record["justification"].strip()), f"food {n}: missing adjudication reason")
            require(result["decision_source"] == "adjudication", f"food {n}: wrong decision source")
            require(result["adjudicator"] == "Crislane Timbo", f"food {n}: wrong adjudicator")
            require(
                result["adjudication_justification"] == record["justification"],
                f"food {n}: adjudication reason changed",
            )
            require(result["adjudication_sheet"] == record["source_sheet"], f"food {n}: source sheet changed")
            adj = class_number(choice)
        else:
            require(a["decision"] == b["decision"], f"food {n}: unresolved disagreement")
            choice, adj = a["decision"], None
            require(result["decision_source"] == "reviewer_agreement", f"food {n}: false adjudication")
            require(
                not result["adjudicator"] and not result["adjudication_justification"],
                f"food {n}: fabricated adjudication",
            )
        require(result["decision"] == choice, f"food {n}: final decision differs from review")
        require(choice != "none", f"food {n}: expected the received all-class review")
        expected.append((n, class_number(choice)))
        source_rows.append((n, class_number(a["decision"]), class_number(b["decision"]), adj))
    require(sum(a[1] == a[2] for a in source_rows) == 400, "original agreement changed")
    return expected, source_rows, adjudicated


def check_hashes(folder: Path, before: Path) -> dict:
    manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
    marker = json.loads((folder / "application.json").read_text(encoding="utf-8"))
    require(marker["status"] == "applied" and marker["protocol_version"] == 3, "review is not activated")
    for name, expected in marker["files"].items():
        require(sha(folder / name, lf=True) == expected, f"activated evidence changed: {name}")
    require(
        sha(ROOT / "data/alignment/alignments.csv", lf=True) == marker["alignments_sha256"],
        "alignment file differs from activation marker",
    )
    for name, expected in manifest["inputs"].items():
        frozen = folder / "baseline" / name
        require(
            frozen.is_file() and sha(frozen, lf=True) == expected, f"prepared input not preserved: {name}"
        )
    for name in ("context", "items"):
        require(sha(folder / f"{name}.csv", lf=True) == manifest[f"{name}_sha256"], f"{name} changed")
    snapshots = json.loads((before / "snapshot.json").read_text(encoding="utf-8"))
    for name, details in snapshots["files"].items():
        require(sha(before / name) == details["sha256"], f"before snapshot changed: {name}")
    receipt = json.loads((folder / "adjudication-receipt.json").read_text(encoding="utf-8"))
    require(receipt["human_confirmed_by_user"] is True, "human approval missing from receipt")
    require(receipt["adjudicator"] == "Crislane Timbo", "receipt adjudicator differs")
    for absolute, expected in receipt["outputs_sha256"].items():
        name = Path(absolute).name
        target = folder / name
        if target.is_file():
            require(sha(target) == expected, f"confirmed output changed: {name}")
    return marker


def alignment_pairs(path: Path) -> tuple[list[tuple[int, int]], str]:
    pairs, other = [], []
    for row in read_rows(path):
        if row["source_type"] == "food" and row["target_iri"].startswith(FOODON):
            require(row["predicate"] == "type", f"unapplied FoodOn candidate: {row['source_key']}")
            pairs.append((int(row["source_key"]), class_number(row["target_iri"].removeprefix(OBO))))
        else:
            other.append(json.dumps(row, sort_keys=True, ensure_ascii=False))
    return sorted(pairs), digest_lines(other)


def original_non_foodon_rows(path: Path) -> str:
    return digest_lines(
        [
            json.dumps(row, sort_keys=True, ensure_ascii=False)
            for row in read_rows(path)
            if not (row["source_type"] == "food" and row["target_iri"].startswith(FOODON))
        ]
    )


def graph_evidence(
    path: Path, *, native: bool, marker: dict | None = None, adjudicated: set[int] | None = None
) -> dict:
    graph = Graph().parse(path, format="turtle")
    pairs = sorted(
        (int(str(s).removeprefix(ID + "food/")), class_number(str(o).removeprefix(OBO)))
        for s, o in graph.subject_objects(RDF.type)
        if str(s).startswith(ID + "food/") and str(o).startswith(FOODON)
    )
    food_type = TACO.Food if native else FIO.FoodItem
    foods = sorted(
        int(str(s).removeprefix(ID + "food/"))
        for s in graph.subjects(RDF.type, food_type)
        if str(s).startswith(ID + "food/")
    )
    nutrition = set()
    nonfoodon = set()
    for s, p, o in graph:
        is_food_type = p == RDF.type and str(s).startswith(ID + "food/") and str(o).startswith(FOODON)
        if not native and not is_food_type:
            require(
                not any(isinstance(term, BNode) for term in (s, p, o)), "unexpected anonymous NICE-Food node"
            )
            nonfoodon.add(f"{s.n3()} {p.n3()} {o.n3()} .")
        related = (
            str(s).startswith((ID + "measurement/", ID + "nutrient/", ID + "category/", ID + "reference/"))
            or p == FIO.hasNutritionalValue
        )
        if related:
            require(not any(isinstance(term, BNode) for term in (s, p, o)), "anonymous nutritional node")
            nutrition.add(f"{s.n3()} {p.n3()} {o.n3()} .")
        require(
            not (
                str(s).startswith(ID + "food/")
                and str(o).startswith(FOODON)
                and p
                in (SKOS.exactMatch, SKOS.closeMatch, SKOS.broadMatch, SKOS.narrowMatch, SKOS.relatedMatch)
            ),
            "published food-to-FoodOn SKOS link",
        )
    provenance = []
    if native and marker is not None:
        for n, cls in pairs:
            subject, target = URIRef(ID + f"food/{n}"), URIRef(FOODON + f"{cls:08d}")
            records = [
                r
                for r in graph.objects(subject, TACO.alignment)
                if (r, RDF.predicate, RDF.type) in graph and (r, RDF.object, target) in graph
            ]
            require(len(records) == 1, f"food {n}: missing or duplicate reviewed assertion")
            record = records[0]
            require((record, RDF.subject, subject) in graph, f"food {n}: wrong assertion subject")
            require((record, TACO.reviewStatus, TACO.Reviewed) in graph, f"food {n}: not marked reviewed")
            reviewers = {str(v) for v in graph.objects(record, TACO.reviewer)}
            expected = {marker["reviewers"]["reviewer_1"], marker["reviewers"]["reviewer_2"]}
            if n in (adjudicated or set()):
                expected.add(marker["reviewers"]["adjudicator"])
            require(reviewers == expected, f"food {n}: reviewer provenance differs")
            require(
                {str(v) for v in graph.objects(record, DCTERMS.date)} == {marker["decision_recorded_on"]},
                f"food {n}: review date differs",
            )
            require(
                {str(v) for v in graph.objects(record, TACO.ontologyVersion)} == {marker["foodon_release"]},
                f"food {n}: ontology release differs",
            )
            require(
                (record, PROV.wasDerivedFrom, URIRef(ID + "review/round-1")) in graph,
                f"food {n}: no review-round provenance",
            )
            provenance.append((n, marker["reviewers"]["adjudicator"] in reviewers))
        review = URIRef(ID + "review/round-1")
        require(
            {str(v) for v in graph.objects(review, TACO.sha256)} == {sha(ROUND / "reviewed-types.csv")},
            "RDF review checksum differs from decisions",
        )
        require(
            {str(v) for v in graph.objects(review, TACO.sourceFile)}
            == {"data/alignment/review/round-1/reviewed-types.csv"},
            "RDF review source path differs",
        )
    result = {
        "pairs": pairs,
        "foods": foods,
        "nutrition": nutrition,
        "nonfoodon": nonfoodon,
        "provenance": sorted(provenance),
        "triples": len(graph),
    }
    del graph
    gc.collect()
    return result


def hierarchy_certificate(path: Path, selected: set[int], out: Path) -> dict:
    index = ROOT / "ontology/imports/foodon-classes.tsv"
    lines = index.read_text(encoding="utf-8").splitlines()
    expected_hash = next(line.split(": ", 1)[1] for line in lines if line.startswith("# sha256:"))
    require(sha(path) == expected_hash, "FoodOn is not the pinned RDF/XML file")
    pinned = {class_number(line.split("\t", 1)[0]) for line in lines if line.startswith("FOODON_")}
    require(selected <= pinned, "final class missing from pinned index")
    about = "{http://www.w3.org/1999/02/22-rdf-syntax-ns#}about"
    resource = "{http://www.w3.org/1999/02/22-rdf-syntax-ns#}resource"
    subclass = "{http://www.w3.org/2000/01/rdf-schema#}subClassOf"
    tree = ET.parse(path)
    parents = defaultdict(set)
    for element in tree.iter():
        child = element.get(about)
        if child:
            for relation in element.findall(subclass):
                parent = relation.get(resource)
                if parent is None:
                    parent = next((part.get(about) for part in relation if part.get(about)), None)
                if parent:
                    parents[child].add(parent)
    del tree
    gc.collect()
    starts = {FOODON + f"{n:08d}" for n in selected}
    safe, todo = set(starts), list(starts)
    while todo:
        for parent in parents[todo.pop()] - safe:
            safe.add(parent)
            todo.append(parent)
    require(not safe & ROOTS, f"final classes reach prohibited roots: {sorted(safe & ROOTS)}")
    edges = sorted((s, p) for s in safe for p in parents[s])
    # Every direct named superclass of every node in the closure is represented.
    require(all(p in safe for _, p in edges), "hierarchy certificate is not closed")
    foreign = sorted((safe | ROOTS) - {iri for iri in safe if iri.startswith(FOODON)})
    numbers = {iri: 100_000_000 + i for i, iri in enumerate(foreign)}
    for iri in safe:
        if iri.startswith(FOODON):
            numbers[iri] = class_number(iri.removeprefix(OBO))
    require(len(set(numbers.values())) == len(numbers), "hierarchy numeric encoding collision")
    (out / "hierarchy-certificate.json").write_text(
        json.dumps(
            {
                "source_sha256": expected_hash,
                "method": "named rdfs:subClassOf closure from RDF/XML",
                "identifier_map": {str(number): iri for iri, number in numbers.items()},
                "safe_node_count": len(safe),
                "edge_count": len(edges),
                "roots": sorted(ROOTS),
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return {
        "safe": sorted(numbers[iri] for iri in safe),
        "roots": sorted(numbers[r] for r in ROOTS),
        "edges": [(numbers[a], numbers[b]) for a, b in edges],
        "pinned": sorted(selected & pinned),
        "selected": sorted(selected),
        "sha256": expected_hash,
    }


def lean_text(data: dict) -> str:
    def tree(values):
        if not values:
            return ".empty"
        middle = len(values) // 2
        return f"(.node {tree(values[:middle])} {values[middle]} {tree(values[middle + 1:])})"

    def listing(name, type_, values):
        return f"def {name} : {type_} := [\n  " + ",\n  ".join(values) + "]\n"

    source = [f"⟨{n}, {a}, {b}, {'none' if c is None else f'some {c}'}⟩" for n, a, b, c in data["source"]]
    text = (
        LEAN_BASE.read_text(encoding="utf-8")
        + "\nnamespace ReviewApplicationData\nopen TypeReviewApplication\n"
    )
    text += "set_option maxRecDepth 100000\nset_option maxHeartbeats 0\n"
    text += f"def safeTree : TypeReviewCertificate.Tree := {tree(sorted(data['safe']))}\n"
    text += f"def selectedTree : TypeReviewCertificate.Tree := {tree(data['selected'])}\n"
    text += listing("sourceRows", "List SourceRow", source)
    for name in ("reviewed", "alignments", "native", "nice", "audit", "published"):
        text += listing(name + "Pairs", "List (Nat × Nat)", [f"({n}, {c})" for n, c in data[name]])
    for name in ("nativeFoods", "niceFoods", "selected", "pinned", "safe", "roots"):
        text += listing(name, "List Nat", [str(n) for n in data[name]])
    text += listing("closureEdges", "List (Nat × Nat)", [f"({a}, {b})" for a, b in data["edges"]])
    text += listing(
        "observedProvenance",
        "List (Nat × Bool)",
        [f"({n}, {'true' if a else 'false'})" for n, a in data["provenance"]],
    )
    for name, value in data["fingerprints"].items():
        text += f'def {name} : String := "{value}"\n'
    text += """
theorem every_source_food_once : sourceRows.map (·.food) = List.range' 1 597 := by decide +kernel
theorem every_native_food_once : nativeFoods = List.range' 1 597 := by decide +kernel
theorem every_nice_food_once : niceFoods = List.range' 1 597 := by decide +kernel
theorem decisions_follow_original_evidence :
    resolved sourceRows = reviewedPairs.map (fun (n, c) => (n, some c)) := by decide +kernel
theorem applied_pairs_exact : alignmentsPairs = reviewedPairs := by decide +kernel
theorem native_pairs_exact : nativePairs = reviewedPairs := by decide +kernel
theorem nice_pairs_exact : nicePairs = reviewedPairs := by decide +kernel
theorem published_pairs_exact : publishedPairs = reviewedPairs := by decide +kernel
theorem audit_pairs_exact : auditPairs = reviewedPairs := by decide +kernel
theorem original_agreement_count :
    (sourceRows.filter (fun r => r.first == r.second)).length = 400 := by decide +kernel
theorem adjudication_count :
    (sourceRows.filter (fun r => r.adjudicated.isSome)).length = 246 := by decide +kernel
theorem other_agreements_count :
    (sourceRows.filter (fun r => r.adjudicated.isNone)).length = 351 := by decide +kernel
theorem provenance_matches_decision_source :
    observedProvenance = sourceRows.map (fun r => (r.food, r.adjudicated.isSome)) := by decide +kernel
theorem distinct_classes : selected.length = 469 := by decide +kernel
theorem safe_tree_exact : TypeReviewCertificate.values safeTree = safe := by decide +kernel
theorem selected_tree_exact : TypeReviewCertificate.values selectedTree = selected := by decide +kernel
theorem selected_classes_pinned : selected.all (fun c => pinned.contains c) = true := by decide +kernel
theorem every_result_class_checked :
    reviewedPairs.all (fun p => TypeReviewCertificate.contains selectedTree p.2) = true := by decide +kernel
theorem selected_in_safe_closure :
    selected.all (fun c => TypeReviewCertificate.contains safeTree c) = true := by decide +kernel
theorem roots_outside_safe_closure : roots.all (fun r => !(safe.contains r)) = true := by decide +kernel
theorem certificate_edges_stay_in_closure :
    closureEdges.all (fun e => TypeReviewCertificate.contains safeTree e.1 &&
      TypeReviewCertificate.contains safeTree e.2) = true := by decide +kernel
theorem native_nutrition_fingerprint_preserved :
    nativeNutritionBefore = nativeNutritionAfter := by decide +kernel
theorem nice_nutrition_fingerprint_preserved : niceNutritionBefore = niceNutritionAfter := by decide +kernel
theorem nice_other_triples_fingerprint_preserved : niceOtherBefore = niceOtherAfter := by decide +kernel
theorem non_foodon_alignments_fingerprint_preserved :
    otherAlignmentsBefore = otherAlignmentsAfter := by decide +kernel
end ReviewApplicationData
"""
    return text


def lean_executable(value: str | None) -> str:
    if value:
        return value
    toolchain = (ROOT / "verification/lean/lean-toolchain").read_text().strip()
    folder = toolchain.replace("/", "--").replace(":", "---")
    binary = Path.home() / ".elan/toolchains" / folder / "bin/lean.exe"
    if binary.is_file():
        return str(binary)
    found = shutil.which("lean")
    require(found is not None, "Lean is unavailable; install the project's pinned Lean toolchain")
    return found


def run_lean(binary: str, path: Path, out: Path) -> subprocess.CompletedProcess:
    result = subprocess.run(
        [binary, str(path)], cwd=ROOT, capture_output=True, text=True, encoding="utf-8", timeout=240
    )
    (out / (path.stem + ".log")).write_text(result.stdout + result.stderr, encoding="utf-8")
    return result


def mutations(data: dict) -> list[tuple[str, dict]]:
    results = []
    for name in (
        "wrong_class_same_count",
        "missing_food",
        "duplicate_food",
        "wrong_provenance",
        "changed_original_response",
        "prohibited_root_in_closure",
        "changed_nutrient_fingerprint",
    ):
        mutant = copy.deepcopy(data)
        if name == "wrong_class_same_count":
            n, c = mutant["nice"][0]
            mutant["nice"][0] = (n, c + 1)
        elif name == "missing_food":
            mutant["alignments"].pop(0)
        elif name == "duplicate_food":
            mutant["native"].append(mutant["native"][0])
        elif name == "wrong_provenance":
            n, yes = mutant["provenance"][0]
            mutant["provenance"][0] = (n, not yes)
        elif name == "changed_original_response":
            n, a, b, c = mutant["source"][0]
            mutant["source"][0] = (n, a + 1, b, c)
        elif name == "prohibited_root_in_closure":
            mutant["safe"].append(mutant["roots"][0])
        else:
            mutant["fingerprints"]["niceNutritionAfter"] = "0" * 64
        require(mutant != data, f"mutant did not change data: {name}")
        results.append((name, mutant))
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--before", type=Path, default=BEFORE)
    parser.add_argument("--out", type=Path, default=OUT)
    parser.add_argument("--foodon", type=Path, default=ROOT / "data/external/foodon/foodon.owl")
    parser.add_argument("--lean")
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    marker = check_hashes(ROUND, args.before)
    evidence = [
        read_rows(ROUND / name)
        for name in (
            "reviewer-1.csv",
            "reviewer-2.csv",
            "reviewed-types.csv",
            "adjudication-all.csv",
            "context.csv",
        )
    ]
    expected, source, adjudicated = check_source_rows(*evidence)
    require(len(expected) == 597, "unexpected reviewed food count")
    print("Evidence: 597 exact decisions, 246 adjudications, 351 agreements; hashes intact", flush=True)
    # Prove the data-integrity check is sensitive to an altered original response.
    changed = copy.deepcopy(evidence)
    changed[0][0]["decision"] = "FOODON_99999999"
    try:
        check_source_rows(*changed)
    except ValueError:
        print("Python mutant: changed original response rejected", flush=True)
    else:
        raise ValueError("source checker accepted a changed original response")
    applied, other_after = alignment_pairs(ROOT / "data/alignment/alignments.csv")
    require(applied == expected, "applied food/class pairs differ from the confirmed decisions")
    other_before = original_non_foodon_rows(args.before / "alignments.csv")
    require(other_before == other_after, "non-FoodOn alignment rows changed")
    audit = sorted(
        (int(r["food_number"]), class_number(r["target_iri"].removeprefix(OBO)))
        for r in read_rows(ROOT / "analysis/data/foodon_types.csv")
    )
    require(
        audit == expected and not read_rows(ROOT / "analysis/data/foodon_typing_gaps.csv"),
        "audit output differs from the confirmed review",
    )
    native = graph_evidence(ROOT / "build/taco.ttl", native=True, marker=marker, adjudicated=set(adjudicated))
    print("Native graph: exact mapping and per-food reviewer provenance checked", flush=True)
    native_before = graph_evidence(args.before / "taco.ttl", native=True)
    require(native["nutrition"] == native_before["nutrition"], "native nutritional triples changed")
    nice = graph_evidence(ROOT / "build/taco_nice_food.ttl", native=False)
    nice_before = graph_evidence(args.before / "taco_nice_food.ttl", native=False)
    require(nice["nutrition"] == nice_before["nutrition"], "NICE-Food nutritional triples changed")
    require(nice["nonfoodon"] == nice_before["nonfoodon"], "NICE-Food non-FoodOn triples changed")
    published = graph_evidence(
        ROOT / "docs/taco-in-nice-food/files/knowledge-graph/taco_nice_food.ttl", native=False
    )
    for name, graph in (("native", native), ("NICE", nice), ("published NICE", published)):
        require(graph["pairs"] == expected and graph["foods"] == FOODS, f"{name}: wrong foods or classes")
    require(published["nonfoodon"] == nice["nonfoodon"], "published export differs from build export")
    print(
        "Graphs: 597 exact pairs in native/build NICE/published NICE; nutritional triples unchanged",
        flush=True,
    )
    certificate = hierarchy_certificate(args.foodon, {c for _, c in expected}, args.out)
    print(
        f"Hierarchy: {len(certificate['safe'])} closed nodes, {len(certificate['edges'])} edges, no roots",
        flush=True,
    )
    data = {
        "source": source,
        "reviewed": expected,
        "alignments": applied,
        "native": native["pairs"],
        "nice": nice["pairs"],
        "published": published["pairs"],
        "audit": audit,
        "nativeFoods": native["foods"],
        "niceFoods": nice["foods"],
        "provenance": native["provenance"],
        **certificate,
        "fingerprints": {
            "nativeNutritionBefore": digest_lines(list(native_before["nutrition"])),
            "nativeNutritionAfter": digest_lines(list(native["nutrition"])),
            "niceNutritionBefore": digest_lines(list(nice_before["nutrition"])),
            "niceNutritionAfter": digest_lines(list(nice["nutrition"])),
            "niceOtherBefore": digest_lines(list(nice_before["nonfoodon"])),
            "niceOtherAfter": digest_lines(list(nice["nonfoodon"])),
            "otherAlignmentsBefore": other_before,
            "otherAlignmentsAfter": other_after,
        },
    }
    binary = lean_executable(args.lean)
    path = args.out / "TypeReviewApplicationData.lean"
    path.write_text(lean_text(data), encoding="utf-8", newline="\n")
    result = run_lean(binary, path, args.out)
    require(result.returncode == 0, f"Lean rejected the baseline certificate; see {path.stem}.log")
    print("Lean: baseline accepted by kernel; running 7 mutation checks", flush=True)
    rejected = []
    mutation_theorems = {
        "wrong_class_same_count": "nice_pairs_exact",
        "missing_food": "applied_pairs_exact",
        "duplicate_food": "native_pairs_exact",
        "wrong_provenance": "provenance_matches_decision_source",
        "changed_original_response": "original_agreement_count",
        "prohibited_root_in_closure": "roots_outside_safe_closure",
        "changed_nutrient_fingerprint": "nice_nutrition_fingerprint_preserved",
    }
    for name, mutant in mutations(data):
        mutant_path = args.out / f"Mutant_{name}.lean"
        base, concrete = lean_text(mutant).split("namespace ReviewApplicationData", 1)
        # Baseline checks every theorem. Each negative test needs just its targeted assertion,
        # avoiding seven redundant, expensive hierarchy certificates.
        concrete = re.sub(r"(?ms)^theorem (\w+).*?(?=^theorem |^end ReviewApplicationData)",
                          lambda m, target=mutation_theorems[name]: m[0] if m[1] == target else "", concrete)
        mutant_path.write_text(base + "namespace ReviewApplicationData" + concrete,
                               encoding="utf-8", newline="\n")
        run = run_lean(binary, mutant_path, args.out)
        require(
            run.returncode != 0 and "error:" in run.stdout + run.stderr,
            f"Lean did not reject the mutant as a proof failure: {name}",
        )
        rejected.append(name)
        print(f"Lean mutant rejected: {name}", flush=True)
    summary = {
        "foods": 597,
        "adjudicated": 246,
        "original_agreements_retained": 351,
        "original_exact_agreement": {"numerator": 400, "denominator": 597},
        "mapping_pairs_equal": True,
        "native_provenance_checked": 597,
        "native_nutritional_triples": len(native["nutrition"]),
        "nice_nutritional_triples": len(nice["nutrition"]),
        "nice_non_foodon_triples": len(nice["nonfoodon"]),
        "nutrition_exactly_unchanged": True,
        "foodon_sha256": certificate["sha256"],
        "hierarchy_certificate_nodes": len(certificate["safe"]),
        "hierarchy_certificate_edges": len(certificate["edges"]),
        "lean_binary": binary,
        "lean_baseline_checked": True,
        "lean_mutants_rejected": rejected,
        "python_mutants_rejected": ["changed original response"],
        "generic_theorems": 9,
        "concrete_theorems": 25,
        "limits": "Checks faithful application and generated finite certificates; RDF parsing and "
        "certificate extraction are Python, and food/class semantic judgements remain human.",
    }
    (args.out / "result.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, OSError, subprocess.TimeoutExpired) as error:
        print(f"VERIFICATION FAILED: {error}", file=sys.stderr)
        raise SystemExit(1) from error
