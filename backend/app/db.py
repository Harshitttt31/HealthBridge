"""Database engine + session helpers (BRD §1 — SQLite via SQLModel).

The engine is created once from DATABASE_URL; `init_db()` creates tables on
startup, and `get_session()` is a FastAPI dependency yielding a scoped session.
"""

from __future__ import annotations

from collections.abc import Iterator

from sqlmodel import Session, SQLModel, create_engine

from app.config import get_settings

settings = get_settings()

# check_same_thread=False is the standard SQLite + threaded-server setting.
_connect_args = (
    {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
)
engine = create_engine(settings.database_url, echo=False, connect_args=_connect_args)


def init_db() -> None:
    """Create all tables. Importing models registers them on SQLModel.metadata."""
    from app import models  # noqa: F401  (side effect: table registration)

    SQLModel.metadata.create_all(engine)


def get_session() -> Iterator[Session]:
    """FastAPI dependency: yield a session, closing it after the request."""
    with Session(engine) as session:
        yield session
