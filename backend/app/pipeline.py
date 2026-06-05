"""Privacy pipeline (BRD §6) — ordered, pure-ish DataFrame transforms.

Step 1 de-identify -> Step 2 noise -> Step 3 tokenize  (per dataset)
Step 4 combine (in-memory join on (company_id, token), drop token)

The token-linked combined table is in-memory only and is never written to disk.
"""

from __future__ import annotations

import hashlib
import hmac
import os

import numpy as np
import pandas as pd

# --- Synthetic company assignment -------------------------------------------
# The source files are a single company (HCL). Per the BRD data prerequisite we
# split employees across several companies, assigned deterministically by
# employee_id so AHC and HRMS agree on every employee's company.
COMPANIES = [
    ("AURT", "Aurora Tech"),
    ("BLPK", "BluePeak Industries"),
    ("CATL", "Catalyst Labs"),
    ("DELT", "Delta Logistics"),
    ("EVRS", "Everest Financial"),
    ("FUSN", "Fusion Retail"),
    ("HRZN", "Horizon Health"),
    ("IRON", "Ironclad Mfg"),
]
COMPANY_NAMES = {code: name for code, name in COMPANIES}


def assign_company_id(employee_id: pd.Series) -> pd.Series:
    """HCL0001234 -> deterministic company code via the numeric suffix."""
    num = employee_id.str.extract(r"(\d+)$")[0].astype(int)
    idx = num % len(COMPANIES)
    return idx.map({i: COMPANIES[i][0] for i in range(len(COMPANIES))})


# --- Identifier columns to strip (Step 1) -----------------------------------
AHC_IDENTIFIERS = ["name"]
HRMS_IDENTIFIERS = [
    "full_name", "date_of_birth", "blood_group", "marital_status", "nationality",
    "highest_qualification", "designation", "employment_type", "employment_status",
    "work_mode", "shift", "date_of_joining", "reporting_manager", "official_email",
    "phone_number", "emergency_contact_name", "emergency_contact_number",
    "uan_number", "pf_account_number", "annual_ctc_inr", "leave_balance_days",
    "last_appraisal_rating", "blood_group",
]


def step1_deidentify(df: pd.DataFrame, identifiers: list[str]) -> pd.DataFrame:
    """Drop direct identifiers. Keep employee_id (needed for Step 3) + the rest."""
    drop = [c for c in identifiers if c in df.columns]
    return df.drop(columns=drop)


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


def _hmac_token(employee_id: str, key: bytes) -> str:
    return hmac.new(key, employee_id.encode(), hashlib.sha256).hexdigest()[:32]


def step3_tokenize(df: pd.DataFrame, key: bytes | None = None) -> pd.DataFrame:
    """Add a deterministic HMAC-SHA256 token column from employee_id.

    Same key + same employee_id -> identical token across both datasets, which
    is what lets Step 4 join them without exposing the raw id.
    """
    if key is None:
        secret = os.environ.get("HMAC_SECRET_KEY", "dev-only-insecure-key")
        key = secret.encode()
    out = df.copy()
    out["token"] = out["employee_id"].map(lambda e: _hmac_token(e, key))
    return out


def aggregate_hrms_to_employee(hrms: pd.DataFrame) -> pd.DataFrame:
    """Claims-level (one row per claim) -> one row per employee.

    Sum OPD/IPD, count claims; take employee-level attrs (first).
    """
    g = hrms.groupby(["company_id", "token"], as_index=False)
    agg = g.agg(
        department=("department", "first"),
        work_location=("work_location", "first"),
        band=("band", "first"),
        gender=("gender", "first"),
        age=("age", "first"),
        absenteeism_percent_per_month=("absenteeism_percent_per_month", "first"),
        opd_total_inr=("insurance_claim_opd_inr", "sum"),
        ipd_total_inr=("insurance_claim_ipd_inr", "sum"),
        claim_count=("claim_id", "count"),
    )
    return agg


def step4_combine(ahc_scored: pd.DataFrame, hrms_emp: pd.DataFrame) -> pd.DataFrame:
    """In-memory inner join on (company_id, token); then DROP token + employee_id.

    The returned frame has no identifiers and is the only thing scoring/grouping
    downstream ever sees.
    """
    joined = ahc_scored.merge(hrms_emp, on=["company_id", "token"], how="inner",
                              suffixes=("", "_hrms"))
    # Drop the link keys and any leftover identifier columns.
    drop = [c for c in ["token", "employee_id", "age_hrms"] if c in joined.columns]
    return joined.drop(columns=drop)
