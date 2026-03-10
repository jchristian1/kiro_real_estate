"""
Property-based tests for credential never plaintext.

Feature: agent-app

**Property 2: Credential Never Plaintext** — for any IMAP test or credential
update, app_password never appears in log output, error responses, or API
responses.

**Validates: Requirements 5.8, 19.1, 19.4**
"""

import logging
import secrets
import uuid
from datetime import datetime
from unittest.mock import patch

import bcrypt
import pytest
from fastapi.testclient import TestClient
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import gmail_lead_sync.agent_models  # noqa: F401 — registers agent tables
from api.main import app, get_db
from api.services.credential_encryption import encrypt_app_password
from gmail_lead_sync.agent_models import AgentPreferences, AgentSession, AgentUser
from gmail_lead_sync.models import Base, Credentials


# ---------------------------------------------------------------------------
# DB isolation fixture
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def setup_db():
    db_name = f"test_{uuid.uuid4().hex}"
    engine = create_engine(
        f"sqlite:///file:{db_name}?mode=memory&cache=shared&uri=true",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    yield TestingSessionLocal
    app.dependency_overrides.pop(get_db, None)
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _create_agent_with_session(db, onboarding_step: int = 2) -> tuple:
    """Create an agent with preferences and return (agent, session_token)."""
    email = f"agent_{uuid.uuid4().hex[:8]}@test.com"
    password_hash = bcrypt.hashpw(b"password", bcrypt.gensalt()).decode()
    agent = AgentUser(
        email=email,
        password_hash=password_hash,
        full_name="Test Agent",
        onboarding_step=onboarding_step,
        onboarding_completed=(onboarding_step >= 6),
        created_at=datetime.utcnow(),
    )
    db.add(agent)
    db.commit()
    db.refresh(agent)

    prefs = AgentPreferences(
        agent_user_id=agent.id,
        hot_threshold=80,
        warm_threshold=50,
        sla_minutes_hot=5,
        watcher_enabled=True,
        watcher_admin_override=False,
        created_at=datetime.utcnow(),
    )
    db.add(prefs)
    db.commit()

    token = secrets.token_hex(64)
    now = datetime.utcnow()
    session = AgentSession(
        id=token,
        agent_user_id=agent.id,
        created_at=now,
        expires_at=now.replace(year=now.year + 1),
    )
    db.add(session)
    db.commit()

    return agent, token


def _store_credentials(db, agent: AgentUser, gmail_address: str, app_password: str) -> None:
    """Encrypt and store credentials for an agent."""
    encrypted = encrypt_app_password(app_password)
    creds = Credentials(
        agent_id=str(agent.id),
        email_encrypted=gmail_address,
        app_password_encrypted=encrypted,
    )
    db.add(creds)
    db.flush()
    agent.credentials_id = creds.id
    db.commit()


# ---------------------------------------------------------------------------
# Strategy: printable ASCII passwords that are clearly identifiable
# ---------------------------------------------------------------------------

_APP_PASSWORD_STRATEGY = st.text(
    alphabet="abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789",
    min_size=8,
    max_size=32,
)


def _response_contains_password(response_text: str, app_password: str) -> bool:
    """Return True if the plaintext password appears anywhere in the response body."""
    return app_password in response_text


# ---------------------------------------------------------------------------
# Property 2: Credential Never Plaintext
# ---------------------------------------------------------------------------


class TestProperty2CredentialNeverPlaintext:
    """
    Property 2: app_password never appears in API responses or log records,
    regardless of whether the IMAP test succeeds or fails.
    """

    @given(app_password=_APP_PASSWORD_STRATEGY)
    @settings(max_examples=25, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_failed_imap_test_does_not_leak_password_in_response(
        self, setup_db, app_password
    ):
        """
        When an IMAP test fails (any error code), the response body must not
        contain the plaintext app_password.
        """
        db = setup_db()
        agent, token = _create_agent_with_session(db, onboarding_step=2)
        db.close()

        client = TestClient(app, cookies={"agent_session": token})

        # Mock IMAP to return a failure without making a real network call
        imap_failure = {"success": False, "error": "INVALID_PASSWORD", "message": "Bad credentials."}
        with patch("api.routers.agent_onboarding.test_imap_connection", return_value=imap_failure):
            resp = client.post(
                "/api/v1/agent/onboarding/gmail",
                json={"gmail_address": "agent@gmail.com", "app_password": app_password},
            )

        assert app_password not in resp.text, (
            f"Plaintext app_password found in IMAP failure response body. "
            f"Status: {resp.status_code}"
        )

    @given(app_password=_APP_PASSWORD_STRATEGY)
    @settings(max_examples=25, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_successful_imap_connect_does_not_return_password(
        self, setup_db, app_password
    ):
        """
        When an IMAP connection succeeds, the success response must not
        contain the plaintext app_password.
        """
        db = setup_db()
        agent, token = _create_agent_with_session(db, onboarding_step=2)
        db.close()

        client = TestClient(app, cookies={"agent_session": token})

        imap_success = {"success": True, "last_sync": None}
        with patch("api.routers.agent_onboarding.test_imap_connection", return_value=imap_success):
            resp = client.post(
                "/api/v1/agent/onboarding/gmail",
                json={"gmail_address": "agent@gmail.com", "app_password": app_password},
            )

        assert app_password not in resp.text, (
            f"Plaintext app_password found in successful IMAP connect response. "
            f"Status: {resp.status_code}"
        )

    @given(app_password=_APP_PASSWORD_STRATEGY)
    @settings(max_examples=25, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_account_gmail_test_does_not_return_password(
        self, setup_db, app_password
    ):
        """
        GET /account/gmail/test uses stored (encrypted) credentials — the
        decrypted app_password must never appear in the response.
        """
        db = setup_db()
        agent, token = _create_agent_with_session(db, onboarding_step=6)
        _store_credentials(db, agent, "agent@gmail.com", app_password)
        db.close()

        client = TestClient(app, cookies={"agent_session": token})

        imap_success = {"success": True, "last_sync": None}
        with patch("api.routers.agent_account.test_imap_connection", return_value=imap_success):
            resp = client.post("/api/v1/agent/account/gmail/test")

        assert app_password not in resp.text, (
            f"Plaintext app_password found in account gmail test response. "
            f"Status: {resp.status_code}"
        )

    @given(app_password=_APP_PASSWORD_STRATEGY)
    @settings(max_examples=25, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_account_gmail_get_does_not_return_password(
        self, setup_db, app_password
    ):
        """
        GET /account/gmail returns connection status — must never include
        the plaintext app_password in the response body.
        """
        db = setup_db()
        agent, token = _create_agent_with_session(db, onboarding_step=6)
        _store_credentials(db, agent, "agent@gmail.com", app_password)
        db.close()

        client = TestClient(app, cookies={"agent_session": token})
        resp = client.get("/api/v1/agent/account/gmail")

        assert app_password not in resp.text, (
            f"Plaintext app_password found in GET /account/gmail response. "
            f"Status: {resp.status_code}"
        )

    @given(app_password=_APP_PASSWORD_STRATEGY)
    @settings(max_examples=20, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_imap_failure_does_not_log_password(self, setup_db, app_password):
        """
        When an IMAP test fails, the plaintext app_password must not appear
        in any log records emitted during the request.
        """
        db = setup_db()
        agent, token = _create_agent_with_session(db, onboarding_step=2)
        db.close()

        client = TestClient(app, cookies={"agent_session": token})

        log_records: list = []

        class CapturingHandler(logging.Handler):
            def emit(self, record: logging.LogRecord) -> None:
                log_records.append(self.format(record))

        handler = CapturingHandler()
        root_logger = logging.getLogger()
        root_logger.addHandler(handler)

        try:
            imap_failure = {"success": False, "error": "CONNECTION_FAILED", "message": "Failed."}
            with patch("api.routers.agent_onboarding.test_imap_connection", return_value=imap_failure):
                client.post(
                    "/api/v1/agent/onboarding/gmail",
                    json={"gmail_address": "agent@gmail.com", "app_password": app_password},
                )
        finally:
            root_logger.removeHandler(handler)

        for record in log_records:
            assert app_password not in record, (
                f"Plaintext app_password found in log output during IMAP failure. "
                f"Log entry: {record[:200]}"
            )
