"""
Integration test: Full agent onboarding flow.

Tests the complete sequence:
  signup → profile → gmail (mock IMAP) → sources → automation → templates → go-live → test simulation

Requirements: 1.1, 3.5, 9.1, 9.4
"""

import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, StaticPool
from sqlalchemy.orm import sessionmaker

from gmail_lead_sync.models import Base
from api.main import app, get_db


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def db_engine():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)


@pytest.fixture
def db_session(db_engine):
    SessionLocal = sessionmaker(bind=db_engine)
    session = SessionLocal()
    yield session
    session.close()


@pytest.fixture
def client(db_session):
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app, raise_server_exceptions=True) as c:
        yield c
    app.dependency_overrides.clear()


# ── Helpers ───────────────────────────────────────────────────────────────────

def signup_and_login(client, email="agent@example.com", password="securepass123"):
    """Sign up and return the authenticated client (session cookie set)."""
    r = client.post("/api/v1/agent/auth/signup", json={"email": email, "password": password})
    assert r.status_code in (200, 201), f"Signup failed: {r.text}"
    return r.json()


# ── Tests ─────────────────────────────────────────────────────────────────────

class TestFullOnboardingFlow:
    """End-to-end onboarding: signup → all steps → go-live."""

    def test_signup_creates_agent_and_session(self, client):
        agent = signup_and_login(client)
        assert agent["email"] == "agent@example.com"
        # onboarding_completed may not be in signup response; check onboarding_step
        assert agent.get("onboarding_completed", False) is False
        assert agent["onboarding_step"] in (0, 1)

    def test_me_returns_agent_after_signup(self, client):
        signup_and_login(client)
        r = client.get("/api/v1/agent/auth/me")
        assert r.status_code == 200
        assert r.json()["email"] == "agent@example.com"

    def test_profile_step(self, client):
        signup_and_login(client)
        r = client.put("/api/v1/agent/onboarding/profile", json={
            "full_name": "Jane Agent",
            "phone": "555-0100",
            "timezone": "America/New_York",
            "service_area": "Greater Boston",
        })
        assert r.status_code == 200
        me = client.get("/api/v1/agent/auth/me").json()
        assert me["onboarding_step"] >= 2

    def test_gmail_step_with_mock_imap(self, client):
        signup_and_login(client)
        client.put("/api/v1/agent/onboarding/profile", json={
            "full_name": "Jane Agent", "timezone": "America/New_York",
        })
        with patch("api.routers.agent_onboarding.test_imap_connection", return_value={"success": True}):
            r = client.post("/api/v1/agent/onboarding/gmail", json={
                "gmail_address": "jane@gmail.com",
                "app_password": "abcd efgh ijkl mnop",
            })
        assert r.status_code == 200

    def test_sources_step(self, client, db_session):
        signup_and_login(client)
        client.put("/api/v1/agent/onboarding/profile", json={
            "full_name": "Jane Agent", "timezone": "America/New_York",
        })
        with patch("api.routers.agent_onboarding.test_imap_connection", return_value={"success": True}):
            client.post("/api/v1/agent/onboarding/gmail", json={
                "gmail_address": "jane@gmail.com", "app_password": "abcd efgh ijkl mnop",
            })
        r = client.put("/api/v1/agent/onboarding/sources", json={"enabled_lead_source_ids": []})
        assert r.status_code == 200

    def test_automation_step(self, client):
        signup_and_login(client)
        client.put("/api/v1/agent/onboarding/profile", json={
            "full_name": "Jane Agent", "timezone": "America/New_York",
        })
        with patch("api.routers.agent_onboarding.test_imap_connection", return_value={"success": True}):
            client.post("/api/v1/agent/onboarding/gmail", json={
                "gmail_address": "jane@gmail.com", "app_password": "abcd efgh ijkl mnop",
            })
        client.put("/api/v1/agent/onboarding/sources", json={"enabled_lead_source_ids": []})
        r = client.put("/api/v1/agent/onboarding/automation", json={
            "hot_threshold": 80,
            "warm_threshold": 50,
            "sla_minutes_hot": 15,
            "enable_tour_question": True,
        })
        assert r.status_code == 200

    def test_templates_step(self, client):
        signup_and_login(client)
        client.put("/api/v1/agent/onboarding/profile", json={
            "full_name": "Jane Agent", "timezone": "America/New_York",
        })
        with patch("api.routers.agent_onboarding.test_imap_connection", return_value={"success": True}):
            client.post("/api/v1/agent/onboarding/gmail", json={
                "gmail_address": "jane@gmail.com", "app_password": "abcd efgh ijkl mnop",
            })
        client.put("/api/v1/agent/onboarding/sources", json={"enabled_lead_source_ids": []})
        client.put("/api/v1/agent/onboarding/automation", json={
            "hot_threshold": 80, "warm_threshold": 50,
            "sla_minutes_hot": 15, "enable_tour_question": True,
        })
        r = client.put("/api/v1/agent/onboarding/templates", json={
            "templates": [
                {"template_type": "INITIAL_INVITE", "subject": "Hi {lead_name}", "body": "Hello {lead_name}, I am {agent_name}.", "tone": "PROFESSIONAL"},
                {"template_type": "POST_HOT",       "subject": "Following up",   "body": "Just checking in, {lead_name}.",        "tone": "FRIENDLY"},
                {"template_type": "POST_WARM",      "subject": "Thanks {lead_name}", "body": "Got your form, {lead_name}.",        "tone": "PROFESSIONAL"},
                {"template_type": "POST_NURTURE",   "subject": "Let's meet",    "body": "Book here: {form_link}",                  "tone": "SHORT"},
            ]
        })
        assert r.status_code == 200

    def test_simulation_leaves_no_records(self, client, db_session):
        """Property 20: simulation must not persist any records."""
        signup_and_login(client)
        client.put("/api/v1/agent/onboarding/profile", json={
            "full_name": "Jane Agent", "timezone": "America/New_York",
        })
        with patch("api.routers.agent_onboarding.test_imap_connection", return_value={"success": True}):
            client.post("/api/v1/agent/onboarding/gmail", json={
                "gmail_address": "jane@gmail.com", "app_password": "abcd efgh ijkl mnop",
            })
        client.put("/api/v1/agent/onboarding/sources", json={"enabled_lead_source_ids": []})
        client.put("/api/v1/agent/onboarding/automation", json={
            "hot_threshold": 80, "warm_threshold": 50,
            "sla_minutes_hot": 15, "enable_tour_question": True,
        })
        client.put("/api/v1/agent/onboarding/templates", json={
            "templates": [
                {"template_type": "INITIAL_INVITE", "subject": "Hi {lead_name}", "body": "Hello {lead_name}.", "tone": "PROFESSIONAL"},
                {"template_type": "POST_HOT",        "subject": "Follow up",      "body": "Hi {lead_name}.",    "tone": "FRIENDLY"},
                {"template_type": "POST_WARM",         "subject": "Thanks",         "body": "Got it {lead_name}.", "tone": "PROFESSIONAL"},
                {"template_type": "POST_NURTURE",       "subject": "Meet",           "body": "{form_link}",         "tone": "SHORT"},
            ]
        })

        from gmail_lead_sync.models import Lead
        from gmail_lead_sync.agent_models import LeadEvent

        lead_count_before = db_session.query(Lead).count()
        event_count_before = db_session.query(LeadEvent).count()

        r = client.post("/api/v1/agent/onboarding/test", json={})
        assert r.status_code == 200

        assert db_session.query(Lead).count() == lead_count_before
        assert db_session.query(LeadEvent).count() == event_count_before

    def test_go_live_requires_all_preconditions(self, client):
        """go-live without completing all steps returns incomplete checklist."""
        signup_and_login(client)
        # Only complete profile — skip gmail, sources, automation, templates
        client.put("/api/v1/agent/onboarding/profile", json={
            "full_name": "Jane Agent", "timezone": "America/New_York",
        })
        r = client.post("/api/v1/agent/onboarding/complete", json={})
        # Should fail with missing preconditions
        assert r.status_code in (200, 400, 422)
        body = r.json()
        if r.status_code == 200:
            assert body.get("success") is False or body.get("missing")

    def test_full_flow_go_live_succeeds(self, client):
        """Complete all steps then go live — onboarding_completed becomes True."""
        signup_and_login(client)
        client.put("/api/v1/agent/onboarding/profile", json={
            "full_name": "Jane Agent", "timezone": "America/New_York",
        })
        with patch("api.routers.agent_onboarding.test_imap_connection", return_value={"success": True}):
            client.post("/api/v1/agent/onboarding/gmail", json={
                "gmail_address": "jane@gmail.com", "app_password": "abcd efgh ijkl mnop",
            })
        client.put("/api/v1/agent/onboarding/sources", json={"enabled_lead_source_ids": []})
        client.put("/api/v1/agent/onboarding/automation", json={
            "hot_threshold": 80, "warm_threshold": 50,
            "sla_minutes_hot": 15, "enable_tour_question": True,
        })
        client.put("/api/v1/agent/onboarding/templates", json={
            "templates": [
                {"template_type": "INITIAL_INVITE", "subject": "Hi {lead_name}", "body": "Hello {lead_name}.", "tone": "PROFESSIONAL"},
                {"template_type": "POST_HOT",        "subject": "Follow up",      "body": "Hi {lead_name}.",    "tone": "FRIENDLY"},
                {"template_type": "POST_WARM",         "subject": "Thanks",         "body": "Got it {lead_name}.", "tone": "PROFESSIONAL"},
                {"template_type": "POST_NURTURE",       "subject": "Meet",           "body": "{form_link}",         "tone": "SHORT"},
            ]
        })
        r = client.post("/api/v1/agent/onboarding/complete", json={})
        assert r.status_code == 200
        me = client.get("/api/v1/agent/auth/me").json()
        assert me["onboarding_completed"] is True
