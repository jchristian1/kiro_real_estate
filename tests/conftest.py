"""
Shared pytest fixtures for all test suites.

Provides a properly configured SQLite in-memory database engine using
StaticPool so that all connections share the same in-memory database.
This is required because SQLite :memory: databases are per-connection by
default — without StaticPool, create_all() and the test session would
see different databases.
"""

import pytest
from sqlalchemy import create_engine, StaticPool
from sqlalchemy.orm import sessionmaker

# Import all models so that Base.metadata is fully populated before
# any fixture calls create_all().
from gmail_lead_sync.models import Base  # noqa: F401
import gmail_lead_sync.agent_models  # noqa: F401 — registers AgentUser etc.
import api.models.web_ui_models  # noqa: F401 — registers User, Session, etc.


@pytest.fixture(autouse=True)
def reset_imap_rate_limiter():
    """Reset the IMAP rate limiter before each test to prevent cross-test pollution."""
    from api.services.imap_service import _attempt_timestamps, _lock
    with _lock:
        _attempt_timestamps.clear()
    yield
    with _lock:
        _attempt_timestamps.clear()


@pytest.fixture
def db_engine():
    """
    In-memory SQLite engine shared across all connections via StaticPool.

    StaticPool ensures that every SQLAlchemy connection (including the one
    used by create_all and the one used by the test session) talks to the
    same in-memory database.
    """
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)


@pytest.fixture
def db_session(db_engine):
    """Yield a SQLAlchemy session bound to the test engine."""
    SessionLocal = sessionmaker(bind=db_engine)
    session = SessionLocal()
    yield session
    session.close()
