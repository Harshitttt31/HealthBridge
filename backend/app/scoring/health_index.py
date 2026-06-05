"""Deterministic 0-1000 Health Index engine (BRD §7).

Pure, vectorized over a DataFrame of AHC biomarkers. No ML, no training.
Driven by weights.csv + reference_ranges.py so the model is calibratable
without touching this code.
"""

from __future__ import annotations

import os
import numpy as np
import pandas as pd

from .reference_ranges import REFERENCE_RANGES, CRITICAL_RULES, CRITICAL_CAP

_WEIGHTS_PATH = os.path.join(os.path.dirname(__file__), "weights.csv")


def load_weights() -> pd.DataFrame:
    """weights.csv -> DataFrame[column, domain, weight_pct, direction]."""
    w = pd.read_csv(_WEIGHTS_PATH)
    w = w[w["weight_pct"] > 0].reset_index(drop=True)
    return w


def _subscore(values: np.ndarray, direction: str, bounds) -> np.ndarray:
    """0-100 sub-score via piecewise-linear interpolation (100 optimal -> 0 critical)."""
    hard_low, soft_low, soft_high, hard_high = bounds
    v = values.astype(float)

    if direction == "up_bad":
        # Full score up to soft_high, 0 at hard_high.
        xp = [soft_high, hard_high]
        fp = [100.0, 0.0]
    elif direction == "down_bad":
        # 0 at hard_low, full score from soft_low up.
        xp = [hard_low, soft_low]
        fp = [0.0, 100.0]
    else:  # band
        xp = [hard_low, soft_low, soft_high, hard_high]
        fp = [0.0, 100.0, 100.0, 0.0]

    # np.interp clamps to the end values outside [xp[0], xp[-1]] — exactly the
    # "full points below optimal / zero past critical" behaviour we want.
    out = np.interp(v, xp, fp)
    # NaN inputs -> neutral 75 (don't reward or harshly punish missing tests).
    out = np.where(np.isnan(v), 75.0, out)
    return np.clip(out, 0.0, 100.0)


def score_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Add health_index, band, and per-domain score columns to a copy of df.

    Returns a new DataFrame with:
      - health_index (0-1000)
      - band (Excellent/Good/Fair/Poor/Critical)
      - domain__<Domain> (0-100) for each domain
      - subscores kept internally for top-risk-driver analysis downstream
    """
    weights = load_weights()
    out = df.copy()

    sub = pd.DataFrame(index=df.index)        # 0-100 subscores
    weighted = pd.DataFrame(index=df.index)   # subscore/100 * weight_pct

    for _, row in weights.iterrows():
        col, direction, wpct = row["column"], row["direction"], float(row["weight_pct"])
        if col not in df.columns or col not in REFERENCE_RANGES:
            continue
        s = _subscore(df[col].to_numpy(), direction, REFERENCE_RANGES[col])
        sub[col] = s
        weighted[col] = (s / 100.0) * wpct

    # index_raw = Σ(subscore/100 * weight_pct) * 10  -> 0..1000
    index_raw = weighted.sum(axis=1) * 10.0

    # Critical override: cap severe cases (BRD §7.2.3).
    critical = pd.Series(False, index=df.index)
    for col, (op, thr) in CRITICAL_RULES.items():
        if col not in df.columns:
            continue
        vals = df[col]
        hit = vals.gt(thr) if op == "gt" else vals.lt(thr)
        critical |= hit.fillna(False)
    index_capped = np.where(critical, np.minimum(index_raw, CRITICAL_CAP), index_raw)

    out["health_index"] = np.round(np.clip(index_capped, 0, 1000)).astype(int)
    out["critical_flag"] = critical.to_numpy()
    # Named health_band to avoid colliding with HRMS's job `band` (L1-L7),
    # which is a grouping quasi-identifier and must survive the join intact.
    out["health_band"] = out["health_index"].map(band_for_score)

    # Domain scores: weighted mean of member subscores (0-100).
    for domain, grp in weights.groupby("domain"):
        cols = [c for c in grp["column"] if c in sub.columns]
        if not cols:
            continue
        w = grp.set_index("column").loc[cols, "weight_pct"].to_numpy()
        dom = (sub[cols].to_numpy() * w).sum(axis=1) / w.sum()
        out[f"domain__{domain}"] = np.round(dom, 1)

    # Stash subscores frame for downstream "top risk drivers" (not persisted).
    out.attrs["subscores"] = sub
    out.attrs["param_weights"] = weights.set_index("column")["weight_pct"].to_dict()
    return out


def band_for_score(score: float) -> str:
    if score >= 800:
        return "Excellent"
    if score >= 650:
        return "Good"
    if score >= 500:
        return "Fair"
    if score >= 350:
        return "Poor"
    return "Critical"
