"""Ingestion & schema validation (BRD §4, FR-02/03).

Parse an uploaded AHC or HRMS file (CSV or XLSX), reconcile the company key to
canonical `company_id`, and validate the schema. Problems are *reported*, never
silently dropped (Risk §15: "unmatched records reported, not silently dropped").

The two datasets differ structurally:
  - AHC  : single header row.
  - HRMS : a grouped banner row sits above the real header, so the true columns
           are on the second row — the loader auto-detects and re-reads.
"""

from __future__ import annotations

import io
from dataclasses import dataclass, field

import pandas as pd

from app.models import UploadKind
from app.pipeline import reconcile_company_id
from app.pipeline.companies import COMPANY_ID

# Columns each dataset must have for the pipeline to run. A missing required
# column fails validation; missing "expected" columns are warnings only.
_KEY_COLS = {COMPANY_ID, "CUG", "companyID"}

AHC_REQUIRED = {"employee_id", "age", "sex"}
AHC_EXPECTED_BIOMARKERS = {
    "hba1c_percent", "fbs_mg_dl", "systolic_bp_mmhg", "diastolic_bp_mmhg",
    "ldl_mg_dl", "hdl_mg_dl", "creatinine_mg_dl", "haemoglobin_g_dl", "bmi",
}

HRMS_REQUIRED = {"employee_id", "claim_id"}
HRMS_EXPECTED = {
    "department", "work_location", "band", "gender", "age",
    "absenteeism_percent_per_month",
    "insurance_claim_opd_inr", "insurance_claim_ipd_inr",
}


@dataclass
class ValidationResult:
    """Outcome of ingesting one file."""

    ok: bool
    kind: UploadKind
    row_count: int = 0
    employee_count: int = 0
    company_ids: list[str] = field(default_factory=list)
    missing_required: list[str] = field(default_factory=list)
    missing_expected: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    message: str = ""

    def as_dict(self) -> dict:
        return {
            "ok": self.ok,
            "kind": self.kind.value,
            "row_count": self.row_count,
            "employee_count": self.employee_count,
            "company_ids": self.company_ids,
            "missing_required": self.missing_required,
            "missing_expected": self.missing_expected,
            "warnings": self.warnings,
            "message": self.message,
        }


def _read_any(source: str | bytes | io.BytesIO, filename: str, header: int = 0) -> pd.DataFrame:
    """Read CSV or XLSX from a path or raw bytes, at the given header row."""
    is_csv = filename.lower().endswith(".csv")
    if isinstance(source, (bytes, bytearray)):
        source = io.BytesIO(source)
    if isinstance(source, io.BytesIO):
        source.seek(0)
    return pd.read_csv(source, header=header) if is_csv else pd.read_excel(source, header=header)


def _looks_headerless(cols) -> bool:
    """True when row 0 is HRMS's grouped banner (key columns absent / many 'Unnamed')."""
    cols = [str(c) for c in cols]
    has_key = any(c in _KEY_COLS or c == "employee_id" for c in cols)
    unnamed = sum(1 for c in cols if c.startswith("Unnamed"))
    return (not has_key) or unnamed >= max(2, len(cols) // 3)


def load_dataframe(source: str | bytes | io.BytesIO, filename: str,
                   kind: UploadKind) -> pd.DataFrame:
    """Load a dataset, auto-detecting HRMS's grouped two-row header."""
    df = _read_any(source, filename, header=0)
    if kind == UploadKind.hrms and _looks_headerless(df.columns):
        df = _read_any(source, filename, header=1)
    return df


def validate(source: str | bytes | io.BytesIO, filename: str,
             kind: UploadKind) -> tuple[pd.DataFrame | None, ValidationResult]:
    """Load + validate. Returns (reconciled_df_or_None, result).

    On a hard schema failure the dataframe is None and result.ok is False.
    """
    try:
        df = load_dataframe(source, filename, kind)
    except Exception as exc:  # parse failure
        return None, ValidationResult(ok=False, kind=kind,
                                      message=f"Could not read file: {exc}")

    cols = set(map(str, df.columns))
    required = AHC_REQUIRED if kind == UploadKind.ahc else HRMS_REQUIRED
    expected = AHC_EXPECTED_BIOMARKERS if kind == UploadKind.ahc else HRMS_EXPECTED

    # Company key is required but may arrive under any of its aliases.
    has_company_key = bool(_KEY_COLS & cols)
    missing_required = sorted(required - cols)
    if not has_company_key:
        missing_required.append("company_id (or CUG/companyID)")

    result = ValidationResult(
        ok=not missing_required,
        kind=kind,
        row_count=len(df),
        missing_required=missing_required,
        missing_expected=sorted(expected - cols),
    )
    if missing_required:
        result.message = "Missing required column(s): " + ", ".join(missing_required)
        return None, result

    # Reconcile and gather company / employee facts for the report.
    df = reconcile_company_id(df)
    result.company_ids = sorted(map(str, df[COMPANY_ID].dropna().unique()))
    if "employee_id" in df.columns:
        result.employee_count = int(df["employee_id"].nunique())

    # Soft warnings — surfaced to the uploader, not blocking.
    if df[COMPANY_ID].isna().any():
        result.warnings.append("Some rows have a blank company_id.")
    if "employee_id" in df.columns and df["employee_id"].isna().any():
        result.warnings.append("Some rows have a blank employee_id.")
    if kind == UploadKind.ahc and "employee_id" in df.columns:
        dupes = int(df["employee_id"].duplicated().sum())
        if dupes:
            result.warnings.append(f"{dupes} duplicate employee_id row(s) in AHC.")
    if result.missing_expected:
        result.warnings.append(
            "Missing expected (non-blocking) column(s): "
            + ", ".join(result.missing_expected)
        )

    n_co = len(result.company_ids)
    result.message = (
        f"OK: {result.row_count:,} rows, {result.employee_count:,} employees, "
        f"{n_co} company(ies)."
    )
    return df, result
