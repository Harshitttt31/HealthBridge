"""HRA integration invariants (framework Stages 2-4).

Covers the non-negotiable rules for folding the questionnaire into the score:
  - split_hra isolates the questionnaire from the clinical half, keeping only
    consented rows, and never carries employee_id into the HRA store
  - apply_three_pillar tags rows COMPLETE (AHC + HRA) vs LABS-ONLY and keeps the
    composite in [0, 1000]
  - the labs-only fallback drops the behavioural pillar and renormalises
  - raw HRA never survives scoring (privacy gate)
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from app.pipeline.hra import (
    COMPLETE, CONSENT_COL, HRA_FIELDS, LABS_ONLY,
    apply_three_pillar, has_hra_columns, split_hra,
)


def _tokenised() -> pd.DataFrame:
    """A tokenised, de-identified AHC+HRA frame (post Step 3)."""
    return pd.DataFrame({
        "company_id": ["jpm001"] * 3,
        "token": ["t1", "t2", "t3"],
        "employee_id": ["E1", "E2", "E3"],
        "age": [30, 45, 52],
        "bmi": [22.0, 28.0, 33.0],
        "fbs_mg_dl": [90, 130, 200],
        "systolic_bp_mmhg": [115, 140, 165],
        "ldl_mg_dl": [90, 140, 180],
        "smoking": ["never", "current", None],
        "alcohol": ["none", "heavy", None],
        "physical_activity": ["high", "low", None],
        "diet_quality": ["good", "poor", None],
        "sleep": ["adequate", "poor", None],
        "stress": ["none", "mod_severe", None],
        "waist_cm": [80, 105, np.nan],
        "fh_diabetes": [False, True, False],
        "fh_hypertension": [False, True, False],
        "fh_cvd": [False, False, False],
        "fh_stroke": [False, False, False],
        "fh_cancer": [False, False, False],
        CONSENT_COL: [True, True, False],
    })


def _scored() -> pd.DataFrame:
    """An AHC frame as it looks after score_dataframe (clinical health_index)."""
    return pd.DataFrame({
        "token": ["t1", "t2", "t3"],
        "health_index": [820, 600, 410],
        "critical_flag": [False, False, False],
        "fbs_mg_dl": [90, 130, 200],
        "systolic_bp_mmhg": [115, 140, 165],
        "ldl_mg_dl": [90, 140, 180],
        "bmi": [22.0, 28.0, 33.0],
    })


# --- split_hra --------------------------------------------------------------
def test_split_isolates_consented_questionnaire():
    clinical, hra, info = split_hra(_tokenised())

    # Clinical half carries no questionnaire / consent columns.
    assert not any(c in clinical.columns for c in HRA_FIELDS)
    assert CONSENT_COL not in clinical.columns
    assert "employee_id" in clinical.columns  # dropped later in the upload path

    # HRA half: only the two consented rows, token-keyed, no employee_id.
    assert hra is not None
    assert list(hra["token"]) == ["t1", "t2"]
    assert "employee_id" not in hra.columns
    # t3 has questionnaire answers but declined consent -> captured, not stored.
    assert info["captured"] == 3 and info["consented"] == 2


def test_split_without_hra_columns_returns_none():
    df = pd.DataFrame({"token": ["t1"], "employee_id": ["E1"], "bmi": [24.0]})
    clinical, hra, info = split_hra(df)
    assert hra is None
    assert info["captured"] == 0
    assert "bmi" in clinical.columns


def test_has_hra_columns():
    assert has_hra_columns(_tokenised()) is True
    assert has_hra_columns(pd.DataFrame({"bmi": [1]})) is False


# --- apply_three_pillar -----------------------------------------------------
def test_complete_vs_labs_only_tiers():
    clinical, hra, _ = split_hra(_tokenised())
    out = apply_three_pillar(_scored(), hra)

    tiers = dict(zip(out["token"], out["completeness_tier"]))
    assert tiers["t1"] == COMPLETE and tiers["t2"] == COMPLETE
    assert tiers["t3"] == LABS_ONLY  # declined consent -> labs only


def test_behavioural_pillar_only_for_complete_rows():
    clinical, hra, _ = split_hra(_tokenised())
    out = apply_three_pillar(_scored(), hra).set_index("token")
    assert not pd.isna(out.loc["t1", "pillar_behavioural"])
    assert pd.isna(out.loc["t3", "pillar_behavioural"])  # labs-only: no behaviour


def test_composite_in_bounds():
    clinical, hra, _ = split_hra(_tokenised())
    out = apply_three_pillar(_scored(), hra)
    assert out["health_index"].between(0, 1000).all()


def test_labs_only_when_no_hra_store():
    out = apply_three_pillar(_scored(), None)
    assert (out["completeness_tier"] == LABS_ONLY).all()
    assert out["pillar_behavioural"].isna().all()
    assert out["health_index"].between(0, 1000).all()


def test_no_raw_hra_survives_scoring():
    clinical, hra, _ = split_hra(_tokenised())
    out = apply_three_pillar(_scored(), hra)
    assert not any(c in out.columns for c in HRA_FIELDS)


def test_healthy_complete_scores_above_unhealthy_complete():
    clinical, hra, _ = split_hra(_tokenised())
    out = apply_three_pillar(_scored(), hra).set_index("token")
    # t1 is healthy labs + healthy behaviour; t2 is worse on both.
    assert out.loc["t1", "health_index"] > out.loc["t2", "health_index"]
