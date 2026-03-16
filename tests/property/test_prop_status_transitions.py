"""
Property-based tests for status transition validity.

Feature: agent-app

**Property 18: Status Transition Validity** — any transition not in the valid
set is rejected with 422; any transition in the valid set is accepted with 200.

**Validates: Requirements 12.6**
"""

import secrets
import uuid
from datetime import datetime, timedelta
from typing import List, Optional, Tuple

import bcrypt
import pytest
from fastapi.testclient import TestClient
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import gmail_lead_sync.agent_models  # noqa: F401 — registers agent tables
from api.main import app, get_db
from gmail_lead_sync.agent_models import AgentPreferences, AgentSession, AgentUser
from gmail_lead_sync.models import Base, Lead, LeadSource

# ---------------------------------------------------------------------------
# Transition tables
# ---------------------------------------------------------------------------

VALID_TRANSITIONS = {
    None: ["CONTACTED", "APPOINTMENT_SET", "LOST"],
    "NEW": ["CONTACTED", "APPOINTMENT_SET", "LOST"],
    "INVITE_SENT": ["CONTACTED", "APPOINTMENT_SET", "LOST"],
    "FORM_SUBMITTED": ["CONTACTED", "APPOINTMENT_SET", "LOST"],
    "SCORED": ["CONTACTED", "APPOINTMENT_SET", "LOST"],
    "CONTACTED": ["APPOINTMENT_SET", "LOST", "CLOSED"],
    "APPOINTMENT_SET": ["CONTACTED", "LOST", "CLOSED"],
    "LOST": ["CONTACTED"],
    "CLOSED": [],
}

# All states that a lead can be in (agent_current_state column values)
ALL_FROM_STATES: List[Optional[str]] = [
    None,
    "NEW",
    "INVITE_SENT",
    "FORM_SUBMITTED",
    "SCORED",
    "CONTACTED",
    "APPOINTMENT_SET",
    "LOST",
    "CLOSED",
]

# All target statuses the PATCH endpoint accepts
ALL_TARGET_STATUSES: List[str] = ["CONTACTED", "APPOINTMENT_SET", "LOST", "CLOSED"]

# Build exhaustive lists of (from_state, to_state) pairs
_valid_pairs: List[Tuple[Optional[str], str]] = [
    (from_state, to_state)
    for from_state in ALL_FROM_STATES
    for to_state in VALID_TRANSITIONS.get(from_state, [])
    if to_state in ALL_TARGET_STATUSES
]

_invalid_pairs: List[Tuple[Optional[str], str]] = [
    (from_state, to_state)
    for from_state in ALL_FROM_STATES
    for to_state in ALL_TARGET_STATUSES
    if to_state not in VALID_TRANSITIONS.get(from_state, [])
]


# ---------------------------------------------------------------------------
# DB isolation fixture — named in-memory SQLite per test run
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def setup_db():
    db_name = f"test_{uuid.uuid4().hex}"
    engine = create_engine(
        f"sqlite:///file:{db_name}?mode=memory&cache=shared&uri=true",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    yield TestingSessionLocal, engine
    app.dependency_overrides.pop(get_db, None)
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _create_agent(db) -> AgentUser:
    uid = uuid.uuid4().hex[:8]
    password_hash = bcrypt.hashpw(b"password", bcrypt.gensalt()).decode()
    agent = AgentUser(
        email=f"agent_{uid}@example.com",
        password_hash=password_hash,
        full_name=f"Agent {uid}",
        onboarding_step=1,
        onboarding_completed=True,
        created_at=datetime.utcnow(),
    )
    db.add(agent)
    db.commit()
    db.refresh(agent)

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
# Property 18a: Invalid transitions are rejected with 422
# ---------------------------------------------------------------------------


class TestProperty18InvalidTransitionsRejected:
    """
    Property 18: Status Transition Validity — invalid transitions
    **Validates: Requirements 12.6**

    Any transition not in the valid set must be rejected with HTTP 422.
    """

    @given(transition=st.sampled_from(_invalid_pairs))
    @settings(
        max_examples=len(_invalid_pairs),
        deadline=None,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
    )
    def test_invalid_transition_returns_422(
        self,
        setup_db,
        transition: Tuple[Optional[str], str],
    ):
        """
        Property 18: Status Transition Validity — invalid transitions rejected
        **Validates: Requirements 12.6**

        For any (from_state, to_state) pair where to_state is NOT in
        VALID_TRANSITIONS[from_state], PATCH /api/v1/agent/leads/{id}/status
        must return 422.
        """
        from_state, to_state = transition
        TestingSessionLocal, engine = setup_db

        def override_get_db():
            db = TestingSessionLocal()
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[get_db] = override_get_db
        Base.metadata.create_all(bind=engine)

        db = TestingSessionLocal()
        try:
            agent = _create_agent(db)
            lead = _create_lead(db, agent.id, from_state)
            token = _create_session(db, agent.id)
            lead_id = lead.id
        finally:
            db.close()

        with TestClient(app, raise_server_exceptions=False) as client:
            resp = client.patch(
                f"/api/v1/agent/leads/{lead_id}/status",
                json={"status": to_state},
                cookies={"agent_session": token},
            )

        assert resp.status_code == 422, (
            f"Expected 422 for invalid transition {from_state!r} → {to_state!r}, "
            f"got {resp.status_code}: {resp.text}"
        )


# ---------------------------------------------------------------------------
# Property 18b: Valid transitions are accepted with 200
# ---------------------------------------------------------------------------


class TestProperty18ValidTransitionsAccepted:
    """
    Property 18: Status Transition Validity — valid transitions
    **Validates: Requirements 12.6**

    Any transition in the valid set must be accepted with HTTP 200 and the
    response body must reflect the new current_state.
    """

    @given(transition=st.sampled_from(_valid_pairs))
    @settings(
        max_examples=len(_valid_pairs),
        deadline=None,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
    )
    def test_valid_transition_returns_200(
        self,
        setup_db,
        transition: Tuple[Optional[str], str],
    ):
        """
        Property 18: Status Transition Validity — valid transitions accepted
        **Validates: Requirements 12.6**

        For any (from_state, to_state) pair where to_state IS in
        VALID_TRANSITIONS[from_state], PATCH /api/v1/agent/leads/{id}/status
        must return 200 and the response body must have current_state == to_state.
        """
        from_state, to_state = transition
        TestingSessionLocal, engine = setup_db

        def override_get_db():
            db = TestingSessionLocal()
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[get_db] = override_get_db
        Base.metadata.create_all(bind=engine)

        db = TestingSessionLocal()
        try:
            agent = _create_agent(db)
            lead = _create_lead(db, agent.id, from_state)
            token = _create_session(db, agent.id)
            lead_id = lead.id
        finally:
            db.close()

        with TestClient(app, raise_server_exceptions=False) as client:
            resp = client.patch(
                f"/api/v1/agent/leads/{lead_id}/status",
                json={"status": to_state},
                cookies={"agent_session": token},
            )

        assert resp.status_code == 200, (
            f"Expected 200 for valid transition {from_state!r} → {to_state!r}, "
            f"got {resp.status_code}: {resp.text}"
        )
        body = resp.json()
        assert body["current_state"] == to_state, (
            f"Expected current_state={to_state!r} after transition from {from_state!r}, "
            f"got current_state={body.get('current_state')!r}"
        )
