"""Health Index engine — formula (BRD §7):

    Health Index = 1000
      − Σ ( domain_max_deduction × min(1.0, base_fraction × amplifier) )
      − [ 200 × min(B / 7, 1) ]   ← complication-weighted Charlson burden
    then critical-value floor, clamp [0, 1000]

Clinical domains (Σ, sum to 800):
  cardiovascular, glycaemic, metabolic_syndrome, renal, haematology,
  hepatic, fitness, thyroid, inflammatory, nutrition.

Each domain function returns either:
  • a plain float (base_fraction)
  • a dict with keys: fraction (float), amplifier (float, default 1.0),
    and optionally egfr (float).

Chronic burden is separate: formulas.chronic_burden_score(row) → raw
Charlson sum B; engine applies 200 × min(B / 7, 1).

Public API:
  compute_health_index(row) -> dict   (per-employee detail)
  score_dataframe(df)       -> DataFrame
"""

from __future__ import annotations

import pandas as pd

from . import formulas
from .deduction_config import (
    BAND_LABELS, CHARLSON_CAP, CHRONIC_MAX_DEDUCTION,
    CRITICAL, CRITICAL_CAP, MAX_DEDUCTION,
)

# Clinical domain functions only — chronic burden is handled separately.
DOMAIN_FUNCS = {
    "cardiovascular":    formulas.cardiovascular,
    "glycaemic":         formulas.glycaemic,
    "metabolic_syndrome": formulas.metabolic_syndrome,
    "renal":             formulas.renal,   # also returns egfr
    "haematology":       formulas.haematology,
    "hepatic":           formulas.hepatic,
    "fitness":           formulas.fitness,
    "thyroid":           formulas.thyroid,
    "inflammatory":      formulas.inflammatory,
    "nutrition":         formulas.nutrition,
}


def _breaches_critical(row, egfr) -> bool:
    for col, (op, thr) in CRITICAL.items():
        val = egfr if col == "egfr" else formulas._num(row, col)
        if formulas._isnan(val):
            continue
        if op == ">" and val > thr:
            return True
        if op == "<" and val < thr:
            return True
    return False


def compute_health_index(row) -> dict:
    """Score one employee row under the deduction formula."""
    score = 1000.0
    deductions: dict[str, float] = {}
    fractions: dict[str, float] = {}
    egfr = None

    # Mechanism 1: cross-domain amplifiers from anchor conditions.
    cross_amplifiers = formulas.compute_amplifiers(row)

    # Σ clinical domains
    for domain, fn in DOMAIN_FUNCS.items():
        result = fn(row)
        if isinstance(result, dict):
            base_frac = result.get("fraction", 0.0)
            formula_amplifier = result.get("amplifier", 1.0)
            if "egfr" in result:
                egfr = result["egfr"]
        else:
            base_frac = float(result)
            formula_amplifier = 1.0

        # Combined amplifier: formula-level × cross-domain (both default to 1.0)
        amplifier = formula_amplifier * cross_amplifiers.get(domain, 1.0)
        effective_frac = max(0.0, min(1.0, base_frac * amplifier))
        ded = MAX_DEDUCTION[domain] * effective_frac
        deductions[domain] = round(ded, 1)
        fractions[domain] = round(effective_frac, 3)
        score -= ded

    # Mechanism 2: complication-weighted chronic burden — 200 × min(B / 7, 1)
    # B includes control_modifier (diabetes HbA1c) and multi-condition synergy,
    # capturing neuropathy/MSK/retinopathy that the 72-parameter panel can't measure.
    B = formulas.chronic_burden_score(row)
    chronic_frac = min(B / CHARLSON_CAP, 1.0)
    chronic_ded = CHRONIC_MAX_DEDUCTION * chronic_frac
    deductions["chronic_disease"] = round(chronic_ded, 1)
    fractions["chronic_disease"] = round(chronic_frac, 3)
    score -= chronic_ded

    # Clamp, then critical floor
    score = max(0.0, min(1000.0, score))
    critical = _breaches_critical(row, egfr)
    if critical:
        score = min(score, CRITICAL_CAP)

    band = next(lbl for thr, lbl in BAND_LABELS if score >= thr)
    top_drivers = sorted(deductions.items(), key=lambda kv: kv[1], reverse=True)[:3]
    return {
        "health_index": round(score),
        "band": band,
        "critical_flag": bool(critical),
        "deductions": deductions,
        "penalty_fractions": fractions,
        "top_risk_drivers": [d for d, _ in top_drivers],
    }


def score_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Add health_index, health_band, critical_flag, and per-domain columns.

    domain__<name> is the domain's health score 0–100 (100 = no penalty,
    0 = full penalty), keeping "higher is better" semantics for aggregation.
    Includes chronic_disease as domain__chronic_disease.
    """
    out = df.copy()
    all_domains = list(MAX_DEDUCTION.keys()) + ["chronic_disease"]

    if len(df) == 0:
        out["health_index"] = pd.Series(dtype="int64")
        out["health_band"] = pd.Series(dtype="object")
        out["critical_flag"] = pd.Series(dtype="bool")
        for d in all_domains:
            out[f"domain__{d}"] = pd.Series(dtype="float64")
        return out

    results = [compute_health_index(row) for _, row in df.iterrows()]

    out["health_index"] = [r["health_index"] for r in results]
    out["health_band"] = [r["band"] for r in results]
    out["critical_flag"] = [r["critical_flag"] for r in results]
    for d in all_domains:
        out[f"domain__{d}"] = [round((1.0 - r["penalty_fractions"][d]) * 100.0, 1)
                               for r in results]
    return out


def band_for_score(score: float) -> str:
    """Score -> band label (kept for callers that mapped scores directly)."""
    return next(lbl for thr, lbl in BAND_LABELS if score >= thr)
