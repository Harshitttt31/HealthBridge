"""Processing endpoint (BRD §10, FR-04..09).

  POST /process  (hr or employer) -> step 4 combine + score + group + aggregate
                                      + step 5 release, for the caller's company.

Runs only over the caller's own company. Both the AHC and HRMS de-identified sets
must already be uploaded. The token-linked combined table lives only in memory;
only the k>=20 cohort aggregates are persisted (GroupResult).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, delete, select

from app.aggregate import aggregate_company
from app.auth import CurrentUser, get_current_user
from app.db import get_session
from app.grouping.mondrian import age_band, mondrian
from app.models import GroupResult, Upload, UploadKind, UploadStatus
from app.pipeline import (
    HRA_FIELDS, aggregate_hrms_to_employee, apply_three_pillar, step4_combine,
    step5_release,
)
from app.pipeline.companies import COMPANY_NAMES
from app.scoring.health_index import score_dataframe
from app.storage import has_deident, load_deident

router = APIRouter(tags=["process"])

# AHC columns carried into the join (scores + grouping inputs, no identifiers).
# Pillar sub-scores + completeness tier ride along; raw HRA never does.
_AHC_KEEP_BASE = ["company_id", "token", "age", "sex", "chronic_disease",
                  "health_index", "health_band", "critical_flag",
                  "pillar_clinical", "pillar_behavioural", "pillar_future",
                  "completeness_tier"]


def _run_company(company_id: str) -> dict:
    """Full in-memory pipeline for one company; returns the released payload."""
    ahc = load_deident(company_id, UploadKind.ahc)
    hrms = load_deident(company_id, UploadKind.hrms)
    hra = (load_deident(company_id, UploadKind.hra)
           if has_deident(company_id, UploadKind.hra) else None)

    # Score AHC (clinical pillar), then fold in the HRA -> three-pillar composite
    # with a completeness tier. apply_three_pillar consumes the raw HRA and never
    # attaches it; keep only what the join/grouping needs afterwards.
    ahc = score_dataframe(ahc)
    ahc = apply_three_pillar(ahc, hra)
    keep = [c for c in _AHC_KEEP_BASE if c in ahc.columns] + \
           [c for c in ahc.columns if c.startswith("domain__")]
    ahc = ahc[keep]
    leaked_hra = [c for c in HRA_FIELDS if c in ahc.columns]
    if leaked_hra:
        raise RuntimeError(f"raw HRA leaked past scoring: {leaked_hra}")

    # Aggregate HRMS claims to employee level, then Step 4 join (drops token).
    hrms_emp = aggregate_hrms_to_employee(hrms)
    combined = step4_combine(ahc, hrms_emp)
    if "token" in combined.columns or "employee_id" in combined.columns:
        raise RuntimeError("token/employee_id leaked past Step 4")
    if any(c in combined.columns for c in HRA_FIELDS):
        raise RuntimeError("raw HRA leaked into the combined table")
    if combined.empty:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY,
                            detail="No AHC/HRMS records matched on token.")
    combined["age_band"] = age_band(combined["age"])

    # Mondrian k>=20 grouping -> aggregate -> Step 5 release gate.
    cohorts = mondrian(combined)
    payload = aggregate_company(cohorts, company_id,
                                COMPANY_NAMES.get(company_id, company_id))
    return step5_release(payload)


@router.post("/process")
def process(user: CurrentUser = Depends(get_current_user),
            session: Session = Depends(get_session)) -> dict:
    company_id = user.company_id

    missing = [k.value for k in (UploadKind.ahc, UploadKind.hrms)
               if not has_deident(company_id, k)]
    if missing:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail=f"Upload required before processing: missing {missing}.",
        )

    payload = _run_company(company_id)

    # Replace any prior results for this company with the fresh cohort set.
    session.exec(delete(GroupResult).where(GroupResult.company_id == company_id))
    for rec in payload["cohorts"]:
        session.add(GroupResult.from_payload(
            company_id=company_id, cohort_label=rec["label"], n=rec["n"], payload=rec,
        ))
    # Mark this company's uploads as processed.
    for up in session.exec(select(Upload).where(
            Upload.company_id == company_id,
            Upload.status == UploadStatus.received)).all():
        up.status = UploadStatus.processed
        session.add(up)
    session.commit()

    return {
        "company_id": company_id,
        "cohort_count": payload["summary"].get("cohort_count", 0),
        "employees_covered": payload["summary"].get("employees_covered", 0),
        "summary": payload["summary"],
    }
