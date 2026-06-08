"""Persistence model (BRD §3 repo layout, §10 endpoints) — SQLModel tables.

Only three things are stored: the demo users, a row of metadata per upload, and
the final group-level results. Per the privacy rules (§6 Step 4) the sensitive
token-linked employee table is NEVER persisted — nothing here holds an
individual's row after de-identification.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from enum import Enum

from sqlmodel import Field, SQLModel


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Role(str, Enum):
    """The two BRD roles (FR-01). HR uploads HRMS; Employer uploads AHC."""

    hr = "hr"
    employer = "employer"


class UploadKind(str, Enum):
    ahc = "ahc"
    hrms = "hrms"


class UploadStatus(str, Enum):
    received = "received"      # file parsed + steps 1-3 run, de-identified set stored
    processed = "processed"    # rolled into a /process run
    failed = "failed"


class User(SQLModel, table=True):
    """An HR or Employer user, scoped to exactly one company (§5)."""

    id: int | None = Field(default=None, primary_key=True)
    email: str = Field(index=True, unique=True)
    hashed_password: str
    role: Role
    company_id: str = Field(index=True)
    created_at: datetime = Field(default_factory=_utcnow)


class Upload(SQLModel, table=True):
    """Metadata for one dataset upload. The data itself lives outside the DB;
    this row just tracks what was uploaded, by whom, and its pipeline status."""

    id: int | None = Field(default=None, primary_key=True)
    company_id: str = Field(index=True)
    kind: UploadKind
    status: UploadStatus = UploadStatus.received
    filename: str | None = None
    row_count: int = 0
    message: str | None = None          # validation notes / failure reason
    created_at: datetime = Field(default_factory=_utcnow)


class GroupResult(SQLModel, table=True):
    """One k>=20 cohort's aggregated Group Health Index (§9). The only
    analysis output that leaves the processing layer is stored here."""

    id: int | None = Field(default=None, primary_key=True)
    company_id: str = Field(index=True)
    cohort_label: str
    n: int                              # cohort size, always >= 20
    payload_json: str                   # serialized cohort aggregate (health + claims)
    created_at: datetime = Field(default_factory=_utcnow)

    @property
    def payload(self) -> dict:
        return json.loads(self.payload_json)

    @classmethod
    def from_payload(cls, company_id: str, cohort_label: str, n: int,
                     payload: dict) -> "GroupResult":
        return cls(
            company_id=company_id,
            cohort_label=cohort_label,
            n=n,
            payload_json=json.dumps(payload),
        )
