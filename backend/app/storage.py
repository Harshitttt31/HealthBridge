"""De-identified dataset storage (BRD §6, §10).

After steps 1-3, each dataset is stored per (company_id, kind) so that /process
can later combine a company's AHC + HRMS. This holds token-bearing but
identifier-free data; the token-linked *combined* table is never written here.

Backed by parquet files under a gitignored storage dir.
"""

from __future__ import annotations

import os

import pandas as pd

from app.models import UploadKind

STORAGE_DIR = os.environ.get(
    "STORAGE_DIR", os.path.join(os.path.dirname(os.path.dirname(__file__)), "storage")
)


def _path(company_id: str, kind: UploadKind) -> str:
    safe = "".join(ch for ch in company_id if ch.isalnum() or ch in "-_")
    return os.path.join(STORAGE_DIR, f"{safe}__{kind.value}.parquet")


def save_deident(company_id: str, kind: UploadKind, df: pd.DataFrame) -> str:
    """Persist a company's de-identified dataset, overwriting any prior upload."""
    os.makedirs(STORAGE_DIR, exist_ok=True)
    path = _path(company_id, kind)
    df.to_parquet(path, index=False)
    return path


def load_deident(company_id: str, kind: UploadKind) -> pd.DataFrame:
    return pd.read_parquet(_path(company_id, kind))


def has_deident(company_id: str, kind: UploadKind) -> bool:
    return os.path.exists(_path(company_id, kind))
