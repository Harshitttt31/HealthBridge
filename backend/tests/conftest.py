"""Shared fixtures for the invariant suite.

Small synthetic AHC/HRMS frames that mirror the real schema's privacy-relevant
columns, so the privacy tests run without touching the 100k Excel files.
"""

from __future__ import annotations

import pandas as pd
import pytest

# Identifier columns that must never survive de-identification.
AHC_IDENTIFIER_COLS = ["name"]
HRMS_IDENTIFIER_COLS = [
    "full_name", "official_email", "phone_number", "uan_number",
    "pf_account_number", "emergency_contact_name",
]

TEST_KEY = b"unit-test-fixed-key"


@pytest.fixture
def ahc_raw() -> pd.DataFrame:
    return pd.DataFrame({
        "CUG": ["jpm001", "jpm001", "tcs001"],
        "employee_id": ["JPM0000001", "JPM0000002", "TCS0000001"],
        "name": ["Asha R", "Vikram S", "Neha P"],
        "sex": ["F", "M", "F"],
        "age": [34, 47, 29],
        "hba1c_percent": [5.4, 7.1, 5.0],
        "systolic_bp_mmhg": [118, 140, 110],
        "creatinine_mg_dl": [0.8, 1.1, 0.7],
    })


@pytest.fixture
def hrms_raw() -> pd.DataFrame:
    # Claims-level: one row per claim (JPM0000001 has two claims).
    return pd.DataFrame({
        "CUG": ["jpm001", "jpm001", "jpm001", "tcs001"],
        "company_name": ["JPMorgan Chase"] * 3 + ["Tata Consultancy Services"],
        "employee_id": ["JPM0000001", "JPM0000001", "JPM0000002", "TCS0000001"],
        "full_name": ["Asha R", "Asha R", "Vikram S", "Neha P"],
        "official_email": ["a@x.com", "a@x.com", "v@x.com", "n@x.com"],
        "phone_number": ["999", "999", "888", "777"],
        "uan_number": ["U1", "U1", "U2", "U3"],
        "pf_account_number": ["P1", "P1", "P2", "P3"],
        "emergency_contact_name": ["X", "X", "Y", "Z"],
        "department": ["Eng", "Eng", "Eng", "Ops"],
        "work_location": ["BLR", "BLR", "BLR", "PUN"],
        "band": ["L3", "L3", "L4", "L2"],
        "gender": ["F", "F", "M", "F"],
        "age": [34, 34, 47, 29],
        "absenteeism_percent_per_month": [1.2, 1.2, 2.0, 0.5],
        "claim_id": ["C1", "C2", "C3", "C4"],
        "insurance_claim_opd_inr": [500, 300, 0, 1200],
        "insurance_claim_ipd_inr": [0, 0, 8000, 0],
    })
