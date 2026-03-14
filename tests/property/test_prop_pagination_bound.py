"""
Property-based tests for pagination bound.

Feature: agent-app

**Property 17: Pagination Bound** — for any paginated leads inbox response,
the number of leads returned is at most 25.

**Validates: Requirements 11.4**
"""

import math
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


def _create_leads(db, agent_user_id: int, n: int) -> None:
    """Bulk-create n leads for the given agent."""
    source_id = _ensure_lead_source(db)
    buckets = ["HOT", "WARM", "NURTURE"]
    for i in range(n):
        lead = Lead(
            name=f"Lead {i}",
            phone="555-0000",
            source_email="source@example.com",
            lead_source_id=source_id,
            gmail_uid=f"uid_{agent_user_id}_{i}_{uuid.uuid4().hex}",
            agent_user_id=agent_user_id,
            score_bucket=buckets[i % 3],
            score=85 - (i % 3) * 20,
            created_at=datetime.utcnow(),
        )
        db.add(lead)
    db.commit()


# ---------------------------------------------------------------------------
# Property 17: Pagination Bound
# ---------------------------------------------------------------------------


class TestProperty17PaginationBound:
    """
    Property 17: Pagination Bound
    **Validates: Requirements 11.4**

    For any paginated leads inbox response, the number of leads returned is
    at most 25.  Also verifies page_size == 25, correct total_pages, and that
    page 1 returns min(n_leads, 25) leads.
    """

    @given(
        n_leads=st.integers(0, 60),
        page=st.integers(1, 5),
    )
    @settings(
        max_examples=40,
        deadline=None,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
    )
    def test_page_never_exceeds_25_leads(
        self, setup_db, n_leads: int, page: int
    ):
        """
        Property 17: Pagination Bound — GET /api/v1/agent/leads?page={page}
        **Validates: Requirements 11.4**

        For any number of leads (0–60) and any page (1–5):
        - len(response["leads"]) <= 25
        - response["page_size"] == 25
        - total_pages == ceil(n_leads / 25) when n_leads > 0, else 1
        - when n_leads > 0 and page == 1: len(leads) == min(n_leads, 25)
        """
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
            _create_leads(db, agent.id, n_leads)
            token = _create_session(db, agent.id)
        finally:
            db.close()

        with TestClient(app, raise_server_exceptions=False) as client:
            resp = client.get(
                "/api/v1/agent/leads",
                params={"page": page},
                cookies={"agent_session": token},
            )

        assert resp.status_code == 200, (
            f"Expected 200, got {resp.status_code}: {resp.text}"
        )
        data = resp.json()
        leads = data["leads"]

        # Core property: never more than 25 leads on any page
        assert len(leads) <= 25, (
            f"Page {page} returned {len(leads)} leads — exceeds PAGE_SIZE=25 "
            f"(n_leads={n_leads})"
        )

        # page_size field must always report 25
        assert data["page_size"] == 25, (
            f"page_size={data['page_size']!r}, expected 25"
        )

        # total_pages: ceil(n_leads / 25) when n_leads > 0, else 1
        expected_total_pages = math.ceil(n_leads / 25) if n_leads > 0 else 1
        assert data["total_pages"] == expected_total_pages, (
            f"total_pages={data['total_pages']}, expected {expected_total_pages} "
            f"(n_leads={n_leads})"
        )

        # On page 1 with at least one lead, must return exactly min(n_leads, 25)
        if n_leads > 0 and page == 1:
            expected_count = min(n_leads, 25)
            assert len(leads) == expected_count, (
                f"Page 1 returned {len(leads)} leads, expected {expected_count} "
                f"(n_leads={n_leads})"
            )
