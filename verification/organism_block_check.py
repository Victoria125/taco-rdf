"""Why the build refuses FoodOn classes with a whole organism or plant among their ancestors, checked three
ways, and how many of the foods it held back the step-1 candidates can still type.

1. Chains, checked by Lean: for every class marked blocked (in the step-1 sheet or the alignment inputs), a
   chain of rdfs:subClassOf edges from it to COB_0000022 (organism) or PO_0000003 (whole plant), found by
   search over the edges Fuseki's FoodOn gives. Lean checks each edge of each chain against the edge list,
   and verification/lean/TacoTyping.lean proves that such a chain makes a food typed with the class a member
   of the root, and that without one it never is.
2. A reasoner: owlrl computes the RDFS closure of the same edges plus one made-up food typed with each
   candidate class. The foods it then types as organism or whole plant must be exactly those typed with a
   blocked class.
3. Fuseki: the same question as a property path, rdfs:subClassOf*.

It also lists FoodOn's owl:disjointWith axioms on these classes and their ancestors, prints the chains of the
foods whose candidate FoodOn itself places under a plant, and counts the held-back foods that now have a
usable candidate.

    $env:PYTHONPATH = "src"; python verification/organism_block_check.py --lake-project C:/path/to/project
"""

from __future__ import annotations

import argparse
import csv
import sys
from collections import deque
from pathlib import Path

import owlrl
from rdflib import RDF, RDFS, Graph, Namespace, URIRef

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "verification"))
import taco_typing_state as state  # noqa: E402

SHEET = ROOT / "build" / "taco" / "foodon_round2" / "candidates.csv"
GAPS = ROOT / "analysis" / "data" / "foodon_typing_gaps.csv"
OUT = ROOT / "build" / "verification" / "OrganismChains.lean"
OBO = "http://purl.obolibrary.org/obo/"
ROOTS = ("COB_0000022", "PO_0000003")
EX = Namespace("urn:example:food/")
PREFIXES = ("PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#> "
            "PREFIX owl: <http://www.w3.org/2002/07/owl#> ")


def split(value: str) -> set[str]:
    return {c.strip().removeprefix(OBO) for c in value.replace("|", ";").split(";") if c.strip()}


def values(classes: set[str]) -> str:
    return " ".join(f"<{OBO}{c}>" for c in sorted(classes))


def subclass_edges(classes: set[str]) -> set[tuple[str, str]]:
    """Every rdfs:subClassOf edge between named classes above the given ones."""
    edges: set[tuple[str, str]] = set()
    items = sorted(classes)
    for i in range(0, len(items), 100):
        query = (f"{PREFIXES} SELECT DISTINCT ?a ?b WHERE {{ VALUES ?c {{ {values(set(items[i:i + 100]))} }} "
                 "?c rdfs:subClassOf* ?a . ?a rdfs:subClassOf ?b . FILTER (isIRI(?a) && isIRI(?b)) }")
        for b in state.sparql(query):
            edges.add((b["a"]["value"].removeprefix(OBO), b["b"]["value"].removeprefix(OBO)))
    return edges


def chain(start: str, up: dict[str, set[str]]) -> list[str] | None:
    """The shortest chain of edges from a class to a root, by breadth-first search."""
    seen = {start: [start]}
    queue = deque([start])
    while queue:
        node = queue.popleft()
        if node in ROOTS:
            return seen[node]
        for parent in sorted(up.get(node, ())):
            if parent not in seen:
                seen[parent] = [*seen[node], parent]
                queue.append(parent)
    return None


def reasoner(classes: set[str], edges: set[tuple[str, str]]) -> set[str]:
    """The classes whose made-up food the RDFS closure types as organism or whole plant."""
    g = Graph()
    for a, b in edges:
        g.add((URIRef(OBO + a), RDFS.subClassOf, URIRef(OBO + b)))
    for c in classes:
        g.add((EX[c], RDF.type, URIRef(OBO + c)))
    owlrl.DeductiveClosure(owlrl.RDFS_Semantics).expand(g)
    return {c for c in classes if any((EX[c], RDF.type, URIRef(OBO + r)) in g for r in ROOTS)}


def labels(classes: set[str]) -> dict[str, str]:
    query = (f"{PREFIXES} SELECT ?c (SAMPLE(?l) AS ?label) WHERE {{ VALUES ?c {{ {values(classes)} }} "
             "?c rdfs:label ?l } GROUP BY ?c")
    return {b["c"]["value"].removeprefix(OBO): b["label"]["value"] for b in state.sparql(query)}


def lean_data(ids: dict[str, int], edges: set[tuple[str, str]], chains: dict[str, list[str]],
              held_back: dict[int, bool], claims: dict[str, int]) -> str:
    edge_list = ", ".join(f"({ids[a]}, {ids[b]})" for a, b in sorted(edges))
    chain_list = ",\n  ".join("[" + ", ".join(str(ids[c]) for c in ch) + "]"
                              for _, ch in sorted(chains.items()))
    roots = ", ".join(str(ids[r]) for r in ROOTS if r in ids)
    fixed = ", ".join(f"({n}, {'true' if ok else 'false'})" for n, ok in sorted(held_back.items()))
    return f"""

/-! ## Chains from blocked classes to organism or whole plant (verification/organism_block_check.py) -/

namespace OrganismChains

set_option maxRecDepth 100000
set_option maxHeartbeats 0

/-- FoodOn's rdfs:subClassOf edges above the candidate classes, classes numbered. -/
def edges : List (Prod Nat Nat) := [{edge_list}]

def roots : List Nat := [{roots}]

/-- Each step of a chain must be an edge of FoodOn. -/
def steps : List Nat → Bool
  | a :: b :: t => edges.contains (a, b) && steps (b :: t)
  | _ => true

def chains : List (List Nat) := [
  {chain_list}]

theorem every_chain_is_made_of_foodon_edges : chains.all steps = true := by decide +kernel

theorem every_chain_ends_at_organism_or_whole_plant :
    chains.all (fun ch => match ch.getLast? with | some r => roots.contains r | none => false) = true := by
  decide +kernel

theorem n_blocked_classes : chains.length = {claims['blocked']} := by decide

/-- The foods whose historical candidates are all blocked, and whether step 1 found a usable class. -/
def heldBack : List (Prod Nat Bool) := [{fixed}]

theorem n_held_back : heldBack.length = {claims['held_back']} := by decide
theorem n_now_usable : (heldBack.filter (·.2)).length = {claims['now_usable']} := by decide

end OrganismChains
"""


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--lake-project", type=Path, default=ROOT / "verification" / "lean",
                   help="a Lake project with Mathlib built (default verification/lean)")
    p.add_argument("--no-mutants", action="store_true", help="skip the mutation tests of the Lean file")
    args = p.parse_args()
    with SHEET.open(encoding="utf-8-sig") as fh:
        sheet = {int(r["food_number"]): r for r in csv.DictReader(fh, delimiter=";")}
    with GAPS.open(encoding="utf-8") as fh:
        gaps = list(csv.DictReader(fh))
    blocked = set().union(*(split(r["blocked_classes"]) for r in sheet.values()))
    for g in gaps:
        iris = [c.strip() for c in g["candidate_iri"].split(" | ") if c.strip()]
        whys = g["candidate_obstacle"].split(" | ")
        for i, iri in enumerate(iris):
            if i < len(whys) and whys[i] in ("organism_class", "foodon_axiom_conflict"):
                blocked.add(iri.removeprefix(OBO))
    usable = set().union(*(split(r["usable_classes"]) for r in sheet.values()))
    classes = blocked | usable
    problems = []

    edges = subclass_edges(classes)
    up: dict[str, set[str]] = {}
    for a, b in edges:
        up.setdefault(a, set()).add(b)
    chains = {c: ch for c in sorted(classes) if (ch := chain(c, up))}
    by_fuseki = state.with_organism_ancestor({OBO + c for c in classes})
    found = {"chain search": set(chains), "owlrl reasoner": reasoner(classes, edges),
             "Fuseki path": {c.removeprefix(OBO) for c in by_fuseki}}
    print(f"{len(classes)} candidate classes ({len(blocked)} marked blocked, {len(usable)} usable); "
          f"{len(edges)} FoodOn subclass edges above them")
    print("  reach organism or whole plant by: " + ", ".join(f"{k} {len(v)}" for k, v in found.items()))
    for name, s in found.items():
        if s != blocked:
            problems.append(f"{name} differs from the blocked marks: extra {sorted(s - blocked)[:5]}, "
                            f"missing {sorted(blocked - s)[:5]}")

    nodes = {n for e in edges for n in e}
    disjoint = state.sparql(f"{PREFIXES} SELECT ?a ?b WHERE {{ VALUES ?a {{ {values(nodes)} }} "
                            "{ ?a owl:disjointWith ?b } UNION { ?b owl:disjointWith ?a } }")
    print(f"  owl:disjointWith axioms on these classes or their ancestors: {len(disjoint)}")
    disjoint_classes = {b[k]["value"].removeprefix(OBO) for b in disjoint for k in ("a", "b")}
    names = labels(disjoint_classes) if disjoint_classes else {}
    for b in disjoint:
        a, c = (b[k]["value"].removeprefix(OBO) for k in ("a", "b"))
        print(f"    {names.get(a, a)} disjoint with {names.get(c, c)}")

    conflicts = [g for g in gaps if "foodon_axiom_conflict" in g["candidate_obstacle"]]
    names = labels({x for g in conflicts for c in split(g["candidate_iri"]) for x in chains.get(c, [c])})
    print("  foods whose candidate FoodOn itself places under a plant:")
    for g in conflicts:
        for c in split(g["candidate_iri"]):
            if c in chains:
                path = " is_a ".join(names.get(x, x) for x in chains[c])
                print(f"    {g['food_number']} {g['name_pt']}: {path}")

    held = {int(g["food_number"]) for g in gaps
            if g["candidate_iri"] and split(g["candidate_iri"]) <= blocked}
    held_back = {n: bool(split(sheet[n]["usable_classes"])) for n in held}
    print(f"  held-back foods (every historical candidate blocked): {len(held_back)}; "
          f"with a usable candidate after step 1: {sum(held_back.values())}")

    ids = {c: i for i, c in enumerate(sorted(nodes | classes | set(ROOTS)))}
    claims = {"blocked": 86, "held_back": 35, "now_usable": 28}
    blocked_chains = {c: chains[c] for c in blocked if c in chains}
    base = (ROOT / "verification" / "lean" / "TacoTyping.lean").read_text(encoding="utf-8")
    state.write_lean(OUT, base + lean_data(ids, edges, blocked_chains, held_back, claims))
    print(f"wrote {OUT}; checking with Lean")
    code = state.check_with_lean(OUT, args.lake_project)
    if not args.no_mutants:
        start = min(blocked_chains)
        problems += state.mutants_rejected(OUT, args.lake_project, [
            ("a step that is no FoodOn edge", r"(def chains : List \(List Nat\) := \[\r?\n  \[)",
             rf"\g<1>{ids[start]}, ")])
    for problem in problems:
        print(f"PROBLEM: {problem}")
    return 1 if problems or code else 0


if __name__ == "__main__":
    sys.exit(main())
