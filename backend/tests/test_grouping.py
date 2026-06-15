"""Grouping invariants (BRD §13).

  - every cohort returned by Mondrian has n >= K (20)
  - no cohort spans more than one company_id
  - the engine still splits when a valid k-preserving split exists
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from app.grouping.mondrian import K, mondrian

DEPARTMENTS = ["Engineering", "Operations", "Sales"]
LOCATIONS = ["Bangalore", "Pune"]
AGE_BANDS = ["<30", "30-39", "40-49", "50+"]
GENDERS = ["M", "F"]
JOB_BANDS = ["L2", "L3", "L4"]


def _population(n: int, company_id: str, seed: int) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    return pd.DataFrame({
        "company_id": company_id,
        "department": rng.choice(DEPARTMENTS, n),
        "work_location": rng.choice(LOCATIONS, n),
        "age_band": rng.choice(AGE_BANDS, n),
        "gender": rng.choice(GENDERS, n),
        "band": rng.choice(JOB_BANDS, n),
        "health_index": rng.integers(300, 950, n),
    })


def test_every_cohort_meets_k():
    cohorts = mondrian(_population(600, "jpm001", 1))
    assert cohorts, "expected at least one cohort"
    assert all(len(c) >= K for c in cohorts)


def test_no_cohort_spans_companies():
    # Group each company independently (as /process does); every cohort must be
    # single-company.
    for cid, seed in [("jpm001", 2), ("tcs001", 3)]:
        for cohort in mondrian(_population(500, cid, seed)):
            assert set(cohort["company_id"]) == {cid}


def test_engine_actually_splits():
    # With 600 well-distributed rows the engine should produce multiple cohorts,
    # not dump everyone into one bucket.
    cohorts = mondrian(_population(600, "jpm001", 4))
    assert len(cohorts) > 1


def test_small_population_stays_one_cohort():
    # Below 2*K no split can keep both children >= K, so it must stay whole.
    pop = _population(25, "jpm001", 5)
    cohorts = mondrian(pop)
    assert len(cohorts) == 1
    assert len(cohorts[0]) == 25
