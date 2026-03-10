"""
Property-based tests for Onboarding Test Simulation Leaves No Records.

Feature: agent-app

**Property 20: Onboarding Test Simulation Leaves No Records** — record counts
in `leads`, `lead_events`, `agent_templates` are identical before and after
simulation.

**Validates: Requirements 9.3**
"""

import secrets
from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from hypothesis import HealthCheck, given, settings, strategies as st
from sqlalchemy import create_engine, func
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from api.main import app, get_db
from gmail_lead_sync.models import Base, Lead
import gmail_lead_sync.agent_models  # noqa: F401 — registers agent tables
from gmail_lead_sync.agent_models import (
    AgentSession,
    AgentTemplate,
    AgentUser,
    BuyerAutomationConfig,
    LeadEvent,
)

# ---------------------------------------------------------------------------
# In-memory SQLite test database (StaticPool — same connection for all threads)
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

TEST_URL = "/api/v1/agent/onboarding/test"
AGENT_SESSION_COOKIE = "agent_session"

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _create_agent_with_session(db) -> tuple[AgentUser, str]:
    """Create an agent at onboarding_step=5 with a valid session."""
    agent = AgentUser(
        email=f"prop_sim_{secrets.token_hex(4)}@example.com",
        password_hash="$2b$12$fakehash",
        full_name="Sim Test Agent",
        onboarding_step=5,
        onboarding_completed=False,
        created_at=datetime.utcnow(),
    )
    db.add(agent)
    db.flush()

    token = secrets.token_hex(64)
    now = datetime.utcnow()
    session = AgentSession(
        id=token,
        agent_user_id=agent.id,
        created_at=now,
        expires_at=now + timedelta(days=30),
        last_accessed=now,
    )
    db.add(session)
    db.commit()
    db.refresh(agent)
    return agent, token


def _count_records(db) -> dict[str, int]:
    """Return current record counts for leads, lead_events, agent_templates."""
    return {
        "leads": db.query(func.count(Lead.id)).scalar(),
        "lead_events": db.query(func.count(LeadEvent.id)).scalar(),
        "agent_templates": db.query(func.count(AgentTemplate.id)).scalar(),
    }


# ---------------------------------------------------------------------------
# Property 20: Onboarding Test Simulation Leaves No Records
# ---------------------------------------------------------------------------


class TestProperty20OnboardingTestSimulationLeavesNoRecords:
    """
    Property 20: Onboarding Test Simulation Leaves No Records
    **Validates: Requirements 9.3**

    For any agent configuration (with or without BuyerAutomationConfig,
    with or without AgentTemplates), calling POST /test does NOT change the
    count of records in `leads`, `lead_events`, or `agent_templates` tables.
    """

    @given(
        has_config=st.booleans(),
        has_templates=st.booleans(),
    )
    @settings(
        max_examples=8,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
    )
    def test_simulation_leaves_no_records(
        self,
        has_config: bool,
        has_templates: bool,
    ):
        """
        Property 20: Onboarding Test Simulation Leaves No Records
        **Validates: Requirements 9.3**

        For any combination of BuyerAutomationConfig and AgentTemplates presence,
        POST /test must not create any new records in leads, lead_events, or
        agent_templates.
        """
        db = TestingSessionLocal()
        try:
            agent, token = _create_agent_with_session(db)

            # Optionally create BuyerAutomationConfig
            if has_config:
                config = BuyerAutomationConfig(
                    agent_user_id=agent.id,
                    name="Test Config",
                    created_at=datetime.utcnow(),
                )
                db.add(config)
                db.commit()

            # Optionally create AgentTemplates
            if has_templates:
                for ttype in ["INITIAL_INVITE", "POST_HOT", "POST_WARM", "POST_NURTURE"]:
                    tmpl = AgentTemplate(
                        agent_user_id=agent.id,
                        template_type=ttype,
                        subject=f"Subject {ttype}",
                        body=f"Body {ttype}",
                        is_active=True,
                        created_at=datetime.utcnow(),
                    )
                    db.add(tmpl)
                db.commit()

            # Count records BEFORE calling the endpoint
            counts_before = _count_records(db)

            with TestClient(app, raise_server_exceptions=False) as c:
                resp = c.post(
                    TEST_URL,
                    cookies={AGENT_SESSION_COOKIE: token},
                )

            assert resp.status_code == 200, (
                f"Expected 200 from POST /test, got {resp.status_code}. "
                f"has_config={has_config}, has_templates={has_templates}. "
                f"body={resp.text}"
            )

            # Count records AFTER calling the endpoint
            db.expire_all()
            counts_after = _count_records(db)

            assert counts_before == counts_after, (
                f"Record counts changed after POST /test simulation! "
                f"has_config={has_config}, has_templates={has_templates}. "
                f"before={counts_before}, after={counts_after}"
            )
        finally:
            db.close()

    @given(
        call_count=st.integers(min_value=1, max_value=5),
    )
    @settings(
        max_examples=8,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
    )
    def test_repeated_simulation_calls_leave_no_records(
        self,
        call_count: int,
    ):
        """
        Property 20: Onboarding Test Simulation Leaves No Records (repeated calls)
        **Validates: Requirements 9.3**

        For any number of repeated calls to POST /test (1–5), the record counts
        in leads, lead_events, and agent_templates remain unchanged after all calls.
        """
        db = TestingSessionLocal()
        try:
            agent, token = _create_agent_with_session(db)

            # Count records BEFORE any calls
            counts_before = _count_records(db)

            with TestClient(app, raise_server_exceptions=False) as c:
                for i in range(call_count):
                    resp = c.post(
                        TEST_URL,
                        cookies={AGENT_SESSION_COOKIE: token},
                    )
                    assert resp.status_code == 200, (
                        f"Call {i + 1}/{call_count}: expected 200, got {resp.status_code}. "
                        f"body={resp.text}"
                    )

            # Count records AFTER all calls
            db.expire_all()
            counts_after = _count_records(db)

            assert counts_before == counts_after, (
                f"Record counts changed after {call_count} repeated POST /test calls! "
                f"before={counts_before}, after={counts_after}"
            )
        finally:
            db.close()
