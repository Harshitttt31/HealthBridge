"""Seed demo users — one HR per real company, plus a single Health Provider.

Idempotent: existing emails are skipped, so it is safe to re-run. Credentials
are intentionally simple for the prototype:

    hr@<company_id>.demo     / demo1234   (role: hr       -> HRMS upload)
    provider@hclhealth.demo  / demo1234   (role: provider -> AHC upload for all companies)

Run (from backend/):  python -m app.seed
"""

from __future__ import annotations

from sqlmodel import Session, select

from app.auth import hash_password
from app.db import engine, init_db
from app.models import Role, User
from app.pipeline import COMPANY_NAMES

DEMO_PASSWORD = "demo1234"

# The single Health Provider account that uploads AHC data for all companies.
PROVIDER_EMAIL = "provider@hclhealth.demo"
PROVIDER_COMPANY_ID = "provider"  # sentinel; provider is not scoped to one company


def seed() -> None:
    init_db()
    created = 0
    with Session(engine) as session:
        # One HR user per company.
        for company_id in COMPANY_NAMES:
            email = f"hr@{company_id}.demo"
            if not session.exec(select(User).where(User.email == email)).first():
                session.add(User(
                    email=email,
                    hashed_password=hash_password(DEMO_PASSWORD),
                    role=Role.hr,
                    company_id=company_id,
                ))
                created += 1

        # Single provider account.
        if not session.exec(select(User).where(User.email == PROVIDER_EMAIL)).first():
            session.add(User(
                email=PROVIDER_EMAIL,
                hashed_password=hash_password(DEMO_PASSWORD),
                role=Role.provider,
                company_id=PROVIDER_COMPANY_ID,
            ))
            created += 1

        session.commit()

    total = len(COMPANY_NAMES) + 1
    print(f"Seed complete: {created} new users created ({total} demo users — "
          f"{len(COMPANY_NAMES)} HR + 1 provider). Password for all: {DEMO_PASSWORD}")


if __name__ == "__main__":
    seed()
