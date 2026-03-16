"""
Property-based tests for authentication failure logging.

# Feature: production-hardening, Property 19: Auth failure logs contain username and IP but not password

**Property 19: Auth failure logs contain username and IP but not password** —
for any failed authentication attempt, the resulting log entry at WARNING level
SHALL contain the ``username_attempted`` and ``source_ip`` fields and SHALL NOT
contain the attempted password string.

**Validates: Requirements 11.8**
"""

import logging
import uuid
from typing import List

import pytest
from fastapi.testclient import TestClient
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import gmail_lead_sync.agent_models  # noqa: F401 — registers agent tables
from api.main import app, get_db
from gmail_lead_sync.models import Base

# ---------------------------------------------------------------------------
# In-memory SQLite test database
# ---------------------------------------------------------------------------

_DB_NAME = f"prop_auth_logging_{uuid.uuid4().hex}"

engine = create_engine(
    f"sqlite:///file:{_DB_NAME}?mode=memory&cache=shared&uri=true",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    app.dependency_overrides[get_db] = override_get_db
    yield
    Base.metadata.drop_all(bind=engine)
    app.dependency_overrides.pop(get_db, None)


# ---------------------------------------------------------------------------
# Log capture helper
# ---------------------------------------------------------------------------


class CapturingHandler(logging.Handler):
    """Captures log records for inspection."""

    def __init__(self):
        super().__init__()
        self.records: List[logging.LogRecord] = []

    def emit(self, record: logging.LogRecord):
        self.records.append(record)

    def get_warning_messages(self) -> List[str]:
        """Return formatted messages from WARNING-level records."""
        return [
            self.format(record)
            for record in self.records
            if record.levelno >= logging.WARNING
        ]

    def get_all_messages(self) -> List[str]:
        """Return all formatted messages."""
        return [self.format(record) for record in self.records]


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

# Random usernames (email-like for agent, plain for admin)
_username_strategy = st.text(
    alphabet=st.characters(
        whitelist_categories=("Ll", "Lu", "Nd"),
        whitelist_characters="._-",
    ),
    min_size=3,
    max_size=30,
)

_email_strategy = st.builds(
    lambda local, domain: f"{local}@{domain}.com",
    local=st.text(
        alphabet="abcdefghijklmnopqrstuvwxyz0123456789",
        min_size=3,
        max_size=15,
    ),
    domain=st.text(
        alphabet="abcdefghijklmnopqrstuvwxyz",
        min_size=3,
        max_size=10,
    ),
)

# Random passwords — must be non-empty and not overlap with username
_password_strategy = st.text(
    alphabet=st.characters(
        whitelist_categories=("Ll", "Lu", "Nd"),
        whitelist_characters="!@#$%^&*",
    ),
    min_size=8,
    max_size=30,
)


# ---------------------------------------------------------------------------
# Property 19: Auth failure logs contain username and IP but not password
# ---------------------------------------------------------------------------


class TestProperty19AuthFailureLogging:
    """
    Property 19: Auth failure logs contain username and IP but not password.
    **Validates: Requirements 11.8**
    """

    @given(
        username=_username_strategy,
        password=_password_strategy,
    )
    @settings(
        max_examples=50,
        deadline=None,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
    )
    def test_admin_login_failure_logs_username_not_password(
        self, setup_db, username: str, password: str
    ):
        """
        # Feature: production-hardening, Property 19: Auth failure logs contain username and IP but not password
        **Validates: Requirements 11.8**

        For any failed admin login attempt, the WARNING log entry SHALL contain
        the username_attempted and SHALL NOT contain the attempted password.
        """
        Base.metadata.create_all(bind=engine)
        app.dependency_overrides[get_db] = override_get_db

        handler = CapturingHandler()
        handler.setFormatter(logging.Formatter("%(message)s %(extra)s", defaults={"extra": ""}))
        handler.setLevel(logging.WARNING)

        # Capture from the auth logger
        auth_logger = logging.getLogger("api.auth")
        auth_logger.addHandler(handler)

        try:
            with TestClient(app, raise_server_exceptions=False) as client:
                resp = client.post(
                    "/api/v1/auth/login",
                    json={"username": username, "password": password},
                )
        finally:
            auth_logger.removeHandler(handler)

        # Should be 401 (invalid credentials) or 422 (validation error)
        # We only check logging for actual auth failures (401)
        if resp.status_code == 401:
            warning_records = [
                r for r in handler.records
                if r.levelno >= logging.WARNING
            ]
            assert warning_records, (
                f"No WARNING log entry produced for failed admin login "
                f"(username={username!r})"
            )

            # Check that username appears in the log
            found_username = False
            found_password = False
            for record in warning_records:
                msg = record.getMessage()
                # Check extra fields
                extra_str = str(getattr(record, "username_attempted", ""))
                if username in msg or username in extra_str:
                    found_username = True
                if password in msg or password in extra_str:
                    found_password = True

            assert found_username, (
                f"Username '{username}' not found in WARNING log entries: "
                f"{[r.getMessage() for r in warning_records]}"
            )
            assert not found_password, (
                f"Password '{password}' found in WARNING log entries — "
                f"passwords must never be logged!"
            )

    @given(
        email=_email_strategy,
        password=_password_strategy,
    )
    @settings(
        max_examples=50,
        deadline=None,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
    )
    def test_agent_login_failure_logs_email_not_password(
        self, setup_db, email: str, password: str
    ):
        """
        # Feature: production-hardening, Property 19: Auth failure logs contain username and IP but not password
        **Validates: Requirements 11.8**

        For any failed agent login attempt, the WARNING log entry SHALL contain
        the email (username_attempted) and SHALL NOT contain the attempted password.
        """
        Base.metadata.create_all(bind=engine)
        app.dependency_overrides[get_db] = override_get_db

        handler = CapturingHandler()
        handler.setLevel(logging.WARNING)

        auth_logger = logging.getLogger("api.auth")
        auth_logger.addHandler(handler)

        try:
            with TestClient(app, raise_server_exceptions=False) as client:
                resp = client.post(
                    "/api/v1/agent/auth/login",
                    json={"email": email, "password": password},
                )
        finally:
            auth_logger.removeHandler(handler)

        # Only check logging for actual auth failures (401)
        if resp.status_code == 401:
            warning_records = [
                r for r in handler.records
                if r.levelno >= logging.WARNING
            ]
            assert warning_records, (
                f"No WARNING log entry produced for failed agent login "
                f"(email={email!r})"
            )

            found_email = False
            found_password = False
            for record in warning_records:
                msg = record.getMessage()
                extra_username = str(getattr(record, "username_attempted", ""))
                if email in msg or email in extra_username:
                    found_email = True
                if password in msg or password in extra_username:
                    found_password = True

            assert found_email, (
                f"Email '{email}' not found in WARNING log entries: "
                f"{[r.getMessage() for r in warning_records]}"
            )
            assert not found_password, (
                f"Password '{password}' found in WARNING log entries — "
                f"passwords must never be logged!"
            )

    def test_admin_login_failure_log_contains_source_ip(self, setup_db):
        """
        # Feature: production-hardening, Property 19: Auth failure logs contain username and IP but not password
        **Validates: Requirements 11.8**

        The WARNING log entry for a failed admin login SHALL contain source_ip.
        """
        handler = CapturingHandler()
        handler.setLevel(logging.WARNING)

        auth_logger = logging.getLogger("api.auth")
        auth_logger.addHandler(handler)

        try:
            with TestClient(app, raise_server_exceptions=False) as client:
                resp = client.post(
                    "/api/v1/auth/login",
                    json={"username": "nonexistent_user_xyz", "password": "wrongpass"},
                )
        finally:
            auth_logger.removeHandler(handler)

        if resp.status_code == 401:
            warning_records = [
                r for r in handler.records
                if r.levelno >= logging.WARNING
            ]
            assert warning_records, "No WARNING log for failed admin login"

            # Check that source_ip is present in the log record
            found_ip = False
            for record in warning_records:
                source_ip = getattr(record, "source_ip", None)
                if source_ip is not None:
                    found_ip = True
                    break
                # Also check in the message
                msg = record.getMessage()
                if "source_ip" in msg or "testclient" in msg or "127.0.0.1" in msg:
                    found_ip = True
                    break

            assert found_ip, (
                f"source_ip not found in WARNING log entries: "
                f"{[r.getMessage() for r in warning_records]}"
            )

    def test_agent_login_failure_log_contains_source_ip(self, setup_db):
        """
        # Feature: production-hardening, Property 19: Auth failure logs contain username and IP but not password
        **Validates: Requirements 11.8**

        The WARNING log entry for a failed agent login SHALL contain source_ip.
        """
        handler = CapturingHandler()
        handler.setLevel(logging.WARNING)

        auth_logger = logging.getLogger("api.auth")
        auth_logger.addHandler(handler)

        try:
            with TestClient(app, raise_server_exceptions=False) as client:
                resp = client.post(
                    "/api/v1/agent/auth/login",
                    json={"email": "nonexistent@example.com", "password": "wrongpass123"},
                )
        finally:
            auth_logger.removeHandler(handler)

        if resp.status_code == 401:
            warning_records = [
                r for r in handler.records
                if r.levelno >= logging.WARNING
            ]
            assert warning_records, "No WARNING log for failed agent login"

            found_ip = False
            for record in warning_records:
                source_ip = getattr(record, "source_ip", None)
                if source_ip is not None:
                    found_ip = True
                    break
                msg = record.getMessage()
                if "source_ip" in msg or "testclient" in msg or "127.0.0.1" in msg:
                    found_ip = True
                    break

            assert found_ip, (
                f"source_ip not found in WARNING log entries: "
                f"{[r.getMessage() for r in warning_records]}"
            )

    def test_password_never_appears_in_any_log_level(self, setup_db):
        """
        # Feature: production-hardening, Property 19: Auth failure logs contain username and IP but not password
        **Validates: Requirements 11.8**

        The attempted password SHALL NOT appear in any log entry at any level
        during a failed authentication attempt.
        """
        unique_password = f"UNIQUE_SECRET_PASS_{uuid.uuid4().hex}"

        handler = CapturingHandler()
        handler.setLevel(logging.DEBUG)

        root_logger = logging.getLogger()
        root_logger.addHandler(handler)

        try:
            with TestClient(app, raise_server_exceptions=False) as client:
                client.post(
                    "/api/v1/auth/login",
                    json={"username": "testuser", "password": unique_password},
                )
        finally:
            root_logger.removeHandler(handler)

        # The unique password must not appear in any log message
        for record in handler.records:
            msg = record.getMessage()
            assert unique_password not in msg, (
                f"Password '{unique_password}' found in log at level "
                f"{record.levelname}: {msg}"
            )
            # Also check extra fields
            for attr in vars(record).values():
                if isinstance(attr, str):
                    assert unique_password not in attr, (
                        f"Password found in log record attribute: {attr}"
                    )
