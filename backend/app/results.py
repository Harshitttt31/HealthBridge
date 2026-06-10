"""Results endpoints (BRD §10, FR-10).

  GET /results/companies -> (provider only) list of companies that have processed data
  GET /results/groups    -> k>=20 cohort Group Health Index records
  GET /results/summary   -> company-level rollup (fully group-aggregated)

HR users are locked to their JWT company_id. Providers may pass an optional
?company_id= query param to view any company's results.
"""

from __future__ import annotations

import numpy as np
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlmodel import Session, select

from app.auth import CurrentUser, get_current_user
from app.db import get_session
from app.models import GroupResult, Role, Upload, UploadKind, UploadStatus
from app.pipeline.companies import COMPANY_NAMES

router = APIRouter(prefix="/results", tags=["results"])

MIN_GROUP = 20
BANDS = ["Excellent", "Good", "Fair", "Poor", "Critical"]
SCORE_AXIS = 650  # health-axis split (mirrors aggregate.aggregate_company)


def _resolve_company(user: CurrentUser, company_id: str | None) -> str:
    """Return the company_id to query. Providers may override; HR cannot."""
    if user.role == Role.provider:
        if not company_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Providers must supply ?company_id=",
            )
        return company_id
    return user.company_id


def _cohorts_for(company_id: str, session: Session) -> list[dict]:
    rows = session.exec(
        select(GroupResult).where(GroupResult.company_id == company_id)
    ).all()
    cohorts = [r.payload for r in rows if r.n >= MIN_GROUP]
    cohorts.sort(key=lambda c: c.get("group_health_score", 0))
    return cohorts


@router.get("/companies")
def results_companies(user: CurrentUser = Depends(get_current_user),
                      session: Session = Depends(get_session)) -> dict:
    """Return all companies that have AHC data uploaded.
    Each entry also carries whether that company has been processed yet.
    Providers use this to populate the company selection dropdown.
    """
    ahc_rows = session.exec(
        select(Upload.company_id)
        .where(Upload.kind == UploadKind.ahc)
        .where(Upload.status != UploadStatus.failed)
        .distinct()
    ).all()
    company_ids = sorted(set(str(r) for r in ahc_rows))

    processed_ids = set(
        str(r) for r in session.exec(select(GroupResult.company_id).distinct()).all()
    )

    companies = [
        {
            "company_id": cid,
            "company_name": COMPANY_NAMES.get(cid, cid),
            "processed": cid in processed_ids,
        }
        for cid in company_ids
    ]
    return {"companies": companies}


@router.get("/groups")
def results_groups(user: CurrentUser = Depends(get_current_user),
                   session: Session = Depends(get_session),
                   company_id: str | None = Query(default=None)) -> dict:
    cid = _resolve_company(user, company_id)
    cohorts = _cohorts_for(cid, session)
    return {
        "company_id": cid,
        "company_name": COMPANY_NAMES.get(cid, cid),
        "processed": bool(cohorts),
        "cohort_count": len(cohorts),
        "cohorts": cohorts,
    }


@router.get("/summary")
def results_summary(user: CurrentUser = Depends(get_current_user),
                    session: Session = Depends(get_session),
                    company_id: str | None = Query(default=None)) -> dict:
    cid = _resolve_company(user, company_id)
    cohorts = _cohorts_for(cid, session)
    total = sum(c.get("n", 0) for c in cohorts)

    base = {
        "company_id": cid,
        "company_name": COMPANY_NAMES.get(cid, cid),
        "processed": bool(cohorts),
        "cohort_count": len(cohorts),
        "employees_covered": total,
    }
    if not cohorts or total == 0:
        return {**base, "avg_health_score": 0, "avg_cost_per_head_inr": 0,
                "band_distribution": {b: 0.0 for b in BANDS}, "quadrants": {},
                "score_axis": SCORE_AXIS, "cost_axis": 0}

    avg_score = sum(c["group_health_score"] * c["n"] for c in cohorts) / total
    avg_cost = sum(c.get("cost_per_head_inr", 0) * c["n"] for c in cohorts) / total

    band_dist = {}
    for b in BANDS:
        share = sum(c.get("band_distribution", {}).get(b, 0.0) * c["n"] for c in cohorts)
        band_dist[b] = round(share / total, 1)

    quadrants: dict[str, int] = {}
    for c in cohorts:
        quadrants[c.get("quadrant", "?")] = quadrants.get(c.get("quadrant", "?"), 0) + 1

    costs = [c.get("cost_per_head_inr", 0) for c in cohorts]
    cost_axis = round(float(np.median(costs))) if costs else 0

    return {
        **base,
        "avg_health_score": round(avg_score, 1),
        "avg_cost_per_head_inr": round(avg_cost),
        "band_distribution": band_dist,
        "quadrants": quadrants,
        "score_axis": SCORE_AXIS,
        "cost_axis": cost_axis,
    }
