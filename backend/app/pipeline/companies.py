"""Company reconciliation (BRD §4.1).

Both datasets already carry the real company key in a `CUG` column (10 real
companies, e.g. jpm001 -> "JPMorgan Chase"). We rename it to the canonical
`company_id`; HRMS additionally carries `company_name`, the source of the
code->name display map.
"""

from __future__ import annotations

import pandas as pd

COMPANY_KEY_SRC = "CUG"          # AHC + HRMS both use this; HRMS spec also allows companyID
COMPANY_ID = "company_id"

# Fallback display names for the 10 known companies, used when a HRMS-derived
# map isn't available (e.g. scoring AHC in isolation).
COMPANY_NAMES = {
    "accn001": "Accenture",
    "cisco001": "Cisco Systems",
    "dell001": "Dell Technologies",
    "ibm001": "IBM",
    "infy001": "Infosys",
    "jpm001": "JPMorgan Chase",
    "orcl001": "Oracle",
    "sap001": "SAP",
    "tcs001": "Tata Consultancy Services",
    "wipro001": "Wipro",
}


def reconcile_company_id(df: pd.DataFrame) -> pd.DataFrame:
    """Rename the source company key (`CUG`/`companyID`) to canonical `company_id`.

    Idempotent: a frame that already has `company_id` is returned unchanged.
    """
    if COMPANY_ID in df.columns:
        return df
    for src in (COMPANY_KEY_SRC, "companyID"):
        if src in df.columns:
            return df.rename(columns={src: COMPANY_ID})
    raise KeyError(f"No company key found; expected one of CUG/companyID/{COMPANY_ID}")


def build_company_names(hrms: pd.DataFrame) -> dict[str, str]:
    """Derive a {company_id: company_name} map from the HRMS `company_name` column.

    Falls back to the static COMPANY_NAMES for any code the HRMS map misses.
    """
    df = reconcile_company_id(hrms)
    names = dict(COMPANY_NAMES)
    if "company_name" in df.columns:
        derived = (
            df.dropna(subset=[COMPANY_ID, "company_name"])
            .drop_duplicates(COMPANY_ID)
            .set_index(COMPANY_ID)["company_name"]
            .to_dict()
        )
        names.update(derived)
    return names
