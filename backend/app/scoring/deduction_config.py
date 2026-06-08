"""Deduction-model configuration for the Health Index (BRD §7, deduction refactor).

Every employee starts at 1000. Each domain subtracts up to its MAX_DEDUCTION
allowance, scaled by a penalty fraction in [0, 1] from that domain's clinical
formula (see formulas.py). Chronic disease subtracts a Charlson-weighted penalty.
A critical-value floor then caps severe cases.

All thresholds live here so the model is tunable without touching engine logic.
"""

from __future__ import annotations

import math

# Max deduction per domain (the "weight"); these MUST sum to 1000.
MAX_DEDUCTION = {
    "cardiovascular": 170,
    "glycaemic": 140,
    "chronic_disease": 200,
    "metabolic_syndrome": 90,
    "renal": 90,
    "haematology": 80,
    "hepatic": 80,
    "fitness": 60,
    "thyroid": 40,
    "inflammatory": 30,
    "nutrition": 20,
}
assert sum(MAX_DEDUCTION.values()) == 1000, "domain allowances must sum to 1000"

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
CHARLSON_CAP = 7.0   # burden at which the full chronic_disease allowance is deducted

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

# Product toggle (BRD note §8): if True, chronic disease becomes a multiplier on
# the (1000 - clinical_deductions) subtotal instead of a flat 200-point deduction.
# Left False by design; the chronic layer is an additive Charlson penalty.
CHRONIC_AS_MULTIPLIER = False


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
