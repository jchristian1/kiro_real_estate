"""
Unit tests for agent templates CRUD endpoints.

Tests cover:
- GET /api/v1/agent/templates — returns all 4 types, is_custom flag
- PUT /api/v1/agent/templates/{type} — create with version=1, update increments version
- PUT /api/v1/agent/templates/{type} — 422 for invalid type
- POST /api/v1/agent/templates/{type}/preview — renders with sample data
- DELETE /api/v1/agent/templates/{type} — deletes override, idempotent
- All endpoints return 401 when unauthenticated

Requirements: 14.1, 14.2, 14.3, 14.4
"""

import secrets
from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from api.main import app, get_db
from gmail_lead_sync.agent_models import (  # noqa: F401 — registers agent tables
    AgentSession,
    AgentTemplate,
    AgentUser,
)
from gmail_lead_sync.models import Base, LeadSource

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


def _create_agent(full_name: str = "Test Agent", phone: str = "555-0100", email: str = None) -> tuple[AgentUser, str]:
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
    db.close()
    return agent, token


def _auth_cookies(token: str) -> dict:
    return {"agent_session": token}


# ---------------------------------------------------------------------------
# GET /api/v1/agent/templates
# ---------------------------------------------------------------------------


def test_list_templates_unauthenticated():
    resp = client.get("/api/v1/agent/templates")
    assert resp.status_code == 401


def test_list_templates_returns_all_four_types():
    _, token = _create_agent()
    resp = client.get("/api/v1/agent/templates", cookies=_auth_cookies(token))
    assert resp.status_code == 200
    data = resp.json()
    types = {t["type"] for t in data["templates"]}
    assert types == {"INITIAL_INVITE", "POST_HOT", "POST_WARM", "POST_NURTURE"}


def test_list_templates_no_overrides_is_custom_false():
    _, token = _create_agent()
    resp = client.get("/api/v1/agent/templates", cookies=_auth_cookies(token))
    assert resp.status_code == 200
    for tmpl in resp.json()["templates"]:
        assert tmpl["is_custom"] is False
        assert tmpl["version"] == 0


def test_list_templates_with_override_is_custom_true():
    agent, token = _create_agent()
    # Create an override
    db = TestingSessionLocal()
    db.add(AgentTemplate(
        agent_user_id=agent.id,
        template_type="POST_HOT",
        subject="Custom subject",
        body="Custom body",
        tone="FRIENDLY",
        is_active=True,
        version=1,
        created_at=datetime.utcnow(),
    ))
    db.commit()
    db.close()

    resp = client.get("/api/v1/agent/templates", cookies=_auth_cookies(token))
    assert resp.status_code == 200
    by_type = {t["type"]: t for t in resp.json()["templates"]}
    assert by_type["POST_HOT"]["is_custom"] is True
    assert by_type["POST_HOT"]["subject"] == "Custom subject"
    assert by_type["INITIAL_INVITE"]["is_custom"] is False


# ---------------------------------------------------------------------------
# PUT /api/v1/agent/templates/{type}
# ---------------------------------------------------------------------------


def test_put_template_unauthenticated():
    resp = client.put(
        "/api/v1/agent/templates/INITIAL_INVITE",
        json={"subject": "Hi", "body": "Body"},
    )
    assert resp.status_code == 401


def test_put_template_creates_with_version_1():
    _, token = _create_agent()
    resp = client.put(
        "/api/v1/agent/templates/INITIAL_INVITE",
        json={"subject": "Hello {lead_name}", "body": "Welcome!"},
        cookies=_auth_cookies(token),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    assert data["version"] == 1
    assert isinstance(data["template_id"], int)


def test_put_template_increments_version_on_update():
    _, token = _create_agent()
    # First save
    resp1 = client.put(
        "/api/v1/agent/templates/POST_HOT",
        json={"subject": "v1 subject", "body": "v1 body"},
        cookies=_auth_cookies(token),
    )
    assert resp1.json()["version"] == 1

    # Second save — version should be 2
    resp2 = client.put(
        "/api/v1/agent/templates/POST_HOT",
        json={"subject": "v2 subject", "body": "v2 body"},
        cookies=_auth_cookies(token),
    )
    assert resp2.status_code == 200
    assert resp2.json()["version"] == 2


def test_put_template_multiple_saves_increment_monotonically():
    _, token = _create_agent()
    for expected_version in range(1, 5):
        resp = client.put(
            "/api/v1/agent/templates/POST_WARM",
            json={"subject": f"v{expected_version}", "body": "body"},
            cookies=_auth_cookies(token),
        )
        assert resp.status_code == 200
        assert resp.json()["version"] == expected_version


def test_put_template_invalid_type_returns_422():
    _, token = _create_agent()
    resp = client.put(
        "/api/v1/agent/templates/INVALID_TYPE",
        json={"subject": "Hi", "body": "Body"},
        cookies=_auth_cookies(token),
    )
    assert resp.status_code == 422


def test_put_template_case_insensitive_type():
    _, token = _create_agent()
    resp = client.put(
        "/api/v1/agent/templates/initial_invite",
        json={"subject": "Hi {lead_name}", "body": "Body"},
        cookies=_auth_cookies(token),
    )
    assert resp.status_code == 200
    assert resp.json()["version"] == 1


def test_put_template_with_tone():
    _, token = _create_agent()
    resp = client.put(
        "/api/v1/agent/templates/POST_NURTURE",
        json={"subject": "Hi", "body": "Body", "tone": "FRIENDLY"},
        cookies=_auth_cookies(token),
    )
    assert resp.status_code == 200
    # Verify tone was persisted
    list_resp = client.get("/api/v1/agent/templates", cookies=_auth_cookies(token))
    by_type = {t["type"]: t for t in list_resp.json()["templates"]}
    assert by_type["POST_NURTURE"]["tone"] == "FRIENDLY"


# ---------------------------------------------------------------------------
# POST /api/v1/agent/templates/{type}/preview
# ---------------------------------------------------------------------------


def test_preview_unauthenticated():
    resp = client.post(
        "/api/v1/agent/templates/INITIAL_INVITE/preview",
        json={"subject": "Hi {lead_name}", "body": "Hello {agent_name}"},
    )
    assert resp.status_code == 401


def test_preview_renders_placeholders():
    agent, token = _create_agent(full_name="Sarah Smith", phone="555-9999")
    resp = client.post(
        "/api/v1/agent/templates/INITIAL_INVITE/preview",
        json={
            "subject": "Hi {lead_name}, contact {agent_name}",
            "body": "Call {agent_phone} or email {agent_email}. Form: {form_link}",
        },
        cookies=_auth_cookies(token),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "Alex Johnson" in data["subject_rendered"]
    assert "Sarah Smith" in data["subject_rendered"]
    assert "555-9999" in data["body_rendered"]
    assert "https://app.example.com/form/123" in data["body_rendered"]


def test_preview_subject_has_no_newlines():
    _, token = _create_agent()
    resp = client.post(
        "/api/v1/agent/templates/POST_HOT/preview",
        json={"subject": "Line1\nLine2", "body": "Body"},
        cookies=_auth_cookies(token),
    )
    assert resp.status_code == 200
    assert "\n" not in resp.json()["subject_rendered"]


def test_preview_invalid_type_returns_422():
    _, token = _create_agent()
    resp = client.post(
        "/api/v1/agent/templates/BOGUS/preview",
        json={"subject": "Hi", "body": "Body"},
        cookies=_auth_cookies(token),
    )
    assert resp.status_code == 422


def test_preview_no_unresolved_placeholders():
    _, token = _create_agent(full_name="Agent Name", phone="555-1234")
    resp = client.post(
        "/api/v1/agent/templates/POST_WARM/preview",
        json={
            "subject": "Hi {lead_name}",
            "body": "{lead_name} {agent_name} {agent_phone} {agent_email} {form_link}",
        },
        cookies=_auth_cookies(token),
    )
    assert resp.status_code == 200
    data = resp.json()
    import re
    # No unresolved {placeholder} tokens should remain
    assert not re.search(r"\{[a-z_]+\}", data["subject_rendered"])
    assert not re.search(r"\{[a-z_]+\}", data["body_rendered"])


# ---------------------------------------------------------------------------
# DELETE /api/v1/agent/templates/{type}
# ---------------------------------------------------------------------------


def test_delete_template_unauthenticated():
    resp = client.delete("/api/v1/agent/templates/POST_HOT")
    assert resp.status_code == 401


def test_delete_template_removes_override():
    agent, token = _create_agent()
    # Create override first
    client.put(
        "/api/v1/agent/templates/POST_HOT",
        json={"subject": "Custom", "body": "Custom body"},
        cookies=_auth_cookies(token),
    )
    # Verify it's custom
    list_resp = client.get("/api/v1/agent/templates", cookies=_auth_cookies(token))
    by_type = {t["type"]: t for t in list_resp.json()["templates"]}
    assert by_type["POST_HOT"]["is_custom"] is True

    # Delete
    del_resp = client.delete("/api/v1/agent/templates/POST_HOT", cookies=_auth_cookies(token))
    assert del_resp.status_code == 200
    assert del_resp.json() == {"ok": True, "reverted_to": "platform_default"}

    # Now should be platform default
    list_resp2 = client.get("/api/v1/agent/templates", cookies=_auth_cookies(token))
    by_type2 = {t["type"]: t for t in list_resp2.json()["templates"]}
    assert by_type2["POST_HOT"]["is_custom"] is False


def test_delete_template_idempotent_no_override():
    _, token = _create_agent()
    # No override exists — should still return 200
    resp = client.delete("/api/v1/agent/templates/POST_NURTURE", cookies=_auth_cookies(token))
    assert resp.status_code == 200
    assert resp.json()["ok"] is True
    assert resp.json()["reverted_to"] == "platform_default"


def test_delete_template_invalid_type_returns_422():
    _, token = _create_agent()
    resp = client.delete("/api/v1/agent/templates/UNKNOWN", cookies=_auth_cookies(token))
    assert resp.status_code == 422


def test_delete_then_recreate_starts_at_version_1():
    _, token = _create_agent()
    # Create, then delete, then recreate
    client.put(
        "/api/v1/agent/templates/INITIAL_INVITE",
        json={"subject": "v1", "body": "body"},
        cookies=_auth_cookies(token),
    )
    client.put(
        "/api/v1/agent/templates/INITIAL_INVITE",
        json={"subject": "v2", "body": "body"},
        cookies=_auth_cookies(token),
    )
    client.delete("/api/v1/agent/templates/INITIAL_INVITE", cookies=_auth_cookies(token))

    # Recreate — should start at version 1 again
    resp = client.put(
        "/api/v1/agent/templates/INITIAL_INVITE",
        json={"subject": "fresh", "body": "body"},
        cookies=_auth_cookies(token),
    )
    assert resp.status_code == 200
    assert resp.json()["version"] == 1
