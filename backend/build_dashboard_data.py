"""Offline orchestrator: read the AHC + HRMS Excel files, run the full privacy
pipeline + scoring + Mondrian grouping + aggregation, and write group-level JSON
for the dashboard.

This is the same logic that will later sit behind the FastAPI /process endpoint.
The sensitive token-linked table stays in memory; only group aggregates are written.

Usage:
    python build_dashboard_data.py \
        --ahc  "C:\\path\\ahc.xlsx" \
        --hrms "C:\\path\\hrms.xlsx" \
        --out  "..\\frontend\\app\\data"
"""

from __future__ import annotations

import argparse
import json
import os
import time

import pandas as pd

from app.pipeline import (
    assign_company_id, step1_deidentify, step2_noise, step3_tokenize,
    aggregate_hrms_to_employee, step4_combine,
    AHC_IDENTIFIERS, HRMS_IDENTIFIERS, COMPANY_NAMES,
)
from app.scoring.health_index import score_dataframe
from app.grouping.mondrian import mondrian, age_band
from app.aggregate import aggregate_company

AHC_NOISE_COLS = ["hba1c_percent", "systolic_bp_mmhg", "diastolic_bp_mmhg",
                  "fbs_mg_dl", "ldl_mg_dl"]
HRMS_NOISE_COLS = ["insurance_claim_opd_inr", "insurance_claim_ipd_inr",
                   "absenteeism_percent_per_month"]


def log(msg: str):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def run(ahc_path: str, hrms_path: str, out_dir: str):
    t0 = time.time()

    # --- AHC: load, assign company, de-identify, noise, score, tokenize ---
    log("Loading AHC…")
    ahc = pd.read_excel(ahc_path)
    ahc["company_id"] = assign_company_id(ahc["employee_id"])
    ahc = step1_deidentify(ahc, AHC_IDENTIFIERS)
    ahc = step2_noise(ahc, AHC_NOISE_COLS)
    log(f"Scoring {len(ahc):,} AHC rows…")
    ahc = score_dataframe(ahc)
    ahc = step3_tokenize(ahc)
    ahc_keep = ["company_id", "token", "employee_id", "age", "sex", "chronic_disease",
                "health_index", "health_band", "critical_flag"] + \
               [c for c in ahc.columns if c.startswith("domain__")]
    ahc = ahc[ahc_keep]

    # --- HRMS: load (grouped header), assign company, de-identify, noise, tokenize, aggregate ---
    log("Loading HRMS…")
    hrms = pd.read_excel(hrms_path, header=1)
    hrms["company_id"] = assign_company_id(hrms["employee_id"])
    hrms = step1_deidentify(hrms, HRMS_IDENTIFIERS)
    hrms = step2_noise(hrms, HRMS_NOISE_COLS)
    hrms = step3_tokenize(hrms)
    log(f"Aggregating {len(hrms):,} HRMS claim rows to employee level…")
    hrms_emp = aggregate_hrms_to_employee(hrms)

    # --- Step 4: in-memory join, drop token + employee_id ---
    log("Combining (in-memory join on company_id+token)…")
    combined = step4_combine(ahc, hrms_emp)
    combined["age_band"] = age_band(combined["age"])
    assert "token" not in combined.columns and "employee_id" not in combined.columns, \
        "token/employee_id must not survive Step 4"
    log(f"Combined cohort table: {len(combined):,} employees, {combined['company_id'].nunique()} companies")

    # --- Per-company: Mondrian grouping + aggregation ---
    all_cohorts = []
    summaries = []
    for company_id, comp_df in combined.groupby("company_id"):
        cohorts = mondrian(comp_df)
        payload = aggregate_company(cohorts, company_id, COMPANY_NAMES.get(company_id, company_id))
        all_cohorts.extend(payload["cohorts"])
        summaries.append(payload["summary"])
        n_min = min(len(c) for c in cohorts)
        log(f"  {company_id}: {len(cohorts)} cohorts, smallest n={n_min}")
        assert n_min >= 20, f"k>=20 violated in {company_id}"

    os.makedirs(out_dir, exist_ok=True)
    groups_path = os.path.join(out_dir, "groups.json")
    summary_path = os.path.join(out_dir, "summary.json")
    with open(groups_path, "w", encoding="utf-8") as f:
        json.dump({"cohorts": all_cohorts}, f, indent=2)
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump({"companies": summaries}, f, indent=2)

    log(f"Wrote {len(all_cohorts)} cohorts across {len(summaries)} companies")
    log(f"  -> {groups_path}")
    log(f"  -> {summary_path}")
    log(f"Done in {time.time() - t0:.1f}s")


if __name__ == "__main__":
    here = os.path.dirname(os.path.abspath(__file__))
    p = argparse.ArgumentParser()
    p.add_argument("--ahc", required=True)
    p.add_argument("--hrms", required=True)
    p.add_argument("--out", default=os.path.join(here, "..", "frontend", "app", "data"))
    args = p.parse_args()
    run(args.ahc, args.hrms, args.out)
