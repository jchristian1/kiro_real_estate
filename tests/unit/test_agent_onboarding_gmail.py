"""
Unit tests for POST /api/v1/agent/onboarding/gmail.

All IMAP and encryption calls are mocked — no real network or crypto operations.

Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6
"""

import base64
import os
import secrets
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from api.main import app, get_db
from api.routers.agent_auth import AGENT_SESSION_COOKIE_NAME
from api.services.imap_service import (
    ERROR_IMAP_DISABLED,
    ERROR_INVALID_PASSWORD,
    ERROR_RATE_LIMITED,
    ERROR_TWO_FACTOR_REQUIRED,
    IMAPRateLimitError,
    reset_imap_rate_limit,
)
import gmail_lead_sync.agent_models  # noqa: F401 — registers agent tables
from gmail_lead_sync.agent_models import AgentUser
from gmail_lead_sync.models import Base, Credentials

# ---------------------------------------------------------------------------
# Test database setup
# ---------------------------------------------------------------------------

engine = create_engine(
    "sqlite://",
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


app.dependency_overrides[get_db] = override_get_db

# Stable AES-256 key for tests
_TEST_KEY = base64.b64encode(secrets.token_bytes(32)).decode()

GMAIL_URL = "/api/v1/agent/onboarding/gmail"
SIGNUP_URL = "/api/v1/agent/auth/signup"

VALID_GMAIL_PAYLOAD = {
    "gmail_address": "agent@gmail.com",
    "app_password": "abcd efgh ijkl mnop",
}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client(setup_db):
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def authenticated_client(client):
    """Return a client with a valid agent session cookie."""
    resp = client.post(
        SIGNUP_URL,
        json={"email": "agent@example.com", "password": "securepass123", "full_name": "Test Agent"},
    )
    assert resp.status_code == 201
    token = resp.cookies[AGENT_SESSION_COOKIE_NAME]
    client.cookies.set(AGENT_SESSION_COOKIE_NAME, token)

    # Reset rate limiter for the newly created agent
    db = TestingSessionLocal()
    agent = db.query(AgentUser).filter_by(email="agent@example.com").first()
    reset_imap_rate_limit(agent.id)
    db.close()

    return client


@pytest.fixture
def agent_id(authenticated_client):
    db = TestingSessionLocal()
    agent = db.query(AgentUser).filter_by(email="agent@example.com").first()
    aid = agent.id
    db.close()
    return aid


# ---------------------------------------------------------------------------
# Helper: mock a successful IMAP test
# ---------------------------------------------------------------------------

def _imap_success(*args, **kwargs):
    return {"success": True, "last_sync": None}


def _imap_failure(error_code: str):
    def _inner(*args, **kwargs):
        return {
            "success": False,
            "error": error_code,
            "message": f"Safe message for {error_code}",
        }
    return _inner


# ---------------------------------------------------------------------------
# 1. Authentication guard
# ---------------------------------------------------------------------------

class TestAuthGuard:
    def test_unauthenticated_returns_401(self, client):
        resp = client.post(GMAIL_URL, json=VALID_GMAIL_PAYLOAD)
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# 2. Success path (Requirement 5.1, 5.2)
# ---------------------------------------------------------------------------

class TestGmailConnectionSuccess:
    @patch("api.routers.agent_onboarding.test_imap_connection", side_effect=_imap_success)
    @patch.dict(os.environ, {"CREDENTIAL_ENCRYPTION_KEY": _TEST_KEY})
    def test_returns_200(self, _mock, authenticated_client):
        resp = authenticated_client.post(GMAIL_URL, json=VALID_GMAIL_PAYLOAD)
        assert resp.status_code == 200

    @patch("api.routers.agent_onboarding.test_imap_connection", side_effect=_imap_success)
    @patch.dict(os.environ, {"CREDENTIAL_ENCRYPTION_KEY": _TEST_KEY})
    def test_response_body(self, _mock, authenticated_client):
        resp = authenticated_client.post(GMAIL_URL, json=VALID_GMAIL_PAYLOAD)
        data = resp.json()
        assert data["connected"] is True
        assert data["gmail_address"] == VALID_GMAIL_PAYLOAD["gmail_address"]
        assert data["last_sync"] is None

    @patch("api.routers.agent_onboarding.test_imap_connection", side_effect=_imap_success)
    @patch.dict(os.environ, {"CREDENTIAL_ENCRYPTION_KEY": _TEST_KEY})
    def test_credentials_persisted(self, _mock, authenticated_client, agent_id):
        """Credentials record is created and linked to the agent."""
        authenticated_client.post(GMAIL_URL, json=VALID_GMAIL_PAYLOAD)

        db = TestingSessionLocal()
        agent = db.query(AgentUser).filter_by(id=agent_id).first()
        assert agent.credentials_id is not None

        creds = db.query(Credentials).filter_by(id=agent.credentials_id).first()
        assert creds is not None
        db.close()

    @patch("api.routers.agent_onboarding.test_imap_connection", side_effect=_imap_success)
    @patch.dict(os.environ, {"CREDENTIAL_ENCRYPTION_KEY": _TEST_KEY})
    def test_app_password_encrypted_not_plaintext(self, _mock, authenticated_client, agent_id):
        """Requirement 5.2 / 19.1 — app_password must be stored encrypted."""
        authenticated_client.post(GMAIL_URL, json=VALID_GMAIL_PAYLOAD)

        db = TestingSessionLocal()
        agent = db.query(AgentUser).filter_by(id=agent_id).first()
        creds = db.query(Credentials).filter_by(id=agent.credentials_id).first()
        db.close()

        plaintext = VALID_GMAIL_PAYLOAD["app_password"]
        assert creds.app_password_encrypted != plaintext
        # Encrypted value should be base64-encoded blob
        assert len(creds.app_password_encrypted) > len(plaintext)

    @patch("api.routers.agent_onboarding.test_imap_connection", side_effect=_imap_success)
    @patch.dict(os.environ, {"CREDENTIAL_ENCRYPTION_KEY": _TEST_KEY})
    def test_onboarding_step_advanced_to_3(self, _mock, authenticated_client, agent_id):
        """Requirement 5.2 — onboarding_step advances to 3 on success."""
        authenticated_client.post(GMAIL_URL, json=VALID_GMAIL_PAYLOAD)

        db = TestingSessionLocal()
        agent = db.query(AgentUser).filter_by(id=agent_id).first()
        db.close()
        assert agent.onboarding_step == 3

    @patch("api.routers.agent_onboarding.test_imap_connection", side_effect=_imap_success)
    @patch.dict(os.environ, {"CREDENTIAL_ENCRYPTION_KEY": _TEST_KEY})
    def test_second_submission_updates_existing_credentials(self, _mock, authenticated_client, agent_id):
        """Submitting again updates the existing credentials record (no duplicate rows)."""
        authenticated_client.post(GMAIL_URL, json=VALID_GMAIL_PAYLOAD)
        new_payload = {**VALID_GMAIL_PAYLOAD, "gmail_address": "new@gmail.com"}
        authenticated_client.post(GMAIL_URL, json=new_payload)

        db = TestingSessionLocal()
        count = db.query(Credentials).filter_by(agent_id=str(agent_id)).count()
        db.close()
        assert count == 1

    @patch("api.routers.agent_onboarding.test_imap_connection", side_effect=_imap_success)
    @patch.dict(os.environ, {"CREDENTIAL_ENCRYPTION_KEY": _TEST_KEY})
    def test_app_password_not_in_response(self, _mock, authenticated_client):
        """Requirement 19.4 — app_password must never appear in the API response."""
        resp = authenticated_client.post(GMAIL_URL, json=VALID_GMAIL_PAYLOAD)
        assert VALID_GMAIL_PAYLOAD["app_password"] not in resp.text


# ---------------------------------------------------------------------------
# 3. IMAP failure paths (Requirements 5.3, 5.4, 5.5, 5.6)
# ---------------------------------------------------------------------------

class TestGmailConnectionImapFailures:
    @patch(
        "api.routers.agent_onboarding.test_imap_connection",
        side_effect=_imap_failure(ERROR_IMAP_DISABLED),
    )
    @patch.dict(os.environ, {"CREDENTIAL_ENCRYPTION_KEY": _TEST_KEY})
    def test_imap_disabled_returns_422(self, _mock, authenticated_client):
        resp = authenticated_client.post(GMAIL_URL, json=VALID_GMAIL_PAYLOAD)
        assert resp.status_code == 422
        assert resp.json()["error"] == "IMAP_DISABLED"

    @patch(
        "api.routers.agent_onboarding.test_imap_connection",
        side_effect=_imap_failure(ERROR_INVALID_PASSWORD),
    )
    @patch.dict(os.environ, {"CREDENTIAL_ENCRYPTION_KEY": _TEST_KEY})
    def test_invalid_password_returns_422(self, _mock, authenticated_client):
        resp = authenticated_client.post(GMAIL_URL, json=VALID_GMAIL_PAYLOAD)
        assert resp.status_code == 422
        assert resp.json()["error"] == "INVALID_PASSWORD"

    @patch(
        "api.routers.agent_onboarding.test_imap_connection",
        side_effect=_imap_failure(ERROR_TWO_FACTOR_REQUIRED),
    )
    @patch.dict(os.environ, {"CREDENTIAL_ENCRYPTION_KEY": _TEST_KEY})
    def test_two_factor_required_returns_422(self, _mock, authenticated_client):
        resp = authenticated_client.post(GMAIL_URL, json=VALID_GMAIL_PAYLOAD)
        assert resp.status_code == 422
        assert resp.json()["error"] == "TWO_FACTOR_REQUIRED"

    @patch(
        "api.routers.agent_onboarding.test_imap_connection",
        side_effect=_imap_failure(ERROR_RATE_LIMITED),
    )
    @patch.dict(os.environ, {"CREDENTIAL_ENCRYPTION_KEY": _TEST_KEY})
    def test_imap_rate_limited_returns_422(self, _mock, authenticated_client):
        """IMAP-side RATE_LIMITED (from Gmail) returns 422, not 429."""
        resp = authenticated_client.post(GMAIL_URL, json=VALID_GMAIL_PAYLOAD)
        assert resp.status_code == 422
        assert resp.json()["error"] == "RATE_LIMITED"

    @patch(
        "api.routers.agent_onboarding.test_imap_connection",
        side_effect=_imap_failure(ERROR_IMAP_DISABLED),
    )
    @patch.dict(os.environ, {"CREDENTIAL_ENCRYPTION_KEY": _TEST_KEY})
    def test_failure_response_includes_message(self, _mock, authenticated_client):
        resp = authenticated_client.post(GMAIL_URL, json=VALID_GMAIL_PAYLOAD)
        data = resp.json()
        assert "message" in data
        assert isinstance(data["message"], str)
        assert len(data["message"]) > 0

    @patch(
        "api.routers.agent_onboarding.test_imap_connection",
        side_effect=_imap_failure(ERROR_IMAP_DISABLED),
    )
    @patch.dict(os.environ, {"CREDENTIAL_ENCRYPTION_KEY": _TEST_KEY})
    def test_no_credentials_persisted_on_failure(self, _mock, authenticated_client, agent_id):
        """Credentials must NOT be persisted when IMAP test fails."""
        authenticated_client.post(GMAIL_URL, json=VALID_GMAIL_PAYLOAD)

        db = TestingSessionLocal()
        agent = db.query(AgentUser).filter_by(id=agent_id).first()
        db.close()
        assert agent.credentials_id is None

    @patch(
        "api.routers.agent_onboarding.test_imap_connection",
        side_effect=_imap_failure(ERROR_IMAP_DISABLED),
    )
    @patch.dict(os.environ, {"CREDENTIAL_ENCRYPTION_KEY": _TEST_KEY})
    def test_onboarding_step_not_advanced_on_failure(self, _mock, authenticated_client, agent_id):
        """onboarding_step must NOT advance when IMAP test fails."""
        authenticated_client.post(GMAIL_URL, json=VALID_GMAIL_PAYLOAD)

        db = TestingSessionLocal()
        agent = db.query(AgentUser).filter_by(id=agent_id).first()
        db.close()
        assert agent.onboarding_step < 3


# ---------------------------------------------------------------------------
# 4. Rate limiting (Requirement 5.7)
# ---------------------------------------------------------------------------

class TestGmailRateLimiting:
    @patch.dict(os.environ, {"CREDENTIAL_ENCRYPTION_KEY": _TEST_KEY})
    @patch(
        "api.routers.agent_onboarding.check_and_record_imap_attempt",
        side_effect=IMAPRateLimitError(retry_after_seconds=300),
    )
    def test_rate_limit_exceeded_returns_429(self, _mock, authenticated_client):
        resp = authenticated_client.post(GMAIL_URL, json=VALID_GMAIL_PAYLOAD)
        assert resp.status_code == 429

    @patch.dict(os.environ, {"CREDENTIAL_ENCRYPTION_KEY": _TEST_KEY})
    @patch(
        "api.routers.agent_onboarding.check_and_record_imap_attempt",
        side_effect=IMAPRateLimitError(retry_after_seconds=300),
    )
    def test_rate_limit_response_body(self, _mock, authenticated_client):
        resp = authenticated_client.post(GMAIL_URL, json=VALID_GMAIL_PAYLOAD)
        data = resp.json()
        assert data["error"] == "RATE_LIMITED"
        assert data["retry_after_seconds"] == 300

    @patch.dict(os.environ, {"CREDENTIAL_ENCRYPTION_KEY": _TEST_KEY})
    @patch(
        "api.routers.agent_onboarding.check_and_record_imap_attempt",
        side_effect=IMAPRateLimitError(retry_after_seconds=42),
    )
    def test_retry_after_seconds_propagated(self, _mock, authenticated_client):
        resp = authenticated_client.post(GMAIL_URL, json=VALID_GMAIL_PAYLOAD)
        assert resp.json()["retry_after_seconds"] == 42


# ---------------------------------------------------------------------------
# 5. Input validation
# ---------------------------------------------------------------------------

class TestInputValidation:
    @patch.dict(os.environ, {"CREDENTIAL_ENCRYPTION_KEY": _TEST_KEY})
    def test_missing_gmail_address_returns_422(self, authenticated_client):
        resp = authenticated_client.post(GMAIL_URL, json={"app_password": "somepassword"})
        assert resp.status_code == 422

    @patch.dict(os.environ, {"CREDENTIAL_ENCRYPTION_KEY": _TEST_KEY})
    def test_missing_app_password_returns_422(self, authenticated_client):
        resp = authenticated_client.post(GMAIL_URL, json={"gmail_address": "a@gmail.com"})
        assert resp.status_code == 422

    @patch.dict(os.environ, {"CREDENTIAL_ENCRYPTION_KEY": _TEST_KEY})
    def test_empty_app_password_returns_422(self, authenticated_client):
        resp = authenticated_client.post(
            GMAIL_URL, json={"gmail_address": "a@gmail.com", "app_password": ""}
        )
        assert resp.status_code == 422
