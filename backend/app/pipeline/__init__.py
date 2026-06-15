"""Privacy pipeline (BRD §6) — ordered, pure-ish DataFrame transforms.

Per dataset:   Step 1 de-identify -> Step 2 noise -> Step 3 tokenize
Both present:  Step 4 combine (join on (company_id, token), drop token)
On aggregates: Step 5 release (k>=20 floor + optional DP noise)

The token-linked combined table is in-memory only and is never written to disk.
This package re-exports each step so callers can `from app.pipeline import step4_combine`.
"""

from app.pipeline.companies import (
    COMPANY_ID,
    COMPANY_KEY_SRC,
    COMPANY_NAMES,
    build_company_names,
    reconcile_company_id,
)
from app.pipeline.step1_deidentify import (
    AHC_IDENTIFIERS,
    HRMS_IDENTIFIERS,
    step1_deidentify,
)
from app.pipeline.step2_noise import (
    AHC_NOISE_COLS,
    HRMS_NOISE_COLS,
    step2_noise,
)
from app.pipeline.step3_tokenize import step3_tokenize
from app.pipeline.step4_combine import aggregate_hrms_to_employee, step4_combine
from app.pipeline.step5_release import enforce_k, step5_release
from app.pipeline.hra import (
    HRA_FIELDS,
    apply_three_pillar,
    has_hra_columns,
    split_hra,
)

__all__ = [
    "COMPANY_ID", "COMPANY_KEY_SRC", "COMPANY_NAMES",
    "reconcile_company_id", "build_company_names",
    "AHC_IDENTIFIERS", "HRMS_IDENTIFIERS", "step1_deidentify",
    "AHC_NOISE_COLS", "HRMS_NOISE_COLS", "step2_noise",
    "step3_tokenize",
    "aggregate_hrms_to_employee", "step4_combine",
    "enforce_k", "step5_release",
    "HRA_FIELDS", "apply_three_pillar", "has_hra_columns", "split_hra",
]
