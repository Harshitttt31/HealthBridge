"""Step 5 — group-level release (BRD §6, §9).

The ONLY data permitted to leave the processing layer. Two guarantees:

  1. k-anonymity floor — any cohort with n < MIN_GROUP is suppressed (defence in
     depth; Mondrian already enforces k>=20, this is the final gate).
  2. optional DP noise — small Laplace noise on released numeric aggregates so the
     published figures themselves carry deniability. Off by default; means are
     drawn from >=20 people so the perturbation is tiny relative to the value.

Operates on the per-company payload {"summary", "cohorts"} produced by
aggregate_company, returning a cleaned payload safe to persist/serve.
"""

from __future__ import annotations

import numpy as np

MIN_GROUP = 20

# Released numeric fields that DP noise may perturb. Structural fields (n, band,
# quadrant, labels) are left intact so the output stays internally consistent.
_TOP_FIELDS = ["group_health_score", "cost_per_head_inr"]
_CLAIM_FIELDS = ["avg_opd_inr", "avg_ipd_inr", "avg_absenteeism_pct"]


def enforce_k(cohorts: list[dict], min_group: int = MIN_GROUP) -> tuple[list[dict], int]:
    """Drop cohorts below the k floor. Returns (kept, n_suppressed)."""
    kept = [c for c in cohorts if c.get("n", 0) >= min_group]
    return kept, len(cohorts) - len(kept)


def _laplace_frac(rng: np.random.Generator, value: float, scale_frac: float) -> float:
    """Laplace noise scaled to a fraction of the value's magnitude."""
    b = abs(value) * scale_frac
    return float(value + rng.laplace(0.0, b)) if b > 0 else float(value)


def add_dp_noise(cohorts: list[dict], rng: np.random.Generator,
                 scale_frac: float = 0.01) -> list[dict]:
    """Perturb released numeric aggregates with small Laplace noise (in place)."""
    for c in cohorts:
        for f in _TOP_FIELDS:
            if isinstance(c.get(f), (int, float)):
                noisy = _laplace_frac(rng, c[f], scale_frac)
                c[f] = round(noisy, 1) if isinstance(c[f], float) else round(noisy)
        claims = c.get("claims", {})
        for f in _CLAIM_FIELDS:
            if isinstance(claims.get(f), (int, float)):
                noisy = _laplace_frac(rng, claims[f], scale_frac)
                claims[f] = round(noisy, 2) if isinstance(claims[f], float) else round(noisy)
    return cohorts


def step5_release(payload: dict, dp: bool = False, min_group: int = MIN_GROUP,
                  rng: np.random.Generator | None = None) -> dict:
    """Apply the k floor (+ optional DP noise) and refresh summary counts."""
    cohorts, suppressed = enforce_k(payload.get("cohorts", []), min_group)
    if dp:
        cohorts = add_dp_noise(cohorts, rng or np.random.default_rng(7))

    summary = dict(payload.get("summary", {}))
    summary["cohort_count"] = len(cohorts)
    summary["employees_covered"] = sum(c.get("n", 0) for c in cohorts)
    if suppressed:
        summary["suppressed_cohorts"] = suppressed
    return {"summary": summary, "cohorts": cohorts}
