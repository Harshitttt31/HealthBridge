"""Privacy invariants (BRD §13 acceptance criteria).

Covers the non-negotiable de-identification rules:
  - direct identifiers do not survive Step 1
  - Step 3 tokenisation is deterministic, keyed (not a bare hash), and identical
    across both datasets for the same employee_id
  - Step 4 destroys the token + employee_id
  - the final combined table carries no name / contact / employee_id / token
"""

from __future__ import annotations

import hashlib

from app.pipeline import (
    aggregate_hrms_to_employee, reconcile_company_id, step1_deidentify,
    step3_tokenize, step4_combine, AHC_IDENTIFIERS, HRMS_IDENTIFIERS,
)

from tests.conftest import AHC_IDENTIFIER_COLS, HRMS_IDENTIFIER_COLS, TEST_KEY


# --- Step 1: identifiers stripped ------------------------------------------
def test_step1_drops_ahc_identifiers(ahc_raw):
    out = step1_deidentify(ahc_raw, AHC_IDENTIFIERS)
    for col in AHC_IDENTIFIER_COLS:
        assert col not in out.columns
    assert "employee_id" in out.columns  # kept for Step 3, dropped in Step 4


def test_step1_drops_hrms_identifiers(hrms_raw):
    out = step1_deidentify(hrms_raw, HRMS_IDENTIFIERS)
    for col in HRMS_IDENTIFIER_COLS:
        assert col not in out.columns


# --- Step 3: tokenisation properties ---------------------------------------
def test_token_is_deterministic(ahc_raw):
    t1 = step3_tokenize(ahc_raw, key=TEST_KEY)["token"]
    t2 = step3_tokenize(ahc_raw, key=TEST_KEY)["token"]
    assert list(t1) == list(t2)


def test_token_identical_across_datasets(ahc_raw, hrms_raw):
    ahc_t = step3_tokenize(ahc_raw, key=TEST_KEY).set_index("employee_id")["token"]
    hrms_t = step3_tokenize(hrms_raw, key=TEST_KEY).set_index("employee_id")["token"]
    shared = "JPM0000001"
    assert ahc_t[shared] == hrms_t.loc[shared].iloc[0]


def test_token_is_keyed_not_bare_hash(ahc_raw):
    """A bare SHA-256 of the id must NOT equal the token (HMAC keying required)."""
    token = step3_tokenize(ahc_raw, key=TEST_KEY)["token"].iloc[0]
    eid = ahc_raw["employee_id"].iloc[0]
    bare = hashlib.sha256(eid.encode()).hexdigest()[:32]
    assert token != bare


def test_token_changes_with_key(ahc_raw):
    a = step3_tokenize(ahc_raw, key=b"key-A")["token"].iloc[0]
    b = step3_tokenize(ahc_raw, key=b"key-B")["token"].iloc[0]
    assert a != b


# --- Step 4: token + employee_id destroyed ---------------------------------
def _combined(ahc_raw, hrms_raw):
    ahc = step3_tokenize(reconcile_company_id(
        step1_deidentify(ahc_raw, AHC_IDENTIFIERS)), key=TEST_KEY)
    hrms = step3_tokenize(reconcile_company_id(
        step1_deidentify(hrms_raw, HRMS_IDENTIFIERS)), key=TEST_KEY)
    return step4_combine(ahc, aggregate_hrms_to_employee(hrms))


def test_step4_drops_token_and_employee_id(ahc_raw, hrms_raw):
    combined = _combined(ahc_raw, hrms_raw)
    assert "token" not in combined.columns
    assert "employee_id" not in combined.columns


def test_combined_table_has_no_identifiers(ahc_raw, hrms_raw):
    combined = _combined(ahc_raw, hrms_raw)
    forbidden = set(AHC_IDENTIFIER_COLS + HRMS_IDENTIFIER_COLS + ["employee_id", "token"])
    assert forbidden.isdisjoint(combined.columns)


def test_step4_matches_on_token(ahc_raw, hrms_raw):
    """All 3 shared employees join; each collapses to exactly one scored row
    (JPM0000001's two claims aggregate to one employee row)."""
    combined = _combined(ahc_raw, hrms_raw)
    assert len(combined) == 3
    assert set(combined["company_id"]) == {"jpm001", "tcs001"}
