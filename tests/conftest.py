"""Shared test fixtures: an isolated in-memory database."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from fah.db.models import Base


@pytest.fixture()
def db() -> Iterator[Session]:
    # StaticPool keeps a single shared connection so the in-memory DB is visible across threads —
    # required because TestClient runs sync routes in a worker thread, not the test thread.
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    TestSession = sessionmaker(bind=engine, expire_on_commit=False)
    session = TestSession()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()
