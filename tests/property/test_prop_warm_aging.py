"""
Property-based tests for WARM lead aging accuracy.

Feature: agent-app

**Property 12: WARM Lead Aging Accuracy** — `is_aging = TRUE` iff
`(NOW() - created_at) > 24 hours`

**Validates: Requirements 11.6**
"""

import secrets
import uuid
from datetime import datetime, timedelta

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
        sla_minutes_hot=15,
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


def _create_warm_lead(db, agent_user_id: int, *, created_at: datetime) -> Lead:
    source_id = _ensure_lead_source(db)
    lead = Lead(
        name="Test WARM Lead",
        phone="555-0001",
        source_email="source@example.com",
        lead_source_id=source_id,
        gmail_uid=f"uid_{uuid.uuid4().hex}",
        agent_user_id=agent_user_id,
        score_bucket="WARM",
        score=65,
        agent_current_state="NEW",
        created_at=created_at,
    )
    db.add(lead)
    db.commit()
    db.refresh(lead)
    return lead


# ---------------------------------------------------------------------------
# Property 12a: Aging WARM lead (older than 24 hours)
# ---------------------------------------------------------------------------


class TestProperty12AgingWarmLead:
    """
    Property 12: WARM Lead Aging Accuracy — aging case
    **Validates: Requirements 11.6**

    A WARM lead with age > 24 hours must have is_aging == True.
    """

    @given(extra_hours=st.integers(1, 72))
    @settings(
        max_examples=30,
        deadline=None,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
    )
    def test_warm_lead_older_than_24h_is_aging(self, setup_db, extra_hours: int):
        """
        Property 12: WARM Lead Aging Accuracy — aging WARM lead
        **Validates: Requirements 11.6**

        A WARM lead where (NOW() - created_at) > 24 hours must have
        is_aging == True.
        """
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
            created_at = datetime.utcnow() - timedelta(hours=24 + extra_hours)
            _create_warm_lead(db, agent.id, created_at=created_at)
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
        assert len(leads) == 1, f"Expected 1 lead, got {len(leads)}"

        lead = leads[0]
        assert lead["is_aging"] is True, (
            f"Expected is_aging=True for WARM lead with age "
            f"{24 + extra_hours}h > 24h, got is_aging={lead['is_aging']}"
        )


# ---------------------------------------------------------------------------
# Property 12b: Non-aging WARM lead (less than 24 hours old)
# ---------------------------------------------------------------------------


class TestProperty12NonAgingWarmLead:
    """
    Property 12: WARM Lead Aging Accuracy — non-aging case
    **Validates: Requirements 11.6**

    A WARM lead with age <= 24 hours must have is_aging == False.
    """

    @given(age_minutes=st.integers(0, 23 * 60))
    @settings(
        max_examples=30,
        deadline=None,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
    )
    def test_warm_lead_within_24h_not_aging(self, setup_db, age_minutes: int):
        """
        Property 12: WARM Lead Aging Accuracy — non-aging WARM lead
        **Validates: Requirements 11.6**

        A WARM lead where (NOW() - created_at) <= 24 hours must have
        is_aging == False.
        """
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
            created_at = datetime.utcnow() - timedelta(minutes=age_minutes)
            _create_warm_lead(db, agent.id, created_at=created_at)
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
        assert len(leads) == 1, f"Expected 1 lead, got {len(leads)}"

        lead = leads[0]
        assert lead["is_aging"] is False, (
            f"Expected is_aging=False for WARM lead with age "
            f"{age_minutes}min ({age_minutes / 60:.1f}h) <= 24h, "
            f"got is_aging={lead['is_aging']}"
        )
