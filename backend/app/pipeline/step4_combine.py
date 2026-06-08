"""Step 4 — combine & destroy tokens (BRD §6).

Join AHC and HRMS in memory on (company_id, token), then DROP token + employee_id.
The token-linked table is never persisted; the returned identifier-free frame is
the only thing scoring/grouping downstream ever sees. HRMS claims are aggregated
to one row per employee here so each employee is a single scored row.
"""

from __future__ import annotations

import pandas as pd


def aggregate_hrms_to_employee(hrms: pd.DataFrame) -> pd.DataFrame:
    """Claims-level (one row per claim) -> one row per employee.

    Sum OPD/IPD, count claims; take employee-level attrs (first).
    """
    g = hrms.groupby(["company_id", "token"], as_index=False)
    return g.agg(
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


def step4_combine(ahc_scored: pd.DataFrame, hrms_emp: pd.DataFrame) -> pd.DataFrame:
    """In-memory inner join on (company_id, token); then DROP token + employee_id.

    The returned frame has no identifiers and is the only thing scoring/grouping
    downstream ever sees.
    """
    joined = ahc_scored.merge(hrms_emp, on=["company_id", "token"], how="inner",
                              suffixes=("", "_hrms"))
    drop = [c for c in ["token", "employee_id", "age_hrms"] if c in joined.columns]
    return joined.drop(columns=drop)
