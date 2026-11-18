"""How well TACO's typed foods suggest FoodOn types for NEVO's foods: the Brazilian table helping the Dutch.

scripts/nevo_foodon_candidates.py gives each NEVO food without a type the FoodOn type of its most similar
typed TACO food (by English name). This measures that suggestion:

1. Known answers: each of NICE-Food's typed NEVO foods gets the type of its most similar typed TACO food. How
   often is that one of the food's own types, or a parent or child of one in Fuseki's FoodOn?
2. NEVO's foods without a type: how many get a TACO suggestion, and how many of those the build could publish
   (a class of the pinned FoodOn release with no organism or whole-plant ancestor).

It writes build/nevo/foodon_pilot/taco_neighbours.json, with NEVO names, for `demo both`; build/ is ignored by
git, as NEVO's names may not be redistributed.

    $env:PYTHONPATH = "src"; python verification/nevo_from_taco_check.py
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "verification"))
import taco_typing_state as state  # noqa: E402

OBO = "http://purl.obolibrary.org/obo/"
OUT = ROOT / "build" / "nevo" / "foodon_pilot" / "taco_neighbours.json"


def load(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def ancestors(classes: set[str]) -> dict[str, set[str]]:
    """Each class's ancestors in Fuseki's FoodOn, the class itself included."""
    out = {c: {c} for c in classes}
    items = sorted(classes)
    for i in range(0, len(items), 100):
        values = " ".join(f"<{OBO}{c}>" for c in items[i:i + 100])
        for b in state.sparql("PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#> SELECT ?c ?a WHERE { "
                              f"VALUES ?c {{ {values} }} ?c rdfs:subClassOf* ?a . FILTER isIRI(?a) }}"):
            out[b["c"]["value"].removeprefix(OBO)].add(b["a"]["value"].removeprefix(OBO))
    return out


def main() -> int:
    nevo = load("nevo_foodon_candidates")
    foods = nevo.nevo_foods(state.ENDPOINT)
    taco = nevo.taco_typed()
    typed = [f for f in foods if f["classes"]]
    untyped = [f for f in foods if not f["classes"]]

    def suggestion(food: dict) -> tuple[float, dict] | None:
        found = nevo.neighbours(food["name_en"], taco, n=1)
        return found[0] if found else None

    known = [(f, s) for f in typed if (s := suggestion(f))]
    classes = {c for f, _ in known for c, _ in f["classes"]} | {s["classes"][0][0] for _, (_, s) in known}
    up = ancestors(classes)
    exact = near = 0
    for f, (_, s) in known:
        c, truth = s["classes"][0][0], {t for t, _ in f["classes"]}
        exact += c in truth
        near += any(c in up.get(t, {t}) or t in up.get(c, {c}) for t in truth)
    print(f"1. known answers: {len(typed)} typed NEVO foods; {len(known)} get a TACO suggestion; it is their "
          f"type for {exact} ({exact / len(known):.0%}), their type, a parent or a child for {near} "
          f"({near / len(known):.0%})")

    offered = [(f, s) for f in untyped if (s := suggestion(f))]
    targets = {s["classes"][0][0] for _, (_, s) in offered}
    pinned = state.pinned_release()
    blocked = {c.removeprefix(OBO) for c in state.with_organism_ancestor({OBO + c for c in targets})}
    usable = [(f, sc, s) for f, (sc, s) in offered
              if OBO + s["classes"][0][0] in pinned and s["classes"][0][0] not in blocked]
    print(f"2. untyped NEVO foods: {len(untyped)}; {len(offered)} get a TACO suggestion; {len(usable)} of "
          "them usable")
    examples = sorted(usable, key=lambda x: (-x[1], x[0]["name_en"]))[:8]
    for f, sc, s in examples:
        print(f"   {f['name_en']}  <-  TACO {s['name_en']}  ->  {s['classes'][0][1]} ({sc})")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({
        "typed": len(typed), "known_with_suggestion": len(known), "exact": exact, "near": near,
        "untyped": len(untyped), "offered": len(offered), "usable": len(usable),
        "examples": [{"nevo": f["name_en"], "taco": s["name_en"], "foodon": s["classes"][0][1], "score": sc}
                     for f, sc, s in examples]}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
