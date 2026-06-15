"""Group Health Index aggregation (BRD §9).

Per cohort (n >= 20): health half (from AHC scores) + claims half (from HRMS),
plus a 2-axis risk quadrant. Only group-level numbers leave this layer.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .grouping.mondrian import label_for_cohort, QUASI_IDS

BANDS = ["Excellent", "Good", "Fair", "Poor", "Critical"]
MIN_GROUP = 20  # k-anonymity floor; also suppresses rare conditions

COST_AXIS_THRESHOLD = None  # set per-company at runtime (median cost-per-head)


def _band_distribution(cohort: pd.DataFrame) -> dict:
    counts = cohort["health_band"].value_counts()
    n = len(cohort)
    return {b: round(100 * int(counts.get(b, 0)) / n, 1) for b in BANDS}


def _weakest_domains(cohort: pd.DataFrame, k: int = 3) -> list[dict]:
    dom_cols = [c for c in cohort.columns if c.startswith("domain__")]
    means = {c.replace("domain__", ""): round(float(cohort[c].mean()), 1) for c in dom_cols}
    worst = sorted(means.items(), key=lambda kv: kv[1])[:k]
    return [{"domain": d, "score": s} for d, s in worst]


def _hra_coverage(cohort: pd.DataFrame) -> float:
    """% of the cohort scored with a complete (AHC + consented HRA) profile."""
    if "completeness_tier" not in cohort.columns or not len(cohort):
        return 0.0
    return round(100 * float((cohort["completeness_tier"] == "COMPLETE").mean()), 1)


def _mean_pillar(cohort: pd.DataFrame, col: str) -> float | None:
    """Cohort mean of a 0..1 pillar as a 0..100 score; None if unavailable.

    behavioural is NaN for labs-only rows, so the mean skips them (pandas default)
    and is None only when every row is labs-only.
    """
    if col not in cohort.columns:
        return None
    m = cohort[col].mean()
    return None if pd.isna(m) else round(100 * float(m), 1)


def _chronic_prevalence(cohort: pd.DataFrame) -> list[dict]:
    """% with each chronic condition; suppress any affecting < MIN_GROUP employees."""
    if "chronic_disease" not in cohort.columns:
        return []
    n = len(cohort)
    exploded = (
        cohort["chronic_disease"].dropna().astype(str)
        .str.split(",").explode().str.strip()
    )
    exploded = exploded[exploded != ""]
    counts = exploded.value_counts()
    out = []
    for cond, cnt in counts.items():
        if cnt < MIN_GROUP:
            continue  # k-anonymity: don't reveal rare conditions
        out.append({"condition": cond, "pct": round(100 * int(cnt) / n, 1)})
    return out[:6]


def _quadrant(score: float, cost: float, score_thr: float, cost_thr: float) -> str:
    low_health = score < score_thr
    high_cost = cost > cost_thr
    if low_health and high_cost:
        return "Priority"          # low score / high cost
    if low_health and not high_cost:
        return "Watch"
    if not low_health and high_cost:
        return "Costly but well"
    return "Healthy"


def aggregate_company(cohorts: list[pd.DataFrame], company_id: str, company_name: str) -> dict:
    """Build the per-company payload: cohort records + summary."""
    # Cost-per-head per cohort (avg total claim value per employee).
    raw = []
    for c in cohorts:
        n = len(c)
        opd_total = float(c["opd_total_inr"].sum())
        ipd_total = float(c["ipd_total_inr"].sum())
        cost_per_head = (opd_total + ipd_total) / n
        raw.append((c, n, opd_total, ipd_total, cost_per_head))

    score_thr = 650  # health axis split (Good threshold)
    costs = [r[4] for r in raw]
    cost_thr = float(np.median(costs)) if costs else 0.0

    records = []
    for i, (c, n, opd_total, ipd_total, cost_per_head) in enumerate(raw):
        score = round(float(c["health_index"].mean()), 1)
        labels = label_for_cohort(c)
        label_str = " · ".join(
            v for k in ["department", "work_location", "age_band"]
            if (v := labels.get(k)) and v != "All"
        ) or "Whole company"
        claims = {
            "avg_opd_inr": round(opd_total / n),
            "total_opd_inr": round(opd_total),
            "avg_ipd_inr": round(ipd_total / n),
            "total_ipd_inr": round(ipd_total),
            "claims_per_employee": round(float(c["claim_count"].mean()), 2),
            "pct_with_claim": round(100 * float((c["claim_count"] > 0).mean()), 1),
            "ipd_rate": round(100 * float((c["ipd_total_inr"] > 0).mean()), 1),
            "avg_absenteeism_pct": round(float(c["absenteeism_percent_per_month"].mean()), 2),
        }
        records.append({
            "cohort_id": f"{company_id}-{i+1:02d}",
            "label": label_str,
            "quasi_ids": labels,
            "n": n,
            "group_health_score": score,
            "band": _band_for(score),
            "band_distribution": _band_distribution(c),
            "weakest_domains": _weakest_domains(c),
            "chronic_prevalence": _chronic_prevalence(c),
            "claims": claims,
            "cost_per_head_inr": round(cost_per_head),
            "quadrant": _quadrant(score, cost_per_head, score_thr, cost_thr),
            "hra_coverage_pct": _hra_coverage(c),
            "pillars": {
                "clinical": _mean_pillar(c, "pillar_clinical"),
                "behavioural": _mean_pillar(c, "pillar_behavioural"),
                "future": _mean_pillar(c, "pillar_future"),
            },
        })

    records.sort(key=lambda r: r["group_health_score"])
    total_emp = sum(r["n"] for r in records)
    summary = {
        "company_id": company_id,
        "company_name": company_name,
        "cohort_count": len(records),
        "employees_covered": total_emp,
        "avg_health_score": round(
            sum(r["group_health_score"] * r["n"] for r in records) / total_emp, 1
        ) if total_emp else 0,
        "avg_cost_per_head_inr": round(
            sum(r["cost_per_head_inr"] * r["n"] for r in records) / total_emp
        ) if total_emp else 0,
        "hra_coverage_pct": round(
            sum(r["hra_coverage_pct"] * r["n"] for r in records) / total_emp, 1
        ) if total_emp else 0,
        "score_axis": score_thr,
        "cost_axis": round(cost_thr),
    }
    return {"summary": summary, "cohorts": records}


def _band_for(score: float) -> str:
    if score >= 800:
        return "Excellent"
    if score >= 650:
        return "Good"
    if score >= 500:
        return "Fair"
    if score >= 350:
        return "Poor"
    return "Critical"
