"""Tenant isolation for HRMS uploads (authorization boundary).

Acceptance criteria from spec:
  - jpm001 HR uploading a pure jpm001 file   -> accepted (None violation)
  - jpm001 HR uploading a pure accn001 file  -> rejected, foreign=[accn001]
  - jpm001 HR uploading jpm001 + accn001 mix -> rejected, foreign=[accn001]
  - file with no rows / no CUG column        -> rejected, found=[]
"""

from __future__ import annotations

import pandas as pd
import pytest

from app.ingestion import check_tenant_isolation
from app.pipeline.companies import COMPANY_ID


def _df(*cugs: str) -> pd.DataFrame:
    return pd.DataFrame({COMPANY_ID: list(cugs), "employee_id": range(len(cugs))})


def test_clean_file_passes():
    assert check_tenant_isolation(_df("jpm001", "jpm001"), "jpm001") is None


def test_wrong_tenant_rejected():
    v = check_tenant_isolation(_df("accn001", "accn001"), "jpm001")
    assert v is not None
    assert v.foreign == ["accn001"]
    assert "jpm001" in v.message()


def test_mixed_file_rejected():
    v = check_tenant_isolation(_df("jpm001", "accn001", "jpm001"), "jpm001")
    assert v is not None
    assert v.foreign == ["accn001"]


def test_empty_file_rejected():
    v = check_tenant_isolation(pd.DataFrame({COMPANY_ID: pd.Series([], dtype=str)}), "jpm001")
    assert v is not None
    assert v.found == []


def test_missing_cug_column_rejected():
    df = pd.DataFrame({"employee_id": ["E1", "E2"]})
    v = check_tenant_isolation(df, "jpm001")
    assert v is not None
    assert v.found == []


def test_multiple_foreign_cugs_rejected():
    v = check_tenant_isolation(_df("tcs001", "accn001"), "jpm001")
    assert v is not None
    assert set(v.foreign) == {"tcs001", "accn001"}


def test_violation_message_multi_company():
    v = check_tenant_isolation(_df("tcs001", "accn001"), "jpm001")
    msg = v.message()
    assert "multiple" in msg.lower() or "tcs001" in msg
