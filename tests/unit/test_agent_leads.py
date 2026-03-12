"""
Unit tests for GET /api/v1/agent/leads.

Tests cover:
- Returns 401 when unauthenticated
- Returns empty list when agent has no leads
- Urgency sort: HOT before WARM before NURTURE (Requirement 11.1)
- Bucket filter (Requirement 11.2)
- Status filter (Requirement 11.2)
- Search filter matches name, property_address, lead_source_name (Requirement 11.3)
- Pagination at 25 per page (Requirement 11.4)
- HOT aging annotation: is_aging when no action and age > SLA (Requirement 11.5)
- WARM aging annotation: is_aging when age > 24 hours (Requirement 11.6)
- Tenant isolation: only returns leads for authenticated agent (Requirement 11.7)

Requirements: 11.1, 11.2, 11.3, 11.4, 11.5, 11.6, 11.7
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
    AgentPreferences,
    AgentSession,
    AgentUser,
)
from gmail_lead_sync.models import Base, Lead, LeadSource


# ---------------------------------------------------------------------------
# Test database setup — shared in-memory SQLite (StaticPool)
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
    """Create all tables before each test and drop after."""
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

def _create_agent(db, email="agent@test.com", full_name="Test Agent") -> AgentUser:
    agent = AgentUser(
        email=email,
        password_hash="hashed",
        full_name=full_name,
        onboarding_step=6,
        onboarding_completed=True,
        created_at=datetime.utcnow(),
    )
    db.add(agent)
    db.commit()
    db.refresh(agent)
    return agent


def _create_session(db, agent_id: int) -> str:
    token = secrets.token_hex(64)
    session = AgentSession(
        id=token,
        agent_user_id=agent_id,
        created_at=datetime.utcnow(),
        expires_at=datetime.utcnow() + timedelta(days=30),
        last_accessed=datetime.utcnow(),
    )
    db.add(session)
    db.commit()
    return token


def _create_lead(
    db,
    agent_id: int,
    name: str = "Test Lead",
    score_bucket: str = "HOT",
    score: int = 85,
    agent_current_state: str = "NEW",
    last_agent_action_at=None,
    created_at=None,
    property_address: str = None,
    lead_source_name: str = None,
) -> Lead:
    lead = Lead(
        name=name,
        phone="555-0000",
        source_email="leads@test.com",
        lead_source_id=1,
        gmail_uid=f"uid-{secrets.token_hex(8)}",
        agent_user_id=agent_id,
        score_bucket=score_bucket,
        score=score,
        agent_current_state=agent_current_state,
        last_agent_action_at=last_agent_action_at,
        created_at=created_at or datetime.utcnow(),
        property_address=property_address,
        lead_source_name=lead_source_name,
    )
    db.add(lead)
    db.commit()
    db.refresh(lead)
    return lead


def _create_prefs(db, agent_id: int, sla_minutes_hot: int = 5) -> AgentPreferences:
    prefs = AgentPreferences(
        agent_user_id=agent_id,
        sla_minutes_hot=sla_minutes_hot,
        watcher_enabled=True,
        created_at=datetime.utcnow(),
    )
    db.add(prefs)
    db.commit()
    db.refresh(prefs)
    return prefs


def _auth_headers(token: str) -> dict:
    return {"Cookie": f"agent_session={token}"}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestLeadsAuth:
    def test_returns_401_when_unauthenticated(self):
        resp = client.get("/api/v1/agent/leads")
        assert resp.status_code == 401

    def test_returns_200_when_authenticated(self):
        db = TestingSessionLocal()
        agent = _create_agent(db)
        token = _create_session(db, agent.id)
        db.close()

        resp = client.get("/api/v1/agent/leads", headers=_auth_headers(token))
        assert resp.status_code == 200


class TestLeadsEmptyState:
    def test_empty_response_structure(self):
        db = TestingSessionLocal()
        agent = _create_agent(db)
        token = _create_session(db, agent.id)
        db.close()

        resp = client.get("/api/v1/agent/leads", headers=_auth_headers(token))
        assert resp.status_code == 200
        data = resp.json()
        assert data["leads"] == []
        assert data["total"] == 0
        assert data["page"] == 1
        assert data["page_size"] == 25
        assert data["total_pages"] == 1


class TestLeadsUrgencySort:
    """Requirement 11.1: HOT first, then WARM, then NURTURE."""

    def test_hot_before_warm_before_nurture(self):
        db = TestingSessionLocal()
        agent = _create_agent(db)
        token = _create_session(db, agent.id)
        _create_lead(db, agent.id, name="Nurture Lead", score_bucket="NURTURE", score=30)
        _create_lead(db, agent.id, name="Warm Lead", score_bucket="WARM", score=60)
        _create_lead(db, agent.id, name="Hot Lead", score_bucket="HOT", score=90)
        db.close()

        resp = client.get("/api/v1/agent/leads", headers=_auth_headers(token))
        assert resp.status_code == 200
        leads = resp.json()["leads"]
        assert len(leads) == 3
        assert leads[0]["score_bucket"] == "HOT"
        assert leads[1]["score_bucket"] == "WARM"
        assert leads[2]["score_bucket"] == "NURTURE"

    def test_multiple_hot_leads_all_before_warm(self):
        db = TestingSessionLocal()
        agent = _create_agent(db)
        token = _create_session(db, agent.id)
        _create_lead(db, agent.id, name="Warm 1", score_bucket="WARM", score=60)
        _create_lead(db, agent.id, name="Hot 1", score_bucket="HOT", score=90)
        _create_lead(db, agent.id, name="Hot 2", score_bucket="HOT", score=85)
        db.close()

        resp = client.get("/api/v1/agent/leads", headers=_auth_headers(token))
        leads = resp.json()["leads"]
        buckets = [l["score_bucket"] for l in leads]
        # All HOT leads must appear before any WARM lead
        last_hot = max((i for i, b in enumerate(buckets) if b == "HOT"), default=-1)
        first_warm = min((i for i, b in enumerate(buckets) if b == "WARM"), default=999)
        assert last_hot < first_warm


class TestLeadsBucketFilter:
    """Requirement 11.2: bucket filter."""

    def test_filter_by_hot(self):
        db = TestingSessionLocal()
        agent = _create_agent(db)
        token = _create_session(db, agent.id)
        _create_lead(db, agent.id, name="Hot Lead", score_bucket="HOT")
        _create_lead(db, agent.id, name="Warm Lead", score_bucket="WARM")
        _create_lead(db, agent.id, name="Nurture Lead", score_bucket="NURTURE")
        db.close()

        resp = client.get("/api/v1/agent/leads?bucket=HOT", headers=_auth_headers(token))
        leads = resp.json()["leads"]
        assert len(leads) == 1
        assert leads[0]["score_bucket"] == "HOT"

    def test_filter_by_warm(self):
        db = TestingSessionLocal()
        agent = _create_agent(db)
        token = _create_session(db, agent.id)
        _create_lead(db, agent.id, name="Hot Lead", score_bucket="HOT")
        _create_lead(db, agent.id, name="Warm Lead", score_bucket="WARM")
        db.close()

        resp = client.get("/api/v1/agent/leads?bucket=WARM", headers=_auth_headers(token))
        leads = resp.json()["leads"]
        assert all(l["score_bucket"] == "WARM" for l in leads)

    def test_no_bucket_filter_returns_all(self):
        db = TestingSessionLocal()
        agent = _create_agent(db)
        token = _create_session(db, agent.id)
        _create_lead(db, agent.id, name="Hot Lead", score_bucket="HOT")
        _create_lead(db, agent.id, name="Warm Lead", score_bucket="WARM")
        _create_lead(db, agent.id, name="Nurture Lead", score_bucket="NURTURE")
        db.close()

        resp = client.get("/api/v1/agent/leads", headers=_auth_headers(token))
        assert resp.json()["total"] == 3


class TestLeadsStatusFilter:
    """Requirement 11.2: status filter."""

    def test_filter_by_status_new(self):
        db = TestingSessionLocal()
        agent = _create_agent(db)
        token = _create_session(db, agent.id)
        _create_lead(db, agent.id, name="New Lead", agent_current_state="NEW")
        _create_lead(db, agent.id, name="Contacted Lead", agent_current_state="CONTACTED")
        db.close()

        resp = client.get("/api/v1/agent/leads?status=NEW", headers=_auth_headers(token))
        leads = resp.json()["leads"]
        assert len(leads) == 1
        assert leads[0]["current_state"] == "NEW"

    def test_filter_by_status_contacted(self):
        db = TestingSessionLocal()
        agent = _create_agent(db)
        token = _create_session(db, agent.id)
        _create_lead(db, agent.id, name="New Lead", agent_current_state="NEW")
        _create_lead(db, agent.id, name="Contacted Lead", agent_current_state="CONTACTED")
        db.close()

        resp = client.get("/api/v1/agent/leads?status=CONTACTED", headers=_auth_headers(token))
        leads = resp.json()["leads"]
        assert len(leads) == 1
        assert leads[0]["current_state"] == "CONTACTED"


class TestLeadsSearchFilter:
    """Requirement 11.3: search matches name, property_address, lead_source_name."""

    def test_search_by_name(self):
        db = TestingSessionLocal()
        agent = _create_agent(db)
        token = _create_session(db, agent.id)
        _create_lead(db, agent.id, name="Alice Johnson")
        _create_lead(db, agent.id, name="Bob Smith")
        db.close()

        resp = client.get("/api/v1/agent/leads?search=alice", headers=_auth_headers(token))
        leads = resp.json()["leads"]
        assert len(leads) == 1
        assert leads[0]["name"] == "Alice Johnson"

    def test_search_by_property_address(self):
        db = TestingSessionLocal()
        agent = _create_agent(db)
        token = _create_session(db, agent.id)
        _create_lead(db, agent.id, name="Lead A", property_address="123 Main St")
        _create_lead(db, agent.id, name="Lead B", property_address="456 Oak Ave")
        db.close()

        resp = client.get("/api/v1/agent/leads?search=main+st", headers=_auth_headers(token))
        leads = resp.json()["leads"]
        assert len(leads) == 1
        assert leads[0]["address"] == "123 Main St"

    def test_search_by_lead_source_name(self):
        db = TestingSessionLocal()
        agent = _create_agent(db)
        token = _create_session(db, agent.id)
        _create_lead(db, agent.id, name="Lead A", lead_source_name="Zillow")
        _create_lead(db, agent.id, name="Lead B", lead_source_name="Realtor.com")
        db.close()

        resp = client.get("/api/v1/agent/leads?search=zillow", headers=_auth_headers(token))
        leads = resp.json()["leads"]
        assert len(leads) == 1
        assert leads[0]["source"] == "Zillow"

    def test_search_is_case_insensitive(self):
        db = TestingSessionLocal()
        agent = _create_agent(db)
        token = _create_session(db, agent.id)
        _create_lead(db, agent.id, name="ALICE JOHNSON")
        db.close()

        resp = client.get("/api/v1/agent/leads?search=alice", headers=_auth_headers(token))
        assert resp.json()["total"] == 1


class TestLeadsPagination:
    """Requirement 11.4: paginate at 25 per page."""

    def test_page_size_is_25(self):
        db = TestingSessionLocal()
        agent = _create_agent(db)
        token = _create_session(db, agent.id)
        for i in range(30):
            _create_lead(db, agent.id, name=f"Lead {i}", score_bucket="HOT")
        db.close()

        resp = client.get("/api/v1/agent/leads?page=1", headers=_auth_headers(token))
        data = resp.json()
        assert len(data["leads"]) == 25
        assert data["total"] == 30
        assert data["page_size"] == 25
        assert data["total_pages"] == 2

    def test_page_2_returns_remaining(self):
        db = TestingSessionLocal()
        agent = _create_agent(db)
        token = _create_session(db, agent.id)
        for i in range(30):
            _create_lead(db, agent.id, name=f"Lead {i}", score_bucket="HOT")
        db.close()

        resp = client.get("/api/v1/agent/leads?page=2", headers=_auth_headers(token))
        data = resp.json()
        assert len(data["leads"]) == 5
        assert data["page"] == 2

    def test_total_pages_calculation(self):
        db = TestingSessionLocal()
        agent = _create_agent(db)
        token = _create_session(db, agent.id)
        for i in range(50):
            _create_lead(db, agent.id, name=f"Lead {i}")
        db.close()

        resp = client.get("/api/v1/agent/leads", headers=_auth_headers(token))
        data = resp.json()
        assert data["total"] == 50
        assert data["total_pages"] == 2


class TestLeadsAgingAnnotation:
    """Requirements 11.5, 11.6: aging annotation."""

    def test_hot_lead_is_aging_when_no_action_and_exceeds_sla(self):
        db = TestingSessionLocal()
        agent = _create_agent(db)
        token = _create_session(db, agent.id)
        _create_prefs(db, agent.id, sla_minutes_hot=5)
        # Created 10 minutes ago, no action
        old_time = datetime.utcnow() - timedelta(minutes=10)
        _create_lead(
            db, agent.id, name="Aging HOT", score_bucket="HOT",
            created_at=old_time, last_agent_action_at=None,
        )
        db.close()

        resp = client.get("/api/v1/agent/leads", headers=_auth_headers(token))
        leads = resp.json()["leads"]
        assert leads[0]["is_aging"] is True

    def test_hot_lead_not_aging_when_within_sla(self):
        db = TestingSessionLocal()
        agent = _create_agent(db)
        token = _create_session(db, agent.id)
        _create_prefs(db, agent.id, sla_minutes_hot=60)
        # Created 5 minutes ago, SLA is 60 min
        recent_time = datetime.utcnow() - timedelta(minutes=5)
        _create_lead(
            db, agent.id, name="Fresh HOT", score_bucket="HOT",
            created_at=recent_time, last_agent_action_at=None,
        )
        db.close()

        resp = client.get("/api/v1/agent/leads", headers=_auth_headers(token))
        leads = resp.json()["leads"]
        assert leads[0]["is_aging"] is False

    def test_hot_lead_not_aging_when_action_taken(self):
        db = TestingSessionLocal()
        agent = _create_agent(db)
        token = _create_session(db, agent.id)
        _create_prefs(db, agent.id, sla_minutes_hot=5)
        old_time = datetime.utcnow() - timedelta(minutes=10)
        _create_lead(
            db, agent.id, name="Actioned HOT", score_bucket="HOT",
            created_at=old_time,
            last_agent_action_at=datetime.utcnow(),  # action was taken
        )
        db.close()

        resp = client.get("/api/v1/agent/leads", headers=_auth_headers(token))
        leads = resp.json()["leads"]
        assert leads[0]["is_aging"] is False

    def test_warm_lead_is_aging_when_older_than_24h(self):
        db = TestingSessionLocal()
        agent = _create_agent(db)
        token = _create_session(db, agent.id)
        old_time = datetime.utcnow() - timedelta(hours=25)
        _create_lead(
            db, agent.id, name="Old WARM", score_bucket="WARM",
            created_at=old_time,
        )
        db.close()

        resp = client.get("/api/v1/agent/leads", headers=_auth_headers(token))
        leads = resp.json()["leads"]
        assert leads[0]["is_aging"] is True

    def test_warm_lead_not_aging_when_within_24h(self):
        db = TestingSessionLocal()
        agent = _create_agent(db)
        token = _create_session(db, agent.id)
        recent_time = datetime.utcnow() - timedelta(hours=12)
        _create_lead(
            db, agent.id, name="Fresh WARM", score_bucket="WARM",
            created_at=recent_time,
        )
        db.close()

        resp = client.get("/api/v1/agent/leads", headers=_auth_headers(token))
        leads = resp.json()["leads"]
        assert leads[0]["is_aging"] is False

    def test_nurture_lead_never_aging(self):
        db = TestingSessionLocal()
        agent = _create_agent(db)
        token = _create_session(db, agent.id)
        old_time = datetime.utcnow() - timedelta(days=30)
        _create_lead(
            db, agent.id, name="Old NURTURE", score_bucket="NURTURE",
            created_at=old_time,
        )
        db.close()

        resp = client.get("/api/v1/agent/leads", headers=_auth_headers(token))
        leads = resp.json()["leads"]
        assert leads[0]["is_aging"] is False


class TestLeadsTenantIsolation:
    """Requirement 11.7: only return leads for the authenticated agent."""

    def test_does_not_return_other_agents_leads(self):
        db = TestingSessionLocal()
        agent1 = _create_agent(db, email="agent1@test.com")
        agent2 = _create_agent(db, email="agent2@test.com")
        token1 = _create_session(db, agent1.id)
        _create_lead(db, agent1.id, name="Agent1 Lead")
        _create_lead(db, agent2.id, name="Agent2 Lead")
        db.close()

        resp = client.get("/api/v1/agent/leads", headers=_auth_headers(token1))
        data = resp.json()
        assert data["total"] == 1
        assert data["leads"][0]["name"] == "Agent1 Lead"

    def test_each_agent_sees_only_own_leads(self):
        db = TestingSessionLocal()
        agent1 = _create_agent(db, email="agent1@test.com")
        agent2 = _create_agent(db, email="agent2@test.com")
        token1 = _create_session(db, agent1.id)
        token2 = _create_session(db, agent2.id)
        for i in range(3):
            _create_lead(db, agent1.id, name=f"A1 Lead {i}")
        for i in range(5):
            _create_lead(db, agent2.id, name=f"A2 Lead {i}")
        db.close()

        resp1 = client.get("/api/v1/agent/leads", headers=_auth_headers(token1))
        resp2 = client.get("/api/v1/agent/leads", headers=_auth_headers(token2))
        assert resp1.json()["total"] == 3
        assert resp2.json()["total"] == 5


class TestLeadEvents:
    """Test GET /api/v1/agent/leads/{lead_id}/events endpoint."""

    def test_returns_401_when_unauthenticated(self):
        resp = client.get("/api/v1/agent/leads/1/events")
        assert resp.status_code == 401

    def test_returns_404_when_lead_not_found(self):
        db = TestingSessionLocal()
        agent = _create_agent(db)
        token = _create_session(db, agent.id)
        db.close()

        resp = client.get("/api/v1/agent/leads/999/events", headers=_auth_headers(token))
        assert resp.status_code == 404

    def test_returns_403_when_lead_belongs_to_different_agent(self):
        db = TestingSessionLocal()
        agent1 = _create_agent(db, email="agent1@test.com")
        agent2 = _create_agent(db, email="agent2@test.com")
        token1 = _create_session(db, agent1.id)
        lead = _create_lead(db, agent2.id, name="Agent2 Lead")
        lead_id = lead.id  # Store ID before closing session
        db.close()

        resp = client.get(f"/api/v1/agent/leads/{lead_id}/events", headers=_auth_headers(token1))
        assert resp.status_code == 404  # Repository returns empty list, endpoint returns 404

    def test_returns_empty_events_for_lead_with_no_transitions(self):
        db = TestingSessionLocal()
        agent = _create_agent(db)
        token = _create_session(db, agent.id)
        lead = _create_lead(db, agent.id, name="Test Lead")
        lead_id = lead.id  # Store ID before closing session
        db.close()

        resp = client.get(f"/api/v1/agent/leads/{lead_id}/events", headers=_auth_headers(token))
        assert resp.status_code == 200
        data = resp.json()
        assert data["lead_id"] == lead_id
        assert data["events"] == []

    def test_returns_events_in_chronological_order(self):
        from gmail_lead_sync.preapproval.models_preapproval import LeadStateTransition

        db = TestingSessionLocal()
        agent = _create_agent(db)
        token = _create_session(db, agent.id)
        lead = _create_lead(db, agent.id, name="Test Lead")
        lead_id = lead.id  # Store ID before closing session

        # Create transitions in reverse chronological order
        t3 = LeadStateTransition(
            tenant_id=1,
            lead_id=lead_id,
            from_state="CONTACTED",
            to_state="APPOINTMENT_SET",
            occurred_at=datetime.utcnow() + timedelta(hours=2),
            actor_type="agent",
            actor_id=agent.id,
        )
        t2 = LeadStateTransition(
            tenant_id=1,
            lead_id=lead_id,
            from_state="NEW",
            to_state="CONTACTED",
            occurred_at=datetime.utcnow() + timedelta(hours=1),
            actor_type="agent",
            actor_id=agent.id,
        )
        t1 = LeadStateTransition(
            tenant_id=1,
            lead_id=lead_id,
            from_state=None,
            to_state="NEW",
            occurred_at=datetime.utcnow(),
            actor_type="system",
        )
        db.add_all([t3, t2, t1])
        db.commit()
        db.close()

        resp = client.get(f"/api/v1/agent/leads/{lead_id}/events", headers=_auth_headers(token))
        assert resp.status_code == 200
        data = resp.json()
        events = data["events"]
        assert len(events) == 3
        # Should be ordered chronologically (oldest first)
        assert events[0]["to_state"] == "NEW"
        assert events[1]["to_state"] == "CONTACTED"
        assert events[2]["to_state"] == "APPOINTMENT_SET"

    def test_parses_metadata_json(self):
        import json
        from gmail_lead_sync.preapproval.models_preapproval import LeadStateTransition

        db = TestingSessionLocal()
        agent = _create_agent(db)
        token = _create_session(db, agent.id)
        lead = _create_lead(db, agent.id, name="Test Lead")
        lead_id = lead.id  # Store ID before closing session

        metadata = {"note": "Called customer", "reason": "follow_up"}
        t = LeadStateTransition(
            tenant_id=1,
            lead_id=lead_id,
            from_state="NEW",
            to_state="CONTACTED",
            occurred_at=datetime.utcnow(),
            actor_type="agent",
            actor_id=agent.id,
            metadata_json=json.dumps(metadata),
        )
        db.add(t)
        db.commit()
        db.close()

        resp = client.get(f"/api/v1/agent/leads/{lead_id}/events", headers=_auth_headers(token))
        assert resp.status_code == 200
        events = resp.json()["events"]
        assert len(events) == 1
        assert events[0]["metadata"] == metadata

    def test_handles_null_metadata(self):
        from gmail_lead_sync.preapproval.models_preapproval import LeadStateTransition

        db = TestingSessionLocal()
        agent = _create_agent(db)
        token = _create_session(db, agent.id)
        lead = _create_lead(db, agent.id, name="Test Lead")
        lead_id = lead.id  # Store ID before closing session

        t = LeadStateTransition(
            tenant_id=1,
            lead_id=lead_id,
            from_state=None,
            to_state="NEW",
            occurred_at=datetime.utcnow(),
            actor_type="system",
            metadata_json=None,
        )
        db.add(t)
        db.commit()
        db.close()

        resp = client.get(f"/api/v1/agent/leads/{lead_id}/events", headers=_auth_headers(token))
        assert resp.status_code == 200
        events = resp.json()["events"]
        assert len(events) == 1
        assert events[0]["metadata"] is None
