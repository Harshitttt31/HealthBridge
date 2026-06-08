"""Central config (BRD §14) — secrets and tunables loaded from the environment.

Secrets (HMAC_SECRET_KEY, JWT_SECRET) must come from a real .env in any non-dev
run; the dev fallbacks here exist only so the app boots on a fresh checkout and
are never safe to ship. See .env.example for the contract.
"""

from __future__ import annotations

import os
from functools import lru_cache

from dotenv import load_dotenv

# Load backend/.env if present; real env vars always win over the file.
load_dotenv()


class Settings:
    """Process-wide settings, read once from the environment."""

    def __init__(self) -> None:
        # Secrets — overridden in .env; dev fallbacks are insecure on purpose.
        self.hmac_secret_key: str = os.environ.get("HMAC_SECRET_KEY", "dev-only-insecure-key")
        self.jwt_secret: str = os.environ.get("JWT_SECRET", "dev-only-insecure-jwt")
        self.jwt_algorithm: str = os.environ.get("JWT_ALGORITHM", "HS256")
        self.jwt_expire_minutes: int = int(os.environ.get("JWT_EXPIRE_MINUTES", "480"))

        # Persistence — SQLite file lives next to the backend by default.
        self.database_url: str = os.environ.get("DATABASE_URL", "sqlite:///./healthbridge.db")

        # CORS — comma-separated list of allowed frontend origins.
        self.cors_origins: list[str] = [
            o.strip()
            for o in os.environ.get(
                "CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000"
            ).split(",")
            if o.strip()
        ]

    @property
    def is_dev_secret(self) -> bool:
        """True when either secret is still the insecure dev fallback."""
        return self.hmac_secret_key.startswith("dev-only") or self.jwt_secret.startswith("dev-only")


@lru_cache
def get_settings() -> Settings:
    return Settings()
