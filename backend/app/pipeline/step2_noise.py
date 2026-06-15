"""Step 2 — calibrated noise (BRD §6).

Add small Gaussian noise to sensitive numeric columns *before* scoring, so
individual values are blurred while group means survive. Applied per dataset.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

# Sensitive numerics the spec calls out for blurring.
AHC_NOISE_COLS = ["hba1c_percent", "systolic_bp_mmhg", "diastolic_bp_mmhg",
                  "fbs_mg_dl", "ldl_mg_dl"]
HRMS_NOISE_COLS = ["insurance_claim_opd_inr", "insurance_claim_ipd_inr",
                   "absenteeism_percent_per_month"]


def step2_noise(df: pd.DataFrame, columns: list[str], sigma_frac: float = 0.01,
                rng: np.random.Generator | None = None) -> pd.DataFrame:
    """Add small Gaussian noise (~1% of value) to sensitive numerics, pre-scoring.

    Kept small so group means are unaffected; values clipped to stay non-negative.
    """
    rng = rng or np.random.default_rng(42)
    out = df.copy()
    for c in columns:
        if c in out.columns:
            vals = out[c].to_numpy(dtype=float)
            noise = rng.normal(0.0, np.abs(vals) * sigma_frac)
            out[c] = np.clip(vals + noise, 0, None)
    return out
