"""
Property-based tests for tenant isolation.

Feature: agent-app

**Property 1: Tenant Isolation** — for any agent API response, every resource
in the response has `agent_user_id` matching the authenticated agent.

**Validates: Requirements 10.2, 11.7, 17.3, 18.1, 18.2**
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
    yield TestingSessionLocal
    app.dependency_overrides.pop(get_db, None)
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _create_agent(db, email: str) -> AgentUser:
    """Create an agent with a hashed password."""
    password_hash = bcrypt.hashpw(b"password", bcrypt.gensalt()).decode()
    agent = AgentUser(
        email=email,
        password_hash=password_hash,
        full_name=f"Agent {email}",
        onboarding_step=1,
        onboarding_completed=True,
        created_at=datetime.utcnow(),
    )
    db.add(agent)
    db.commit()
    db.refresh(agent)

    # Create preferences so dashboard/leads endpoints work
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


def _create_lead(db, agent_user_id: int, index: int = 0) -> Lead:
    """Create a lead belonging to the given agent."""
    source_id = _ensure_lead_source(db)
    lead = Lead(
        name=f"Lead {index} for agent {agent_user_id}",
        phone="555-0000",
        source_email="source@example.com",
        lead_source_id=source_id,
        gmail_uid=f"uid_{agent_user_id}_{index}_{uuid.uuid4().hex}",
        agent_user_id=agent_user_id,
        score_bucket="HOT",
        score=85,
        created_at=datetime.utcnow(),
    )
    db.add(lead)
    db.commit()
    db.refresh(lead)
    return lead


# ---------------------------------------------------------------------------
# Property 1: Tenant Isolation
# ---------------------------------------------------------------------------


class TestProperty1TenantIsolation:
    """
    Property 1: Tenant Isolation
    **Validates: Requirements 10.2, 11.7, 17.3, 18.1, 18.2**

    For any agent API response, every resource in the response has
    agent_user_id matching the authenticated agent.
    """

    @given(
        n_leads_a=st.integers(min_value=1, max_value=5),
        n_leads_b=st.integers(min_value=1, max_value=5),
    )
    @settings(
        max_examples=20,
        deadline=None,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
    )
    def test_leads_endpoint_returns_only_own_leads(
        self, setup_db, n_leads_a: int, n_leads_b: int
    ):
        """
        Property 1: Tenant Isolation — GET /api/v1/agent/leads
        **Validates: Requirements 11.7, 18.1**

        For any N leads belonging to agent_a and M leads belonging to agent_b,
        GET /api/v1/agent/leads authenticated as agent_a returns only leads
        where agent_user_id == agent_a.id.
        """
        TestingSessionLocal = setup_db
        # Re-apply override inside Hypothesis body
        def override_get_db():
            db = TestingSessionLocal()
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[get_db] = override_get_db

        db = TestingSessionLocal()
        try:
            # Create two agents
            uid = uuid.uuid4().hex[:8]
            agent_a = _create_agent(db, f"agent_a_{uid}@example.com")
            agent_b = _create_agent(db, f"agent_b_{uid}@example.com")

            # Create leads for each agent
            leads_a = [_create_lead(db, agent_a.id, i) for i in range(n_leads_a)]
            leads_b_ids = {_create_lead(db, agent_b.id, i).id for i in range(n_leads_b)}

            agent_a_lead_ids = {lead.id for lead in leads_a}

            # Authenticate as agent_a
            token_a = _create_session(db, agent_a.id)
        finally:
            db.close()

        with TestClient(app, raise_server_exceptions=False) as client:
            resp = client.get(
                "/api/v1/agent/leads",
                cookies={"agent_session": token_a},
            )

        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        returned_leads = data["leads"]

        # Every returned lead must belong to agent_a
        for lead in returned_leads:
            assert lead["id"] in agent_a_lead_ids, (
                f"Lead id={lead['id']} does not belong to agent_a "
                f"(agent_a leads: {agent_a_lead_ids}, agent_b leads: {leads_b_ids})"
            )

        # No lead from agent_b should appear
        returned_ids = {lead["id"] for lead in returned_leads}
        cross_tenant = returned_ids & leads_b_ids
        assert not cross_tenant, (
            f"Cross-tenant leak: lead ids {cross_tenant} from agent_b appeared in agent_a's response"
        )

    @given(
        n_leads_a=st.integers(min_value=1, max_value=5),
        n_leads_b=st.integers(min_value=1, max_value=5),
    )
    @settings(
        max_examples=20,
        deadline=None,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
    )
    def test_dashboard_hot_leads_belong_to_authenticated_agent(
        self, setup_db, n_leads_a: int, n_leads_b: int
    ):
        """
        Property 1: Tenant Isolation — GET /api/v1/agent/dashboard
        **Validates: Requirements 10.2, 18.1**

        For any N HOT leads belonging to agent_a and M HOT leads belonging to
        agent_b, the dashboard hot_leads list contains only ids from agent_a's
        leads.
        """
        TestingSessionLocal = setup_db

        def override_get_db():
            db = TestingSessionLocal()
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[get_db] = override_get_db

        db = TestingSessionLocal()
        try:
            uid = uuid.uuid4().hex[:8]
            agent_a = _create_agent(db, f"dash_a_{uid}@example.com")
            agent_b = _create_agent(db, f"dash_b_{uid}@example.com")

            leads_a = [_create_lead(db, agent_a.id, i) for i in range(n_leads_a)]
            leads_b_ids = {_create_lead(db, agent_b.id, i).id for i in range(n_leads_b)}

            agent_a_lead_ids = {lead.id for lead in leads_a}
            token_a = _create_session(db, agent_a.id)
        finally:
            db.close()

        with TestClient(app, raise_server_exceptions=False) as client:
            resp = client.get(
                "/api/v1/agent/dashboard",
                cookies={"agent_session": token_a},
            )

        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        hot_leads = data.get("hot_leads", [])

        # Every hot_lead id must be in agent_a's lead ids
        for hot_lead in hot_leads:
            assert hot_lead["id"] in agent_a_lead_ids, (
                f"Hot lead id={hot_lead['id']} does not belong to agent_a "
                f"(agent_a leads: {agent_a_lead_ids}, agent_b leads: {leads_b_ids})"
            )

        # No lead from agent_b should appear in hot_leads
        returned_ids = {hl["id"] for hl in hot_leads}
        cross_tenant = returned_ids & leads_b_ids
        assert not cross_tenant, (
            f"Cross-tenant leak: hot lead ids {cross_tenant} from agent_b appeared in agent_a's dashboard"
        )

    @given(n_leads_b=st.integers(min_value=1, max_value=5))
    @settings(
        max_examples=20,
        deadline=None,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
    )
    def test_lead_detail_returns_403_for_other_agents_leads(
        self, setup_db, n_leads_b: int
    ):
        """
        Property 1: Tenant Isolation — GET /api/v1/agent/leads/{id}
        **Validates: Requirements 18.2, 12.2**

        For each lead belonging to agent_b, a request authenticated as agent_a
        must receive a 403 response.
        """
        TestingSessionLocal = setup_db

        def override_get_db():
            db = TestingSessionLocal()
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[get_db] = override_get_db

        db = TestingSessionLocal()
        try:
            uid = uuid.uuid4().hex[:8]
            agent_a = _create_agent(db, f"detail_a_{uid}@example.com")
            agent_b = _create_agent(db, f"detail_b_{uid}@example.com")

            leads_b_ids = [_create_lead(db, agent_b.id, i).id for i in range(n_leads_b)]
            token_a = _create_session(db, agent_a.id)
        finally:
            db.close()

        with TestClient(app, raise_server_exceptions=False) as client:
            for lead_b_id in leads_b_ids:
                resp = client.get(
                    f"/api/v1/agent/leads/{lead_b_id}",
                    cookies={"agent_session": token_a},
                )
                assert resp.status_code == 403, (
                    f"Expected 403 for cross-agent lead id={lead_b_id}, "
                    f"got {resp.status_code}: {resp.text}"
                )
