"""Database engine, session factory, and schema/initialisation helpers."""

from __future__ import annotations

import logging
from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from fah.config import get_settings
from fah.db.models import Base

logger = logging.getLogger("fah.db")

_settings = get_settings()

# SQLite needs check_same_thread=False for FastAPI's threadpool; harmless for other backends.
_connect_args = (
    {"check_same_thread": False} if _settings.database_url.startswith("sqlite") else {}
)

engine: Engine = create_engine(
    _settings.database_url, connect_args=_connect_args, future=True
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)


@event.listens_for(Engine, "connect")
def _enable_sqlite_fk(dbapi_connection, _connection_record) -> None:  # type: ignore[no-untyped-def]
    """Enforce foreign keys on SQLite (off by default)."""
    if _settings.database_url.startswith("sqlite"):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


def init_db() -> None:
    """Create all tables and the data directories. Idempotent."""
    _settings.ensure_dirs()
    Base.metadata.create_all(bind=engine)
    logger.info("Schema ensured at %s", _settings.database_url)


def get_db() -> Iterator[Session]:
    """FastAPI dependency — yields a session and always closes it."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def session_scope() -> Iterator[Session]:
    """Transactional scope for scripts/tests: commits on success, rolls back on error."""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
