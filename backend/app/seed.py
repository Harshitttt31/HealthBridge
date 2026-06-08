"""Seed demo users (BRD §5) — one HR + one Employer per real company.

Idempotent: existing emails are skipped, so it is safe to re-run. Credentials
are intentionally simple for the prototype:

    hr@<company_id>.demo        / demo1234   (role: hr        -> HRMS upload)
    employer@<company_id>.demo  / demo1234   (role: employer  -> AHC upload)

Run (from backend/):  python -m app.seed
"""

from __future__ import annotations

from sqlmodel import Session, select

from app.auth import hash_password
from app.db import engine, init_db
from app.models import Role, User
from app.pipeline import COMPANY_NAMES

DEMO_PASSWORD = "demo1234"


def seed() -> None:
    init_db()
    created = 0
    with Session(engine) as session:
        for company_id in COMPANY_NAMES:
            for role, prefix in ((Role.hr, "hr"), (Role.employer, "employer")):
                email = f"{prefix}@{company_id}.demo"
                exists = session.exec(select(User).where(User.email == email)).first()
                if exists:
                    continue
                session.add(User(
                    email=email,
                    hashed_password=hash_password(DEMO_PASSWORD),
                    role=role,
                    company_id=company_id,
                ))
                created += 1
        session.commit()
    total = len(COMPANY_NAMES) * 2
    print(f"Seed complete: {created} new users created ({total} demo users across "
          f"{len(COMPANY_NAMES)} companies). Password for all: {DEMO_PASSWORD}")


if __name__ == "__main__":
    seed()
