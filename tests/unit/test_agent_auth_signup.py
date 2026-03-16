"""
Unit tests for POST /api/v1/agent/auth/signup.

Requirements: 1.1, 1.2, 1.3, 1.5
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from api.main import app, get_db
from gmail_lead_sync.models import Base
# Import agent_models to register all agent tables with Base.metadata
import gmail_lead_sync.agent_models  # noqa: F401
from gmail_lead_sync.agent_models import AgentUser, AgentSession
from api.routers.agent_auth import AGENT_SESSION_COOKIE_NAME

# StaticPool ensures all sessions share the same in-memory SQLite connection
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


@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client(setup_db):
    return TestClient(app, raise_server_exceptions=False)


SIGNUP_URL = "/api/v1/agent/auth/signup"
VALID_PAYLOAD = {
    "email": "agent@example.com",
    "password": "securepass123",
    "full_name": "Jane Agent",
}


class TestSignupSuccess:
    """Requirement 1.1 — successful account creation."""

    def test_returns_201(self, client):
        resp = client.post(SIGNUP_URL, json=VALID_PAYLOAD)
        assert resp.status_code == 201

    def test_response_body(self, client):
        resp = client.post(SIGNUP_URL, json=VALID_PAYLOAD)
        data = resp.json()
        assert "agent_user_id" in data
        assert data["email"] == VALID_PAYLOAD["email"]
        assert data["onboarding_step"] == 0

    def test_agent_user_persisted(self, client):
        client.post(SIGNUP_URL, json=VALID_PAYLOAD)
        db = TestingSessionLocal()
        user = db.query(AgentUser).filter_by(email=VALID_PAYLOAD["email"]).first()
        db.close()
        assert user is not None
        assert user.full_name == VALID_PAYLOAD["full_name"]

    def test_password_is_hashed(self, client):
        """Plain-text password must NOT be stored."""
        client.post(SIGNUP_URL, json=VALID_PAYLOAD)
        db = TestingSessionLocal()
        user = db.query(AgentUser).filter_by(email=VALID_PAYLOAD["email"]).first()
        db.close()
        assert user.password_hash != VALID_PAYLOAD["password"]
        assert user.password_hash.startswith("$2b$")

    def test_session_cookie_set(self, client):
        """Requirement 1.5 — auto-login sets agent_session cookie."""
        resp = client.post(SIGNUP_URL, json=VALID_PAYLOAD)
        assert AGENT_SESSION_COOKIE_NAME in resp.cookies
        assert len(resp.cookies[AGENT_SESSION_COOKIE_NAME]) > 0

    def test_session_record_created(self, client):
        resp = client.post(SIGNUP_URL, json=VALID_PAYLOAD)
        token = resp.cookies[AGENT_SESSION_COOKIE_NAME]
        db = TestingSessionLocal()
        session = db.query(AgentSession).filter_by(id=token).first()
        db.close()
        assert session is not None

    def test_session_token_is_64_bytes(self, client):
        """Requirement 2.6 — 64-byte token stored as 128-char hex."""
        resp = client.post(SIGNUP_URL, json=VALID_PAYLOAD)
        token = resp.cookies[AGENT_SESSION_COOKIE_NAME]
        assert len(token) == 128  # 64 bytes hex-encoded


class TestDuplicateEmail:
    """Requirement 1.2 — duplicate email returns 409."""

    def test_duplicate_email_returns_409(self, client):
        client.post(SIGNUP_URL, json=VALID_PAYLOAD)
        resp = client.post(SIGNUP_URL, json=VALID_PAYLOAD)
        assert resp.status_code == 409

    def test_duplicate_email_error_body(self, client):
        client.post(SIGNUP_URL, json=VALID_PAYLOAD)
        resp = client.post(SIGNUP_URL, json=VALID_PAYLOAD)
        assert resp.json()["error"] == "EMAIL_ALREADY_EXISTS"


class TestPasswordValidation:
    """Requirement 1.3 — password shorter than 8 chars returns 422."""

    def test_short_password_returns_422(self, client):
        payload = {**VALID_PAYLOAD, "password": "short"}
        resp = client.post(SIGNUP_URL, json=payload)
        assert resp.status_code == 422

    def test_exactly_7_chars_returns_422(self, client):
        payload = {**VALID_PAYLOAD, "password": "1234567"}
        resp = client.post(SIGNUP_URL, json=payload)
        assert resp.status_code == 422

    def test_exactly_8_chars_succeeds(self, client):
        payload = {**VALID_PAYLOAD, "password": "12345678"}
        resp = client.post(SIGNUP_URL, json=payload)
        assert resp.status_code == 201

    def test_missing_password_returns_422(self, client):
        payload = {"email": "a@b.com", "full_name": "Test"}
        resp = client.post(SIGNUP_URL, json=payload)
        assert resp.status_code == 422


class TestInputValidation:
    """Basic input validation edge cases."""

    def test_invalid_email_returns_422(self, client):
        payload = {**VALID_PAYLOAD, "email": "not-an-email"}
        resp = client.post(SIGNUP_URL, json=payload)
        assert resp.status_code == 422

    def test_missing_full_name_returns_422(self, client):
        payload = {"email": "a@b.com", "password": "securepass"}
        resp = client.post(SIGNUP_URL, json=payload)
        assert resp.status_code == 422
