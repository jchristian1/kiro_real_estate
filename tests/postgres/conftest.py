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

    We set DATABASE_URL in the environment before invoking Alembic so that
    migrations/env.py picks up the Postgres URL (it reads DATABASE_URL and
    falls back to the alembic.ini SQLite default otherwise).
    """
    import os as _os

    engine = create_engine(pg_base_url, echo=False)

    # Apply migrations via Alembic — must set DATABASE_URL so env.py uses Postgres
    from alembic.config import Config as AlembicConfig
    from alembic import command as alembic_command

    _prev_db_url = _os.environ.get("DATABASE_URL")
    _os.environ["DATABASE_URL"] = pg_base_url
    try:
        alembic_cfg = AlembicConfig("alembic.ini")
        alembic_command.upgrade(alembic_cfg, "head")
    finally:
        if _prev_db_url is None:
            _os.environ.pop("DATABASE_URL", None)
        else:
            _os.environ["DATABASE_URL"] = _prev_db_url

    yield engine

    # Teardown: drop and recreate the public schema — faster and more reliable
    # than running `alembic downgrade base` through the full historical chain
    # (many old migrations have SQLite-specific DDL in their downgrade paths).
    with engine.connect() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))
        conn.commit()

    engine.dispose()


@pytest.fixture(scope="function")
def pg_session(pg_engine):
    """
    Function-scoped session — each test gets a fresh savepoint that is
    rolled back on teardown so tests are fully isolated.

    We use begin_nested() (SAVEPOINT) so that repository calls to
    session.commit() flush to the savepoint without committing the outer
    transaction.  The outer transaction is rolled back at teardown.
    """
    connection = pg_engine.connect()
    outer_transaction = connection.begin()
    # Wrap in a savepoint so repo commits don't escape to the real DB
    nested = connection.begin_nested()
    Session = sessionmaker(bind=connection, join_transaction_mode="create_savepoint")
    session = Session()

    yield session

    session.close()
    # Roll back to the savepoint, then roll back the outer transaction
    if nested.is_active:
        nested.rollback()
    outer_transaction.rollback()
    connection.close()
