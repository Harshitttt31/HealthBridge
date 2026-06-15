"""Step 3 — tokenise IDs (BRD §6).

Replace `employee_id` with a keyed HMAC-SHA256 token. Deterministic, so the same
employee maps to the same token in both datasets and they can be joined in Step 4
without ever exposing the raw id. The key comes from HMAC_SECRET_KEY (never a bare
hash, never committed).
"""

from __future__ import annotations

import hashlib
import hmac
import os

import pandas as pd


def _hmac_token(employee_id: str, key: bytes) -> str:
    return hmac.new(key, str(employee_id).encode(), hashlib.sha256).hexdigest()[:32]


def step3_tokenize(df: pd.DataFrame, key: bytes | None = None) -> pd.DataFrame:
    """Add a deterministic HMAC-SHA256 `token` column derived from employee_id."""
    if key is None:
        secret = os.environ.get("HMAC_SECRET_KEY", "dev-only-insecure-key")
        key = secret.encode()
    out = df.copy()
    out["token"] = out["employee_id"].map(lambda e: _hmac_token(e, key))
    return out
