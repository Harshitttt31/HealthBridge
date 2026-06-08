"""End-to-end + performance acceptance (BRD §13).

Drives the real API surface (login -> upload -> process -> results) over the
actual 100k AHC/HRMS datasets and asserts:
  - a 100k-row upload processes end-to-end on a laptop in minutes (NFR-05)
  - every released cohort has n >= 20
  - company isolation: another company sees nothing
  - no identifier ever appears in a released payload

Opt-in: set RUN_E2E=1 (and optionally AHC_PATH / HRMS_PATH). Skipped otherwise,
so the normal suite stays fast. Uses a throwaway DB + storage dir.
"""

from __future__ import annotations

import os
import tempfile
import time

import pytest

_RUN = os.environ.get("RUN_E2E")
_AHC = os.environ.get(
    "AHC_PATH", r"C:\Users\PC\Downloads\healthbridge_ahc_full_panel_100k.csv")
_HRMS = os.environ.get(
    "HRMS_PATH", r"C:\Users\PC\Downloads\healthbridge_hrms_100k.csv")

pytestmark = pytest.mark.skipif(
    not (_RUN and os.path.exists(_AHC) and os.path.exists(_HRMS)),
    reason="set RUN_E2E=1 and provide the real AHC/HRMS datasets",
)

# Isolate persistence BEFORE importing the app (settings are cached at import).
_TMP = tempfile.mkdtemp(prefix="hb_e2e_")
os.environ["DATABASE_URL"] = f"sqlite:///{_TMP.replace(os.sep, '/')}/e2e.db"
os.environ["STORAGE_DIR"] = os.path.join(_TMP, "storage")
os.environ.setdefault("HMAC_SECRET_KEY", "e2e-test-key")
os.environ.setdefault("JWT_SECRET", "e2e-jwt-key")

# Forbidden columns in any released cohort payload.
_FORBIDDEN = {"name", "full_name", "employee_id", "token", "official_email",
              "phone_number", "uan_number", "pf_account_number"}

# Time budget for "in minutes" (generous for a laptop).
_BUDGET_S = 600


def _payload_strings(obj) -> list[str]:
    """Flatten all dict keys in a nested payload for identifier scanning."""
    keys = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            keys.append(str(k))
            keys.extend(_payload_strings(v))
    elif isinstance(obj, list):
        for v in obj:
            keys.extend(_payload_strings(v))
    return keys


def test_full_pipeline_100k():
    from fastapi.testclient import TestClient

    from app.main import app
    from app.seed import seed

    seed()
    client = TestClient(app)

    def token(email: str) -> str:
        r = client.post("/auth/login", json={"email": email, "password": "demo1234"})
        assert r.status_code == 200, r.text
        return r.json()["access_token"]

    employer = {"Authorization": f"Bearer {token('employer@jpm001.demo')}"}
    hr = {"Authorization": f"Bearer {token('hr@jpm001.demo')}"}
    other = {"Authorization": f"Bearer {token('employer@tcs001.demo')}"}

    t0 = time.time()

    # Upload the full 100k AHC + HRMS (isolation keeps only jpm001 rows).
    # Send the raw CSV bytes straight through — no Excel round-trip.
    with open(_AHC, "rb") as f:
        ahc_bytes = f.read()
    r = client.post("/upload/ahc", headers=employer,
                    files={"file": ("ahc.csv", ahc_bytes, "text/csv")})
    assert r.status_code == 200, r.text
    assert r.json()["rows_stored"] > 0

    with open(_HRMS, "rb") as f:
        hrms_bytes = f.read()
    r = client.post("/upload/hrms", headers=hr,
                    files={"file": ("hrms.csv", hrms_bytes, "text/csv")})
    assert r.status_code == 200, r.text

    # Process.
    r = client.post("/process", headers=employer)
    assert r.status_code == 200, r.text
    elapsed = time.time() - t0
    assert elapsed < _BUDGET_S, f"end-to-end took {elapsed:.0f}s (> {_BUDGET_S}s)"

    # Results: every cohort k>=20, no identifiers leaked.
    groups = client.get("/results/groups", headers=employer).json()
    assert groups["processed"] and groups["cohort_count"] > 0
    for cohort in groups["cohorts"]:
        assert cohort["n"] >= 20
        leaked = _FORBIDDEN & set(_payload_strings(cohort))
        assert not leaked, f"identifier leaked into payload: {leaked}"

    summary = client.get("/results/summary", headers=employer).json()
    assert summary["employees_covered"] > 0
    assert 0 <= summary["avg_health_score"] <= 1000

    # Isolation: a different company that never processed sees nothing.
    other_groups = client.get("/results/groups", headers=other).json()
    assert other_groups["processed"] is False
    assert other_groups["cohort_count"] == 0

    print(f"\nE2E ok: {groups['cohort_count']} cohorts, "
          f"{summary['employees_covered']} employees, {elapsed:.0f}s")
