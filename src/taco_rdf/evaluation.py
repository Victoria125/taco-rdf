"""Review of the food alignments: the items and forms reviewers fill in, and the results drawn from them."""

from __future__ import annotations

import csv
import hashlib
import json
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, replace
from pathlib import Path

from rdflib import Graph, URIRef
from rdflib.namespace import OWL, PROV, RDF, RDFS

from .graph import Alignment, FoodName
from .namespaces import ALIGNMENTS_CSV, CORRECTIONS_DIR, FOOD_NAMES_EN, FOODON_MODULE_TTL, RAW_XLS, ROOT
from .parse import Table

DECISIONS = ("accept", "relation", "class", "none", "unsure")
RELATIONS = ("type", "exact", "close", "narrow", "broad", "related")
CERTAINTY = ("certain", "uncertain")
CONTEXT = ["food_number", "name_pt", "name_en", "group", "current_relation", "current_class", "current_label",
           "current_definition", "candidates", "foodon_release"]
ANSWER = ["decision", "relation", "class", "certainty", "justification", "evidence", "reviewer",
          "reviewed_on"]
FOODON_CURIE = re.compile(r"^FOODON_\d{8}$")
DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
PREDICATE_OF = {"type": "rdf:type", "exact": "skos:exactMatch", "close": "skos:closeMatch",
                "narrow": "skos:narrowMatch", "broad": "skos:broadMatch", "related": "skos:relatedMatch",
                "closeMatch": "skos:closeMatch", "exactMatch": "skos:exactMatch",
                "narrowMatch": "skos:narrowMatch", "broadMatch": "skos:broadMatch",
                "relatedMatch": "skos:relatedMatch"}
MODULE_IRI = URIRef("https://w3id.org/taco-rdf/imports/foodon-module")


@dataclass(frozen=True)
class FoodOnIndex:
    release: str
    labels: dict[str, str]

    def check(self, release: str, target: str = "") -> None:
        if release != self.release:
            raise ValueError(f"foodon_release differs from the pinned module: {release}")
        if target and target not in self.labels:
            raise ValueError(f"class {target} is absent from the pinned FoodOn module; "
                             "extend the module from the same release and prepare a new round")


def foodon_index() -> FoodOnIndex:
    graph = Graph().parse(FOODON_MODULE_TTL)
    releases = list(graph.objects(MODULE_IRI, PROV.wasDerivedFrom))
    if len(releases) != 1 or not isinstance(releases[0], URIRef):
        raise ValueError("the FoodOn module must identify exactly one source release")
    labels = {}
    for cls in graph.subjects(RDF.type, OWL.Class):
        target = str(cls).removeprefix("http://purl.obolibrary.org/obo/")
        if FOODON_CURIE.fullmatch(target):
            values = list(graph.objects(cls, RDFS.label))
            english = [str(v) for v in values if getattr(v, "language", None) == "en"]
            labels[target] = min(english or [str(v) for v in values], default="")
    return FoodOnIndex(str(releases[0]), labels)


@dataclass(frozen=True)
class Item:
    food_number: int
    part: str
    stratum: str = ""
    stratum_size: int = 0
    sample_size: int = 0
    flag: str = ""

    @property
    def inclusion_probability(self) -> float | None:
        return self.sample_size / self.stratum_size if self.part == "sample" else None


@dataclass(frozen=True)
class Answer:
    food_number: int
    current_class: str
    current_relation: str
    decision: str
    relation: str
    target: str
    certainty: str
    justification: str
    evidence: str
    reviewer: str
    reviewed_on: str
    foodon_release: str
    context: tuple[str, ...]
    a_evidence: str = ""
    b_evidence: str = ""

    @property
    def mapped(self) -> bool:
        return bool(self.current_class)


@dataclass(frozen=True)
class Agreement:
    agreed: list[int]
    disagreed: list[int]
    kappa: float | None

    @property
    def kappa_text(self) -> str:
        return "not estimable" if self.kappa is None else f"{self.kappa:.2f}"

    @property
    def share(self) -> float:
        total = len(self.agreed) + len(self.disagreed)
        return len(self.agreed) / total if total else 0.0


def _rank(seed: str, food: int) -> str:
    return hashlib.sha256(f"{seed}:{food}".encode()).hexdigest()


def links_by_food(table: Table, alignments: list[Alignment]) -> dict[int, Alignment]:
    by_food = {}
    for a in alignments:
        if a.source_type == "food":
            food = int(a.source_key)
            if food not in table.foods or food in by_food:
                raise ValueError(f"the review needs at most one mapping per known food: {food}")
            by_food[food] = a
    return by_food


def load_problem_cases(path: Path) -> dict[int, str]:
    with open(path, newline="", encoding="utf-8") as fh:
        return {int(r["food_number"]): r["flag"] for r in csv.DictReader(fh)}


def review_items(table: Table, alignments: list[Alignment], problem_cases: dict[int, str], *,
                 seed: str, per_stratum: int, prepared_group: str = "Alimentos preparados") -> list[Item]:
    """A stratified sample by group and relation, then the problem cases, then every prepared dish."""
    if per_stratum < 1:
        raise ValueError("per_stratum must be positive")
    unknown = sorted(set(problem_cases) - set(table.foods))
    if unknown:
        raise ValueError(f"problem cases name unknown foods: {unknown}")
    by_food = links_by_food(table, alignments)
    strata = defaultdict(list)
    for food in table.foods.values():
        relation = by_food[food.id].predicate if food.id in by_food else "none"
        strata[(food.group_id, relation)].append(food.id)
    items: dict[int, Item] = {}
    for (group, relation), foods in sorted(strata.items()):
        chosen = sorted(foods, key=lambda f: _rank(seed, f))[:per_stratum]
        for food in chosen:
            items[food] = Item(food, "sample", f"{group}/{relation}", len(foods), len(chosen),
                               problem_cases.get(food, ""))
    for food, flag in sorted(problem_cases.items()):
        items.setdefault(food, Item(food, "problem case", flag=flag))
    prepared = table.groups.index(prepared_group) + 1
    for food in sorted(f.id for f in table.foods.values() if f.group_id == prepared):
        items.setdefault(food, Item(food, "prepared dish"))
    return sorted(items.values(), key=lambda i: _rank(seed + ":order", i.food_number))


def item_rows(items: list[Item]) -> list[dict]:
    rows = []
    for i in items:
        probability = "" if i.inclusion_probability is None else round(i.inclusion_probability, 4)
        rows.append({"food_number": i.food_number, "part": i.part, "stratum": i.stratum,
                     "stratum_size": i.stratum_size, "sample_size": i.sample_size,
                     "inclusion_probability": probability, "flag": i.flag})
    return rows


def form_rows(items: list[Item], table: Table, alignments: list[Alignment], names_en: dict[int, FoodName],
              release: str, lookup: dict[int, tuple[str, str]] | None = None) -> list[dict]:
    """The blank form: what the reviewer needs to judge each food, and empty answer columns."""
    by_food = links_by_food(table, alignments)
    rows = []
    for item in items:
        food = table.foods[item.food_number]
        link = by_food.get(food.id)
        definition, candidates = (lookup or {}).get(food.id, ("", ""))
        rows.append({
            "food_number": food.id, "name_pt": food.name, "name_en": names_en[food.id].name_en,
            "group": table.groups[food.group_id - 1],
            "current_relation": link.predicate if link else "none",
            "current_class": link.target_iri.rsplit("/", 1)[-1] if link else "",
            "current_label": link.target_label if link else "",
            "current_definition": definition, "candidates": candidates, "foodon_release": release,
            **dict.fromkeys(ANSWER, ""),
        })
    return rows


def write_rows(path: Path, rows: list[dict], fields: list[str]) -> None:
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def read_rows(path: Path) -> list[dict]:
    with open(path, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def review_hash(path: Path) -> str:
    data = path.read_bytes()
    if path.suffix != ".xls":
        data = data.replace(b"\r\n", b"\n")
    return hashlib.sha256(data).hexdigest()


def input_hashes() -> dict[str, str]:
    paths = {
        "alignments": ALIGNMENTS_CSV, "workbook": RAW_XLS, "names": FOOD_NAMES_EN,
        "problem_cases": ROOT / "data/alignment/review/problem_cases.csv",
        "foodon_module": FOODON_MODULE_TTL,
        "correction_cells": CORRECTIONS_DIR / "cells.csv", "correction_ids": CORRECTIONS_DIR / "ids.csv",
        "protocol": ROOT / "docs/alignment-review.md",
    }
    return {f"{name}_sha256": review_hash(path) for name, path in paths.items()}


def indexed_rows(rows: list[dict], name: str) -> dict[int, dict]:
    indexed = {}
    for row in rows:
        try:
            food = int(row["food_number"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"{name}: invalid food_number") from exc
        if food in indexed:
            raise ValueError(f"{name}: duplicate food_number {food}")
        indexed[food] = row
    return indexed


def check_context(rows: list[dict], expected: list[dict], name: str) -> None:
    actual, reference = indexed_rows(rows, name), indexed_rows(expected, "reference context")
    if set(actual) != set(reference):
        raise ValueError(f"{name}: foods differ from the reference context: "
                         f"{sorted(set(actual) ^ set(reference))}")
    for food, baseline in reference.items():
        changed = [key for key, value in baseline.items() if key not in ANSWER
                   and actual[food].get(key) != str(value)]
        if changed:
            raise ValueError(f"{name}: food {food} differs from the reference context: {', '.join(changed)}")


def validate_round(folder: Path, manifest: dict) -> list[dict]:
    if manifest.get("hash_format") != "sha256-lf-v1":
        raise ValueError("unsupported review hash format; prepare a round with sha256-lf-v1 checksums")
    hashes = input_hashes()
    for name in ("context", "items"):
        path = folder / f"{name}.csv"
        if not path.is_file():
            raise ValueError(f"missing {path.name}; prepare a round with a fixed reference context")
        hashes[f"{name}_sha256"] = review_hash(path)
    changed = [key for key, digest in hashes.items() if manifest.get(key) != digest]
    if changed:
        raise ValueError("review inputs differ from the manifest: " + ", ".join(changed)
                         + "; restore the recorded inputs or prepare a new round")
    foodon_index().check(manifest["foodon_release"])
    context = read_rows(folder / "context.csv")
    indexed = indexed_rows(context, "context.csv")
    items = indexed_rows(read_rows(folder / "items.csv"), "items.csv")
    if not context or len(context) != manifest["items"] or set(indexed) != set(items):
        raise ValueError("context.csv and items.csv must cover exactly the foods in the manifest")
    if any(set(row) != set(CONTEXT) or None in row.values() for row in context):
        raise ValueError("context.csv has missing or unexpected columns")
    if any(row["foodon_release"] != manifest["foodon_release"] for row in context):
        raise ValueError("context.csv uses a different FoodOn release from the manifest")
    return context


def _problems(row: dict) -> list[str]:
    decision, relation, target = row["decision"].strip(), row["relation"].strip(), row["class"].strip()
    found = []
    if decision not in DECISIONS:
        found.append(f"decision must be one of {', '.join(DECISIONS)}")
    if row["certainty"].strip() not in CERTAINTY:
        found.append(f"certainty must be one of {', '.join(CERTAINTY)}")
    if not row["justification"].strip():
        found.append("justification is empty")
    if not row["reviewer"].strip():
        found.append("reviewer is empty")
    if not DATE.match(row["reviewed_on"].strip()):
        found.append("reviewed_on must be a date, YYYY-MM-DD")
    if not row["foodon_release"].strip():
        found.append("foodon_release is empty")
    if decision in ("relation", "class") and relation not in RELATIONS:
        found.append(f"relation must be one of {', '.join(RELATIONS)}")
    if decision == "class" and not FOODON_CURIE.match(target):
        found.append("class must be a FoodOn identifier such as FOODON_03309834")
    if decision == "relation" and not row["current_class"].strip():
        found.append("an unmapped food has no relation to change; use class or accept")
    if decision == "unsure" and row["certainty"].strip() != "uncertain":
        found.append("an unsure decision is uncertain")
    return found


def read_answers(path: Path, expected: list[dict] | None = None) -> dict[int, Answer]:
    """Read a filled form, refusing it while any row is incomplete or inconsistent."""
    rows = read_rows(path)
    indexed = indexed_rows(rows, Path(path).name)
    if expected is not None:
        check_context(rows, expected, Path(path).name)
    foodon = foodon_index()
    answers, problems = {}, []
    for food, row in indexed.items():
        missing = [key for key in CONTEXT + ANSWER if row.get(key) is None]
        if missing:
            problems.append(f"food {food}: missing columns: {', '.join(missing)}")
            continue
        found = _problems(row)
        target = row["class"] if row["decision"].strip() == "class" else (
            row["current_class"] if row["decision"].strip() in ("accept", "relation") else "")
        try:
            foodon.check(row["foodon_release"].strip(), target.strip())
        except ValueError as exc:
            found.append(str(exc))
        if found:
            problems.append(f"food {food}: " + "; ".join(found))
            continue
        value = {k: row[k].strip() for k in ("current_class", "foodon_release", *ANSWER)}
        answers[food] = Answer(
            food_number=food, current_class=value["current_class"], current_relation=row["current_relation"],
            decision=value["decision"], relation=value["relation"], target=value["class"],
            certainty=value["certainty"], justification=value["justification"], evidence=row["evidence"],
            reviewer=value["reviewer"], reviewed_on=value["reviewed_on"],
            foodon_release=value["foodon_release"],
            context=tuple(row[key] for key in CONTEXT),
            a_evidence=row.get("a_evidence", ""), b_evidence=row.get("b_evidence", ""),
        )
    if problems:
        raise ValueError(f"{Path(path).name} has {len(problems)} incomplete rows:\n" + "\n".join(problems))
    return answers


def decision_of(answer: Answer) -> str:
    """For a food with no link, accepting that and saying no class fits are the same decision."""
    return "accept" if not answer.mapped and answer.decision == "none" else answer.decision


def same(a: Answer, b: Answer) -> bool:
    if decision_of(a) != decision_of(b):
        return False
    if a.decision == "relation":
        return a.relation == b.relation
    if a.decision == "class":
        return a.relation == b.relation and a.target == b.target
    return True


def cohen_kappa(first: list[str], second: list[str]) -> float | None:
    if len(first) != len(second):
        raise ValueError("kappa requires equally sized sets of decisions")
    n = len(first)
    if not n:
        return None
    observed = sum(x == y for x, y in zip(first, second, strict=True)) / n
    a, b = Counter(first), Counter(second)
    expected = sum(a[k] * b[k] for k in set(a) | set(b)) / n ** 2
    return None if expected == 1 else (observed - expected) / (1 - expected)


def compare(a: dict[int, Answer], b: dict[int, Answer]) -> Agreement:
    """Agreement between two reviewers on the decision and, where given, on the relation and class."""
    if set(a) != set(b):
        raise ValueError(f"the two forms cover different foods: {sorted(set(a) ^ set(b))[:10]}")
    foods = sorted(a)
    for food in foods:
        if a[food].context != b[food].context:
            raise ValueError(f"food {food}: the reviewers used different contexts")
    agreed = [f for f in foods if same(a[f], b[f])]
    disagreed = [f for f in foods if not same(a[f], b[f])]
    kappa = cohen_kappa([decision_of(a[f]) for f in foods], [decision_of(b[f]) for f in foods])
    return Agreement(agreed, disagreed, kappa)


def adjudication_rows(form: list[dict], a: dict[int, Answer], b: dict[int, Answer],
                      foods: list[int]) -> list[dict]:
    context = {int(r["food_number"]): r for r in form}
    rows = []
    for food in foods:
        row = {k: context[food][k] for k in CONTEXT}
        for who, answer in (("a", a[food]), ("b", b[food])):
            row |= {f"{who}_decision": answer.decision, f"{who}_relation": answer.relation,
                    f"{who}_class": answer.target, f"{who}_certainty": answer.certainty,
                    f"{who}_justification": answer.justification, f"{who}_evidence": answer.evidence,
                    f"{who}_reviewer": answer.reviewer, f"{who}_reviewed_on": answer.reviewed_on}
        rows.append(row | dict.fromkeys(ANSWER, ""))
    return rows


ADJUDICATION = CONTEXT + [f"{w}_{k}" for w in "ab" for k in ANSWER] + ANSWER


def final_answers(a: dict[int, Answer], b: dict[int, Answer], agreement: Agreement,
                  adjudicated: dict[int, Answer]) -> dict[int, Answer]:
    if compare(a, b) != agreement:
        raise ValueError("the agreement does not match the current reviewer answers")
    missing = sorted(set(agreement.disagreed) - set(adjudicated))
    if missing:
        raise ValueError(f"disagreements without an adjudicated decision: {missing}")
    unexpected = sorted(set(adjudicated) - set(agreement.disagreed))
    if unexpected:
        raise ValueError(f"adjudicated decisions for foods without a disagreement: {unexpected}")
    final = {}
    for food in agreement.agreed:
        x, y = a[food], b[food]
        certainty = "uncertain" if "uncertain" in (x.certainty, y.certainty) else "certain"
        evidence = "\n".join(dict.fromkeys(v for v in (x.evidence, y.evidence) if v.strip()))
        final[food] = replace(x, certainty=certainty, justification=f"{x.justification} / {y.justification}",
                              evidence=evidence, reviewer=f"{x.reviewer}; {y.reviewer}",
                              reviewed_on=max(x.reviewed_on, y.reviewed_on),
                              a_evidence=x.evidence, b_evidence=y.evidence)
    for food in agreement.disagreed:
        if adjudicated[food].context != a[food].context:
            raise ValueError(f"food {food}: adjudication uses a different context")
        final[food] = replace(adjudicated[food], a_evidence=a[food].evidence, b_evidence=b[food].evidence)
    return final


def outcome(answer: Answer) -> str:
    if answer.decision == "unsure":
        return "unsure"
    if answer.mapped:
        return {"accept": "correct", "relation": "wrong relation", "class": "wrong class",
                "none": "should not be mapped"}[answer.decision]
    return "class missed" if answer.decision == "class" else "correctly unmapped"


def coverage(table: Table, alignments: list[Alignment]) -> Counter:
    by_food = links_by_food(table, alignments)
    return Counter(by_food[f].predicate if f in by_food else "none" for f in table.foods)


def summarise(items: list[Item], final: dict[int, Answer]) -> dict:
    """Outcomes per part of the review, and the errors found; no estimate for the whole alignment."""
    parts: dict[str, Counter] = defaultdict(Counter)
    strata: dict[str, Counter] = defaultdict(Counter)
    for item in items:
        result = outcome(final[item.food_number])
        parts[item.part][result] += 1
        if item.part == "sample":
            strata[item.stratum][result] += 1
    errors = [final[i.food_number] for i in items
              if outcome(final[i.food_number]) in ("wrong relation", "wrong class", "should not be mapped",
                                                   "class missed")]
    return {"parts": dict(parts), "strata": dict(strata), "errors": errors}


SSSOM_FIELDS = ["subject_id", "subject_label", "predicate_id", "object_id", "object_label",
                "mapping_justification", "author_label", "mapping_date", "object_source_version", "comment"]


def sssom_rows(final: dict[int, Answer], table: Table, alignments: list[Alignment]) -> list[dict]:
    """The reviewed mappings in SSSOM, with sssom:NoTermFound where no FoodOn class fits."""
    by_food = links_by_food(table, alignments)
    foodon = foodon_index()
    rows = []
    for food, answer in sorted(final.items()):
        if answer.decision == "unsure":
            continue
        link = by_food.get(food)
        current_class = link.target_iri.rsplit("/", 1)[-1] if link else ""
        current_relation = link.predicate if link else "none"
        if (answer.current_class, answer.current_relation) != (current_class, current_relation):
            raise ValueError(f"food {food}: the alignment differs from the reviewed context")
        if answer.decision == "class":
            predicate, target, label = PREDICATE_OF[answer.relation], answer.target, ""
        elif answer.decision == "relation":
            predicate, target, label = PREDICATE_OF[answer.relation], answer.current_class, link.target_label
        elif answer.decision == "accept" and link:
            predicate, target, label = PREDICATE_OF[link.predicate], answer.current_class, link.target_label
        else:
            predicate, target, label = "skos:closeMatch", "", ""
        foodon.check(answer.foodon_release, target)
        if target:
            label = foodon.labels[target]
        comment = json.dumps({"justification": answer.justification, "certainty": answer.certainty,
                              "evidence": answer.evidence, "a_evidence": answer.a_evidence,
                              "b_evidence": answer.b_evidence}, ensure_ascii=False)
        rows.append({
            "subject_id": f"tacoid:food/{food}", "subject_label": table.foods[food].name,
            "predicate_id": predicate,
            "object_id": target.replace("FOODON_", "FOODON:") if target else "sssom:NoTermFound",
            "object_label": label, "mapping_justification": "semapv:ManualMappingCuration",
            "author_label": answer.reviewer, "mapping_date": answer.reviewed_on,
            "object_source_version": answer.foodon_release, "comment": comment,
        })
    return rows


SSSOM_HEADER = """# curie_map:
#   FOODON: http://purl.obolibrary.org/obo/FOODON_
#   rdf: http://www.w3.org/1999/02/22-rdf-syntax-ns#
#   semapv: https://w3id.org/semapv/vocab/
#   skos: http://www.w3.org/2004/02/skos/core#
#   sssom: https://w3id.org/sssom/
#   tacoid: https://w3id.org/taco-rdf/id/
# license: https://creativecommons.org/licenses/by/4.0/
# mapping_set_id: https://w3id.org/taco-rdf/review/{round}
"""


def write_sssom(path: Path, rows: list[dict], round_name: str) -> None:
    with open(path, "w", newline="", encoding="utf-8") as fh:
        fh.write(SSSOM_HEADER.format(round=round_name))
        writer = csv.DictWriter(fh, fieldnames=SSSOM_FIELDS, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
