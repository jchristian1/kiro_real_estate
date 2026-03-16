"""
Unit tests for the `get_current_agent` FastAPI dependency.

Verifies that:
- Missing session cookie → 401
- Invalid / non-existent token → 401
- Expired session → 401
- Valid session → returns AgentUser

Requirements: 2.4
"""

import secrets
from datetime import datetime, timedelta

import pytest
from fastapi import Depends
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from api.main import app, get_db
from gmail_lead_sync.models import Base
import gmail_lead_sync.agent_models  # noqa: F401 — registers agent tables
from gmail_lead_sync.agent_models import AgentUser, AgentSession
from api.dependencies.agent_auth import get_current_agent, AGENT_SESSION_COOKIE_NAME

# ---------------------------------------------------------------------------
# In-memory SQLite test database
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


# ---------------------------------------------------------------------------
# Minimal protected route wired into the test app
# ---------------------------------------------------------------------------

from fastapi import APIRouter  # noqa: E402

_test_router = APIRouter()


@_test_router.get("/api/v1/agent/protected-test")
def _protected(agent: AgentUser = Depends(get_current_agent)):
    return {"agent_user_id": agent.id, "email": agent.email}


app.include_router(_test_router)

PROTECTED_URL = "/api/v1/agent/protected-test"

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
def db_session(setup_db):
    db = TestingSessionLocal()
    yield db
    db.close()


def _create_agent(db) -> AgentUser:
    """Insert a minimal AgentUser and return it."""
    user = AgentUser(
        email="test@example.com",
        password_hash="$2b$12$fakehash",
        full_name="Test Agent",
        onboarding_step=0,
        onboarding_completed=False,
        created_at=datetime.utcnow(),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _create_session(db, agent_user_id: int, expires_delta: timedelta) -> AgentSession:
    """Insert an AgentSession with the given expiry offset and return it."""
    token = secrets.token_hex(64)
    now = datetime.utcnow()
    session = AgentSession(
        id=token,
        agent_user_id=agent_user_id,
        created_at=now,
        expires_at=now + expires_delta,
        last_accessed=now,
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


# ---------------------------------------------------------------------------
# Tests: missing cookie
# ---------------------------------------------------------------------------


class TestMissingCookie:
    """No session cookie → 401 UNAUTHORIZED."""

    def test_no_cookie_returns_401(self, client):
        resp = client.get(PROTECTED_URL)
        assert resp.status_code == 401

    def test_no_cookie_error_body(self, client):
        resp = client.get(PROTECTED_URL)
        body = resp.json()
        # Unified error schema: {"error": str, "message": str, "code": str, "details": list|null}
        assert "error" in body
        assert "message" in body
        assert "code" in body


# ---------------------------------------------------------------------------
# Tests: invalid / non-existent token
# ---------------------------------------------------------------------------


class TestInvalidToken:
    """Bogus or non-existent token → 401 UNAUTHORIZED."""

    def test_random_token_returns_401(self, client):
        resp = client.get(PROTECTED_URL, cookies={AGENT_SESSION_COOKIE_NAME: "a" * 128})
        assert resp.status_code == 401

    def test_random_token_error_body(self, client):
        resp = client.get(PROTECTED_URL, cookies={AGENT_SESSION_COOKIE_NAME: "a" * 128})
        body = resp.json()
        # Unified error schema: {"error": str, "message": str, "code": str, "details": list|null}
        assert "error" in body
        assert "message" in body
        assert "code" in body

    def test_empty_string_token_returns_401(self, client):
        resp = client.get(PROTECTED_URL, cookies={AGENT_SESSION_COOKIE_NAME: ""})
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Tests: expired session
# ---------------------------------------------------------------------------


class TestExpiredSession:
    """Session whose expires_at is in the past → 401 UNAUTHORIZED."""

    def test_expired_session_returns_401(self, client, db_session):
        user = _create_agent(db_session)
        session = _create_session(db_session, user.id, timedelta(seconds=-1))
        resp = client.get(
            PROTECTED_URL,
            cookies={AGENT_SESSION_COOKIE_NAME: session.id},
        )
        assert resp.status_code == 401

    def test_expired_session_error_body(self, client, db_session):
        user = _create_agent(db_session)
        session = _create_session(db_session, user.id, timedelta(seconds=-1))
        resp = client.get(
            PROTECTED_URL,
            cookies={AGENT_SESSION_COOKIE_NAME: session.id},
        )
        body = resp.json()
        # Unified error schema: {"error": str, "message": str, "code": str, "details": list|null}
        assert "error" in body
        assert "message" in body
        assert "code" in body


# ---------------------------------------------------------------------------
# Tests: valid session
# ---------------------------------------------------------------------------


class TestValidSession:
    """Valid, non-expired session → 200 with agent info."""

    def test_valid_session_returns_200(self, client, db_session):
        user = _create_agent(db_session)
        session = _create_session(db_session, user.id, timedelta(days=30))
        resp = client.get(
            PROTECTED_URL,
            cookies={AGENT_SESSION_COOKIE_NAME: session.id},
        )
        assert resp.status_code == 200

    def test_valid_session_returns_agent_info(self, client, db_session):
        user = _create_agent(db_session)
        session = _create_session(db_session, user.id, timedelta(days=30))
        resp = client.get(
            PROTECTED_URL,
            cookies={AGENT_SESSION_COOKIE_NAME: session.id},
        )
        data = resp.json()
        assert data["agent_user_id"] == user.id
        assert data["email"] == user.email

    def test_session_expiring_in_future_is_valid(self, client, db_session):
        """Session expiring 1 second from now is still valid."""
        user = _create_agent(db_session)
        session = _create_session(db_session, user.id, timedelta(seconds=5))
        resp = client.get(
            PROTECTED_URL,
            cookies={AGENT_SESSION_COOKIE_NAME: session.id},
        )
        assert resp.status_code == 200
