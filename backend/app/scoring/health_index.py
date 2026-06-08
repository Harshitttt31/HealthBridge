"""Deduction-model Health Index engine (BRD §7, deduction refactor).

Every employee starts at 1000. Each clinical domain subtracts up to its
MAX_DEDUCTION allowance, scaled by a penalty fraction in [0, 1] from a validated
formula (formulas.py). Chronic disease subtracts a Charlson-weighted penalty.
A critical-value floor then caps severe cases, and the score is clamped to
[0, 1000].

Interpretable by construction: "started at 1000, lost 119 for uncontrolled
diabetes, 171 for chronic burden, ...". The per-domain allowances sum to 1000.

Public API:
  - compute_health_index(row) -> dict   (per-employee detail)
  - score_dataframe(df) -> DataFrame     (vectorised wrapper used by the pipeline)

weights.csv and the old build-up model are deprecated (kept for reference).
"""

from __future__ import annotations

import pandas as pd

from . import formulas
from .deduction_config import (
    BAND_LABELS, CRITICAL, CRITICAL_CAP, MAX_DEDUCTION,
)

DOMAIN_FUNCS = {
    "cardiovascular": formulas.cardiovascular,
    "glycaemic": formulas.glycaemic,
    "chronic_disease": formulas.chronic_burden,
    "metabolic_syndrome": formulas.metabolic_syndrome,
    "renal": formulas.renal,            # also returns egfr
    "haematology": formulas.haematology,
    "hepatic": formulas.hepatic,
    "fitness": formulas.fitness,
    "thyroid": formulas.thyroid,
    "inflammatory": formulas.inflammatory,
    "nutrition": formulas.nutrition,
}


def _breaches_critical(row, egfr) -> bool:
    """True if any critical threshold is breached (egfr is the CKD-EPI value)."""
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
    """Score one employee row (Series or dict) under the deduction model."""
    score = 1000.0
    deductions: dict[str, float] = {}
    fractions: dict[str, float] = {}
    egfr = None

    for domain, fn in DOMAIN_FUNCS.items():
        result = fn(row)
        if isinstance(result, dict):
            frac = result.get("fraction", 0.0)
            if "egfr" in result:
                egfr = result["egfr"]
        else:
            frac = result
        frac = max(0.0, min(1.0, frac))
        ded = MAX_DEDUCTION[domain] * frac
        deductions[domain] = round(ded, 1)
        fractions[domain] = round(frac, 3)
        score -= ded

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

    domain__<name> is the domain's *health* score 0-100 (100 = no penalty,
    0 = full penalty), so it keeps the "higher is better" semantics the
    aggregation layer expects for weakest-domain reporting.
    """
    out = df.copy()
    domains = list(MAX_DEDUCTION.keys())

    if len(df) == 0:
        out["health_index"] = pd.Series(dtype="int64")
        out["health_band"] = pd.Series(dtype="object")
        out["critical_flag"] = pd.Series(dtype="bool")
        for d in domains:
            out[f"domain__{d}"] = pd.Series(dtype="float64")
        return out

    results = [compute_health_index(row) for _, row in df.iterrows()]

    out["health_index"] = [r["health_index"] for r in results]
    out["health_band"] = [r["band"] for r in results]
    out["critical_flag"] = [r["critical_flag"] for r in results]
    for d in domains:
        out[f"domain__{d}"] = [round((1.0 - r["penalty_fractions"][d]) * 100.0, 1)
                               for r in results]
    return out


def band_for_score(score: float) -> str:
    """Score -> band label (kept for callers that mapped scores directly)."""
    return next(lbl for thr, lbl in BAND_LABELS if score >= thr)
