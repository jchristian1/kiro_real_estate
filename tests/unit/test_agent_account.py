"""
Unit tests for agent account/Gmail management endpoints.

Tests cover:
- GET  /api/v1/agent/account/gmail          — connection status
- POST /api/v1/agent/account/gmail/test     — test stored credentials
- PUT  /api/v1/agent/account/gmail          — update credentials (test first)
- DELETE /api/v1/agent/account/gmail        — disconnect Gmail
- PATCH /api/v1/agent/account/watcher       — toggle watcher, 403 on admin lock
- PUT  /api/v1/agent/account/preferences    — update service_area, timezone, quiet hours

Requirements: 16.1, 16.2, 16.3, 16.4, 16.5, 16.6
"""

import os
import secrets
from datetime import datetime, timedelta
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# Set up encryption key before importing app
os.environ.setdefault(
    "CREDENTIAL_ENCRYPTION_KEY",
    "dGVzdGtleXRlc3RrZXl0ZXN0a2V5dGVzdGtleXRlc3Q=",  # 32-byte base64
)

from api.main import app, get_db
from gmail_lead_sync.agent_models import (  # noqa: F401
    AgentPreferences,
    AgentSession,
    AgentUser,
)
from gmail_lead_sync.models import Base, Credentials, LeadSource

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
client = TestClient(app, raise_server_exceptions=True)


@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
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


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _create_agent(
    full_name: str = "Test Agent",
    phone: str = "555-0100",
    email: str = None,
    credentials_id: int = None,
) -> tuple[AgentUser, str]:
    """Create an agent and a valid session, return (agent, cookie_value)."""
    db = TestingSessionLocal()
    unique_email = email or f"agent_{secrets.token_hex(4)}@test.com"
    agent = AgentUser(
        email=unique_email,
        password_hash="hashed",
        full_name=full_name,
        phone=phone,
        onboarding_step=6,
        onboarding_completed=True,
        credentials_id=credentials_id,
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
    db.refresh(agent)
    agent_id = agent.id
    db.close()
    return agent_id, token


def _create_credentials(gmail_address: str, app_password_encrypted: str) -> int:
    """Create a Credentials record and return its id."""
    db = TestingSessionLocal()
    creds = Credentials(
        agent_id="test",
        email_encrypted=gmail_address,
        app_password_encrypted=app_password_encrypted,
    )
    db.add(creds)
    db.commit()
    creds_id = creds.id
    db.close()
    return creds_id


def _set_agent_credentials(agent_id: int, credentials_id: int):
    db = TestingSessionLocal()
    agent = db.query(AgentUser).filter(AgentUser.id == agent_id).first()
    agent.credentials_id = credentials_id
    db.commit()
    db.close()


def _create_prefs(agent_id: int, watcher_enabled: bool = True, watcher_admin_override: bool = False):
    db = TestingSessionLocal()
    prefs = AgentPreferences(
        agent_user_id=agent_id,
        watcher_enabled=watcher_enabled,
        watcher_admin_override=watcher_admin_override,
        created_at=datetime.utcnow(),
    )
    db.add(prefs)
    db.commit()
    db.close()


def _auth_cookies(token: str) -> dict:
    return {"agent_session": token}


# ---------------------------------------------------------------------------
# GET /api/v1/agent/account/gmail
# ---------------------------------------------------------------------------


def test_get_gmail_status_unauthenticated():
    resp = client.get("/api/v1/agent/account/gmail")
    assert resp.status_code == 401


def test_get_gmail_status_not_connected():
    agent_id, token = _create_agent()
    resp = client.get("/api/v1/agent/account/gmail", cookies=_auth_cookies(token))
    assert resp.status_code == 200
    data = resp.json()
    assert data["connected"] is False
    assert data["gmail_address"] is None
    assert data["last_sync"] is None
    assert data["watcher_enabled"] is True   # default
    assert data["watcher_admin_locked"] is False  # default


def test_get_gmail_status_connected():
    from api.services.credential_encryption import encrypt_app_password
    agent_id, token = _create_agent()
    creds_id = _create_credentials("agent@gmail.com", encrypt_app_password("testpass"))
    _set_agent_credentials(agent_id, creds_id)

    resp = client.get("/api/v1/agent/account/gmail", cookies=_auth_cookies(token))
    assert resp.status_code == 200
    data = resp.json()
    assert data["connected"] is True
    assert data["gmail_address"] == "agent@gmail.com"


def test_get_gmail_status_reflects_prefs():
    agent_id, token = _create_agent()
    _create_prefs(agent_id, watcher_enabled=False, watcher_admin_override=True)

    resp = client.get("/api/v1/agent/account/gmail", cookies=_auth_cookies(token))
    assert resp.status_code == 200
    data = resp.json()
    assert data["watcher_enabled"] is False
    assert data["watcher_admin_locked"] is True


# ---------------------------------------------------------------------------
# POST /api/v1/agent/account/gmail/test
# ---------------------------------------------------------------------------


def test_test_gmail_unauthenticated():
    resp = client.post("/api/v1/agent/account/gmail/test")
    assert resp.status_code == 401


def test_test_gmail_no_credentials():
    agent_id, token = _create_agent()
    resp = client.post("/api/v1/agent/account/gmail/test", cookies=_auth_cookies(token))
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is False
    assert data["error"] == "NO_CREDENTIALS"


def test_test_gmail_success():
    from api.services.credential_encryption import encrypt_app_password
    agent_id, token = _create_agent()
    creds_id = _create_credentials("agent@gmail.com", encrypt_app_password("testpass"))
    _set_agent_credentials(agent_id, creds_id)

    with patch("api.routers.agent_account.test_imap_connection") as mock_imap:
        mock_imap.return_value = {"success": True, "last_sync": None}
        resp = client.post("/api/v1/agent/account/gmail/test", cookies=_auth_cookies(token))

    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    assert data["error"] is None


def test_test_gmail_imap_failure():
    from api.services.credential_encryption import encrypt_app_password
    agent_id, token = _create_agent()
    creds_id = _create_credentials("agent@gmail.com", encrypt_app_password("testpass"))
    _set_agent_credentials(agent_id, creds_id)

    with patch("api.routers.agent_account.test_imap_connection") as mock_imap:
        mock_imap.return_value = {
            "success": False,
            "error": "INVALID_PASSWORD",
            "message": "Invalid credentials",
        }
        resp = client.post("/api/v1/agent/account/gmail/test", cookies=_auth_cookies(token))

    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is False
    assert data["error"] == "INVALID_PASSWORD"


# ---------------------------------------------------------------------------
# PUT /api/v1/agent/account/gmail
# ---------------------------------------------------------------------------


def test_put_gmail_unauthenticated():
    resp = client.put(
        "/api/v1/agent/account/gmail",
        json={"gmail_address": "a@gmail.com", "app_password": "pass"},
    )
    assert resp.status_code == 401


def test_put_gmail_success_creates_credentials():
    agent_id, token = _create_agent()

    with patch("api.routers.agent_account.test_imap_connection") as mock_imap:
        mock_imap.return_value = {"success": True, "last_sync": None}
        resp = client.put(
            "/api/v1/agent/account/gmail",
            json={"gmail_address": "new@gmail.com", "app_password": "apppass123"},
            cookies=_auth_cookies(token),
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["connected"] is True
    assert data["gmail_address"] == "new@gmail.com"

    # Verify credentials were persisted
    db = TestingSessionLocal()
    agent = db.query(AgentUser).filter(AgentUser.id == agent_id).first()
    assert agent.credentials_id is not None
    creds = db.query(Credentials).filter(Credentials.id == agent.credentials_id).first()
    assert creds.email_encrypted == "new@gmail.com"
    db.close()


def test_put_gmail_imap_failure_returns_422():
    agent_id, token = _create_agent()

    with patch("api.routers.agent_account.test_imap_connection") as mock_imap:
        mock_imap.return_value = {
            "success": False,
            "error": "IMAP_DISABLED",
            "message": "IMAP is disabled",
        }
        resp = client.put(
            "/api/v1/agent/account/gmail",
            json={"gmail_address": "bad@gmail.com", "app_password": "wrongpass"},
            cookies=_auth_cookies(token),
        )

    assert resp.status_code == 422
    assert resp.json()["error"] == "IMAP_DISABLED"


def test_put_gmail_updates_existing_credentials():
    from api.services.credential_encryption import encrypt_app_password
    agent_id, token = _create_agent()
    creds_id = _create_credentials("old@gmail.com", encrypt_app_password("oldpass"))
    _set_agent_credentials(agent_id, creds_id)

    with patch("api.routers.agent_account.test_imap_connection") as mock_imap:
        mock_imap.return_value = {"success": True, "last_sync": None}
        resp = client.put(
            "/api/v1/agent/account/gmail",
            json={"gmail_address": "new@gmail.com", "app_password": "newpass"},
            cookies=_auth_cookies(token),
        )

    assert resp.status_code == 200
    assert resp.json()["gmail_address"] == "new@gmail.com"

    # Verify same credentials record was updated (not a new one)
    db = TestingSessionLocal()
    agent = db.query(AgentUser).filter(AgentUser.id == agent_id).first()
    assert agent.credentials_id == creds_id
    creds = db.query(Credentials).filter(Credentials.id == creds_id).first()
    assert creds.email_encrypted == "new@gmail.com"
    db.close()


def test_put_gmail_app_password_not_in_response():
    """app_password must never appear in the response body (Requirement 19.4)."""
    agent_id, token = _create_agent()

    with patch("api.routers.agent_account.test_imap_connection") as mock_imap:
        mock_imap.return_value = {"success": True, "last_sync": None}
        resp = client.put(
            "/api/v1/agent/account/gmail",
            json={"gmail_address": "a@gmail.com", "app_password": "supersecret123"},
            cookies=_auth_cookies(token),
        )

    assert resp.status_code == 200
    assert "supersecret123" not in resp.text


# ---------------------------------------------------------------------------
# DELETE /api/v1/agent/account/gmail
# ---------------------------------------------------------------------------


def test_delete_gmail_unauthenticated():
    resp = client.delete("/api/v1/agent/account/gmail")
    assert resp.status_code == 401


def test_delete_gmail_clears_credentials_and_stops_watcher():
    from api.services.credential_encryption import encrypt_app_password
    agent_id, token = _create_agent()
    creds_id = _create_credentials("agent@gmail.com", encrypt_app_password("pass"))
    _set_agent_credentials(agent_id, creds_id)
    _create_prefs(agent_id, watcher_enabled=True)

    resp = client.delete("/api/v1/agent/account/gmail", cookies=_auth_cookies(token))
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    assert data["watcher_stopped"] is True

    # Verify credentials_id is cleared
    db = TestingSessionLocal()
    agent = db.query(AgentUser).filter(AgentUser.id == agent_id).first()
    assert agent.credentials_id is None

    # Verify watcher_enabled is False
    prefs = db.query(AgentPreferences).filter(AgentPreferences.agent_user_id == agent_id).first()
    assert prefs.watcher_enabled is False
    db.close()


def test_delete_gmail_idempotent_when_not_connected():
    agent_id, token = _create_agent()
    resp = client.delete("/api/v1/agent/account/gmail", cookies=_auth_cookies(token))
    assert resp.status_code == 200
    assert resp.json()["ok"] is True
    assert resp.json()["watcher_stopped"] is True


# ---------------------------------------------------------------------------
# PATCH /api/v1/agent/account/watcher
# ---------------------------------------------------------------------------


def test_patch_watcher_unauthenticated():
    resp = client.patch("/api/v1/agent/account/watcher", json={"enabled": True})
    assert resp.status_code == 401


def test_patch_watcher_enable():
    agent_id, token = _create_agent()
    _create_prefs(agent_id, watcher_enabled=False)

    resp = client.patch(
        "/api/v1/agent/account/watcher",
        json={"enabled": True},
        cookies=_auth_cookies(token),
    )
    assert resp.status_code == 200
    assert resp.json()["watcher_enabled"] is True


def test_patch_watcher_disable():
    agent_id, token = _create_agent()
    _create_prefs(agent_id, watcher_enabled=True)

    resp = client.patch(
        "/api/v1/agent/account/watcher",
        json={"enabled": False},
        cookies=_auth_cookies(token),
    )
    assert resp.status_code == 200
    assert resp.json()["watcher_enabled"] is False


def test_patch_watcher_admin_locked_returns_403():
    """When watcher_admin_override=True, any toggle returns 403 ADMIN_LOCKED."""
    agent_id, token = _create_agent()
    _create_prefs(agent_id, watcher_enabled=True, watcher_admin_override=True)

    # Try to enable
    resp_enable = client.patch(
        "/api/v1/agent/account/watcher",
        json={"enabled": True},
        cookies=_auth_cookies(token),
    )
    assert resp_enable.status_code == 403
    assert resp_enable.json()["detail"]["error"] == "ADMIN_LOCKED"

    # Try to disable — still 403
    resp_disable = client.patch(
        "/api/v1/agent/account/watcher",
        json={"enabled": False},
        cookies=_auth_cookies(token),
    )
    assert resp_disable.status_code == 403
    assert resp_disable.json()["detail"]["error"] == "ADMIN_LOCKED"


def test_patch_watcher_admin_locked_regardless_of_value():
    """Requirement 16.6: 403 regardless of enabled value when admin-locked."""
    agent_id, token = _create_agent()
    _create_prefs(agent_id, watcher_enabled=False, watcher_admin_override=True)

    for enabled_value in [True, False]:
        resp = client.patch(
            "/api/v1/agent/account/watcher",
            json={"enabled": enabled_value},
            cookies=_auth_cookies(token),
        )
        assert resp.status_code == 403


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
    """Updating only service_area should not reset timezone."""
    agent_id, token = _create_agent()
    # Set timezone first
    client.put(
        "/api/v1/agent/account/preferences",
        json={"timezone": "America/Chicago"},
        cookies=_auth_cookies(token),
    )
    # Update only service_area
    client.put(
        "/api/v1/agent/account/preferences",
        json={"service_area": "Chicago, IL"},
        cookies=_auth_cookies(token),
    )

    db = TestingSessionLocal()
    agent = db.query(AgentUser).filter(AgentUser.id == agent_id).first()
    assert agent.timezone == "America/Chicago"
    assert agent.service_area == "Chicago, IL"
    db.close()


def test_put_preferences_empty_body_returns_ok():
    """Empty body is valid — no fields are required."""
    agent_id, token = _create_agent()
    resp = client.put(
        "/api/v1/agent/account/preferences",
        json={},
        cookies=_auth_cookies(token),
    )
    assert resp.status_code == 200
    assert resp.json()["ok"] is True


def test_put_preferences_creates_prefs_if_not_exists():
    """AgentPreferences should be created if it doesn't exist yet."""
    agent_id, token = _create_agent()

    db = TestingSessionLocal()
    db.query(AgentPreferences).filter(AgentPreferences.agent_user_id == agent_id).first()
    db.close()

    resp = client.put(
        "/api/v1/agent/account/preferences",
        json={"quiet_hours_start": "22:00"},
        cookies=_auth_cookies(token),
    )
    assert resp.status_code == 200

    db = TestingSessionLocal()
    prefs_after = db.query(AgentPreferences).filter(AgentPreferences.agent_user_id == agent_id).first()
    assert prefs_after is not None
    db.close()
