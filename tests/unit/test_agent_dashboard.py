"""
Unit tests for GET /api/v1/agent/dashboard.

Tests cover:
- Returns 401 when unauthenticated
- Returns correct structure with empty data
- HOT leads are included and scoped to the authenticated agent
- Aging leads are computed correctly (no action + age > SLA)
- response_time_today_minutes is computed as mean of AGENT_CONTACTED - EMAIL_RECEIVED
- watcher_status reflects AgentPreferences.watcher_enabled

Requirements: 10.1, 10.2, 10.3, 10.4, 10.5
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
    LeadEvent,
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


@pytest.fixture(autouse=True)
def setup_db():
    """Create all tables before each test and drop after."""
    Base.metadata.create_all(bind=engine)
    # Create a default LeadSource so Lead FK is satisfied
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
    last_agent_action_at=None,
    created_at=None,
) -> Lead:
    lead = Lead(
        name=name,
        phone="555-0000",
        source_email="leads@test.com",
        lead_source_id=1,  # matches the default LeadSource created in setup_db
        gmail_uid=f"uid-{secrets.token_hex(8)}",
        agent_user_id=agent_id,
        score_bucket=score_bucket,
        score=score,
        last_agent_action_at=last_agent_action_at,
        created_at=created_at or datetime.utcnow(),
    )
    db.add(lead)
    db.commit()
    db.refresh(lead)
    return lead


def _create_prefs(db, agent_id: int, sla_minutes_hot: int = 5, watcher_enabled: bool = True) -> AgentPreferences:
    prefs = AgentPreferences(
        agent_user_id=agent_id,
        sla_minutes_hot=sla_minutes_hot,
        watcher_enabled=watcher_enabled,
        created_at=datetime.utcnow(),
    )
    db.add(prefs)
    db.commit()
    db.refresh(prefs)
    return prefs


def _create_lead_event(db, lead_id: int, agent_id: int, event_type: str, created_at=None) -> LeadEvent:
    event = LeadEvent(
        lead_id=lead_id,
        agent_user_id=agent_id,
        event_type=event_type,
        created_at=created_at or datetime.utcnow(),
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestDashboardAuth:
    def test_unauthenticated_returns_401(self):
        client = TestClient(app, raise_server_exceptions=False)
        response = client.get("/api/v1/agent/dashboard")
        assert response.status_code == 401


class TestDashboardEmptyState:
    def test_returns_200_with_empty_data(self):
        db = TestingSessionLocal()
        agent = _create_agent(db)
        token = _create_session(db, agent.id)
        db.close()

        client = TestClient(app, raise_server_exceptions=False)
        response = client.get(
            "/api/v1/agent/dashboard",
            cookies={"agent_session": token},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["hot_lead_count"] == 0
        assert data["hot_leads"] == []
        assert data["aging_lead_count"] == 0
        assert data["aging_leads"] == []
        assert data["response_time_today_minutes"] is None
        assert data["watcher_status"] == "stopped"  # no prefs → stopped

    def test_watcher_running_when_prefs_enabled(self):
        db = TestingSessionLocal()
        agent = _create_agent(db)
        token = _create_session(db, agent.id)
        _create_prefs(db, agent.id, watcher_enabled=True)
        db.close()

        client = TestClient(app, raise_server_exceptions=False)
        response = client.get(
            "/api/v1/agent/dashboard",
            cookies={"agent_session": token},
        )
        assert response.status_code == 200
        assert response.json()["watcher_status"] == "running"

    def test_watcher_stopped_when_prefs_disabled(self):
        db = TestingSessionLocal()
        agent = _create_agent(db)
        token = _create_session(db, agent.id)
        _create_prefs(db, agent.id, watcher_enabled=False)
        db.close()

        client = TestClient(app, raise_server_exceptions=False)
        response = client.get(
            "/api/v1/agent/dashboard",
            cookies={"agent_session": token},
        )
        assert response.status_code == 200
        assert response.json()["watcher_status"] == "stopped"


class TestDashboardHotLeads:
    def test_hot_leads_returned(self):
        db = TestingSessionLocal()
        agent = _create_agent(db)
        token = _create_session(db, agent.id)
        _create_lead(db, agent.id, name="Alice", score_bucket="HOT", score=90)
        _create_lead(db, agent.id, name="Bob", score_bucket="HOT", score=85)
        _create_lead(db, agent.id, name="Carol", score_bucket="WARM", score=60)
        db.close()

        client = TestClient(app, raise_server_exceptions=False)
        response = client.get(
            "/api/v1/agent/dashboard",
            cookies={"agent_session": token},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["hot_lead_count"] == 2
        names = {lead["name"] for lead in data["hot_leads"]}
        assert names == {"Alice", "Bob"}

    def test_tenant_isolation_hot_leads(self):
        """Requirement 10.2: only leads for the authenticated agent are returned."""
        db = TestingSessionLocal()
        agent1 = _create_agent(db, email="agent1@test.com")
        agent2 = _create_agent(db, email="agent2@test.com")
        token1 = _create_session(db, agent1.id)
        # Create HOT lead for agent2 — should NOT appear in agent1's dashboard
        _create_lead(db, agent2.id, name="Other Agent Lead", score_bucket="HOT")
        db.close()

        client = TestClient(app, raise_server_exceptions=False)
        response = client.get(
            "/api/v1/agent/dashboard",
            cookies={"agent_session": token1},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["hot_lead_count"] == 0
        assert data["hot_leads"] == []


class TestDashboardAgingLeads:
    def test_aging_lead_detected(self):
        """Requirement 10.3: HOT lead with no action and age > SLA is aging."""
        db = TestingSessionLocal()
        agent = _create_agent(db)
        token = _create_session(db, agent.id)
        _create_prefs(db, agent.id, sla_minutes_hot=5)
        # Lead created 10 minutes ago, no action
        old_time = datetime.utcnow() - timedelta(minutes=10)
        _create_lead(
            db, agent.id, name="Aging Lead",
            score_bucket="HOT", last_agent_action_at=None, created_at=old_time
        )
        db.close()

        client = TestClient(app, raise_server_exceptions=False)
        response = client.get(
            "/api/v1/agent/dashboard",
            cookies={"agent_session": token},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["aging_lead_count"] == 1
        assert data["aging_leads"][0]["name"] == "Aging Lead"
        assert data["aging_leads"][0]["minutes_since_created"] > 5

    def test_non_aging_lead_with_action(self):
        """HOT lead with last_agent_action_at set is NOT aging."""
        db = TestingSessionLocal()
        agent = _create_agent(db)
        token = _create_session(db, agent.id)
        _create_prefs(db, agent.id, sla_minutes_hot=5)
        old_time = datetime.utcnow() - timedelta(minutes=10)
        _create_lead(
            db, agent.id, name="Contacted Lead",
            score_bucket="HOT",
            last_agent_action_at=datetime.utcnow(),
            created_at=old_time,
        )
        db.close()

        client = TestClient(app, raise_server_exceptions=False)
        response = client.get(
            "/api/v1/agent/dashboard",
            cookies={"agent_session": token},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["aging_lead_count"] == 0

    def test_fresh_hot_lead_not_aging(self):
        """HOT lead created just now is NOT aging even without action."""
        db = TestingSessionLocal()
        agent = _create_agent(db)
        token = _create_session(db, agent.id)
        _create_prefs(db, agent.id, sla_minutes_hot=5)
        _create_lead(
            db, agent.id, name="Fresh Lead",
            score_bucket="HOT", last_agent_action_at=None,
            created_at=datetime.utcnow(),
        )
        db.close()

        client = TestClient(app, raise_server_exceptions=False)
        response = client.get(
            "/api/v1/agent/dashboard",
            cookies={"agent_session": token},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["aging_lead_count"] == 0


class TestDashboardResponseTime:
    def test_response_time_computed_correctly(self):
        """Requirement 10.4: mean of (AGENT_CONTACTED - EMAIL_RECEIVED) for today."""
        db = TestingSessionLocal()
        agent = _create_agent(db)
        token = _create_session(db, agent.id)
        lead = _create_lead(db, agent.id, score_bucket="HOT")

        today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        email_received_time = today + timedelta(hours=9)       # 09:00
        agent_contacted_time = today + timedelta(hours=9, minutes=8)  # 09:08 → 8 min diff

        _create_lead_event(db, lead.id, agent.id, "EMAIL_RECEIVED", created_at=email_received_time)
        _create_lead_event(db, lead.id, agent.id, "AGENT_CONTACTED", created_at=agent_contacted_time)
        db.close()

        client = TestClient(app, raise_server_exceptions=False)
        response = client.get(
            "/api/v1/agent/dashboard",
            cookies={"agent_session": token},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["response_time_today_minutes"] == pytest.approx(8.0, abs=0.1)

    def test_response_time_none_when_no_contacts_today(self):
        """No AGENT_CONTACTED events today → response_time_today_minutes is None."""
        db = TestingSessionLocal()
        agent = _create_agent(db)
        token = _create_session(db, agent.id)
        db.close()

        client = TestClient(app, raise_server_exceptions=False)
        response = client.get(
            "/api/v1/agent/dashboard",
            cookies={"agent_session": token},
        )
        assert response.status_code == 200
        assert response.json()["response_time_today_minutes"] is None

    def test_response_time_mean_of_multiple(self):
        """Mean is computed across multiple leads contacted today."""
        db = TestingSessionLocal()
        agent = _create_agent(db)
        token = _create_session(db, agent.id)

        today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)

        # Lead 1: 4 min response
        lead1 = _create_lead(db, agent.id, name="Lead 1", score_bucket="HOT")
        _create_lead_event(db, lead1.id, agent.id, "EMAIL_RECEIVED",
                           created_at=today + timedelta(hours=9))
        _create_lead_event(db, lead1.id, agent.id, "AGENT_CONTACTED",
                           created_at=today + timedelta(hours=9, minutes=4))

        # Lead 2: 12 min response
        lead2 = _create_lead(db, agent.id, name="Lead 2", score_bucket="HOT")
        _create_lead_event(db, lead2.id, agent.id, "EMAIL_RECEIVED",
                           created_at=today + timedelta(hours=10))
        _create_lead_event(db, lead2.id, agent.id, "AGENT_CONTACTED",
                           created_at=today + timedelta(hours=10, minutes=12))
        db.close()

        client = TestClient(app, raise_server_exceptions=False)
        response = client.get(
            "/api/v1/agent/dashboard",
            cookies={"agent_session": token},
        )
        assert response.status_code == 200
        # Mean of 4 and 12 = 8
        assert response.json()["response_time_today_minutes"] == pytest.approx(8.0, abs=0.1)
