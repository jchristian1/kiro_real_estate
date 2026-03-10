"""
Property-based tests for HOT lead aging accuracy.

Feature: agent-app

**Property 11: HOT Lead Aging Accuracy** — `is_aging = TRUE` iff
`last_agent_action_at IS NULL` AND `(NOW() - created_at) > sla_minutes_hot`

**Validates: Requirements 10.3, 11.5**
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


def _create_agent(db, sla_minutes_hot: int = 5) -> AgentUser:
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
        sla_minutes_hot=sla_minutes_hot,
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


def _create_hot_lead(
    db,
    agent_user_id: int,
    *,
    created_at: datetime,
    last_agent_action_at=None,
) -> Lead:
    source_id = _ensure_lead_source(db)
    lead = Lead(
        name="Test HOT Lead",
        phone="555-0000",
        source_email="source@example.com",
        lead_source_id=source_id,
        gmail_uid=f"uid_{uuid.uuid4().hex}",
        agent_user_id=agent_user_id,
        score_bucket="HOT",
        score=85,
        agent_current_state="NEW",
        created_at=created_at,
        last_agent_action_at=last_agent_action_at,
    )
    db.add(lead)
    db.commit()
    db.refresh(lead)
    return lead


# ---------------------------------------------------------------------------
# Property 11a: Aging HOT lead (no action, old enough)
# ---------------------------------------------------------------------------


class TestProperty11AgingHotLead:
    """
    Property 11: HOT Lead Aging Accuracy — aging case
    **Validates: Requirements 10.3, 11.5**

    A HOT lead with no agent action and age > sla_minutes_hot must have
    is_aging == True.
    """

    @given(
        sla_minutes=st.integers(1, 30),
        extra_minutes=st.integers(1, 60),
    )
    @settings(
        max_examples=30,
        deadline=None,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
    )
    def test_hot_lead_no_action_old_enough_is_aging(
        self, setup_db, sla_minutes: int, extra_minutes: int
    ):
        """
        Property 11: HOT Lead Aging Accuracy — aging HOT lead
        **Validates: Requirements 10.3, 11.5**

        A HOT lead where last_agent_action_at IS NULL and
        (NOW() - created_at) > sla_minutes_hot must have is_aging == True.
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
            agent = _create_agent(db, sla_minutes_hot=sla_minutes)
            # Lead is older than SLA by extra_minutes
            created_at = datetime.utcnow() - timedelta(
                minutes=sla_minutes + extra_minutes
            )
            _create_hot_lead(
                db,
                agent.id,
                created_at=created_at,
                last_agent_action_at=None,
            )
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
            f"Expected is_aging=True for HOT lead with no action and age "
            f"{sla_minutes + extra_minutes}min > sla={sla_minutes}min, "
            f"got is_aging={lead['is_aging']}"
        )


# ---------------------------------------------------------------------------
# Property 11b: Non-aging HOT lead (no action, too recent)
# ---------------------------------------------------------------------------


class TestProperty11NonAgingHotLeadRecent:
    """
    Property 11: HOT Lead Aging Accuracy — non-aging (too recent)
    **Validates: Requirements 10.3, 11.5**

    A HOT lead with no agent action but age well within SLA must have
    is_aging == False.
    """

    @given(
        sla_minutes=st.integers(5, 30),
    )
    @settings(
        max_examples=30,
        deadline=None,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
    )
    def test_hot_lead_no_action_too_recent_not_aging(
        self, setup_db, sla_minutes: int
    ):
        """
        Property 11: HOT Lead Aging Accuracy — non-aging HOT lead (too recent)
        **Validates: Requirements 10.3, 11.5**

        A HOT lead where last_agent_action_at IS NULL but
        (NOW() - created_at) <= sla_minutes_hot must have is_aging == False.
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
            agent = _create_agent(db, sla_minutes_hot=sla_minutes)
            # Lead is only 1 minute old — well within any SLA >= 5 minutes
            created_at = datetime.utcnow() - timedelta(minutes=1)
            _create_hot_lead(
                db,
                agent.id,
                created_at=created_at,
                last_agent_action_at=None,
            )
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
            f"Expected is_aging=False for HOT lead with no action and age "
            f"1min <= sla={sla_minutes}min, got is_aging={lead['is_aging']}"
        )


# ---------------------------------------------------------------------------
# Property 11c: Non-aging HOT lead (has agent action)
# ---------------------------------------------------------------------------


class TestProperty11NonAgingHotLeadHasAction:
    """
    Property 11: HOT Lead Aging Accuracy — non-aging (has agent action)
    **Validates: Requirements 10.3, 11.5**

    A HOT lead that is old enough but has a last_agent_action_at must have
    is_aging == False.
    """

    @given(
        sla_minutes=st.integers(1, 10),
        extra_minutes=st.integers(1, 60),
    )
    @settings(
        max_examples=30,
        deadline=None,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
    )
    def test_hot_lead_with_action_not_aging(
        self, setup_db, sla_minutes: int, extra_minutes: int
    ):
        """
        Property 11: HOT Lead Aging Accuracy — non-aging HOT lead (has action)
        **Validates: Requirements 10.3, 11.5**

        A HOT lead where last_agent_action_at IS NOT NULL must have
        is_aging == False even if (NOW() - created_at) > sla_minutes_hot.
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
            agent = _create_agent(db, sla_minutes_hot=sla_minutes)
            # Lead is old enough to be aging...
            created_at = datetime.utcnow() - timedelta(
                minutes=sla_minutes + extra_minutes
            )
            # ...but has a recent agent action
            _create_hot_lead(
                db,
                agent.id,
                created_at=created_at,
                last_agent_action_at=datetime.utcnow(),
            )
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
            f"Expected is_aging=False for HOT lead with agent action "
            f"(age {sla_minutes + extra_minutes}min > sla={sla_minutes}min but "
            f"last_agent_action_at is set), got is_aging={lead['is_aging']}"
        )
