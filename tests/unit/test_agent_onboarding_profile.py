"""
Unit tests for PUT /api/v1/agent/onboarding/profile.

Requirements: 4.1, 4.3
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from api.main import app, get_db
from gmail_lead_sync.models import Base, Company
import gmail_lead_sync.agent_models  # noqa: F401 — registers agent tables
from gmail_lead_sync.agent_models import AgentUser, AgentSession
from api.routers.agent_auth import (
    AGENT_SESSION_COOKIE_NAME,
    _hash_password,
    _create_agent_session,
)

# ---------------------------------------------------------------------------
# Test DB setup
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

PROFILE_URL = "/api/v1/agent/onboarding/profile"


@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db():
    session = TestingSessionLocal()
    yield session
    session.close()


@pytest.fixture
def agent_user(db):
    """Create a test agent user."""
    user = AgentUser(
        email="agent@example.com",
        password_hash=_hash_password("password123"),
        full_name="Original Name",
        onboarding_step=0,
        onboarding_completed=False,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def auth_client(agent_user):
    """TestClient with a valid agent session cookie."""
    db = TestingSessionLocal()
    session = _create_agent_session(db, agent_user.id)
    db.close()
    client = TestClient(app, raise_server_exceptions=False)
    client.cookies.set(AGENT_SESSION_COOKIE_NAME, session.id)
    return client


@pytest.fixture
def company(db):
    """Create a test company."""
    c = Company(name="Acme Realty")
    db.add(c)
    db.commit()
    db.refresh(c)
    return c


# ---------------------------------------------------------------------------
# Success cases
# ---------------------------------------------------------------------------

class TestProfileSuccess:
    """Requirement 4.1 — profile persisted, onboarding_step advances to 2."""

    def test_returns_200(self, auth_client):
        resp = auth_client.put(PROFILE_URL, json={
            "full_name": "Jane Agent",
            "timezone": "America/New_York",
        })
        assert resp.status_code == 200

    def test_response_body(self, auth_client):
        resp = auth_client.put(PROFILE_URL, json={
            "full_name": "Jane Agent",
            "timezone": "America/New_York",
        })
        data = resp.json()
        assert data["ok"] is True
        assert data["onboarding_step"] == 2

    def test_full_name_persisted(self, auth_client, agent_user, db):
        auth_client.put(PROFILE_URL, json={
            "full_name": "Jane Agent",
            "timezone": "UTC",
        })
        db.refresh(agent_user)
        assert agent_user.full_name == "Jane Agent"

    def test_phone_persisted(self, auth_client, agent_user, db):
        auth_client.put(PROFILE_URL, json={
            "full_name": "Jane Agent",
            "phone": "555-1234",
            "timezone": "UTC",
        })
        db.refresh(agent_user)
        assert agent_user.phone == "555-1234"

    def test_timezone_persisted(self, auth_client, agent_user, db):
        auth_client.put(PROFILE_URL, json={
            "full_name": "Jane Agent",
            "timezone": "America/Los_Angeles",
        })
        db.refresh(agent_user)
        assert agent_user.timezone == "America/Los_Angeles"

    def test_service_area_persisted(self, auth_client, agent_user, db):
        auth_client.put(PROFILE_URL, json={
            "full_name": "Jane Agent",
            "timezone": "UTC",
            "service_area": "Brooklyn, NY",
        })
        db.refresh(agent_user)
        assert agent_user.service_area == "Brooklyn, NY"

    def test_onboarding_step_advanced_to_2(self, auth_client, agent_user, db):
        auth_client.put(PROFILE_URL, json={
            "full_name": "Jane Agent",
            "timezone": "UTC",
        })
        db.refresh(agent_user)
        assert agent_user.onboarding_step == 2

    def test_timezone_defaults_to_utc_when_empty(self, auth_client, agent_user, db):
        """When timezone is omitted, defaults to UTC."""
        auth_client.put(PROFILE_URL, json={"full_name": "Jane Agent"})
        db.refresh(agent_user)
        assert agent_user.timezone == "UTC"

    def test_optional_fields_can_be_null(self, auth_client, agent_user, db):
        """phone and service_area are optional."""
        auth_client.put(PROFILE_URL, json={"full_name": "Jane Agent"})
        db.refresh(agent_user)
        assert agent_user.phone is None
        assert agent_user.service_area is None

    def test_step_not_regressed_if_already_past_2(self, auth_client, agent_user, db):
        """If agent is already at step 3, step should not go back to 2."""
        agent_user.onboarding_step = 3
        db.commit()
        auth_client.put(PROFILE_URL, json={"full_name": "Jane Agent"})
        db.refresh(agent_user)
        assert agent_user.onboarding_step == 3


# ---------------------------------------------------------------------------
# Company join code (Requirement 4.3)
# ---------------------------------------------------------------------------

class TestCompanyJoinCode:
    """Requirement 4.3 — company association via join code."""

    def test_valid_join_code_associates_company(self, auth_client, agent_user, company, db):
        auth_client.put(PROFILE_URL, json={
            "full_name": "Jane Agent",
            "timezone": "UTC",
            "company_join_code": "Acme Realty",
        })
        db.refresh(agent_user)
        assert agent_user.company_id == company.id

    def test_unknown_join_code_does_not_fail(self, auth_client, agent_user, db):
        """Unknown join code is silently ignored — still returns 200."""
        resp = auth_client.put(PROFILE_URL, json={
            "full_name": "Jane Agent",
            "timezone": "UTC",
            "company_join_code": "NONEXISTENT",
        })
        assert resp.status_code == 200
        db.refresh(agent_user)
        assert agent_user.company_id is None

    def test_no_join_code_leaves_company_null(self, auth_client, agent_user, db):
        auth_client.put(PROFILE_URL, json={"full_name": "Jane Agent"})
        db.refresh(agent_user)
        assert agent_user.company_id is None


# ---------------------------------------------------------------------------
# Authentication guard
# ---------------------------------------------------------------------------

class TestAuthGuard:
    """Requirement 2.4 — unauthenticated requests return 401."""

    def test_no_cookie_returns_401(self):
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.put(PROFILE_URL, json={"full_name": "Jane Agent"})
        assert resp.status_code == 401

    def test_invalid_cookie_returns_401(self):
        client = TestClient(app, raise_server_exceptions=False)
        client.cookies.set(AGENT_SESSION_COOKIE_NAME, "invalid_token_xyz")
        resp = client.put(PROFILE_URL, json={"full_name": "Jane Agent"})
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

class TestValidation:
    """full_name is required."""

    def test_missing_full_name_returns_422(self, auth_client):
        resp = auth_client.put(PROFILE_URL, json={"timezone": "UTC"})
        assert resp.status_code == 422

    def test_empty_full_name_returns_422(self, auth_client):
        resp = auth_client.put(PROFILE_URL, json={"full_name": "", "timezone": "UTC"})
        assert resp.status_code == 422
