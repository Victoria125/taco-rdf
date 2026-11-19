/-!
# Exact-value QUDT -> NICE-Food OM bridge: what can and cannot be proved

This is a *model* of the six entries in src/taco_rdf/nice_food.py:UNITS,
not a proof that FoodOn or CDNO annotations are scientifically right.
The Python regression checks the correspondence between these constructors,
the production dictionary, the generated RDF, and SHACL constraints.

This file deliberately avoids Mathlib and has no admitted proofs.
-/

namespace TacoUnitBridge

inductive SourceUnit where
  | gram | percent | milligram | microgram | kilocalorie | kilojoule
  deriving DecidableEq, Repr

inductive NiceUnit where
  | gramPerHectogram | milligramPerHectogram
  | microgramTextOnly
  | kilocaloriePerHectogram | kilojoulePerHectogram
  deriving DecidableEq, Repr

/-- This is exactly the unit dictionary currently used by TACO-RDF's NICE-Food export. -/
def convertUnit : SourceUnit → NiceUnit
  | .gram => .gramPerHectogram
  | .percent => .gramPerHectogram
  | .milligram => .milligramPerHectogram
  | .microgram => .microgramTextOnly
  | .kilocalorie => .kilocaloriePerHectogram
  | .kilojoule => .kilojoulePerHectogram

/-- The source distinguishes gram from percent, but the export unit does not. -/
theorem gram_percent_same_target :
    convertUnit .gram = convertUnit .percent := rfl

theorem gram_percent_distinct :
    SourceUnit.gram ≠ SourceUnit.percent := by decide

/-- Consequently a generic, lossless left inverse from OM units is impossible. -/
theorem convertUnit_not_injective :
    ¬ Function.Injective convertUnit := by
  intro h
  have impossible : SourceUnit.gram = SourceUnit.percent := h gram_percent_same_target
  exact gram_percent_distinct impossible

theorem no_lossless_unit_inverse :
    ¬ ∃ inv : NiceUnit → SourceUnit, ∀ u : SourceUnit, inv (convertUnit u) = u := by
  intro h
  obtain ⟨inv, rightInverse⟩ := h
  have g := rightInverse SourceUnit.gram
  have p := rightInverse SourceUnit.percent
  have impossible : SourceUnit.gram = SourceUnit.percent := by
    calc
      SourceUnit.gram = inv (convertUnit SourceUnit.gram) := g.symm
      _ = inv (convertUnit SourceUnit.percent) := by rw [gram_percent_same_target]
      _ = SourceUnit.percent := p
  exact gram_percent_distinct impossible

/-- Whether the current exporter writes an OM unit IRI; for µg it writes only a string. -/
def hasOmUnitIri : NiceUnit → Bool
  | .microgramTextOnly => false
  | _ => true

theorem microgram_iri_is_missing :
    hasOmUnitIri (convertUnit .microgram) = false := rfl

theorem gram_has_unit_iri :
    hasOmUnitIri (convertUnit .gram) = true := rfl

/-- An abstract status-aware cell. α can be an exact decimal, rational, or other value type. -/
inductive SourceCell (α : Type) where
  | measured (value : α) (unit : SourceUnit)
  | trace | notApplicable | underReevaluation

/-- Export preserves the exact *value* for measured cells and emits no number for status cells. -/
def exportCell {α : Type} : SourceCell α → Option (α × NiceUnit)
  | .measured v u => some (v, convertUnit u)
  | .trace => none
  | .notApplicable => none
  | .underReevaluation => none

theorem measured_value_is_unchanged {α : Type} (v : α) (u : SourceUnit) :
    exportCell (.measured v u) = some (v, convertUnit u) := rfl

theorem trace_has_no_number {α : Type} :
    exportCell (SourceCell.trace : SourceCell α) = none := rfl

theorem not_applicable_has_no_number {α : Type} :
    exportCell (SourceCell.notApplicable : SourceCell α) = none := rfl

theorem under_reevaluation_has_no_number {α : Type} :
    exportCell (SourceCell.underReevaluation : SourceCell α) = none := rfl

end TacoUnitBridge
