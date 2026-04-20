"""
Unit tests for agent account management endpoints (PR A1).

Gmail/watcher endpoints removed — only preferences remain.

Tests cover:
- PUT /api/v1/agent/account/preferences — update service_area, timezone, quiet hours

Requirements: 16.5
"""

import os
import secrets
from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

os.environ.setdefault(
    "CREDENTIAL_ENCRYPTION_KEY",
    "dGVzdGtleXRlc3RrZXl0ZXN0a2V5dGVzdGtleXRlc3Q=",
)

from api.main import app, get_db
from gmail_lead_sync.agent_models import AgentPreferences, AgentSession, AgentUser  # noqa: F401
from gmail_lead_sync.models import Base, LeadSource

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
    db = TestingSessionLocal()
    ls = LeadSource(
        sender_email="leads@test.com",
        identifier_snippet="Lead",
        name_regex=r"Name:\s*(.+)",
        phone_regex=r"Phone:\s*([\d-]+)",
    )
    db.add(ls)
    db.commit()
    db.close()
    yield
    Base.metadata.drop_all(bind=engine)


def _create_agent(full_name: str = "Test Agent", phone: str = "555-0100") -> tuple[int, str]:
    db = TestingSessionLocal()
    agent = AgentUser(
        email=f"agent_{secrets.token_hex(4)}@test.com",
        password_hash="hashed",
        full_name=full_name,
        phone=phone,
        onboarding_completed=True,
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


def _auth_cookies(token: str) -> dict:
    return {"agent_session": token}


# ---------------------------------------------------------------------------
# PUT /api/v1/agent/account/preferences
# ---------------------------------------------------------------------------

def test_put_preferences_unauthenticated():
    resp = client.put("/api/v1/agent/account/preferences", json={})
    assert resp.status_code == 401


def test_put_preferences_updates_service_area():
    agent_id, token = _create_agent()
    resp = client.put(
        "/api/v1/agent/account/preferences",
        json={"service_area": "Brooklyn, NY"},
        cookies=_auth_cookies(token),
    )
    assert resp.status_code == 200
    assert resp.json()["ok"] is True
    db = TestingSessionLocal()
    agent = db.query(AgentUser).filter(AgentUser.id == agent_id).first()
    assert agent.service_area == "Brooklyn, NY"
    db.close()


def test_put_preferences_updates_timezone():
    agent_id, token = _create_agent()
    resp = client.put(
        "/api/v1/agent/account/preferences",
        json={"timezone": "America/New_York"},
        cookies=_auth_cookies(token),
    )
    assert resp.status_code == 200
    db = TestingSessionLocal()
    agent = db.query(AgentUser).filter(AgentUser.id == agent_id).first()
    assert agent.timezone == "America/New_York"
    db.close()


def test_put_preferences_updates_quiet_hours():
    agent_id, token = _create_agent()
    resp = client.put(
        "/api/v1/agent/account/preferences",
        json={"quiet_hours_start": "21:00", "quiet_hours_end": "08:00"},
        cookies=_auth_cookies(token),
    )
    assert resp.status_code == 200
    db = TestingSessionLocal()
    prefs = db.query(AgentPreferences).filter(AgentPreferences.agent_user_id == agent_id).first()
    assert prefs is not None
    assert prefs.quiet_hours_start is not None
    assert prefs.quiet_hours_end is not None
    db.close()


def test_put_preferences_partial_update_preserves_other_fields():
    agent_id, token = _create_agent()
    client.put("/api/v1/agent/account/preferences", json={"timezone": "America/Chicago"}, cookies=_auth_cookies(token))
    client.put("/api/v1/agent/account/preferences", json={"service_area": "Chicago, IL"}, cookies=_auth_cookies(token))
    db = TestingSessionLocal()
    agent = db.query(AgentUser).filter(AgentUser.id == agent_id).first()
    assert agent.timezone == "America/Chicago"
    assert agent.service_area == "Chicago, IL"
    db.close()


def test_put_preferences_empty_body_returns_ok():
    _, token = _create_agent()
    resp = client.put("/api/v1/agent/account/preferences", json={}, cookies=_auth_cookies(token))
    assert resp.status_code == 200
    assert resp.json()["ok"] is True


def test_put_preferences_creates_prefs_if_not_exists():
    agent_id, token = _create_agent()
    resp = client.put(
        "/api/v1/agent/account/preferences",
        json={"quiet_hours_start": "22:00"},
        cookies=_auth_cookies(token),
    )
    assert resp.status_code == 200
    db = TestingSessionLocal()
    prefs = db.query(AgentPreferences).filter(AgentPreferences.agent_user_id == agent_id).first()
    assert prefs is not None
    db.close()


# ---------------------------------------------------------------------------
# Confirm removed endpoints return 404/405
# ---------------------------------------------------------------------------

def test_get_gmail_endpoint_removed():
    """GET /agent/account/gmail must not exist after PR A1."""
    _, token = _create_agent()
    resp = client.get("/api/v1/agent/account/gmail", cookies=_auth_cookies(token))
    assert resp.status_code in (404, 405)


def test_patch_watcher_endpoint_removed():
    """PATCH /agent/account/watcher must not exist after PR A1."""
    _, token = _create_agent()
    resp = client.patch("/api/v1/agent/account/watcher", json={"enabled": True}, cookies=_auth_cookies(token))
    assert resp.status_code in (404, 405)
