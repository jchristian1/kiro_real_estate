"""
Shared fixtures for the Postgres-backed test suite.

These tests require a real PostgreSQL instance.  They are skipped
automatically when POSTGRES_TEST_URL is not set in the environment.

Set the env var to run them:

    export POSTGRES_TEST_URL=postgresql://user:pass@localhost:5432/test_db
    pytest tests/postgres/ -v

Or run via the Makefile target:

    make test-postgres

The database named in POSTGRES_TEST_URL must already exist.
Alembic migrations are applied fresh at the start of each session and
torn down at the end.
"""

from __future__ import annotations

import os
import uuid

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# ---------------------------------------------------------------------------
# Skip the entire suite when no Postgres URL is configured
# ---------------------------------------------------------------------------

POSTGRES_TEST_URL = os.environ.get("POSTGRES_TEST_URL", "")

collect_ignore_glob: list[str] = []

if not POSTGRES_TEST_URL:
    # Mark every test in this package as skipped at collection time
    def pytest_collection_modifyitems(items, config):
        skip = pytest.mark.skip(
            reason="POSTGRES_TEST_URL not set — skipping Postgres suite"
        )
        for item in items:
            if "postgres" in str(item.fspath):
                item.add_marker(skip)


# ---------------------------------------------------------------------------
# Session-scoped engine — one Postgres connection per test session
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def pg_base_url() -> str:
    """Return the Postgres URL or skip the test."""
    url = os.environ.get("POSTGRES_TEST_URL", "")
    if not url:
        pytest.skip("POSTGRES_TEST_URL not set")
    return url


@pytest.fixture(scope="session")
def pg_engine(pg_base_url):
    """
    Session-scoped SQLAlchemy engine connected to the test Postgres DB.

    Applies all Alembic migrations on setup and drops all tables on teardown.
    """
    engine = create_engine(pg_base_url, echo=False)

    # Apply migrations via Alembic
    from alembic.config import Config as AlembicConfig
    from alembic import command as alembic_command

    alembic_cfg = AlembicConfig("alembic.ini")
    alembic_cfg.set_main_option("sqlalchemy.url", pg_base_url)
    alembic_command.upgrade(alembic_cfg, "head")

    yield engine

    # Teardown: drop all tables so the DB is clean for the next run
    alembic_command.downgrade(alembic_cfg, "base")
    engine.dispose()


@pytest.fixture(scope="function")
def pg_session(pg_engine):
    """
    Function-scoped session — each test gets a fresh transaction that is
    rolled back on teardown so tests are fully isolated.
    """
    connection = pg_engine.connect()
    transaction = connection.begin()
    Session = sessionmaker(bind=connection)
    session = Session()

    yield session

    session.close()
    transaction.rollback()
    connection.close()
