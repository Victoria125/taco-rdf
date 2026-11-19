# ruff: noqa: E501, RUF001
"""Check that TACO's NICE-Food export follows NEVO's pattern as far as the data allow, and that matching it
changed nothing else.

TACO's export marks each food with the edition it comes from (dcterms:hasVersion), as NICE-Food marks NEVO's
food items ("NEVO-Online 2021 7.0"@nl). Against Fuseki's nicefood dataset and the export file
(docs/taco-in-nice-food/files/knowledge-graph/taco_nice_food.ttl), this script checks:

1. Same properties: on food items, nutritional values and measures, every property NEVO's graph uses is used by
   TACO's export too, but NEVO's own food codes (fio:hasNevoCode21, fio:hasNevoCode23). TACO's properties are
   read twice, from Fuseki and with rdflib from the file, and must agree.
2. The version: every TACO food has exactly one dcterms:hasVersion, in the file and in Fuseki, written as
   NICE-Food writes NEVO's: a string in the table's own language (NEVO's Dutch, TACO's Portuguese).
3. Nothing else changed: against the export published before (commit 5714556), the only triples added are one
   dcterms:hasVersion per food, and none is removed, so every value, status and derivation is kept. The export
   in build/ is the file in docs/.
4. Same answers: with --baseline, NICE-Food's protein queries and the competency questions give, on Fuseki, the
   same rows as before the change. --save-baseline writes those rows; they hold NEVO rows, so keep them in
   build/, which is not committed.
5. Why those answers cannot change: every triple pattern of those queries has a fixed predicate (read with
   rdflib's SPARQL parser), and none is dcterms:hasVersion.
6. The nutrients that keep TACO's own URI, each of one kind, checked against NEVO's nutrient labels (Fuseki,
   English and Dutch): 0, NEVO has no such nutrient; 1, NEVO has it only split or qualified (cis or trans, n-3 or
   n-6, available) and TACO does not say which form its value is; 2, TACO's own tagname or name gives a form NEVO
   has a code for (scripts/nutrient_definitions.py, COULD_TAKE), so it could take that code: a decision left
   open, not a reason to keep TACO's URI. They must be the nutrients the alignment file leaves without a code.
7. Lean 4 with Mathlib: the facts above go to build/verification/TacoNevoAlignment.lean as theorems Lean
   decides, with a general theorem proved for all graphs: triples whose predicate a pattern does not name
   cannot change what the pattern reads.
8. Mutants: each check above, and the Lean file, must reject a changed copy of its data.

    $env:PYTHONPATH = "src"; python verification/taco_nevo_alignment_check.py --baseline build/baseline.json
        --lake-project C:/path/to/lake/project
"""

from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

from rdflib import DCTERMS, RDF, Graph, Literal, URIRef
from rdflib.paths import AlternativePath, InvPath, MulPath, NegatedPath, SequencePath
from rdflib.plugins.sparql import prepareQuery
from rdflib.plugins.sparql.algebra import traverse
from rdflib.term import Variable

from taco_rdf.namespaces import FIO, OM
from taco_rdf.namespaces import NEVONUT as NEVONUT_NS
from taco_rdf.nice_food_queries import answers, queries

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "verification"))
import taco_typing_state as state  # noqa: E402


def load(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ds, nice, nd = load("describe_structure"), load("taco_to_nice_food"), load("nutrient_definitions")
EXPORT = ROOT / "docs" / "taco-in-nice-food" / "files" / "knowledge-graph" / "taco_nice_food.ttl"
BEFORE = "5714556"  # the commit that published the export before dcterms:hasVersion
OUT = ROOT / "build" / "verification" / "TacoNevoAlignment.lean"
NEVONUT = str(NEVONUT_NS)
NEVO_CODES = {"fio:hasNevoCode21", "fio:hasNevoCode23"}
HAS_VERSION = "dcterms:hasVersion"
# Nutrients NEVO does not have: no NEVO label, English or Dutch, may match.
ABSENT = {"manganese": r"manga+n", "alanine": r"\balanin", "arginine": r"arginin", "aspartic_acid": r"aspar",
          "cystine": r"cyst", "glutamic_acid": r"glutam", "glycine": r"glycin", "histidine": r"histidin",
          "isoleucine": r"isoleucin", "leucine": r"\bleucin", "lysine": r"lysin", "methionine": r"methionin",
          "phenylalanine": r"(ph|f)enylalanin", "proline": r"prolin", "serine": r"\bserin",
          "threonine": r"threonin", "tyrosine": r"tyrosin", "valine": r"\bvalin"}
# Nutrients NEVO has only split or qualified: every NEVO label that matches must carry the qualifier.
CIS_TRANS, SERIES = r"\b(cis|trans)\b", r"\bn-[36]\b"
QUALIFIED = {"fa_14_1": (r"^C14:1\b", CIS_TRANS), "fa_16_1": (r"^C16:1\b", CIS_TRANS),
             "fa_18_1": (r"^C18:1\b", CIS_TRANS), "fa_20_1": (r"^C20:1\b", CIS_TRANS),
             "fa_20_4": (r"^C20:4\b", SERIES), "fa_22_5": (r"^C22:5\b", SERIES),
             "fa_18_2t": (r"^C18:2\b.*\btrans\b", r"\b(n-6|cis)\b"),
             "mufa": (r"monounsaturated|enkelvoudig onverzadigd", CIS_TRANS),
             "carbohydrate": (r"carbohydrate|koolhydraten", r"available|beschikbaar")}


# 1. Same properties

def fuseki_properties(endpoint: str) -> dict[str, dict[str, set[str]]]:
    out: dict[str, dict[str, set[str]]] = {}
    for name, src in (("TACO", ds.TACO), ("NEVO", ds.NEVO)):
        for level, pattern in ds.LEVELS.items():
            query = f"SELECT DISTINCT ?p WHERE {{ {pattern.format(src=src)} . ?x ?p ?o }}"
            out.setdefault(name, {})[level] = {ds.short(r["p"]) for r in ds.rows(endpoint, query)}
    return out


def taco_nodes(g: Graph) -> dict[str, set]:
    foods = set(g.subjects(DCTERMS.isVersionOf, URIRef(ds.TACO)))
    values = {v for f in foods for v in g.objects(f, FIO.hasNutritionalValue)}
    return {"food item": foods, "nutritional value": values,
            "measure": {m for v in values for m in g.objects(v, OM.hasValue)}}


def file_properties(g: Graph) -> dict[str, set[str]]:
    return {level: {ds.short(str(p)) for x in xs for p in g.predicates(x)} for level, xs in taco_nodes(g).items()}


def check_properties(props: dict[str, dict[str, set[str]]], from_file: dict[str, set[str]]) -> list[str]:
    out = []
    for level, nevo in props["NEVO"].items():
        out += [f"1. {level}: NEVO uses {p}, TACO does not" for p in sorted(nevo - props["TACO"][level] - NEVO_CODES)]
        if from_file[level] != props["TACO"][level]:
            out.append(f"1. {level}: TACO's properties in Fuseki and in the file differ: "
                       f"{sorted(from_file[level] ^ props['TACO'][level])}")
    return out


# 2. The version

def file_versions(g: Graph) -> dict[int, list[Literal]]:
    return {int(str(f).rsplit("/", 1)[-1]): list(g.objects(f, DCTERMS.hasVersion)) for f in taco_nodes(g)["food item"]}


def fuseki_versions(endpoint: str) -> tuple[dict[int, int], dict[str, set[tuple[str, str]]]]:
    per_food = {int(r["f"].rsplit("/", 1)[-1]): int(r["n"]) for r in ds.rows(
        endpoint, f"SELECT ?f (COUNT(?v) AS ?n) WHERE {{ ?f dcterms:isVersionOf <{ds.TACO}> "
        "OPTIONAL { ?f dcterms:hasVersion ?v } } GROUP BY ?f")}
    forms: dict[str, set[tuple[str, str]]] = {}
    for r in ds.rows(endpoint, "SELECT DISTINCT ?src (DATATYPE(?v) AS ?dt) (LANG(?v) AS ?lang) WHERE { "
                     "?f dcterms:isVersionOf ?src ; dcterms:hasVersion ?v }"):
        forms.setdefault(r["src"], set()).add((r["dt"], r.get("lang", "")))
    return per_food, forms


def check_versions(in_file: dict[int, list[Literal]], in_fuseki: dict[int, int],
                   forms: dict[str, set[tuple[str, str]]]) -> list[str]:
    out = [f"2. food {n} has {vs!r} in the file, not one {nice.TACO_VERSION!r}"
           for n, vs in sorted(in_file.items()) if vs != [nice.TACO_VERSION]]
    if in_fuseki != {n: len(vs) for n, vs in in_file.items()}:
        out.append("2. Fuseki's versions per food are not the file's")
    # NICE-Food writes NEVO's version as a string in NEVO's language (Literal(..., lang="nl")); TACO's must be
    # a string in TACO's.
    expected = {ds.TACO: {(str(RDF.langString), "pt")}, ds.NEVO: {(str(RDF.langString), "nl")}}
    if any(forms.get(src) != form for src, form in expected.items()):
        out.append(f"2. TACO's versions are {forms.get(ds.TACO)}, NEVO's {forms.get(ds.NEVO)}")
    return out


# 3. Nothing else changed

def published_before() -> Graph:
    path = EXPORT.relative_to(ROOT).as_posix()
    text = subprocess.run(["git", "-C", str(ROOT), "show", f"{BEFORE}:{path}"], capture_output=True,
                          check=True).stdout
    return Graph().parse(data=text, format="turtle")


def check_diff(added: set, removed: set, foods: set) -> list[str]:
    expected = {(f, DCTERMS.hasVersion, nice.TACO_VERSION) for f in foods}
    out = [f"3. {len(removed)} triples of the earlier export are gone, e.g. {sorted(removed)[0]}"] if removed else []
    if added != expected:
        out.append(f"3. added: {len(added - expected)} triples other than the versions, "
                   f"{len(expected - added)} versions missing")
    return out


# 4. Same answers (the rows come from taco_rdf.nice_food_queries.answers, as scripts/rebuild_nicefood.py's do)

def check_answers(now: dict[str, list[tuple[str, ...]]], before: dict[str, list]) -> list[str]:
    out = [f"4. {k}: no rows before the change" for k in sorted(set(now) - set(before))]
    for k, rows in before.items():
        old = sorted(tuple(r) for r in rows)
        if now.get(k) != old:
            out.append(f"4. {k}: {len(old)} rows before, {len(now.get(k, []))} now, "
                       f"{len(set(old) ^ set(now.get(k, [])))} differ")
    return out


# 5. Why those answers cannot change

def path_terms(p: object) -> list:
    if isinstance(p, (SequencePath, AlternativePath)):
        return [t for a in p.args for t in path_terms(a)]
    if isinstance(p, MulPath):
        return path_terms(p.path)
    if isinstance(p, InvPath):
        return path_terms(p.arg)
    if isinstance(p, NegatedPath):  # matches every predicate but those listed
        return [Variable("negated")]
    return [p]


def read_predicates(query: str) -> tuple[set[str], bool]:
    """The fixed predicates of a query's triple patterns, and whether any predicate is not fixed."""
    found: set[str] = set()
    variable = False

    def visit(node: object) -> None:
        nonlocal variable
        if getattr(node, "name", None) == "BGP":
            for _, p, _ in node.triples:
                for t in path_terms(p):
                    if isinstance(t, Variable):
                        variable = True
                    else:
                        found.add(ds.short(str(t)))

    traverse(prepareQuery(query).algebra, visitPost=visit)
    return found, variable


def check_queries(read: dict[str, tuple[set[str], bool]]) -> list[str]:
    return [f"5. {name}: " + ("a predicate is not fixed" if variable else f"reads {HAS_VERSION}")
            for name, (preds, variable) in read.items() if variable or HAS_VERSION in preds]


# 6. The nutrients that keep TACO's own URI

def taco_nutrients(endpoint: str) -> dict[str, int]:
    value = ds.LEVELS["nutritional value"].format(src=ds.TACO)
    return {r["nu"]: int(r["n"]) for r in ds.rows(
        endpoint, f"SELECT ?nu (COUNT(*) AS ?n) WHERE {{ {value} . ?x fio:hasNutrient ?nu }} GROUP BY ?nu")}


def nevo_labels(endpoint: str) -> list[str]:
    return [r["l"] for r in ds.rows(endpoint, "SELECT ?x ?l WHERE { ?x a fio:Nutrient ; rdfs:label ?l "
                                              f'FILTER STRSTARTS(STR(?x), "{NEVONUT}") }}')]


def without_nevo_code() -> set[str]:
    with nice.NUTRIENTS.open(encoding="utf-8", newline="") as fh:
        return {r["taco_nutrient"] for r in csv.DictReader(fh) if not r["nevo_code"]}


def check_own(own: dict[str, int], csv_own: set[str], labels: list[str]) -> tuple[list[str], list[dict]]:
    out, facts = [], []
    for key, values in sorted(own.items()):
        if key in ABSENT:
            matching = [label for label in labels if re.search(ABSENT[key], label, re.I)]
            facts.append({"key": key, "kind": 0, "matching": len(matching), "qualified": 0, "values": values})
            out += [f"6. {key}: NEVO has {matching}; TACO might use NEVO's code"] if matching else []
        elif key in QUALIFIED:
            pattern, qualifier = QUALIFIED[key]
            matching = [label for label in labels if re.search(pattern, label, re.I)]
            plain = [label for label in matching if not re.search(qualifier, label, re.I)]
            could = key in nd.COULD_TAKE  # TACO names the form; NEVO must have it, qualified
            facts.append({"key": key, "kind": 2 if could else 1, "matching": len(matching),
                          "qualified": len(matching) - len(plain), "values": values})
            if not matching or (could and len(plain) == len(matching)):
                out.append(f"6. {key}: no NEVO label matches with its qualifier; the rule does not describe NEVO")
            if plain and not could:
                out.append(f"6. {key}: NEVO has {plain} without the qualifier; TACO might use NEVO's code")
        else:
            out.append(f"6. {key}: no rule says why it keeps TACO's own URI")
    if set(own) != csv_own:
        out.append(f"6. own URIs in the graph and the alignment file differ: {sorted(set(own) ^ csv_own)}")
    return out, facts


# 7. Lean

def finset(ids: dict[str, int], terms: set[str]) -> str:
    return "{" + ", ".join(str(ids[t]) for t in sorted(terms, key=ids.get)) + "}"


def lean_text(ids: dict[str, int], props: dict, versions: dict[int, list], added: Counter, removed: Counter,
              read: dict[str, tuple[set[str], bool]], counts: tuple[list[int], list[int], list[bool]],
              own: list[dict], nevo_named: dict[str, int]) -> str:
    legend = "\n".join(f"  {i} {t}" for t, i in ids.items())
    pairs = [f"({n}, {len(vs)})" for n, vs in sorted(versions.items())]
    versions_text = ",\n  ".join(", ".join(pairs[i:i + 12]) for i in range(0, len(pairs), 12))
    query_preds = set().union(*(p for p, _ in read.values()))

    def by_property(c: Counter) -> str:
        return "[" + ", ".join(f"({ids[p]}, {n})" for p, n in sorted(c.items(), key=lambda kv: ids[kv[0]])) + "]"

    def b(x: bool) -> str:
        return "true" if x else "false"

    own_text = ",\n  ".join(f'{{ key := "{o["key"]}", kind := {o["kind"]}, matching := {o["matching"]}, '
                            f'qualified := {o["qualified"]}, values := {o["values"]} }}' for o in own)
    before, after, same = counts
    t, n = props["TACO"], props["NEVO"]
    return f"""import Mathlib.Data.Finset.Basic
import Mathlib.Data.Finset.Lattice.Lemmas

/-!
# TACO's NICE-Food export follows NEVO's pattern

Generated by verification/taco_nevo_alignment_check.py from Fuseki's nicefood dataset and the export file. Each
property is a number:
{legend}
-/

namespace TacoNevoAlignment

/-- A triple: subject, predicate and object, each a number. -/
abbrev Triple := Nat × Nat × Nat

/-- The triples a pattern with the fixed predicate `p` reads from a graph. -/
def reads (g : Finset Triple) (p : Nat) : Finset Triple := g.filter (fun t => t.2.1 = p)

/-- Triples whose predicate a pattern does not name cannot change what the pattern reads, in any graph. -/
theorem unread_triples_change_nothing (g a : Finset Triple) (p : Nat) (h : ∀ t ∈ a, t.2.1 ≠ p) :
    reads (g ∪ a) p = reads g p := by
  unfold reads
  have h0 : a.filter (fun t => t.2.1 = p) = ∅ := Finset.filter_eq_empty_iff.mpr (fun t ht => h t ht)
  rw [Finset.filter_union, h0, Finset.union_empty]

/-- If every added triple has the predicate `v` and a query names only other predicates, each pattern of the
query reads the same triples as before, so the query gives the same answers. -/
theorem queries_read_the_same (g a : Finset Triple) (ps : Finset Nat) (v : Nat)
    (hv : ∀ t ∈ a, t.2.1 = v) (hq : v ∉ ps) : ∀ p ∈ ps, reads (g ∪ a) p = reads g p := by
  intro p hp
  apply unread_triples_change_nothing
  intro t ht htp
  have hvp : v = p := (hv t ht).symm.trans htp
  exact hq (by rw [hvp]; exact hp)

/-! ## 1. Same properties -/

def hasVersion : Nat := {ids[HAS_VERSION]}
def nevoCodes : Finset Nat := {finset(ids, NEVO_CODES)}
def nevoFood : Finset Nat := {finset(ids, n["food item"])}
def tacoFood : Finset Nat := {finset(ids, t["food item"])}
def nevoValue : Finset Nat := {finset(ids, n["nutritional value"])}
def tacoValue : Finset Nat := {finset(ids, t["nutritional value"])}
def nevoMeasure : Finset Nat := {finset(ids, n["measure"])}
def tacoMeasure : Finset Nat := {finset(ids, t["measure"])}

theorem food_properties : nevoFood ⊆ tacoFood ∪ nevoCodes := by decide
theorem value_properties : nevoValue ⊆ tacoValue := by decide
theorem measure_properties : nevoMeasure ⊆ tacoMeasure := by decide
theorem only_nevo_codes_differ : nevoFood \\ tacoFood = nevoCodes := by decide
theorem version_on_both : hasVersion ∈ nevoFood ∩ tacoFood := by decide

/-! ## 2. One version per food: each TACO food number and how many versions it has in the file -/

def versions : List (Nat × Nat) := [
  {versions_text}]

theorem every_food_listed : versions.map Prod.fst = List.range' 1 {len(versions)} := by decide +kernel
theorem one_version_each : versions.all (fun v => v.2 == 1) = true := by decide +kernel

/-! ## 3. The export against the one published before, by property: triples added and removed -/

def added : List (Nat × Nat) := {by_property(added)}
def removed : List (Nat × Nat) := {by_property(removed)}

theorem only_versions_added : added.map Prod.fst = [hasVersion] := by decide
theorem one_added_per_food : (added.map Prod.snd).sum = versions.length := by decide +kernel
theorem nothing_removed : removed = [] := by decide

/-! ## 4 and 5. NICE-Food's queries: the predicates they name, and their rows before and after -/

def queryPredicates : Finset Nat := {finset(ids, query_preds)}
def rowsBefore : List Nat := {before}
def rowsAfter : List Nat := {after}
def sameRows : List Bool := [{", ".join(b(x) for x in same)}]

theorem queries_do_not_read_versions : hasVersion ∉ queryPredicates := by decide
theorem answers_cannot_change (g a : Finset Triple) (hv : ∀ t ∈ a, t.2.1 = hasVersion) :
    ∀ p ∈ queryPredicates, reads (g ∪ a) p = reads g p :=
  queries_read_the_same g a queryPredicates hasVersion hv queries_do_not_read_versions
theorem same_row_counts : rowsBefore = rowsAfter := by decide
theorem same_rows : sameRows.all id = true := by decide

/-! ## 6. TACO's nutrients that keep TACO's own URI -/

/-- Its kind (0: NEVO lacks it; 1: NEVO has it only split or qualified, and TACO does not say which form; 2: TACO
names a form NEVO has a code for), how many NEVO labels match it, how many of those carry the qualifier, and how
many TACO values name it. -/
structure Own where
  key : String
  kind : Nat
  matching : Nat
  qualified : Nat
  values : Nat

def own : List Own := [
  {own_text}]

def nevoNamed : Nat := {len(nevo_named)}
def nevoNamedValues : Nat := {sum(nevo_named.values())}

/-- What each kind requires of NEVO's labels. -/
def fits (o : Own) : Bool :=
  if o.kind == 0 then o.matching == 0
  else if o.kind == 1 then o.matching != 0 && o.qualified == o.matching
  else o.kind == 2 && o.qualified != 0

theorem own_count : own.length = {len(own)} := by decide
theorem why_own : own.all fits = true := by decide
theorem kinds : (own.filter (·.kind == 0)).length = {sum(o["kind"] == 0 for o in own)} ∧
    (own.filter (·.kind == 1)).length = {sum(o["kind"] == 1 for o in own)} ∧
    (own.filter (·.kind == 2)).length = {sum(o["kind"] == 2 for o in own)} := by decide
theorem values_add_up : nevoNamedValues + (own.map (·.values)).sum = {sum(nevo_named.values()) + sum(o["values"] for o in own)} := by decide

end TacoNevoAlignment
"""


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--endpoint", default=ds.ENDPOINT)
    p.add_argument("--baseline", type=Path, help="rows the queries gave before the change (JSON)")
    p.add_argument("--save-baseline", type=Path, help="write the rows the queries give now, and stop")
    p.add_argument("--lake-project", type=Path, default=ROOT / "verification" / "lean",
                   help="a Lake project with Mathlib built (default verification/lean)")
    p.add_argument("--no-lean", action="store_true", help="skip Lean and its mutants")
    args = p.parse_args()
    if args.save_baseline:
        args.save_baseline.parent.mkdir(parents=True, exist_ok=True)
        args.save_baseline.write_text(json.dumps(answers(args.endpoint), ensure_ascii=False), encoding="utf-8")
        print(f"wrote {args.save_baseline}")
        return 0
    problems: list[str] = []
    g = Graph().parse(EXPORT, format="turtle")

    props, from_file = fuseki_properties(args.endpoint), file_properties(g)
    found = check_properties(props, from_file)
    problems += found
    print(f"1. properties NEVO uses that TACO does not, but NEVO's food codes: {len(found)}; "
          f"only NEVO: {sorted(set().union(*props['NEVO'].values()) - set().union(*props['TACO'].values()))}")

    in_file = file_versions(g)
    per_food, forms = fuseki_versions(args.endpoint)
    found = check_versions(in_file, per_food, forms)
    problems += found
    print(f"2. foods with one version: {sum(len(v) == 1 for v in in_file.values())} of {len(in_file)} in the file, "
          f"{sum(n == 1 for n in per_food.values())} of {len(per_food)} in Fuseki; literal forms TACO "
          f"{forms.get(ds.TACO)}, NEVO {forms.get(ds.NEVO)}")

    before = published_before()
    added, removed = set(g) - set(before), set(before) - set(g)
    foods = taco_nodes(g)["food item"]
    found = check_diff(added, removed, foods)
    built = ROOT / "build" / "taco_nice_food.ttl"
    if built.is_file() and built.read_bytes() != EXPORT.read_bytes():
        found.append("3. build/taco_nice_food.ttl is not the file in docs/")
    problems += found
    added_by = Counter(ds.short(str(p)) for _, p, _ in added)
    removed_by = Counter(ds.short(str(p)) for _, p, _ in removed)
    print(f"3. against commit {BEFORE}: {len(before):,} -> {len(g):,} triples, added {dict(added_by)}, "
          f"removed {len(removed)}")

    now = answers(args.endpoint)
    base = json.loads(args.baseline.read_text(encoding="utf-8")) if args.baseline else None
    found = check_answers(now, base) if base else []
    problems += found
    keys = list(now)
    counts = ([len(base[k]) if base else len(now[k]) for k in keys], [len(now[k]) for k in keys],
              [sorted(tuple(r) for r in base[k]) == now[k] if base else True for k in keys])
    print("4. same rows as before: " + (f"{sum(counts[2])} of {len(keys)} queries "
                                         f"({', '.join(f'{k} {n}' for k, n in zip(keys, counts[1], strict=True))})"
                                         if base else "no --baseline given, not compared"))

    read = {name: read_predicates(q) for name, q in queries().items()}
    found = check_queries(read)
    problems += found
    print(f"5. queries reading {HAS_VERSION} or a predicate that is not fixed: {len(found)} of {len(read)}")

    names = taco_nutrients(args.endpoint)
    own = {u.rsplit("/", 1)[-1]: n for u, n in names.items() if not u.startswith(NEVONUT)}
    nevo_named = {u: n for u, n in names.items() if u.startswith(NEVONUT)}
    labels = nevo_labels(args.endpoint)
    found, facts = check_own(own, without_nevo_code(), labels)
    problems += found
    print(f"6. TACO nutrients: {len(nevo_named)} with NEVO's URI ({sum(nevo_named.values()):,} values), "
          f"{len(own)} with TACO's own ({sum(own.values()):,} values): "
          f"{sum(f['kind'] == 0 for f in facts)} NEVO lacks, {sum(f['kind'] == 1 for f in facts)} NEVO has only "
          f"split or qualified and TACO does not say which, {sum(f['kind'] == 2 for f in facts)} TACO names a form "
          f"NEVO has a code for (could take it); {len(found)} problems ({len(labels)} NEVO labels read)")

    mutants = [
        ("TACO without dcterms:hasVersion", lambda: check_properties(
            {**props, "TACO": {**props["TACO"], "food item": props["TACO"]["food item"] - {HAS_VERSION}}},
            {**from_file, "food item": from_file["food item"] - {HAS_VERSION}})),
        ("a food without its version", lambda: check_versions({**in_file, 1: []}, per_food, forms)),
        ("a value removed", lambda: check_diff(added, removed | {next(iter(before))}, foods)),
        ("a query reads the version", lambda: check_queries(
            {**read, "shared": (read["shared"][0] | {HAS_VERSION}, False)})),
        ("NEVO gets total monounsaturated fatty acids", lambda: check_own(
            own, without_nevo_code(), [*labels, "Fatty acids monounsaturated total"])[0]),
    ]
    if base:
        k = keys[0]
        mutants.append(("a row changed", lambda: check_answers(now, {**base, k: [["x", "y", "z"], *base[k][1:]]})))
    for name, run in mutants:
        if run():
            print(f"8. mutant '{name}': the check caught it")
        else:
            problems.append(f"8. mutant '{name}' was not caught")

    if not args.no_lean:
        terms = (set().union(*props["NEVO"].values(), *props["TACO"].values(), *(p for p, _ in read.values()))
                 | NEVO_CODES | {HAS_VERSION} | set(added_by) | set(removed_by))
        ids = {term: i for i, term in enumerate(sorted(terms))}
        state.write_lean(OUT, lean_text(ids, props, in_file, added_by, removed_by, read, counts, facts,
                                        nevo_named))
        print(f"7. wrote {OUT}; checking with Lean")
        if state.check_with_lean(OUT, args.lake_project):
            # Lean rejects every mutant of a file it rejects, so mutants of it would prove nothing.
            problems.append("7. Lean rejected the theorems; its mutants were not run")
        else:
            problems += state.mutants_rejected(OUT, args.lake_project, [
                ("a query names the version", r"(def queryPredicates : Finset Nat := \{)", rf"\g<1>{ids[HAS_VERSION]}, "),
                ("NEVO uses a property TACO lacks", r"(def nevoValue : Finset Nat := \{)", r"\g<1>999, "),
                ("a food without its version", r"\(1, 1\)", "(1, 0)"),
                ("a triple removed", r"def removed : List \(Nat × Nat\) := \[\]", "def removed : List (Nat × Nat) := [(0, 1)]"),
                ("a NEVO label without the qualifier", r"(kind := 1, matching := \d+, qualified := )\d+", r"\g<1>0"),
                ("a nutrient NEVO lacks found in NEVO", r"(kind := 0, matching := )0", r"\g<1>1"),
                ("a query gave another row count", r"(def rowsAfter : List Nat := \[)\d+", r"\g<1>9999"),
            ])
    for problem in problems:
        print(f"PROBLEM: {problem}")
    print("all checks passed" if not problems else f"{len(problems)} problems")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
