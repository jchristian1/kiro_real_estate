"""
Unit tests for:
  POST /api/v1/agent/auth/login
  POST /api/v1/agent/auth/logout
  GET  /api/v1/agent/auth/me

Requirements: 2.1, 2.2, 2.3, 2.5, 2.6
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from api.main import app, get_db
from gmail_lead_sync.models import Base
import gmail_lead_sync.agent_models  # noqa: F401 — registers agent tables
from gmail_lead_sync.agent_models import AgentSession
from api.routers.agent_auth import AGENT_SESSION_COOKIE_NAME

# ---------------------------------------------------------------------------
# Test DB setup (shared in-memory SQLite)
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


@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client(setup_db):
    return TestClient(app, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

SIGNUP_URL = "/api/v1/agent/auth/signup"
LOGIN_URL = "/api/v1/agent/auth/login"
LOGOUT_URL = "/api/v1/agent/auth/logout"
ME_URL = "/api/v1/agent/auth/me"

VALID_AGENT = {
    "email": "agent@example.com",
    "password": "securepass123",
    "full_name": "Jane Agent",
}


def _signup_and_login(client) -> str:
    """Register an agent and log in; return the session token."""
    client.post(SIGNUP_URL, json=VALID_AGENT)
    resp = client.post(LOGIN_URL, json={"email": VALID_AGENT["email"], "password": VALID_AGENT["password"]})
    assert resp.status_code == 200
    return resp.cookies[AGENT_SESSION_COOKIE_NAME]


def _authed_get(client, url: str, token: str):
    """GET with the session cookie explicitly set."""
    return client.get(url, cookies={AGENT_SESSION_COOKIE_NAME: token})


def _authed_post(client, url: str, token: str, **kwargs):
    """POST with the session cookie explicitly set."""
    return client.post(url, cookies={AGENT_SESSION_COOKIE_NAME: token}, **kwargs)


# ---------------------------------------------------------------------------
# POST /login — success (Requirement 2.1)
# ---------------------------------------------------------------------------

class TestLoginSuccess:
    """Requirement 2.1 — valid credentials set cookie and return agent info."""

    def test_returns_200(self, client):
        client.post(SIGNUP_URL, json=VALID_AGENT)
        resp = client.post(LOGIN_URL, json={"email": VALID_AGENT["email"], "password": VALID_AGENT["password"]})
        assert resp.status_code == 200

    def test_response_body_fields(self, client):
        client.post(SIGNUP_URL, json=VALID_AGENT)
        resp = client.post(LOGIN_URL, json={"email": VALID_AGENT["email"], "password": VALID_AGENT["password"]})
        data = resp.json()
        assert "agent_user_id" in data
        assert data["full_name"] == VALID_AGENT["full_name"]
        assert "onboarding_completed" in data

    def test_session_cookie_set(self, client):
        client.post(SIGNUP_URL, json=VALID_AGENT)
        resp = client.post(LOGIN_URL, json={"email": VALID_AGENT["email"], "password": VALID_AGENT["password"]})
        assert AGENT_SESSION_COOKIE_NAME in resp.cookies
        assert len(resp.cookies[AGENT_SESSION_COOKIE_NAME]) > 0

    def test_session_token_is_64_bytes(self, client):
        """Requirement 2.6 — 64-byte token stored as 128-char hex."""
        client.post(SIGNUP_URL, json=VALID_AGENT)
        resp = client.post(LOGIN_URL, json={"email": VALID_AGENT["email"], "password": VALID_AGENT["password"]})
        token = resp.cookies[AGENT_SESSION_COOKIE_NAME]
        assert len(token) == 128

    def test_session_record_created_in_db(self, client):
        client.post(SIGNUP_URL, json=VALID_AGENT)
        resp = client.post(LOGIN_URL, json={"email": VALID_AGENT["email"], "password": VALID_AGENT["password"]})
        token = resp.cookies[AGENT_SESSION_COOKIE_NAME]
        db = TestingSessionLocal()
        session = db.query(AgentSession).filter_by(id=token).first()
        db.close()
        assert session is not None

    def test_each_login_creates_new_session(self, client):
        """Two logins should produce two distinct session tokens."""
        client.post(SIGNUP_URL, json=VALID_AGENT)
        creds = {"email": VALID_AGENT["email"], "password": VALID_AGENT["password"]}
        token1 = client.post(LOGIN_URL, json=creds).cookies[AGENT_SESSION_COOKIE_NAME]
        token2 = client.post(LOGIN_URL, json=creds).cookies[AGENT_SESSION_COOKIE_NAME]
        assert token1 != token2


# ---------------------------------------------------------------------------
# POST /login — invalid credentials (Requirement 2.2)
# ---------------------------------------------------------------------------

class TestLoginInvalidCredentials:
    """Requirement 2.2 — invalid credentials return 401."""

    def test_wrong_password_returns_401(self, client):
        client.post(SIGNUP_URL, json=VALID_AGENT)
        resp = client.post(LOGIN_URL, json={"email": VALID_AGENT["email"], "password": "wrongpassword"})
        assert resp.status_code == 401

    def test_wrong_password_error_body(self, client):
        client.post(SIGNUP_URL, json=VALID_AGENT)
        resp = client.post(LOGIN_URL, json={"email": VALID_AGENT["email"], "password": "wrongpassword"})
        assert resp.json()["error"] == "INVALID_CREDENTIALS"

    def test_unknown_email_returns_401(self, client):
        resp = client.post(LOGIN_URL, json={"email": "nobody@example.com", "password": "anypassword"})
        assert resp.status_code == 401

    def test_unknown_email_error_body(self, client):
        resp = client.post(LOGIN_URL, json={"email": "nobody@example.com", "password": "anypassword"})
        assert resp.json()["error"] == "INVALID_CREDENTIALS"

    def test_no_cookie_on_failure(self, client):
        resp = client.post(LOGIN_URL, json={"email": "nobody@example.com", "password": "anypassword"})
        assert AGENT_SESSION_COOKIE_NAME not in resp.cookies


# ---------------------------------------------------------------------------
# POST /logout (Requirement 2.3)
# ---------------------------------------------------------------------------

class TestLogout:
    """Requirement 2.3 — logout invalidates session and clears cookie."""

    def test_logout_returns_200(self, client):
        token = _signup_and_login(client)
        resp = _authed_post(client, LOGOUT_URL, token)
        assert resp.status_code == 200

    def test_logout_deletes_session_from_db(self, client):
        token = _signup_and_login(client)
        _authed_post(client, LOGOUT_URL, token)
        db = TestingSessionLocal()
        db.expire_all()
        session = db.query(AgentSession).filter_by(id=token).first()
        db.close()
        assert session is None

    def test_logout_clears_cookie(self, client):
        token = _signup_and_login(client)
        resp = _authed_post(client, LOGOUT_URL, token)
        # After logout the cookie value should be empty or absent
        cookie_val = resp.cookies.get(AGENT_SESSION_COOKIE_NAME, "")
        assert cookie_val == ""

    def test_logout_without_session_returns_200(self, client):
        """Logout with no active session should still return 200."""
        resp = client.post(LOGOUT_URL)
        assert resp.status_code == 200

    def test_me_returns_401_after_logout(self, client):
        """Session must be invalidated — /me should fail after logout."""
        token = _signup_and_login(client)
        _authed_post(client, LOGOUT_URL, token)
        resp = _authed_get(client, ME_URL, token)
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# GET /me (Requirement 2.5)
# ---------------------------------------------------------------------------

class TestMe:
    """Requirement 2.5 — /me returns agent profile for valid session."""

    def test_me_returns_200(self, client):
        token = _signup_and_login(client)
        resp = _authed_get(client, ME_URL, token)
        assert resp.status_code == 200

    def test_me_response_fields(self, client):
        token = _signup_and_login(client)
        resp = _authed_get(client, ME_URL, token)
        data = resp.json()
        assert data["email"] == VALID_AGENT["email"]
        assert data["full_name"] == VALID_AGENT["full_name"]
        assert "agent_user_id" in data
        assert "onboarding_completed" in data
        assert "onboarding_step" in data

    def test_me_without_session_returns_401(self, client):
        """No cookie → 401."""
        resp = client.get(ME_URL)
        assert resp.status_code == 401

    def test_me_with_invalid_token_returns_401(self, client):
        """Bogus token → 401."""
        resp = _authed_get(client, ME_URL, "a" * 128)
        assert resp.status_code == 401

    def test_me_onboarding_step_is_zero_after_signup(self, client):
        token = _signup_and_login(client)
        resp = _authed_get(client, ME_URL, token)
        assert resp.json()["onboarding_step"] == 0
