/-!
# Applying a confirmed type-only review

Core Lean only. These theorems concern the resolution and preservation rules,
not whether a nutritionist's chosen class describes the physical food correctly.
The independent Python checker appends separately read CSV/RDF data and checks
the resulting finite certificates with `decide +kernel`, never `native_decide`.
-/

namespace TypeReviewApplication

def resolve (first second : Nat) (adjudicated : Option Nat) : Option Nat :=
  match adjudicated with
  | some choice => some choice
  | none => if first = second then some first else none

theorem explicit_decision_wins (first second choice : Nat) :
    resolve first second (some choice) = some choice := rfl

theorem agreement_preserved (first second : Nat) (same : first = second) :
    resolve first second none = some first := by
  simp [resolve, same]

theorem disagreement_without_adjudication_rejected (first second : Nat)
    (different : first ≠ second) : resolve first second none = none := by
  simp [resolve, different]

theorem accepted_without_adjudication_is_original_agreement (first second choice : Nat)
    (accepted : resolve first second none = some choice) :
    first = second ∧ choice = first := by
  by_cases same : first = second
  · simp [resolve, same] at accepted
    exact ⟨same, by simpa only [same] using accepted.symm⟩
  · simp [resolve, same] at accepted

theorem accepted_disagreement_requires_adjudication (first second choice : Nat)
    (adjudicated : Option Nat) (different : first ≠ second)
    (accepted : resolve first second adjudicated = some choice) :
    adjudicated = some choice := by
  cases adjudicated with
  | none => simp [resolve, different] at accepted
  | some c => simpa [resolve] using accepted

structure SourceRow where
  food : Nat
  first : Nat
  second : Nat
  adjudicated : Option Nat
  deriving DecidableEq, Repr

def resolved (rows : List SourceRow) : List (Nat × Option Nat) :=
  rows.map fun row => (row.food, resolve row.first row.second row.adjudicated)

theorem resolution_preserves_keys (rows : List SourceRow) :
    (resolved rows).map Prod.fst = rows.map SourceRow.food := by
  simp [resolved, List.map_map]

inductive Reach (edge : Nat → Nat → Prop) : Nat → Nat → Prop
  | refl (a : Nat) : Reach edge a a
  | step {a b c : Nat} : edge a b → Reach edge b c → Reach edge a c

theorem a_closed_set_contains_every_reachable_class
    {edge : Nat → Nat → Prop} {safe : Nat → Prop}
    (closed : ∀ a b, safe a → edge a b → safe b) :
    ∀ a b, safe a → Reach edge a b → safe b := by
  intro a b start path
  induction path with
  | refl => exact start
  | step e _ ih => exact ih (closed _ _ start e)

theorem a_closed_set_excluding_a_root_cannot_reach_it
    {edge : Nat → Nat → Prop} {safe : Nat → Prop}
    (closed : ∀ a b, safe a → edge a b → safe b)
    (start root : Nat) (hasStart : safe start) (noRoot : ¬ safe root) :
    ¬ Reach edge start root := by
  intro path
  exact noRoot (a_closed_set_contains_every_reachable_class closed start root hasStart path)

end TypeReviewApplication

namespace TypeReviewCertificate

inductive Tree where
  | empty
  | node (left : Tree) (value : Nat) (right : Tree)

def values : Tree → List Nat
  | .empty => []
  | .node left value right => values left ++ [value] ++ values right

def contains (tree : Tree) (value : Nat) : Bool :=
  match tree with
  | .empty => false
  | .node left root right =>
    if value = root then true else if value < root then contains left value else contains right value

theorem contains_implies_membership (tree : Tree) (value : Nat)
    (found : contains tree value = true) : value ∈ values tree := by
  induction tree with
  | empty => simp [contains] at found
  | node left root right ihLeft ihRight =>
    simp only [contains] at found
    split at found
    · rename_i same
      simp [values, same]
    · split at found
      · simp [values, ihLeft found]
      · simp [values, ihRight found]

end TypeReviewCertificate
