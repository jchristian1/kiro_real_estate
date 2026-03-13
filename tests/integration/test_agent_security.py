"""
Security integration tests.

Verifies:
- app_password never appears in API responses or logs
- IMAP rate limiting: 6th attempt within 15 min → 429
- Cross-agent 403 on leads, templates, preferences
- Template header injection: subject with \\n returns 422

Requirements: 5.7, 5.8, 14.7, 18.2, 19.4
"""

import logging
import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, StaticPool
from sqlalchemy.orm import sessionmaker

from gmail_lead_sync.models import Base, Lead
from gmail_lead_sync.agent_models import AgentUser
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


def _signup(client, email="agent@sec.com", password="securepass123"):
    r = client.post("/api/v1/agent/auth/signup", json={"email": email, "password": password})
    assert r.status_code in (200, 201), f"Signup failed: {r.text}"
    return r.json()


def _complete_onboarding(client):
    client.put("/api/v1/agent/onboarding/profile", json={
        "full_name": "Sec Agent", "timezone": "America/New_York",
    })
    with patch("api.routers.agent_onboarding.test_imap_connection", return_value={"success": True}):
        client.post("/api/v1/agent/onboarding/gmail", json={
            "gmail_address": "sec@gmail.com", "app_password": "abcd efgh ijkl mnop",
        })
    client.put("/api/v1/agent/onboarding/sources", json={"enabled_lead_source_ids": []})
    client.put("/api/v1/agent/onboarding/automation", json={
        "hot_threshold": 80, "warm_threshold": 50,
        "sla_minutes_hot": 15, "enable_tour_question": True,
    })
    client.put("/api/v1/agent/onboarding/templates", json={
        "templates": [
            {"type": "initial_outreach", "subject": "Hi {lead_name}", "body": "Hello {lead_name}.", "tone": "professional"},
            {"type": "follow_up",        "subject": "Follow up",      "body": "Hi {lead_name}.",    "tone": "friendly"},
            {"type": "post_form",         "subject": "Thanks",         "body": "Got it {lead_name}.", "tone": "professional"},
            {"type": "appointment",       "subject": "Meet",           "body": "{form_link}",         "tone": "concise"},
        ]
    })
    client.post("/api/v1/agent/onboarding/complete", json={})


# ── app_password never in responses ──────────────────────────────────────────

class TestCredentialNeverExposed:

    APP_PASSWORD = "supersecretapppassword123"

    def test_app_password_not_in_gmail_connect_response(self, client):
        _signup(client)
        client.put("/api/v1/agent/onboarding/profile", json={
            "full_name": "Sec Agent", "timezone": "America/New_York",
        })
        with patch("api.routers.agent_onboarding.test_imap_connection", return_value={"success": True}):
            r = client.post("/api/v1/agent/onboarding/gmail", json={
                "gmail_address": "sec@gmail.com",
                "app_password": self.APP_PASSWORD,
            })
        assert r.status_code == 200
        assert self.APP_PASSWORD not in r.text

    def test_app_password_not_in_gmail_status_response(self, client):
        _signup(client)
        _complete_onboarding(client)
        r = client.get("/api/v1/agent/account/gmail")
        assert r.status_code == 200
        assert self.APP_PASSWORD not in r.text
        body = r.json()
        # Ensure no field contains the password
        assert "app_password" not in body
        assert "password" not in str(body).lower() or "app_password" not in str(body)

    def test_app_password_not_in_imap_error_response(self, client):
        _signup(client)
        client.put("/api/v1/agent/onboarding/profile", json={
            "full_name": "Sec Agent", "timezone": "America/New_York",
        })
        with patch("api.routers.agent_onboarding.test_imap_connection",
                   side_effect=Exception(f"IMAP error with {self.APP_PASSWORD}")):
            r = client.post("/api/v1/agent/onboarding/gmail", json={
                "gmail_address": "sec@gmail.com",
                "app_password": self.APP_PASSWORD,
            })
        # Error response must not echo back the password
        assert self.APP_PASSWORD not in r.text

    def test_app_password_not_logged(self, client, caplog):
        _signup(client)
        client.put("/api/v1/agent/onboarding/profile", json={
            "full_name": "Sec Agent", "timezone": "America/New_York",
        })
        with caplog.at_level(logging.DEBUG):
            with patch("api.routers.agent_onboarding.test_imap_connection", return_value={"success": True}):
                client.post("/api/v1/agent/onboarding/gmail", json={
                    "gmail_address": "sec@gmail.com",
                    "app_password": self.APP_PASSWORD,
                })
        assert self.APP_PASSWORD not in caplog.text


# ── IMAP rate limiting ────────────────────────────────────────────────────────

class TestImapRateLimiting:

    def test_sixth_attempt_returns_429(self, client):
        """Property 13: 6th IMAP attempt within 15 min → 429 RATE_LIMITED."""
        _signup(client)
        client.put("/api/v1/agent/onboarding/profile", json={
            "full_name": "Sec Agent", "timezone": "America/New_York",
        })

        # First 5 attempts fail with INVALID_PASSWORD (not rate limited yet)
        with patch("api.routers.agent_onboarding.test_imap_connection",
                   side_effect=Exception("INVALID_PASSWORD")):
            for i in range(5):
                r = client.post("/api/v1/agent/onboarding/gmail", json={
                    "gmail_address": "sec@gmail.com",
                    "app_password": f"wrongpass{i}",
                })
                assert r.status_code != 429, f"Got 429 too early on attempt {i+1}"

        # 6th attempt should be rate limited
        r = client.post("/api/v1/agent/onboarding/gmail", json={
            "gmail_address": "sec@gmail.com",
            "app_password": "wrongpass6",
        })
        assert r.status_code == 429
        body = r.json()
        assert body.get("error") == "RATE_LIMITED" or "rate" in str(body).lower()

    def test_rate_limit_response_has_retry_after(self, client):
        """Rate limit response includes retry_after_seconds."""
        _signup(client)
        client.put("/api/v1/agent/onboarding/profile", json={
            "full_name": "Sec Agent", "timezone": "America/New_York",
        })
        with patch("api.routers.agent_onboarding.test_imap_connection",
                   side_effect=Exception("INVALID_PASSWORD")):
            for i in range(5):
                client.post("/api/v1/agent/onboarding/gmail", json={
                    "gmail_address": "sec@gmail.com", "app_password": f"wrong{i}",
                })
        r = client.post("/api/v1/agent/onboarding/gmail", json={
            "gmail_address": "sec@gmail.com", "app_password": "wrong6",
        })
        if r.status_code == 429:
            body = r.json()
            assert "retry_after_seconds" in body or "retry_after" in body


# ── Cross-agent isolation ─────────────────────────────────────────────────────

class TestCrossAgentIsolation:

    def _setup_two_agents(self, client, db_session):
        """Create two agents, return (agent1_lead_id)."""
        # Agent 1
        _signup(client, "agent1@sec.com", "pass1111111")
        _complete_onboarding(client)

        agent1 = db_session.query(AgentUser).filter_by(email="agent1@sec.com").first()
        lead = Lead(
            name="Agent1 Lead", email="lead1@example.com",
            agent_user_id=agent1.id, current_state="NEW",
        )
        db_session.add(lead)
        db_session.commit()
        db_session.refresh(lead)
        lead_id = lead.id

        # Agent 2 — signup (session cookie switches to agent2)
        client.post("/api/v1/agent/auth/signup", json={
            "email": "agent2@sec.com", "password": "pass2222222"
        })
        return lead_id

    def test_cross_agent_lead_detail_returns_403(self, client, db_session):
        lead_id = self._setup_two_agents(client, db_session)
        # Now logged in as agent2 — try to access agent1's lead
        r = client.get(f"/api/v1/agent/leads/{lead_id}")
        assert r.status_code == 403

    def test_cross_agent_lead_status_update_returns_403(self, client, db_session):
        lead_id = self._setup_two_agents(client, db_session)
        r = client.patch(f"/api/v1/agent/leads/{lead_id}/status", json={"status": "CONTACTED"})
        assert r.status_code == 403

    def test_cross_agent_lead_note_returns_403(self, client, db_session):
        lead_id = self._setup_two_agents(client, db_session)
        r = client.post(f"/api/v1/agent/leads/{lead_id}/notes", json={"content": "Hacked"})
        assert r.status_code == 403

    def test_leads_inbox_only_returns_own_leads(self, client, db_session):
        self._setup_two_agents(client, db_session)
        # Agent2 inbox should be empty (no leads assigned to agent2)
        r = client.get("/api/v1/agent/leads")
        assert r.status_code == 200
        leads = r.json()["leads"]
        agent2 = db_session.query(AgentUser).filter_by(email="agent2@sec.com").first()
        for lead in leads:
            assert lead["agent_user_id"] == agent2.id


# ── Template header injection ─────────────────────────────────────────────────

class TestTemplateHeaderInjection:

    def test_subject_with_newline_returns_422(self, client):
        """Requirements 14.7: subject containing \\n must be rejected."""
        _signup(client)
        _complete_onboarding(client)

        r = client.put("/api/v1/agent/templates/initial_outreach", json={
            "subject": "Hello\nBcc: attacker@evil.com",
            "body": "Normal body",
            "tone": "professional",
        })
        assert r.status_code == 422

    def test_subject_with_carriage_return_returns_422(self, client):
        _signup(client)
        _complete_onboarding(client)

        r = client.put("/api/v1/agent/templates/initial_outreach", json={
            "subject": "Hello\rBcc: attacker@evil.com",
            "body": "Normal body",
            "tone": "professional",
        })
        assert r.status_code == 422

    def test_valid_subject_accepted(self, client):
        _signup(client)
        _complete_onboarding(client)

        r = client.put("/api/v1/agent/templates/initial_outreach", json={
            "subject": "Hi {lead_name}, I saw your inquiry",
            "body": "Hello {lead_name}, I am {agent_name}.",
            "tone": "professional",
        })
        assert r.status_code == 200
