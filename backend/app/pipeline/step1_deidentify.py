"""Step 1 — de-identify (BRD §6).

Drop direct identifiers from each dataset. `employee_id` is intentionally kept
here because Step 3 needs it to derive the matching token; it is dropped in
Step 4 immediately after the join.
"""

from __future__ import annotations

import pandas as pd

# Direct identifiers stripped at upload.
AHC_IDENTIFIERS = ["name"]
HRMS_IDENTIFIERS = [
    "full_name", "date_of_birth", "blood_group", "marital_status", "nationality",
    "highest_qualification", "designation", "employment_type", "employment_status",
    "work_mode", "shift", "date_of_joining", "reporting_manager", "official_email",
    "phone_number", "emergency_contact_name", "emergency_contact_number",
    "uan_number", "pf_account_number", "annual_ctc_inr", "leave_balance_days",
    "last_appraisal_rating",
]


def step1_deidentify(df: pd.DataFrame, identifiers: list[str]) -> pd.DataFrame:
    """Drop direct identifiers. Keep employee_id (needed for Step 3) + the rest."""
    drop = [c for c in identifiers if c in df.columns]
    return df.drop(columns=drop)
