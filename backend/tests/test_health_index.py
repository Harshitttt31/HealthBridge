"""Deduction-model Health Index tests (BRD §7 refactor, doc §6-§7).

Worked-example invariants + a dataset-level sanity check (opt-in via the real
AHC file). Exact per-domain numbers are illustrative; we assert the structural
properties that must always hold.
"""

from __future__ import annotations

import os

import pandas as pd
import pytest

from app.scoring.deduction_config import CRITICAL_CAP, MAX_DEDUCTION
from app.scoring.health_index import compute_health_index, score_dataframe

_HEALTHY = dict(
    age=32, sex="M", hba1c_percent=5.2, fbs_mg_dl=85, systolic_bp_mmhg=115,
    diastolic_bp_mmhg=75, total_cholesterol_mg_dl=170, ldl_mg_dl=90, hdl_mg_dl=55,
    triglycerides_mg_dl=110, creatinine_mg_dl=0.8, haemoglobin_g_dl=15.0, bmi=23.0,
    ast_sgot_u_l=22, alt_sgpt_u_l=24, platelet_count_lakhs_cumm=2.5,
    vo2_max_ml_kg_min=46, tsh_uiu_ml=2.0, crp_mg_l=0.5, vitamin_d_ng_ml=35,
    vitamin_b12_pg_ml=400, ferritin_ng_ml=120, chronic_disease="",
)
_COMORBID = dict(
    age=54, sex="M", hba1c_percent=8.1, fbs_mg_dl=160, systolic_bp_mmhg=145,
    diastolic_bp_mmhg=92, total_cholesterol_mg_dl=240, ldl_mg_dl=170, hdl_mg_dl=34,
    triglycerides_mg_dl=210, creatinine_mg_dl=1.5, haemoglobin_g_dl=12.0, bmi=31.0,
    ast_sgot_u_l=45, alt_sgpt_u_l=40, platelet_count_lakhs_cumm=2.0,
    vo2_max_ml_kg_min=30, tsh_uiu_ml=2.0, crp_mg_l=4.0, vitamin_d_ng_ml=15,
    vitamin_b12_pg_ml=400, ferritin_ng_ml=120,
    chronic_disease="Type 2 Diabetes,Hypertension,Dyslipidaemia,Obesity",
)


def test_allowances_sum_to_1000():
    assert sum(MAX_DEDUCTION.values()) == 1000


def test_healthy_is_near_perfect():
    r = compute_health_index(_HEALTHY)
    assert r["health_index"] >= 950
    assert r["band"] == "Excellent"
    assert r["critical_flag"] is False


def test_comorbid_far_below_healthy():
    healthy = compute_health_index(_HEALTHY)["health_index"]
    comorbid = compute_health_index(_COMORBID)["health_index"]
    assert comorbid < healthy
    assert 0 <= comorbid <= 1000


def test_critical_value_floors_score():
    row = {**_HEALTHY, "creatinine_mg_dl": 6.0, "chronic_disease": "Chronic Kidney Disease"}
    r = compute_health_index(row)
    assert r["critical_flag"] is True
    assert r["health_index"] <= CRITICAL_CAP


def test_bounds_and_missing_inputs():
    # Sparse panel must score in range without crashing.
    sparse = {"hba1c_percent": 9.0, "chronic_disease": "Type 2 Diabetes"}
    r = compute_health_index(sparse)
    assert 0 <= r["health_index"] <= 1000
    assert len(r["penalty_fractions"]) == len(MAX_DEDUCTION)


def test_score_dataframe_columns():
    df = pd.DataFrame([_HEALTHY, _COMORBID])
    scored = score_dataframe(df)
    assert scored["health_index"].between(0, 1000).all()
    for d in MAX_DEDUCTION:
        col = f"domain__{d}"
        assert col in scored.columns
        assert scored[col].between(0, 100).all()


def test_top_risk_drivers_present():
    r = compute_health_index(_COMORBID)
    assert 1 <= len(r["top_risk_drivers"]) <= 3
    # The biggest deduction must be listed first.
    biggest = max(r["deductions"], key=r["deductions"].get)
    assert r["top_risk_drivers"][0] == biggest


# --- dataset-level validation (doc §7) -- opt-in on the real AHC file --------
_AHC = os.environ.get("AHC_PATH", r"C:\Users\PC\Downloads\healthbridge_ahc_full_panel_100k.csv")


@pytest.mark.skipif(not os.path.exists(_AHC), reason="real AHC dataset not present")
def test_dataset_monotonicity():
    df = pd.read_csv(_AHC)
    scored = score_dataframe(df)
    idx = scored["health_index"]

    blank = df["chronic_disease"].isna() | (df["chronic_disease"].astype(str).str.strip() == "")
    diabetic = df["hba1c_percent"] >= 6.5

    assert idx.between(0, 1000).all()
    assert idx[~blank].mean() < idx[blank].mean()          # chronic disease lowers the mean
    assert idx[diabetic].mean() < idx[~diabetic].mean()     # diabetics score lower
    # Distribution is spread, not clustered at an extreme.
    assert idx.std() > 25
    assert idx.quantile(0.95) < 1000
