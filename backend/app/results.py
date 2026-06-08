"""Results endpoints (BRD §10, FR-10).

  GET /results/groups   -> the caller's k>=20 cohort Group Health Index records
  GET /results/summary  -> a company-level rollup (still fully group-aggregated)

Both read only persisted GroupResult rows for the caller's own company_id, so no
response can ever derive from fewer than 20 employees or cross a company boundary.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlmodel import Session, select

from app.auth import CurrentUser, get_current_user
from app.db import get_session
from app.models import GroupResult
from app.pipeline.companies import COMPANY_NAMES

router = APIRouter(prefix="/results", tags=["results"])

MIN_GROUP = 20
BANDS = ["Excellent", "Good", "Fair", "Poor", "Critical"]


def _cohorts_for(company_id: str, session: Session) -> list[dict]:
    rows = session.exec(
        select(GroupResult).where(GroupResult.company_id == company_id)
    ).all()
    # Defensive k-floor (already guaranteed at write time).
    cohorts = [r.payload for r in rows if r.n >= MIN_GROUP]
    cohorts.sort(key=lambda c: c.get("group_health_score", 0))
    return cohorts


@router.get("/groups")
def results_groups(user: CurrentUser = Depends(get_current_user),
                   session: Session = Depends(get_session)) -> dict:
    cohorts = _cohorts_for(user.company_id, session)
    return {
        "company_id": user.company_id,
        "company_name": COMPANY_NAMES.get(user.company_id, user.company_id),
        "processed": bool(cohorts),
        "cohort_count": len(cohorts),
        "cohorts": cohorts,
    }


@router.get("/summary")
def results_summary(user: CurrentUser = Depends(get_current_user),
                    session: Session = Depends(get_session)) -> dict:
    cohorts = _cohorts_for(user.company_id, session)
    total = sum(c.get("n", 0) for c in cohorts)

    base = {
        "company_id": user.company_id,
        "company_name": COMPANY_NAMES.get(user.company_id, user.company_id),
        "processed": bool(cohorts),
        "cohort_count": len(cohorts),
        "employees_covered": total,
    }
    if not cohorts or total == 0:
        return {**base, "avg_health_score": 0, "avg_cost_per_head_inr": 0,
                "band_distribution": {b: 0.0 for b in BANDS}, "quadrants": {}}

    # Employee-weighted rollups across cohorts.
    avg_score = sum(c["group_health_score"] * c["n"] for c in cohorts) / total
    avg_cost = sum(c.get("cost_per_head_inr", 0) * c["n"] for c in cohorts) / total

    # Company-wide band distribution (weight each cohort's % by its headcount).
    band_dist = {}
    for b in BANDS:
        share = sum(c.get("band_distribution", {}).get(b, 0.0) * c["n"] for c in cohorts)
        band_dist[b] = round(share / total, 1)

    # Cohort counts per risk quadrant.
    quadrants: dict[str, int] = {}
    for c in cohorts:
        quadrants[c.get("quadrant", "?")] = quadrants.get(c.get("quadrant", "?"), 0) + 1

    return {
        **base,
        "avg_health_score": round(avg_score, 1),
        "avg_cost_per_head_inr": round(avg_cost),
        "band_distribution": band_dist,
        "quadrants": quadrants,
    }
