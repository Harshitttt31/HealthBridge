"""Deduction-model configuration for the Health Index (BRD §7).

Two compounding mechanisms on top of the plain additive model:

Mechanism 1 — Cross-domain amplification (measured, linked systems)
  When an anchor condition is present it amplifies the penalty fraction of
  clinically-linked domains that don't already take that condition as a formula
  input (to avoid double-counting).  A = 1 + Σ(bonuses), capped at AMPLIFIER_CAP.
  New fraction = min(1.0, base_fraction × A).  A diabetic with pristine kidneys
  (renal fraction 0) loses nothing extra — correct.

Mechanism 2 — Complication-weighted chronic burden (unmeasured systems)
  B = Σ[Charlson_weight × control_modifier] + synergy
  control_modifier (diabetes): HbA1c <7 → 1.0 · 7–9 → 1.3 · ≥9 → 1.6
  synergy = 0.5 × max(0, n_anchor_conditions − 1)
  chronic_deduction = 200 × min(B / 7, 1)
  Captures neuropathy, retinopathy, MSK and infection risk that the 72-parameter
  panel cannot directly measure.

All thresholds live here so the model is tunable without touching engine logic.
"""

from __future__ import annotations

import math

# Max deduction per clinical domain; MUST sum to 800.
# The remaining 200 is reserved for the chronic-burden term (always separate).
MAX_DEDUCTION = {
    "cardiovascular": 170,
    "glycaemic": 140,
    "metabolic_syndrome": 90,
    "renal": 90,
    "haematology": 80,
    "hepatic": 80,
    "fitness": 60,
    "thyroid": 40,
    "inflammatory": 30,
    "nutrition": 20,
}
assert sum(MAX_DEDUCTION.values()) == 800, "clinical domain allowances must sum to 800"

# Fixed allowance for the complication-weighted chronic burden term.
CHRONIC_MAX_DEDUCTION = 200

# Penalty-fraction bands. Each maps a formula output to a fraction in [0, 1].
# List form: ordered (upper_threshold_exclusive, fraction); last entry uses inf.
# Dict form: categorical label -> fraction.
BANDS = {
    "cardiovascular_ascvd_pct": [(5, 0.0), (7.5, 0.25), (15, 0.55), (20, 0.80), (math.inf, 1.0)],
    "glycaemic_hba1c":          [(5.7, 0.0), (6.5, 0.35), (7.5, 0.65), (9.0, 0.85), (math.inf, 1.0)],
    # eGFR is mapped to a CKD stage first (higher eGFR is better), then to a fraction.
    "renal_stage":              {"G1": 0.0, "G2": 0.15, "G3a": 0.45, "G3b": 0.70, "G4": 0.90, "G5": 1.0},
    "hepatic_fib4":             [(1.30, 0.0), (2.67, 0.5), (math.inf, 1.0)],
    "metsyn_components":        {0: 0.0, 1: 0.15, 2: 0.35, 3: 0.60, 4: 0.80, 5: 1.0},
    "haematology_anaemia":      {"normal": 0.0, "mild": 0.40, "moderate": 0.70, "severe": 1.0},
    "fitness_vo2_cat":          {"excellent": 0.0, "good": 0.20, "fair": 0.50, "poor": 0.80, "very_poor": 1.0},
    "thyroid_tsh":              {"euthyroid": 0.0, "subclinical": 0.50, "overt": 1.0},
    "inflammatory_crp":         [(1.0, 0.0), (3.0, 0.40), (10.0, 0.80), (math.inf, 1.0)],
    "nutrition_status":         {"sufficient": 0.0, "insufficient": 0.50, "deficient": 1.0},
}

# Charlson comorbidity weights for the chronic_disease column.
CHARLSON = {
    "Chronic Kidney Disease": 3.0, "Type 2 Diabetes": 2.0, "Fatty Liver (NAFLD)": 2.0,
    "Hypertension": 1.5, "Hyperthyroidism": 1.5, "Obesity": 1.5,
    "Dyslipidaemia": 1.0, "Hypothyroidism": 1.0, "Anaemia": 1.0, "Hyperuricaemia": 0.5,
}
CHARLSON_CAP = 7.0  # burden at which the full chronic_disease allowance is deducted

# Control modifier for complication risk (Mechanism 2).
# HbA1c brackets → multiplier on Charlson weight for Type 2 Diabetes.
DIABETES_CONTROL_MODIFIER = [
    (7.0, 1.0),   # HbA1c < 7  → well-controlled
    (9.0, 1.3),   # HbA1c 7–9 → suboptimal
    (float("inf"), 1.6),  # HbA1c ≥ 9 → poor control
]

# Synergy bonus per additional anchor condition beyond the first.
SYNERGY_PER_EXTRA_ANCHOR = 0.5

# Cross-domain amplification matrix (Mechanism 1).
# anchor_condition -> {domain: bonus}
# Rule: only amplify links the domain formula does NOT already contain.
# ASCVD takes diabetes, BP, and lipids as inputs → cardiovascular not amplified
# for Diabetes/Hypertension/Dyslipidaemia. CKD-EPI uses only creatinine; FIB-4
# uses only liver enzymes — neither "knows" the patient is diabetic, so legitimate.
AMPLIFICATION_MATRIX = {
    "Type 2 Diabetes":     {"renal": 0.40, "hepatic": 0.25},
    "Hypertension":        {"renal": 0.30},
    "Chronic Kidney Disease": {"cardiovascular": 0.40},
    "Obesity":             {"hepatic": 0.25},
    "Fatty Liver (NAFLD)": {"cardiovascular": 0.15},
}

# Anchor conditions (used for synergy count).
ANCHOR_CONDITIONS = frozenset(AMPLIFICATION_MATRIX.keys())

# Maximum amplifier A = 1 + Σ(bonuses) allowed per domain.
AMPLIFIER_CAP = 1.6

# Critical thresholds -> final score capped at CRITICAL_CAP if any breached.
CRITICAL = {
    "creatinine_mg_dl": (">", 5.0),
    "fbs_mg_dl":        (">", 300.0),
    "haemoglobin_g_dl": ("<", 7.0),
    "egfr":             ("<", 15.0),   # computed (CKD-EPI), not a raw column
    "qtcb_ms":          (">", 500.0),
}
CRITICAL_CAP = 300

# Score -> band label (ordered high to low; first threshold met wins).
BAND_LABELS = [(800, "Excellent"), (650, "Good"), (500, "Fair"), (350, "Poor"), (0, "Critical")]



def band_fraction(value, table) -> float:
    """Map a numeric `value` to a fraction via an ordered band list.

    `table` is [(upper_exclusive, fraction), ...] with a final inf entry.
    Missing/NaN values contribute no penalty (fraction 0.0).
    """
    if value is None or value != value:  # None or NaN
        return 0.0
    for upper, frac in table:
        if value < upper:
            return frac
    return table[-1][1]
