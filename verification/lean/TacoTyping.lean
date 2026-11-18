import Aesop
import Plausible
import Mathlib.Tactic.Linarith

/-!
# TACO-RDF's FoodOn typing policy, in Lean 4 with Mathlib

1. Why a class that FoodOn places under a whole organism or plant cannot be a food's type: `rdf:type` is
   inherited along `rdfs:subClassOf` (RDFS rule rdfs9), so along any chain of subclass edges.
2. Which alignment rows the build publishes as `rdf:type`: only `type` rows to a class of the pinned FoodOn
   release with no organism ancestor. No SKOS row (exact, close, narrow, broad, related) is ever published as a
   type.
3. Counting by a property splits a list in two, so typed plus untyped foods are all foods.

Each property is proved, and Plausible also tries random cases, as a test run beside the proof.
verification/taco_typing_state.py appends the 597 TACO foods to a copy of this file, with theorems stating the
counts claimed in the project's reports; the file checks only if every claim holds.
-/

namespace TacoTyping

/-! ## 1. Types are inherited along subclass chains -/

/-- A chain of subclass edges from class `a` to class `b` (reflexive and transitive closure). -/
inductive Reach (sub : Nat → Nat → Prop) : Nat → Nat → Prop
  | refl (a : Nat) : Reach sub a a
  | step {a b c : Nat} : sub a b → Reach sub b c → Reach sub a c

/-- If membership follows each subclass edge (rdfs9), it follows every chain of them. -/
theorem type_inherited {sub : Nat → Nat → Prop} {member : Nat → Nat → Prop}
    (rdfs9 : ∀ x c d, member x c → sub c d → member x d) :
    ∀ x c d, member x c → Reach sub c d → member x d := by
  intro x c d h r
  revert h
  induction r with
  | refl => intro h; exact h
  | step e _ ih => intro h; exact ih (rdfs9 _ _ _ h e)

/-- So typing a food with a class that has an organism among its ancestors makes the food an organism.
    This is why the build refuses such classes. -/
theorem organism_ancestor_makes_food_an_organism {sub : Nat → Nat → Prop} {member : Nat → Nat → Prop}
    (rdfs9 : ∀ x c d, member x c → sub c d → member x d) (food cls organism : Nat)
    (typed : member food cls) (chain : Reach sub cls organism) : member food organism :=
  type_inherited rdfs9 food cls organism typed chain

/-! ## 1b. Only such chains make a food an organism, so a type without one is safe -/

theorem reach_trans {sub : Nat → Nat → Prop} {a b c : Nat} (h1 : Reach sub a b) (h2 : Reach sub b c) :
    Reach sub a c := by
  revert h2
  induction h1 with
  | refl => intro h2; exact h2
  | step e _ ih => intro h2; exact Reach.step e (ih h2)

/-- What RDFS entails from the asserted types: a food is a member of every class an asserted class reaches. -/
def Entailed (sub asserted : Nat → Nat → Prop) (x d : Nat) : Prop :=
  ∃ c, asserted x c ∧ Reach sub c d

theorem entailed_contains_asserted (sub asserted : Nat → Nat → Prop) (x c : Nat) (h : asserted x c) :
    Entailed sub asserted x c :=
  ⟨c, h, Reach.refl c⟩

theorem entailed_follows_rdfs9 (sub asserted : Nat → Nat → Prop) (x c d : Nat)
    (h : Entailed sub asserted x c) (e : sub c d) : Entailed sub asserted x d := by
  obtain ⟨c0, hc0, r⟩ := h
  exact ⟨c0, hc0, reach_trans r (Reach.step e (Reach.refl d))⟩

/-- It is the least such membership: every membership that holds the asserted types and follows rdfs9
    contains it. So nothing else is entailed. -/
theorem entailed_least {sub asserted member : Nat → Nat → Prop}
    (base : ∀ x c, asserted x c → member x c) (rdfs9 : ∀ x c d, member x c → sub c d → member x d)
    (x d : Nat) (h : Entailed sub asserted x d) : member x d := by
  obtain ⟨c, hc, r⟩ := h
  exact type_inherited rdfs9 x c d (base x c hc) r

/-- Typing a food only with classes that reach no organism class keeps it from being entailed an organism:
    this is the fix, choosing a food class instead of the organism or plant class. -/
theorem not_organism_without_chain {sub asserted : Nat → Nat → Prop} (x organism : Nat)
    (h : ∀ c, asserted x c → ¬ Reach sub c organism) : ¬ Entailed sub asserted x organism := by
  rintro ⟨c, hc, r⟩
  exact h c hc r

/-- A food with no asserted type is entailed a member of no class at all. A SKOS link asserts no type,
    so queries that select foods by rdf:type and rdfs:subClassOf, as NICE-Food's do, cannot find it. -/
theorem no_class_without_type {sub asserted : Nat → Nat → Prop} (x : Nat) (h : ∀ c, ¬ asserted x c) :
    ∀ d, ¬ Entailed sub asserted x d := by
  rintro d ⟨c, hc, _⟩
  exact h c hc

/-! ## 2. What the build publishes as a type -/

inductive Relation
  | type | exact | close | narrow | broad | related
  deriving DecidableEq, Repr

/-- The six relations, numbered, so that Plausible can draw them at random. -/
def relation (k : Nat) : Relation :=
  match k % 6 with
  | 0 => .type | 1 => .exact | 2 => .close | 3 => .narrow | 4 => .broad | _ => .related

/-- The publication rule of docs/foodon-typing.md, for one alignment row. -/
def published (r : Relation) (pinned organismAncestor : Bool) : Bool :=
  decide (r = .type) && pinned && !organismAncestor

theorem published_only_type (r : Relation) (p o : Bool) (h : published r p o = true) : r = .type := by
  unfold published at h; aesop

theorem skos_never_published (r : Relation) (p o : Bool) (h : r ≠ .type) : published r p o = false := by
  unfold published; aesop

theorem published_never_organism (r : Relation) (p o : Bool) (h : published r p o = true) : o = false := by
  unfold published at h; aesop

theorem published_pinned (r : Relation) (p o : Bool) (h : published r p o = true) : p = true := by
  unfold published at h; aesop

/-! ## 3. Counting -/

theorem count_split {α : Type} (p : α → Bool) (l : List α) :
    (l.filter p).length + (l.filter (fun a => !p a)).length = l.length := by
  induction l with
  | nil => rfl
  | cons a t ih =>
    cases h : p a <;> simp [List.filter, h] <;> linarith

/-! ## 4. Agreement and kappa (round 2's scoring) -/

/-- How many positions two lists of decisions agree on. -/
def agreements : List Nat → List Nat → Nat
  | a :: as, b :: bs => (if a = b then 1 else 0) + agreements as bs
  | _, _ => 0

theorem agreements_symm : ∀ a b : List Nat, agreements a b = agreements b a
  | [], [] => rfl
  | [], _ :: _ => rfl
  | _ :: _, [] => rfl
  | x :: xs, y :: ys => by
    simp only [agreements]
    rw [agreements_symm xs ys]
    by_cases h : x = y
    · subst h; rfl
    · simp [h, Ne.symm h]

theorem agreements_le_length : ∀ a b : List Nat, agreements a b ≤ a.length
  | [], _ => by simp [agreements]
  | _ :: _, [] => by simp [agreements]
  | x :: xs, y :: ys => by
    have := agreements_le_length xs ys
    simp only [agreements, List.length_cons]
    split <;> omega

/-- Kappa over n decisions with A agreements and E = Σ_k a_k·b_k (counts per decision) is
    (n·A − E) / (n² − E). Its numerator never exceeds its denominator, so kappa is at most 1 ... -/
theorem kappa_at_most_one (n A E : Int) (hA : A ≤ n) (hn : 0 ≤ n) : n * A - E ≤ n * n - E := by
  have : n * A ≤ n * n := Int.mul_le_mul_of_nonneg_left hA hn
  linarith

/-- ... and it is 1 exactly when the reviewers agree on every food. -/
theorem kappa_one_iff (n A E : Int) (hn : 0 < n) : n * A - E = n * n - E ↔ A = n := by
  constructor
  · intro h
    have h2 : n * A = n * n := by linarith
    exact Int.eq_of_mul_eq_mul_left (Int.ne_of_gt hn) h2
  · intro h
    rw [h]

/-! ## Random tests with Plausible, beside the proofs -/

#eval Plausible.Testable.check (∀ (a b : List Nat), agreements a b = agreements b a)
#eval Plausible.Testable.check (∀ (a b : List Nat), agreements a b ≤ a.length)

#eval Plausible.Testable.check (∀ (k : Nat) (p o : Bool), published (relation k) p o = true → relation k = .type)
#eval Plausible.Testable.check (∀ (k : Nat) (p o : Bool), published (relation k) p o = true → o = false)
#eval Plausible.Testable.check (∀ (l : List Nat),
  (l.filter (· % 3 == 0)).length + (l.filter (fun a => !(a % 3 == 0))).length = l.length)

end TacoTyping
