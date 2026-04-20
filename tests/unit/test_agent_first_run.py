"""
Unit tests for PUT /api/v1/agent/first-run/profile (PR A2).

Behavioral contract:
- 200 on valid profile save
- onboarding_completed=True in DB after save
- Response body is {"ok": true} — no onboarding_step field
- 401 when unauthenticated
- 422 when full_name is missing or empty
"""

import secrets
from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from api.main import app, get_db
from gmail_lead_sync.agent_models import AgentSession, AgentUser  # noqa: F401
from gmail_lead_sync.models import Base

FIRST_RUN_URL = "/api/v1/agent/first-run/profile"
AGENT_SESSION_COOKIE = "agent_session"

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
client = TestClient(app, raise_server_exceptions=True)


@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    app.dependency_overrides[get_db] = override_get_db
    yield
    Base.metadata.drop_all(bind=engine)


def _create_agent(onboarding_completed: bool = False) -> tuple[int, str]:
    """Create an agent and session, return (agent_id, token)."""
    import bcrypt
    db = TestingSessionLocal()
    agent = AgentUser(
        email=f"agent_{secrets.token_hex(4)}@test.com",
        password_hash=bcrypt.hashpw(b"pass", bcrypt.gensalt()).decode(),
        full_name="",
        onboarding_completed=onboarding_completed,
        created_at=datetime.utcnow(),
    )
    db.add(agent)
    db.flush()
    token = secrets.token_hex(64)
    session = AgentSession(
        id=token,
        agent_user_id=agent.id,
        created_at=datetime.utcnow(),
        expires_at=datetime.utcnow() + timedelta(hours=1),
        last_accessed=datetime.utcnow(),
    )
    db.add(session)
    db.commit()
    agent_id = agent.id
    db.close()
    return agent_id, token


def _cookies(token: str) -> dict:
    return {AGENT_SESSION_COOKIE: token}


# ---------------------------------------------------------------------------
# Success
# ---------------------------------------------------------------------------

def test_returns_200():
    _, token = _create_agent()
    resp = client.put(FIRST_RUN_URL, json={"full_name": "Jane Agent"}, cookies=_cookies(token))
    assert resp.status_code == 200


def test_response_body_is_ok_only():
    """Response must be {"ok": true} — no onboarding_step field."""
    _, token = _create_agent()
    resp = client.put(FIRST_RUN_URL, json={"full_name": "Jane Agent"}, cookies=_cookies(token))
    data = resp.json()
    assert data == {"ok": True}
    assert "onboarding_step" not in data


def test_onboarding_completed_set_true():
    """onboarding_completed must be True in DB after save."""
    agent_id, token = _create_agent(onboarding_completed=False)
    client.put(FIRST_RUN_URL, json={"full_name": "Jane Agent"}, cookies=_cookies(token))
    db = TestingSessionLocal()
    agent = db.query(AgentUser).filter(AgentUser.id == agent_id).first()
    assert agent.onboarding_completed is True
    db.close()


def test_profile_fields_persisted():
    agent_id, token = _create_agent()
    client.put(FIRST_RUN_URL, json={
        "full_name": "Jane Agent",
        "phone": "555-0100",
        "timezone": "America/Chicago",
    }, cookies=_cookies(token))
    db = TestingSessionLocal()
    agent = db.query(AgentUser).filter(AgentUser.id == agent_id).first()
    assert agent.full_name == "Jane Agent"
    assert agent.phone == "555-0100"
    assert agent.timezone == "America/Chicago"
    db.close()


def test_already_completed_can_update_profile():
    """Agents who already completed first-run can still update their profile."""
    agent_id, token = _create_agent(onboarding_completed=True)
    resp = client.put(FIRST_RUN_URL, json={"full_name": "Updated Name"}, cookies=_cookies(token))
    assert resp.status_code == 200
    db = TestingSessionLocal()
    agent = db.query(AgentUser).filter(AgentUser.id == agent_id).first()
    assert agent.full_name == "Updated Name"
    db.close()


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

def test_unauthenticated_returns_401():
    resp = client.put(FIRST_RUN_URL, json={"full_name": "Jane Agent"})
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def test_missing_full_name_returns_422():
    _, token = _create_agent()
    resp = client.put(FIRST_RUN_URL, json={}, cookies=_cookies(token))
    assert resp.status_code == 422


def test_empty_full_name_returns_422():
    _, token = _create_agent()
    resp = client.put(FIRST_RUN_URL, json={"full_name": ""}, cookies=_cookies(token))
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Old endpoint is gone
# ---------------------------------------------------------------------------

def test_old_onboarding_profile_endpoint_removed():
    """PUT /agent/onboarding/profile must not exist after A2."""
    _, token = _create_agent()
    resp = client.put(
        "/api/v1/agent/onboarding/profile",
        json={"full_name": "Jane Agent"},
        cookies=_cookies(token),
    )
    assert resp.status_code in (404, 405)


def test_old_onboarding_templates_endpoint_removed():
    """PUT /agent/onboarding/templates must not exist after A2."""
    _, token = _create_agent()
    resp = client.put(
        "/api/v1/agent/onboarding/templates",
        json={"templates": []},
        cookies=_cookies(token),
    )
    assert resp.status_code in (404, 405)
