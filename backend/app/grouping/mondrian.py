"""Mondrian k-anonymity grouping (BRD §7/§8).

Within a single company, partition employees into cohorts of size >= K (K=20),
recursively splitting on the quasi-identifier whose split most reduces the
within-group variance of the Health Index — i.e. the most analytically
meaningful cut. This is how the portal "decides the most important factors".
"""

from __future__ import annotations

import numpy as np
import pandas as pd

QUASI_IDS = ["department", "work_location", "age_band", "gender", "band"]
K = 20


def age_band(age: pd.Series) -> pd.Series:
    bins = [0, 30, 40, 50, 200]
    labels = ["<30", "30-39", "40-49", "50+"]
    return pd.cut(age, bins=bins, right=False, labels=labels).astype(str)


def _weighted_within_variance(df: pd.DataFrame, dim: str, target: str) -> float:
    """Size-weighted mean of per-subgroup variance of `target` after splitting on `dim`."""
    n = len(df)
    total = 0.0
    for _, sub in df.groupby(dim, observed=True):
        total += len(sub) * float(np.var(sub[target].to_numpy()))
    return total / n


def _best_split_dimension(df: pd.DataFrame, dims: list[str], target: str):
    """Pick the dim whose valid split (all children >= K, >1 child) most reduces
    within-group variance. Returns dim name or None if no valid split exists."""
    best_dim, best_var = None, None
    for dim in dims:
        counts = df[dim].value_counts()
        if len(counts) < 2 or counts.min() < K:
            continue  # splitting here would create a sub-K group
        var = _weighted_within_variance(df, dim, target)
        if best_var is None or var < best_var:
            best_dim, best_var = dim, var
    return best_dim


def mondrian(df: pd.DataFrame, quasi_ids: list[str] = QUASI_IDS, target: str = "health_index"):
    """Return a list of cohort DataFrames, each with n >= K, none spanning companies.

    Assumes `df` is already a single company's rows.
    """
    cohorts = []
    stack = [df]
    while stack:
        part = stack.pop()
        dim = _best_split_dimension(part, quasi_ids, target)
        if dim is None:
            cohorts.append(part)
            continue
        children = [sub for _, sub in part.groupby(dim, observed=True)]
        # Guard (best_split already guarantees >= K, but stay defensive).
        if all(len(c) >= K for c in children) and len(children) > 1:
            stack.extend(children)
        else:
            cohorts.append(part)
    return cohorts


def label_for_cohort(cohort: pd.DataFrame, quasi_ids: list[str] = QUASI_IDS) -> dict:
    """Generalized label: only the quasi-ids that are constant within the cohort."""
    fixed = {}
    for q in quasi_ids:
        vals = cohort[q].unique()
        fixed[q] = str(vals[0]) if len(vals) == 1 else "All"
    return fixed
