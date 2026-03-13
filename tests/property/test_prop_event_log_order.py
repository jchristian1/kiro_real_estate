"""
Property-based tests for event log chronological ordering.

# Feature: production-hardening, Property 8: Event log is chronologically ordered

**Property 8: Event log is chronologically ordered** — for any lead with one or
more LeadStateTransition rows, the GET /api/v1/agent/leads/{lead_id}/events
endpoint SHALL return those rows in ascending occurred_at order.

**Validates: Requirements 8.7**
"""

import secrets
import time
import uuid
from datetime import datetime, timedelta
from typing import List, Optional

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

_DB_NAME = f"prop_event_log_order_{uuid.uuid4().hex}"

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
    """Create a lead in a specific state.

    Note: agent_current_state has a column default of 'NEW', so passing None
    will result in the DB storing 'NEW'. We always pass 'NEW' explicitly.
    """
    source_id = _ensure_lead_source(db)
    # Normalise: None and 'NEW' both represent the initial state; the column
    # default is 'NEW', so store 'NEW' explicitly to match what the router reads.
    initial_state = from_state if from_state is not None else "NEW"
    lead = Lead(
        name="Test Lead",
        phone="555-0000",
        source_email="source@example.com",
        lead_source_id=source_id,
        gmail_uid=f"uid_{uuid.uuid4().hex}",
        agent_user_id=agent_user_id,
        score_bucket="HOT",
        score=85,
        agent_current_state=initial_state,
        created_at=datetime.utcnow(),
    )
    db.add(lead)
    db.commit()
    db.refresh(lead)
    return lead


# ---------------------------------------------------------------------------
# Transition sequences for testing
# ---------------------------------------------------------------------------

# Each sequence is a list of (from_state, to_state) pairs that will be
# executed in order to create multiple transitions.
# Note: leads are created with agent_current_state='NEW' (the column default),
# so the first from_state is always 'NEW', not None.
TRANSITION_SEQUENCES = [
    # Single transition
    [("NEW", "CONTACTED")],
    # Two transitions
    [("NEW", "CONTACTED"), ("CONTACTED", "APPOINTMENT_SET")],
    # Three transitions
    [("NEW", "CONTACTED"), ("CONTACTED", "APPOINTMENT_SET"), ("APPOINTMENT_SET", "CLOSED")],
    # Four transitions
    [("NEW", "CONTACTED"), ("CONTACTED", "APPOINTMENT_SET"), ("APPOINTMENT_SET", "CONTACTED"), ("CONTACTED", "CLOSED")],
    # Alternative path
    [("NEW", "APPOINTMENT_SET"), ("APPOINTMENT_SET", "CLOSED")],
]


# ---------------------------------------------------------------------------
# Property 8: Event log chronological ordering
# ---------------------------------------------------------------------------


class TestProperty8EventLogChronologicalOrder:
    """
    Property 8: Event log is chronologically ordered
    **Validates: Requirements 8.7**

    The events endpoint returns transitions in chronological order (occurred_at ascending).
    """

    @given(sequence=st.sampled_from(TRANSITION_SEQUENCES))
    @settings(
        max_examples=len(TRANSITION_SEQUENCES),
        deadline=None,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
    )
    def test_events_returned_in_chronological_order(
        self,
        client: TestClient,
        db_session,
        sequence: List[tuple],
    ):
        """
        Property 8: Event log is chronologically ordered
        **Validates: Requirements 8.7**

        For any lead with multiple state transitions, the GET /api/v1/agent/leads/{lead_id}/events
        endpoint must return those transitions in ascending occurred_at order (oldest first).
        """
        # Create agent and lead
        agent = _create_agent(db_session, f"agent_{uuid.uuid4().hex[:8]}@example.com")
        lead = _create_lead(db_session, agent.id, sequence[0][0])  # Start with first from_state
        token = _create_session(db_session, agent.id)

        # Execute the sequence of transitions with small delays to ensure distinct timestamps
        for from_state, to_state in sequence:
            # Small delay to ensure distinct timestamps
            time.sleep(0.01)
            
            resp = client.patch(
                f"/api/v1/agent/leads/{lead.id}/status",
                json={"status": to_state},
                cookies={"agent_session": token},
            )

            assert resp.status_code == 200, (
                f"Transition {from_state!r} → {to_state!r} failed: "
                f"{resp.status_code}: {resp.text}"
            )

        # Fetch events
        events_resp = client.get(
            f"/api/v1/agent/leads/{lead.id}/events",
            cookies={"agent_session": token},
        )

        assert events_resp.status_code == 200, (
            f"Failed to fetch events: {events_resp.status_code}: {events_resp.text}"
        )

        events_data = events_resp.json()
        events = events_data.get("events", [])

        # Verify we have the expected number of events
        assert len(events) == len(sequence), (
            f"Expected {len(sequence)} events, but got {len(events)}"
        )

        # Verify chronological ordering
        for i in range(len(events) - 1):
            current_time = events[i]["occurred_at"]
            next_time = events[i + 1]["occurred_at"]

            assert current_time <= next_time, (
                f"Events are not in chronological order: "
                f"event {i} occurred_at={current_time} is after "
                f"event {i+1} occurred_at={next_time}. "
                f"Full events: {events}"
            )

        # Verify the sequence matches what we executed
        for i, (from_state, to_state) in enumerate(sequence):
            event = events[i]
            assert event["from_state"] == from_state, (
                f"Event {i} from_state mismatch: expected {from_state!r}, got {event['from_state']!r}"
            )
            assert event["to_state"] == to_state, (
                f"Event {i} to_state mismatch: expected {to_state!r}, got {event['to_state']!r}"
            )
