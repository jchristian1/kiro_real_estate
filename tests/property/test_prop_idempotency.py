"""
Property-based tests for state machine and watcher idempotency.

# Feature: production-hardening, Property 7: State machine and watcher idempotency

**Property 7: State machine and watcher idempotency** — for any lead and any
valid transition (S → T), calling transition() a second time with the same
arguments within the idempotency window SHALL return the existing
LeadStateTransition row and SHALL NOT create a duplicate row.

**Validates: Requirements 8.5, 8.6, 10.4**
"""

import secrets
import uuid
from datetime import datetime, timedelta
from typing import Optional

import bcrypt
import pytest
from fastapi.testclient import TestClient
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import gmail_lead_sync.agent_models  # noqa: F401 — registers agent tables
from api.main import app, get_db
from gmail_lead_sync.agent_models import AgentPreferences, AgentSession, AgentUser
from gmail_lead_sync.models import Base, Lead, LeadSource


# ---------------------------------------------------------------------------
# In-memory SQLite test database
# ---------------------------------------------------------------------------

_DB_NAME = f"prop_idempotency_{uuid.uuid4().hex}"

engine = create_engine(
    f"sqlite:///file:{_DB_NAME}?mode=memory&cache=shared&uri=true",
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


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    app.dependency_overrides[get_db] = override_get_db
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client(setup_db):
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def db_session(setup_db):
    db = TestingSessionLocal()
    yield db
    db.close()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _create_agent(db, email: str) -> AgentUser:
    """Create an agent with a hashed password."""
    password_hash = bcrypt.hashpw(b"password", bcrypt.gensalt()).decode()
    agent = AgentUser(
        email=email,
        password_hash=password_hash,
        full_name="Test Agent",
        onboarding_step=1,
        onboarding_completed=True,
        created_at=datetime.utcnow(),
    )
    db.add(agent)
    db.commit()
    db.refresh(agent)

    # Create preferences
    prefs = AgentPreferences(
        agent_user_id=agent.id,
        hot_threshold=80,
        warm_threshold=50,
        sla_minutes_hot=5,
        watcher_enabled=True,
        created_at=datetime.utcnow(),
    )
    db.add(prefs)
    db.commit()
    return agent


def _create_session(db, agent_user_id: int) -> str:
    """Create a session token for an agent."""
    token = secrets.token_hex(64)
    now = datetime.utcnow()
    session = AgentSession(
        id=token,
        agent_user_id=agent_user_id,
        created_at=now,
        expires_at=now + timedelta(days=1),
        last_accessed=now,
    )
    db.add(session)
    db.commit()
    return token


def _ensure_lead_source(db) -> int:
    """Ensure a lead source exists and return its ID."""
    source = db.query(LeadSource).first()
    if source is None:
        source = LeadSource(
            sender_email="test@leadsource.com",
            identifier_snippet="test",
            name_regex=r"Name: (.+)",
            phone_regex=r"Phone: (.+)",
        )
        db.add(source)
        db.commit()
        db.refresh(source)
    return source.id


def _create_lead(db, agent_user_id: int, from_state: Optional[str]) -> Lead:
    """Create a lead in a specific state."""
    source_id = _ensure_lead_source(db)
    lead = Lead(
        name="Test Lead",
        phone="555-0000",
        source_email="source@example.com",
        lead_source_id=source_id,
        gmail_uid=f"uid_{uuid.uuid4().hex}",
        agent_user_id=agent_user_id,
        score_bucket="HOT",
        score=85,
        agent_current_state=from_state,
        created_at=datetime.utcnow(),
    )
    db.add(lead)
    db.commit()
    db.refresh(lead)
    return lead


# ---------------------------------------------------------------------------
# Valid transitions for testing
# ---------------------------------------------------------------------------

VALID_TRANSITIONS = [
    ("NEW", "CONTACTED"),
    ("NEW", "APPOINTMENT_SET"),
    ("CONTACTED", "APPOINTMENT_SET"),
    ("CONTACTED", "CLOSED"),
    ("APPOINTMENT_SET", "CLOSED"),
]


# ---------------------------------------------------------------------------
# Property 7: State machine idempotency
# ---------------------------------------------------------------------------


class TestProperty7StateTransitionIdempotency:
    """
    Property 7: State machine and watcher idempotency
    **Validates: Requirements 8.5, 8.6, 10.4**

    Calling transition() multiple times with the same parameters within 5 seconds
    returns the same transition row without creating duplicates.
    """

    @given(transition=st.sampled_from(VALID_TRANSITIONS))
    @settings(
        max_examples=len(VALID_TRANSITIONS),
        deadline=None,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
    )
    def test_duplicate_transition_returns_same_row(
        self,
        client: TestClient,
        db_session,
        transition,
    ):
        """
        Property 7: State machine idempotency
        **Validates: Requirements 8.5, 8.6, 10.4**

        For any valid transition (from_state, to_state), calling the transition
        endpoint twice within 5 seconds must return the same transition row
        and must NOT create a duplicate LeadStateTransition record.
        """
        from_state, to_state = transition

        # Create agent and lead
        agent = _create_agent(db_session, f"agent_{uuid.uuid4().hex[:8]}@example.com")
        lead = _create_lead(db_session, agent.id, from_state)
        token = _create_session(db_session, agent.id)

        # First transition
        resp1 = client.patch(
            f"/api/v1/agent/leads/{lead.id}/status",
            json={"status": to_state},
            cookies={"agent_session": token},
        )

        assert resp1.status_code == 200, (
            f"First transition {from_state!r} → {to_state!r} failed: "
            f"{resp1.status_code}: {resp1.text}"
        )

        body1 = resp1.json()
        assert body1["current_state"] == to_state

        # Second transition (within idempotency window)
        resp2 = client.patch(
            f"/api/v1/agent/leads/{lead.id}/status",
            json={"status": to_state},
            cookies={"agent_session": token},
        )

        assert resp2.status_code == 200, (
            f"Second transition {from_state!r} → {to_state!r} failed: "
            f"{resp2.status_code}: {resp2.text}"
        )

        body2 = resp2.json()
        assert body2["current_state"] == to_state

        # Verify no duplicate transitions were created
        # Get the events for this lead
        events_resp = client.get(
            f"/api/v1/agent/leads/{lead.id}/events",
            cookies={"agent_session": token},
        )

        assert events_resp.status_code == 200, (
            f"Failed to fetch events: {events_resp.status_code}: {events_resp.text}"
        )

        events_data = events_resp.json()
        events = events_data.get("events", [])

        # Count transitions matching this from_state → to_state
        matching_transitions = [
            e for e in events
            if e["from_state"] == from_state and e["to_state"] == to_state
        ]

        assert len(matching_transitions) == 1, (
            f"Expected exactly 1 transition for {from_state!r} → {to_state!r}, "
            f"but found {len(matching_transitions)} transitions. "
            f"Events: {events}"
        )
