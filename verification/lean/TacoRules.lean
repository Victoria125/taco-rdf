/-
  The numeric rules of TACO-RDF's Python code, written again in Lean 4 and proved.

  Values are integers counting millionths of their unit, since TACO's values have at most six decimals:
  2.6 g is 2600000. Each definition names the Python function it models. verification/differential.py runs
  this model and the Python code on the same cases, so that what is proved here is known to hold for the
  code too, case by case.

  Core Lean only, no Mathlib. The arithmetic goals are closed by `omega`, Lean's decision procedure for
  linear integer arithmetic.
-/

namespace TacoRules

/-- One unit (g or mg), in millionths. -/
def S : Int := 1000000

/-- The absolute value, written out so that `omega` can reason about it case by case. -/
def iabs (x : Int) : Int := if x < 0 then -x else x

theorem iabs_nonneg (x : Int) : 0 ≤ iabs x := by
  unfold iabs; split <;> omega

theorem iabs_sub_comm (x y : Int) : iabs (x - y) = iabs (y - x) := by
  unfold iabs; split <;> split <;> omega

/-! ## Available carbohydrate: scripts/taco_to_nice_food.py, `available_carbohydrate`

TACO's carbohydrate is total carbohydrate by difference, fibre included. The export derives available
carbohydrate from it: carbohydrate minus fibre where fibre has a number; the total where fibre is not
applicable or a trace; nothing where fibre has no number; and zero where the result is below zero. -/

inductive Fibre where
  | measured (amount : Int)
  | notApplicable
  | trace
  | noNumber
  deriving Repr, DecidableEq

def availableCarbohydrate (total : Int) : Fibre → Option Int
  | .measured f => some (if total - f < 0 then 0 else total - f)
  | .notApplicable => some (if total < 0 then 0 else total)
  | .trace => some (if total < 0 then 0 else total)
  | .noNumber => none

/-- The derived value is never negative. -/
theorem available_nonneg (t v : Int) (f : Fibre) (h : availableCarbohydrate t f = some v) : 0 ≤ v := by
  cases f with
  | measured g => simp only [availableCarbohydrate, Option.some.injEq] at h; split at h <;> omega
  | notApplicable => simp only [availableCarbohydrate, Option.some.injEq] at h; split at h <;> omega
  | trace => simp only [availableCarbohydrate, Option.some.injEq] at h; split at h <;> omega
  | noNumber => simp [availableCarbohydrate] at h

/-- With fibre zero or more, available carbohydrate never exceeds total carbohydrate (or zero). -/
theorem available_le_total (t g v : Int) (hg : 0 ≤ g)
    (h : availableCarbohydrate t (.measured g) = some v) : v ≤ (if t < 0 then 0 else t) := by
  simp only [availableCarbohydrate, Option.some.injEq] at h
  split at h <;> split <;> omega

/-- Where fibre is at most the total, nothing is lost: available plus fibre is the total. -/
theorem available_add_fibre (t g : Int) (h1 : g ≤ t) :
    availableCarbohydrate t (.measured g) = some (t - g) := by
  simp only [availableCarbohydrate, Option.some.injEq]
  split <;> omega

/-- Fibre above the total (pequi, lupin in brine and five more TACO foods) gives zero. -/
theorem available_zero_when_fibre_exceeds (t g : Int) (h : t < g) :
    availableCarbohydrate t (.measured g) = some 0 := by
  simp only [availableCarbohydrate, Option.some.injEq]
  split <;> omega

/-- A slightly negative total without fibre (four TACO fish and meats) gives zero. -/
theorem available_zero_when_total_negative (t : Int) (h : t < 0) :
    availableCarbohydrate t .notApplicable = some 0 ∧ availableCarbohydrate t .trace = some 0 := by
  simp only [availableCarbohydrate, Option.some.injEq]
  constructor <;> split <;> omega

/-- A value is derived exactly when fibre has a number, is not applicable or is a trace. -/
theorem available_none_iff (t : Int) (f : Fibre) : availableCarbohydrate t f = none ↔ f = .noNumber := by
  cases f <;> simp [availableCarbohydrate]

/-! ## EU labelling tolerances: scripts/compare_taco_nevo.py, `within_eu_tolerance`

From the European Commission's guidance of December 2012, around TACO's value `t`; NEVO's value is `n`.
20 % is written `5 * |n - t| ≤ t`, which equals `|n - t| ≤ 0.2 * t` exactly. -/

/-- Protein, available carbohydrate and dietary fibre, in g: ±2 g below 10 g, ±20 % from 10 to 40 g, ±8 g
above 40 g. -/
def withinMacro (t n : Int) : Bool :=
  if t < 10 * S then decide (iabs (n - t) ≤ 2 * S)
  else if t ≤ 40 * S then decide (5 * iabs (n - t) ≤ t)
  else decide (iabs (n - t) ≤ 8 * S)

/-- Five times the half-width of the macronutrient tolerance at `t`. -/
def macroWidth5 (t : Int) : Int :=
  if t < 10 * S then 10 * S else if t ≤ 40 * S then t else 40 * S

/-- The three cases are one band: within the tolerance iff five times the gap is at most `macroWidth5`. -/
theorem withinMacro_iff (t n : Int) : withinMacro t n = true ↔ 5 * iabs (n - t) ≤ macroWidth5 t := by
  unfold withinMacro macroWidth5
  split
  · simp only [decide_eq_true_eq]; omega
  · split
    · simp only [decide_eq_true_eq]
    · simp only [decide_eq_true_eq]; omega

/-- The band never narrows as TACO's value grows: no gap or jump at 10 g or at 40 g. -/
theorem macroWidth5_mono (a b : Int) (h : a ≤ b) : macroWidth5 a ≤ macroWidth5 b := by
  unfold macroWidth5 S
  split <;> split <;> (try split) <;> (try split) <;> omega

/-- A value is always within its own tolerance. -/
theorem withinMacro_self (t : Int) : withinMacro t t = true := by
  rw [withinMacro_iff]
  unfold macroWidth5 iabs S
  simp only [Int.sub_self]
  split <;> (try split) <;> omega

/-- Saturated, monounsaturated and polyunsaturated fatty acids, in g: ±0.8 g below 4 g, ±20 % from 4 g. -/
def withinFattyAcid (t n : Int) : Bool :=
  if t < 4 * S then decide (5 * iabs (n - t) ≤ 4 * S) else decide (5 * iabs (n - t) ≤ t)

def fattyAcidWidth5 (t : Int) : Int := if t < 4 * S then 4 * S else t

theorem withinFattyAcid_iff (t n : Int) :
    withinFattyAcid t n = true ↔ 5 * iabs (n - t) ≤ fattyAcidWidth5 t := by
  unfold withinFattyAcid fattyAcidWidth5
  split <;> simp only [decide_eq_true_eq]

theorem fattyAcidWidth5_mono (a b : Int) (h : a ≤ b) : fattyAcidWidth5 a ≤ fattyAcidWidth5 b := by
  unfold fattyAcidWidth5 S
  split <;> split <;> omega

/-- Sodium, in mg: ±150 mg below 500 mg, ±20 % from 500 mg (the guidance's salt rule, sodium = salt / 2.5). -/
def withinSodium (t n : Int) : Bool :=
  if t < 500 * S then decide (iabs (n - t) ≤ 150 * S) else decide (5 * iabs (n - t) ≤ t)

/-- Unlike the others, the sodium band narrows at 500 mg, from ±150 mg to ±100 mg. This is in the guidance's
own table, which the code copies: a NEVO value 120 mg away is within the tolerance at 499 mg and not at 500 mg. -/
theorem sodium_band_narrows :
    withinSodium (499 * S) (619 * S) = true ∧ withinSodium (500 * S) (620 * S) = false := by
  unfold withinSodium iabs S
  decide

/-- Calcium, magnesium, phosphorus, potassium, copper, iron and zinc: from −35 % to +45 %. -/
def withinMineral (t n : Int) : Bool := decide (65 * t ≤ 100 * n ∧ 100 * n ≤ 145 * t)

/-- Riboflavin, niacin, vitamin B6, vitamin C and retinol: from −35 % to +50 %. -/
def withinVitamin (t n : Int) : Bool := decide (65 * t ≤ 100 * n ∧ 100 * n ≤ 150 * t)

theorem withinMineral_self (t : Int) (h : 0 ≤ t) : withinMineral t t = true := by
  unfold withinMineral; simp only [decide_eq_true_eq]; omega

theorem withinVitamin_self (t : Int) (h : 0 ≤ t) : withinVitamin t t = true := by
  unfold withinVitamin; simp only [decide_eq_true_eq]; omega

/-! ## Within 20 %: scripts/compare_taco_nevo.py, `within_20_percent` -/

/-- `|t - n| ≤ 0.2 * max(|t|, |n|)`. -/
def within20 (t n : Int) : Bool :=
  decide (5 * iabs (t - n) ≤ (if iabs t ≤ iabs n then iabs n else iabs t))

/-- It does not matter which table comes first. -/
theorem within20_symm (t n : Int) : within20 t n = within20 n t := by
  unfold within20
  rw [iabs_sub_comm t n]
  have := iabs_nonneg t; have := iabs_nonneg n
  by_cases h1 : iabs t ≤ iabs n <;> by_cases h2 : iabs n ≤ iabs t <;> simp [h1, h2] <;> omega

theorem within20_self (t : Int) : within20 t t = true := by
  unfold within20
  have := iabs_nonneg t
  simp only [Int.sub_self, decide_eq_true_eq]
  unfold iabs; split <;> split <;> omega

/-! ## The composition check: scripts/check_food_pairs.py, `disagreeing` -/

/-- Water: the two values differ by more than 15 g per 100 g. -/
def waterDisagrees (a b : Int) : Bool := decide (15 * S < iabs (a - b))

theorem waterDisagrees_symm (a b : Int) : waterDisagrees a b = waterDisagrees b a := by
  unfold waterDisagrees; rw [iabs_sub_comm]

/-- A mineral: the higher value is above the trace floor, and the lower is zero or at most a third of it.
The code's `high / low >= 3` is written `3 * low ≤ high`, the same for `low > 0` in exact arithmetic. -/
def mineralDisagrees (trace a b : Int) : Bool :=
  let lo := if a ≤ b then a else b
  let hi := if a ≤ b then b else a
  decide (trace < hi) && (decide (lo = 0) || decide (3 * lo ≤ hi))

/-- It does not matter which table comes first. -/
theorem mineralDisagrees_symm (tr a b : Int) : mineralDisagrees tr a b = mineralDisagrees tr b a := by
  unfold mineralDisagrees
  by_cases h1 : a ≤ b <;> by_cases h2 : b ≤ a <;> simp [h1, h2]
  · have : a = b := by omega
    subst this; rfl
  · exfalso; omega

/-- Two equal values never disagree. -/
theorem mineralDisagrees_self (tr a : Int) (htr : 0 ≤ tr) (ha : 0 ≤ a) : mineralDisagrees tr a a = false := by
  unfold mineralDisagrees
  simp only [Int.le_refl, ite_true, Bool.and_eq_false_iff, decide_eq_false_iff_not, Bool.or_eq_false_iff]
  by_cases h : tr < a
  · right; constructor <;> omega
  · left; exact h

end TacoRules
