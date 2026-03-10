"""
Property-based tests for unauthenticated request rejection.

Feature: agent-app

**Property 21: Unauthenticated Requests Rejected** — any request to
`/api/v1/agent/` without a valid session returns 401.

**Validates: Requirements 2.4**
"""

import secrets
from datetime import datetime, timedelta

import pytest
from fastapi import APIRouter, Depends
from fastapi.testclient import TestClient
from hypothesis import given, settings, strategies as st
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from api.main import app, get_db
from gmail_lead_sync.models import Base
import gmail_lead_sync.agent_models  # noqa: F401 — registers agent tables
from gmail_lead_sync.agent_models import AgentSession, AgentUser
from api.dependencies.agent_auth import AGENT_SESSION_COOKIE_NAME, get_current_agent

# ---------------------------------------------------------------------------
# In-memory SQLite test database
# Use a named in-memory DB to avoid sharing state with other test files.
# ---------------------------------------------------------------------------

engine = create_engine(
    "sqlite:///file:prop_unauth_rejection?mode=memory&cache=shared&uri=true",
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
# Minimal protected route for property tests
# ---------------------------------------------------------------------------

_prop_router = APIRouter()

PROTECTED_URL = "/api/v1/agent/prop-test-protected"


@_prop_router.get(PROTECTED_URL)
def _prop_protected(agent: AgentUser = Depends(get_current_agent)):
    return {"agent_user_id": agent.id}


app.include_router(_prop_router)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    app.dependency_overrides[get_db] = override_get_db
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


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _create_agent(db) -> AgentUser:
    user = AgentUser(
        email="prop_test@example.com",
        password_hash="$2b$12$fakehash",
        full_name="Prop Test Agent",
        onboarding_step=0,
        onboarding_completed=False,
        created_at=datetime.utcnow(),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _create_expired_session(db, agent_user_id: int) -> AgentSession:
    token = secrets.token_hex(64)
    now = datetime.utcnow()
    session = AgentSession(
        id=token,
        agent_user_id=agent_user_id,
        created_at=now - timedelta(days=31),
        expires_at=now - timedelta(seconds=1),  # already expired
        last_accessed=now - timedelta(days=31),
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


# ---------------------------------------------------------------------------
# Property 21: Unauthenticated Requests Rejected
# ---------------------------------------------------------------------------


class TestProperty21UnauthenticatedRejection:
    """
    Property 21: Unauthenticated Requests Rejected
    **Validates: Requirements 2.4**

    Any request to a protected `/api/v1/agent/` route without a valid session
    must return HTTP 401, regardless of:
    1. No session cookie at all
    2. An arbitrary bogus token value
    3. An expired session token
    """

    def test_no_cookie_returns_401(self, client):
        """
        Property 21: Unauthenticated Requests Rejected
        **Validates: Requirements 2.4**

        A request with no session cookie must return 401.
        """
        resp = client.get(PROTECTED_URL)
        assert resp.status_code == 401

    @given(bogus_token=st.text(
        min_size=1,
        max_size=200,
        alphabet=st.characters(min_codepoint=0x21, max_codepoint=0x7E),  # printable ASCII, no spaces/control chars
    ))
    @settings(max_examples=100)
    def test_bogus_token_returns_401(self, bogus_token: str):
        """
        Property 21: Unauthenticated Requests Rejected
        **Validates: Requirements 2.4**

        For any arbitrary non-empty string used as a session token, the
        protected route must return 401 — no bogus token should grant access.
        """
        # Ensure tables exist for each Hypothesis example (may run after other
        # tests that tear down the DB via drop_all).
        Base.metadata.create_all(bind=engine)
        with TestClient(app, raise_server_exceptions=False) as c:
            resp = c.get(
                PROTECTED_URL,
                cookies={AGENT_SESSION_COOKIE_NAME: bogus_token},
            )
        assert resp.status_code == 401, (
            f"Expected 401 for bogus token {bogus_token!r}, got {resp.status_code}"
        )

    def test_expired_session_returns_401(self, client, db_session):
        """
        Property 21: Unauthenticated Requests Rejected
        **Validates: Requirements 2.4**

        A request using an expired session token must return 401.
        """
        user = _create_agent(db_session)
        expired_session = _create_expired_session(db_session, user.id)
        resp = client.get(
            PROTECTED_URL,
            cookies={AGENT_SESSION_COOKIE_NAME: expired_session.id},
        )
        assert resp.status_code == 401

    def test_no_cookie_error_body(self, client):
        """
        Property 21: Unauthenticated Requests Rejected
        **Validates: Requirements 2.4**

        The 401 response for a missing cookie must include the UNAUTHORIZED error.
        """
        resp = client.get(PROTECTED_URL)
        assert resp.json()["detail"]["error"] == "UNAUTHORIZED"

    def test_expired_session_error_body(self, client, db_session):
        """
        Property 21: Unauthenticated Requests Rejected
        **Validates: Requirements 2.4**

        The 401 response for an expired session must include the UNAUTHORIZED error.
        """
        user = _create_agent(db_session)
        expired_session = _create_expired_session(db_session, user.id)
        resp = client.get(
            PROTECTED_URL,
            cookies={AGENT_SESSION_COOKIE_NAME: expired_session.id},
        )
        assert resp.json()["detail"]["error"] == "UNAUTHORIZED"
