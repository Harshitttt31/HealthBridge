"""HRA (Health Risk Assessment) integration — Option 2, provider-captured.

Faithful to healthbridge_hra_integration_framework.html, wired into the LIVE
pipeline (not the standalone reference healthbridge_hra_pipeline.py).

The HRA rides in on the SAME combined upload as the AHC labs — one row per
employee, keyed by employee_id/CUG. The six framework stages map onto the app
like this:

  1 Capture  — questionnaire schema (HRA_FIELDS) + per-employee consent.
  2 Ingest   — `split_hra` separates the questionnaire half from the clinical
               half on the de-identified, tokenised frame (see app/upload.py).
  3 Store    — the questionnaire half is saved under UploadKind.hra: an
               engine-only parquet, never served to a dashboard.
  4 Score    — `apply_three_pillar` joins AHC + HRA by token and folds them into
               a three-pillar Group Health Index:
                   Clinical    (0.45) — the app's lab-based Health Index / 1000
                   Behavioural (0.20) — smoking/alcohol/activity/diet/sleep/
                                        stress/waist (HRA)
                   Future risk (0.35) — labs (FBS, SBP, LDL, BMI) + smoking +
                                        family history
               Every score carries a completeness tier:
                   COMPLETE   — AHC + consented HRA present
                   LABS-ONLY  — HRA missing/declined: behavioural pillar dropped,
                                clinical + future renormalised, future degraded
                                (assume non-smoker, no family history).
  5 Govern   — raw HRA is engine-only; only scores/aggregates leave.
  6 Present  — `hra_coverage_pct` (share COMPLETE) is surfaced on the dashboards.

Privacy: raw HRA never leaves this layer. `split_hra` isolates it,
`apply_three_pillar` consumes it into pillar sub-scores, and the raw
questionnaire columns are dropped before anything is grouped or released.
"""

from __future__ import annotations

import datetime as _dt

import numpy as np
import pandas as pd

from app.scoring.deduction_config import CRITICAL_CAP
from app.scoring.health_index import band_for_score

# --- Stage 1: capture schema -------------------------------------------------
HRA_FIELDS = [
    "smoking", "pack_years", "alcohol", "physical_activity", "diet_quality",
    "sleep", "stress", "waist_cm", "fh_diabetes", "fh_hypertension",
    "fh_cvd", "fh_stroke", "fh_cancer",
]
FAMILY_HISTORY = ["fh_diabetes", "fh_hypertension", "fh_cvd", "fh_stroke", "fh_cancer"]
CONSENT_COL = "hra_consent"
CAPTURE_DATE_COL = "hra_capture_date"

# Framework pillar weights (Stage 4).
PILLAR_WEIGHTS = {"clinical": 0.45, "behavioural": 0.20, "future": 0.35}

# Behavioural category -> 0..1 "goodness" (1.0 = healthiest).
_BEHAVIOUR_MAP = {
    "smoking": {"never": 1.0, "former": 0.7, "current": 0.2},
    "alcohol": {"none": 1.0, "moderate": 0.7, "heavy": 0.3},
    "physical_activity": {"high": 1.0, "moderate": 0.7, "low": 0.3},
    "diet_quality": {"good": 1.0, "average": 0.6, "poor": 0.3},
    "sleep": {"adequate": 1.0, "poor": 0.5},
    "stress": {"none": 1.0, "mild": 0.7, "mod_severe": 0.3},
}

COMPLETE = "COMPLETE"
LABS_ONLY = "LABS-ONLY"


# --- small helpers -----------------------------------------------------------
def _clip01(x):
    return np.clip(x, 0.0, 1.0)


def _num(df: pd.DataFrame, col: str) -> pd.Series:
    """A numeric column as float, or all-zeros if absent (missing => no penalty)."""
    if col in df.columns:
        return pd.to_numeric(df[col], errors="coerce").fillna(0.0)
    return pd.Series(0.0, index=df.index)


def _truthy(series: pd.Series) -> pd.Series:
    """Coerce a family-history column (bool / 0-1 / 'Y'/'yes') to 1.0/0.0."""
    if series.dtype == bool:
        return series.astype(float)
    s = series.astype(str).str.strip().str.lower()
    return s.isin({"1", "true", "yes", "y", "t"}).astype(float)


def has_hra_columns(df: pd.DataFrame) -> bool:
    """True when an upload carries the HRA questionnaire (>= half its fields)."""
    present = sum(1 for c in HRA_FIELDS if c in df.columns)
    return present >= max(1, len(HRA_FIELDS) // 2)


# --- Stage 2 / 3: split off the engine-only questionnaire --------------------
def split_hra(df: pd.DataFrame, capture_date: str | None = None):
    """Split a tokenised, de-identified frame into (clinical, hra, info).

    `df` must already carry a `token` (post Step 3). Returns:
      clinical : `df` with all HRA / consent / capture columns removed.
      hra      : token + questionnaire for rows captured WITH consent, or None
                 when the upload carries no HRA. Engine-only (UploadKind.hra).
      info     : {captured, consented, rows} counts for coverage reporting.

    Consent: an explicit `hra_consent` column wins; otherwise capture implies
    consent (Option 2 — consent is taken at the checkout). Rows that declined
    are excluded from the store entirely.
    """
    hra_cols = [c for c in HRA_FIELDS if c in df.columns]
    drop = [c for c in hra_cols + [CONSENT_COL, CAPTURE_DATE_COL] if c in df.columns]
    clinical = df.drop(columns=drop)

    if not hra_cols or "token" not in df.columns:
        return clinical, None, {"captured": 0, "consented": 0, "rows": len(df)}

    captured = df[hra_cols].notna().any(axis=1)
    if CONSENT_COL in df.columns:
        consent = df[CONSENT_COL].map(lambda v: bool(v) and v == v).to_numpy()
    else:
        consent = captured.to_numpy()
    usable = captured.to_numpy() & consent

    hra = df.loc[usable, ["token"] + hra_cols].copy()
    hra[CONSENT_COL] = True
    if CAPTURE_DATE_COL in df.columns:
        hra[CAPTURE_DATE_COL] = df.loc[usable, CAPTURE_DATE_COL].values
    else:
        hra[CAPTURE_DATE_COL] = capture_date or _dt.date.today().isoformat()

    info = {"captured": int(captured.sum()), "consented": int(usable.sum()),
            "rows": len(df)}
    return clinical, (hra if len(hra) else None), info


# --- Stage 4: the two HRA-fed pillars ---------------------------------------
def behavioural_fraction(h: pd.DataFrame) -> pd.Series:
    """0..1 behavioural health from the questionnaire (1.0 = healthiest)."""
    parts = []
    for col, mapping in _BEHAVIOUR_MAP.items():
        if col in h.columns:
            parts.append(h[col].map(mapping).astype(float).fillna(0.6))
        else:
            parts.append(pd.Series(0.6, index=h.index))
    # Central obesity: waist 90cm -> 1.0, tapering to 0.0 by ~115cm.
    parts.append(_clip01(1.0 - _clip01((_num(h, "waist_cm") - 90) / 25)))
    return _clip01(sum(parts) / len(parts))


def future_fraction(a: pd.DataFrame, h: pd.DataFrame | None) -> pd.Series:
    """0..1 future-risk health (1.0 = lowest risk) from labs + optional HRA.

    When `h` is None the pillar runs degraded — non-smoker / no family history
    assumed — which is the framework's labs-only fallback.
    """
    risk = pd.Series(0.0, index=a.index)
    risk = risk + _clip01((_num(a, "fbs_mg_dl") - 100) / 80) * 0.30
    risk = risk + _clip01((_num(a, "systolic_bp_mmhg") - 120) / 50) * 0.22
    risk = risk + _clip01((_num(a, "ldl_mg_dl") - 100) / 100) * 0.14
    risk = risk + _clip01((_num(a, "bmi") - 25) / 10) * 0.14
    if h is not None:
        if "smoking" in h.columns:
            current = h["smoking"].astype(str).str.lower().eq("current").astype(float)
            risk = risk + current * 0.12
        fh_cols = [c for c in FAMILY_HISTORY if c in h.columns]
        if fh_cols:
            fh = sum(_truthy(h[c]) for c in fh_cols)
            risk = risk + _clip01(fh / 3) * 0.08
    return _clip01(1.0 - _clip01(risk))


def apply_three_pillar(ahc_scored: pd.DataFrame, hra: pd.DataFrame | None) -> pd.DataFrame:
    """Fold HRA into the clinical Health Index -> three-pillar composite.

    `ahc_scored` is the AHC frame after `score_dataframe` (it carries
    `health_index` 0-1000 plus the raw labs and `token`). `hra` is the
    engine-only questionnaire keyed by `token`, or None.

    Returns `ahc_scored` with the pillar sub-scores added
    (`pillar_clinical` / `pillar_behavioural` / `pillar_future`, 0..1;
    behavioural is NaN for labs-only rows), a `completeness_tier`, and
    `health_index` / `health_band` overwritten with the composite. The raw HRA
    is consumed here and never attached to the returned frame.
    """
    out = ahc_scored.copy()
    clinical = _clip01(pd.to_numeric(out["health_index"], errors="coerce") / 1000.0)

    has_hra = pd.Series(False, index=out.index)
    hview = out
    if hra is not None and not hra.empty and "token" in out.columns:
        hcols = [c for c in HRA_FIELDS if c in hra.columns]
        merged = out.merge(
            hra[["token"] + hcols].drop_duplicates("token"),
            on="token", how="left", indicator=True, suffixes=("", "_hra"),
        )
        merged.index = out.index
        has_hra = merged["_merge"].eq("both")
        hview = merged

    behavioural = pd.Series(np.nan, index=out.index)
    future = pd.Series(0.0, index=out.index)

    if bool(has_hra.any()):
        sub = hview[has_hra]
        behavioural.loc[has_hra] = behavioural_fraction(sub).to_numpy()
        future.loc[has_hra] = future_fraction(sub, sub).to_numpy()
    if bool((~has_hra).any()):
        sub = out[~has_hra]
        future.loc[~has_hra] = future_fraction(sub, None).to_numpy()

    w = PILLAR_WEIGHTS
    score = pd.Series(0.0, index=out.index)
    # COMPLETE: full three-pillar.
    score.loc[has_hra] = 1000.0 * (
        w["clinical"] * clinical[has_hra]
        + w["behavioural"] * behavioural[has_hra]
        + w["future"] * future[has_hra]
    )
    # LABS-ONLY: renormalise the two surviving pillars to sum to 1.
    denom = w["clinical"] + w["future"]
    score.loc[~has_hra] = 1000.0 * (
        (w["clinical"] / denom) * clinical[~has_hra]
        + (w["future"] / denom) * future[~has_hra]
    )

    out["pillar_clinical"] = clinical.round(3)
    out["pillar_behavioural"] = behavioural.round(3)
    out["pillar_future"] = future.round(3)
    out["completeness_tier"] = np.where(has_hra, COMPLETE, LABS_ONLY)

    health_index = score.round().clip(0, 1000)
    # Preserve the clinical critical-value floor through the composite.
    if "critical_flag" in out.columns:
        crit = out["critical_flag"].astype(bool)
        health_index.loc[crit] = health_index.loc[crit].clip(upper=CRITICAL_CAP)
    out["health_index"] = health_index.astype(int)
    out["health_band"] = out["health_index"].map(band_for_score)
    return out
