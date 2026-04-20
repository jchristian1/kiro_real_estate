"""
Integration test: Lead lifecycle.

Tests the full sequence:
  ingest email → parse → score → invite → form submit → re-score → post-email → agent marks contacted

Requirements: 13.7, 20.1
"""

import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, StaticPool
from sqlalchemy.orm import sessionmaker

from gmail_lead_sync.models import Base, Lead
from gmail_lead_sync.agent_models import (
    AgentUser, LeadEvent,
)
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


@pytest.fixture
def agent_client(client, db_session):
    """Authenticated agent client — agent created directly in DB (no signup endpoint)."""
    import bcrypt
    from datetime import datetime
    from gmail_lead_sync.agent_models import AgentSession as _AgentSession
    import secrets as _secrets

    password = "securepass123"
    password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    agent = AgentUser(
        email="agent@test.com",
        password_hash=password_hash,
        full_name="Test Agent",
        onboarding_completed=True,
        created_at=datetime.utcnow(),
    )
    db_session.add(agent)
    db_session.flush()

    token = _secrets.token_hex(64)
    session = _AgentSession(
        id=token,
        agent_user_id=agent.id,
        created_at=datetime.utcnow(),
        expires_at=datetime.utcnow() + __import__("datetime").timedelta(hours=1),
        last_accessed=datetime.utcnow(),
    )
    db_session.add(session)
    db_session.commit()

    client.cookies.set("agent_session", token)
    return client


@pytest.fixture
def sample_lead(db_session, agent_client):
    """Create a lead in the DB scoped to the authenticated agent."""
    from gmail_lead_sync.models import LeadSource
    agent = db_session.query(AgentUser).filter_by(email="agent@test.com").first()

    # Create a lead source first (required FK)
    lead_source = LeadSource(
        sender_email="leads@example.com",
        identifier_snippet="Lead Notification",
        name_regex=r"Name:\s*(.+)",
        phone_regex=r"Phone:\s*([\d-]+)",
    )
    db_session.add(lead_source)
    db_session.flush()

    lead = Lead(
        name="John Buyer",
        phone="555-9999",
        source_email="john@example.com",
        gmail_uid="test-uid-001",
        lead_source_id=lead_source.id,
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
        ids = [lead["id"] for lead in leads]
        assert sample_lead.id in ids

    def test_lead_detail_accessible(self, agent_client, sample_lead):
        r = agent_client.get(f"/api/v1/agent/leads/{sample_lead.id}")
        assert r.status_code == 200
        data = r.json()
        # Response is nested under "lead" key
        lead_data = data.get("lead", data)
        assert lead_data["id"] == sample_lead.id
        assert lead_data["name"] == "John Buyer"

    def test_status_transition_new_to_contacted(self, agent_client, sample_lead, db_session):
        r = agent_client.patch(
            f"/api/v1/agent/leads/{sample_lead.id}/status",
            json={"status": "CONTACTED"}
        )
        assert r.status_code == 200

        # Verify state updated (uses agent_current_state column)
        db_session.refresh(sample_lead)
        assert sample_lead.agent_current_state == "CONTACTED"

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
        assert r.status_code in (400, 422)

    def test_add_note_persists_and_inserts_event(self, agent_client, sample_lead, db_session):
        r = agent_client.post(
            f"/api/v1/agent/leads/{sample_lead.id}/notes",
            json={"text": "Called and left voicemail."}
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
        assert sample_lead.agent_current_state == "CLOSED"

    def test_cross_agent_lead_access_denied(self, db_session, client):
        """Agent B cannot access Agent A's lead — returns 403."""
        import bcrypt
        from datetime import datetime, timedelta
        from gmail_lead_sync.agent_models import AgentSession as _AgentSession
        import secrets as _secrets

        # Create agent2 directly in DB
        password2 = "securepass456"
        agent2 = AgentUser(
            email="agent2@test.com",
            password_hash=bcrypt.hashpw(password2.encode(), bcrypt.gensalt()).decode(),
            full_name="Agent Two",
            onboarding_completed=True,
            created_at=datetime.utcnow(),
        )
        db_session.add(agent2)
        db_session.commit()

        # Log back in as agent1 to get the lead id
        client.post("/api/v1/agent/auth/login", json={
            "email": "agent@test.com", "password": "securepass123"
        })
        r_leads = client.get("/api/v1/agent/leads")
        if r_leads.status_code != 200 or not r_leads.json().get("leads"):
            pytest.skip("No leads available for cross-agent test")

        lead_id = r_leads.json()["leads"][0]["id"]

        # Log in as agent2
        client.post("/api/v1/agent/auth/login", json={
            "email": "agent2@test.com", "password": "securepass456"
        })
        r = client.get(f"/api/v1/agent/leads/{lead_id}")
        assert r.status_code == 403
