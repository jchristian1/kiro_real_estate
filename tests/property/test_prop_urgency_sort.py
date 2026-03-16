"""
Property-based tests for urgency sort order.

Feature: agent-app

**Property 15: Urgency Sort Order** — for any leads inbox query result, all HOT
leads appear before all WARM leads, and all WARM leads appear before all NURTURE
leads.

**Validates: Requirements 11.1**
"""

import secrets
import uuid
from datetime import datetime, timedelta

import bcrypt
import pytest
from fastapi.testclient import TestClient
from hypothesis import HealthCheck, assume, given, settings
from hypothesis import strategies as st
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import gmail_lead_sync.agent_models  # noqa: F401 — registers agent tables
from api.main import app, get_db
from gmail_lead_sync.agent_models import AgentPreferences, AgentSession, AgentUser
from gmail_lead_sync.models import Base, Lead, LeadSource


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
    """Create an agent with a hashed password and preferences."""
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
    """Create a valid session and return the token."""
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
    """Return an existing LeadSource id, creating one if needed."""
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


def _create_lead(db, agent_user_id: int, bucket: str, index: int = 0) -> Lead:
    """Create a lead with the given score_bucket belonging to the given agent."""
    source_id = _ensure_lead_source(db)
    score_map = {"HOT": 85, "WARM": 65, "NURTURE": 30}
    lead = Lead(
        name=f"Lead {bucket} {index} agent {agent_user_id}",
        phone="555-0000",
        source_email="source@example.com",
        lead_source_id=source_id,
        gmail_uid=f"uid_{agent_user_id}_{bucket}_{index}_{uuid.uuid4().hex}",
        agent_user_id=agent_user_id,
        score_bucket=bucket,
        score=score_map.get(bucket, 50),
        created_at=datetime.utcnow(),
    )
    db.add(lead)
    db.commit()
    db.refresh(lead)
    return lead


# ---------------------------------------------------------------------------
# Property 15: Urgency Sort Order
# ---------------------------------------------------------------------------


class TestProperty15UrgencySortOrder:
    """
    Property 15: Urgency Sort Order
    **Validates: Requirements 11.1**

    For any leads inbox query result, all HOT leads appear before all WARM
    leads, and all WARM leads appear before all NURTURE leads.
    """

    @given(
        n_hot=st.integers(0, 5),
        n_warm=st.integers(0, 5),
        n_nurture=st.integers(0, 5),
    )
    @settings(
        max_examples=30,
        deadline=None,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
    )
    def test_hot_before_warm_before_nurture(
        self, setup_db, n_hot: int, n_warm: int, n_nurture: int
    ):
        """
        Property 15: Urgency Sort Order — GET /api/v1/agent/leads
        **Validates: Requirements 11.1**

        For any combination of HOT, WARM, and NURTURE leads, the returned list
        must have all HOT leads before all WARM leads, and all WARM leads before
        all NURTURE leads.
        """
        # Skip if no leads at all
        assume(n_hot + n_warm + n_nurture > 0)

        TestingSessionLocal, engine = setup_db

        # Re-apply override and ensure schema inside Hypothesis body
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

            # Create leads in reverse urgency order to stress the sort
            for i in range(n_nurture):
                _create_lead(db, agent.id, "NURTURE", i)
            for i in range(n_warm):
                _create_lead(db, agent.id, "WARM", i)
            for i in range(n_hot):
                _create_lead(db, agent.id, "HOT", i)

            token = _create_session(db, agent.id)
        finally:
            db.close()

        with TestClient(app, raise_server_exceptions=False) as client:
            resp = client.get(
                "/api/v1/agent/leads",
                cookies={"agent_session": token},
            )

        assert resp.status_code == 200, (
            f"Expected 200, got {resp.status_code}: {resp.text}"
        )
        data = resp.json()
        leads = data["leads"]

        # Verify total count
        expected_total = n_hot + n_warm + n_nurture
        assert data["total"] == expected_total, (
            f"Expected total={expected_total}, got {data['total']}"
        )
        assert len(leads) == expected_total, (
            f"Expected {expected_total} leads on page, got {len(leads)}"
        )

        # Extract the sequence of buckets from the response
        buckets = [lead["score_bucket"] for lead in leads]

        # Verify urgency ordering: HOT < WARM < NURTURE
        # Once we see a WARM lead, no HOT lead should follow.
        # Once we see a NURTURE lead, no HOT or WARM lead should follow.
        seen_warm = False
        seen_nurture = False

        for bucket in buckets:
            if bucket == "HOT":
                assert not seen_warm, (
                    f"HOT lead appeared after WARM lead. Bucket sequence: {buckets}"
                )
                assert not seen_nurture, (
                    f"HOT lead appeared after NURTURE lead. Bucket sequence: {buckets}"
                )
            elif bucket == "WARM":
                seen_warm = True
                assert not seen_nurture, (
                    f"WARM lead appeared after NURTURE lead. Bucket sequence: {buckets}"
                )
            elif bucket == "NURTURE":
                seen_nurture = True

        # Verify counts per bucket
        hot_count = buckets.count("HOT")
        warm_count = buckets.count("WARM")
        nurture_count = buckets.count("NURTURE")

        assert hot_count == n_hot, (
            f"Expected {n_hot} HOT leads, got {hot_count}. Buckets: {buckets}"
        )
        assert warm_count == n_warm, (
            f"Expected {n_warm} WARM leads, got {warm_count}. Buckets: {buckets}"
        )
        assert nurture_count == n_nurture, (
            f"Expected {n_nurture} NURTURE leads, got {nurture_count}. Buckets: {buckets}"
        )
