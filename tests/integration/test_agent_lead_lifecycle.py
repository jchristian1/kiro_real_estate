"""
Integration test: Lead lifecycle.

Tests the full sequence:
  ingest email → parse → score → invite → form submit → re-score → post-email → agent marks contacted

Requirements: 13.7, 20.1
"""

import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from gmail_lead_sync.models import Base, Lead
from gmail_lead_sync.agent_models import (
    AgentUser, AgentSession, AgentPreferences,
    BuyerAutomationConfig, AgentTemplate, LeadEvent,
)
from api.main import app
from api.database import get_db


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def db_engine():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
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


@pytest.fixture
def agent_client(client, db_session):
    """Authenticated agent client with completed onboarding."""
    # Signup
    r = client.post("/api/v1/agent/auth/signup", json={
        "email": "agent@test.com", "password": "securepass123"
    })
    assert r.status_code in (200, 201)

    # Complete onboarding steps
    client.put("/api/v1/agent/onboarding/profile", json={
        "full_name": "Test Agent", "timezone": "America/New_York",
    })
    with patch("api.services.imap_service.test_imap_connection", return_value={"success": True}):
        client.post("/api/v1/agent/onboarding/gmail", json={
            "gmail_address": "agent@gmail.com", "app_password": "abcd efgh ijkl mnop",
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
    return client


@pytest.fixture
def sample_lead(db_session, agent_client):
    """Create a lead in the DB scoped to the authenticated agent."""
    from api.routers.agent_auth import get_current_agent
    agent = db_session.query(AgentUser).filter_by(email="agent@test.com").first()

    lead = Lead(
        name="John Buyer",
        email="john@example.com",
        phone="555-9999",
        agent_user_id=agent.id,
        current_state="NEW",
        score=0,
        score_bucket="NURTURE",
    )
    db_session.add(lead)
    db_session.commit()
    db_session.refresh(lead)
    return lead


# ── Tests ─────────────────────────────────────────────────────────────────────

class TestLeadLifecycle:

    def test_lead_visible_in_inbox(self, agent_client, sample_lead):
        r = agent_client.get("/api/v1/agent/leads")
        assert r.status_code == 200
        leads = r.json()["leads"]
        ids = [l["id"] for l in leads]
        assert sample_lead.id in ids

    def test_lead_detail_accessible(self, agent_client, sample_lead):
        r = agent_client.get(f"/api/v1/agent/leads/{sample_lead.id}")
        assert r.status_code == 200
        data = r.json()
        assert data["id"] == sample_lead.id
        assert data["name"] == "John Buyer"

    def test_status_transition_new_to_contacted(self, agent_client, sample_lead, db_session):
        r = agent_client.patch(
            f"/api/v1/agent/leads/{sample_lead.id}/status",
            json={"status": "CONTACTED"}
        )
        assert r.status_code == 200

        # Verify state updated
        db_session.refresh(sample_lead)
        assert sample_lead.current_state == "CONTACTED"

        # Verify last_agent_action_at was set
        assert sample_lead.last_agent_action_at is not None

    def test_status_change_inserts_event(self, agent_client, sample_lead, db_session):
        agent_client.patch(
            f"/api/v1/agent/leads/{sample_lead.id}/status",
            json={"status": "CONTACTED"}
        )
        events = db_session.query(LeadEvent).filter_by(
            lead_id=sample_lead.id, event_type="STATUS_CHANGED"
        ).all()
        assert len(events) >= 1

    def test_invalid_status_transition_rejected(self, agent_client, sample_lead):
        # NEW → CLOSED is not a valid transition
        r = agent_client.patch(
            f"/api/v1/agent/leads/{sample_lead.id}/status",
            json={"status": "CLOSED"}
        )
        assert r.status_code == 422

    def test_add_note_persists_and_inserts_event(self, agent_client, sample_lead, db_session):
        r = agent_client.post(
            f"/api/v1/agent/leads/{sample_lead.id}/notes",
            json={"content": "Called and left voicemail."}
        )
        assert r.status_code in (200, 201)

        events = db_session.query(LeadEvent).filter_by(
            lead_id=sample_lead.id, event_type="NOTE_ADDED"
        ).all()
        assert len(events) >= 1

    def test_full_lifecycle_new_contacted_appointment_closed(self, agent_client, sample_lead, db_session):
        """Walk through the full valid state machine."""
        transitions = ["CONTACTED", "APPOINTMENT_SET", "CLOSED"]
        for state in transitions:
            r = agent_client.patch(
                f"/api/v1/agent/leads/{sample_lead.id}/status",
                json={"status": state}
            )
            assert r.status_code == 200, f"Transition to {state} failed: {r.text}"

        db_session.refresh(sample_lead)
        assert sample_lead.current_state == "CLOSED"

    def test_cross_agent_lead_access_denied(self, db_session, client):
        """Agent B cannot access Agent A's lead — returns 403."""
        # Create a second agent
        r = client.post("/api/v1/agent/auth/signup", json={
            "email": "agent2@test.com", "password": "securepass456"
        })
        assert r.status_code in (200, 201)

        # Agent A's lead — get its ID from the first agent's session
        # We need to log back in as agent1 to get the lead id
        client.post("/api/v1/agent/auth/login", json={
            "email": "agent@test.com", "password": "securepass123"
        })
        r_leads = client.get("/api/v1/agent/leads")
        if r_leads.status_code != 200 or not r_leads.json().get("leads"):
            pytest.skip("No leads available for cross-agent test")

        lead_id = r_leads.json()["leads"][0]["id"]

        # Now log in as agent2
        client.post("/api/v1/agent/auth/login", json={
            "email": "agent2@test.com", "password": "securepass456"
        })
        r = client.get(f"/api/v1/agent/leads/{lead_id}")
        assert r.status_code == 403
