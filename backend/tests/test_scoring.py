"""Scoring invariants (BRD §13).

  - health_index in [0, 1000] for every row
  - critical override caps severe cases at CRITICAL_CAP
  - comorbid employees score lower on average than blank-diagnosis ones
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from app.scoring.health_index import score_dataframe
from app.scoring.reference_ranges import CRITICAL_CAP

_HEALTHY = dict(hba1c_percent=5.2, fbs_mg_dl=85, systolic_bp_mmhg=115,
                diastolic_bp_mmhg=75, ldl_mg_dl=90, hdl_mg_dl=55,
                creatinine_mg_dl=0.8, haemoglobin_g_dl=14.0, bmi=23.0)
_COMORBID = dict(hba1c_percent=8.5, fbs_mg_dl=180, systolic_bp_mmhg=155,
                 diastolic_bp_mmhg=95, ldl_mg_dl=170, hdl_mg_dl=35,
                 creatinine_mg_dl=2.5, haemoglobin_g_dl=11.0, bmi=31.0)


def _people(profile: dict, n: int, chronic: str, rng) -> pd.DataFrame:
    """n employees around a biomarker profile with small jitter."""
    rows = {k: rng.normal(v, abs(v) * 0.03, n) for k, v in profile.items()}
    df = pd.DataFrame(rows)
    df["chronic_disease"] = chronic
    return df


def test_health_index_within_bounds():
    rng = np.random.default_rng(1)
    df = pd.concat([
        _people(_HEALTHY, 50, "", rng),
        _people(_COMORBID, 50, "Diabetes,Hypertension", rng),
    ], ignore_index=True)
    scored = score_dataframe(df)
    assert scored["health_index"].between(0, 1000).all()


def test_critical_override_caps_index():
    # A single severe marker (creatinine > 5) must cap the index, even if every
    # other biomarker is perfect.
    df = pd.DataFrame([{**_HEALTHY, "creatinine_mg_dl": 6.0, "chronic_disease": "CKD"}])
    scored = score_dataframe(df)
    assert bool(scored["critical_flag"].iloc[0]) is True
    assert scored["health_index"].iloc[0] <= CRITICAL_CAP


def test_comorbid_scores_lower_than_healthy():
    rng = np.random.default_rng(7)
    healthy = score_dataframe(_people(_HEALTHY, 100, "", rng))
    comorbid = score_dataframe(_people(_COMORBID, 100, "Diabetes,Hypertension,CKD", rng))
    assert comorbid["health_index"].mean() < healthy["health_index"].mean()


def test_missing_biomarkers_do_not_crash():
    # Sparse panel (only a couple of markers present) still scores in range.
    df = pd.DataFrame({"hba1c_percent": [5.5, 9.0], "chronic_disease": ["", "Diabetes"]})
    scored = score_dataframe(df)
    assert scored["health_index"].between(0, 1000).all()
