"""
Property-based tests for the Onboarding Completeness Gate.

Feature: agent-app

**Property 9: Onboarding Completeness Gate** — `onboarding_completed` is set
to TRUE if and only if all 4 preconditions hold simultaneously.

**Validates: Requirements 9.4**
"""

import json
import secrets
from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from hypothesis import HealthCheck, given, settings, strategies as st
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from api.main import app, get_db
from gmail_lead_sync.models import Base, Credentials
import gmail_lead_sync.agent_models  # noqa: F401 — registers agent tables
from gmail_lead_sync.agent_models import (
    AgentPreferences,
    AgentSession,
    AgentTemplate,
    AgentUser,
    BuyerAutomationConfig,
)

# ---------------------------------------------------------------------------
# In-memory SQLite test database (StaticPool — same connection for all threads)
# Use a named in-memory DB to avoid sharing state with other test files.
# ---------------------------------------------------------------------------

engine = create_engine(
    "sqlite:///file:prop_onboarding_completeness?mode=memory&cache=shared&uri=true",
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

COMPLETE_URL = "/api/v1/agent/onboarding/complete"
AGENT_SESSION_COOKIE = "agent_session"

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
def db_session(setup_db):
    db = TestingSessionLocal()
    yield db
    db.close()


@pytest.fixture
def client(setup_db):
    return TestClient(app, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _create_agent_with_session(db) -> tuple[AgentUser, str]:
    """Create an agent at onboarding_step=5 and return (agent, session_token)."""
    agent = AgentUser(
        email=f"prop_complete_{secrets.token_hex(4)}@example.com",
        password_hash="$2b$12$fakehash",
        full_name="Prop Test Agent",
        onboarding_step=5,  # step guard requires >= 5
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


def _setup_gmail(db, agent: AgentUser) -> None:
    """Precondition 1: link a Credentials record to the agent."""
    cred = Credentials(
        agent_id=f"agent_{agent.id}",
        email_encrypted="encrypted_email",
        app_password_encrypted="encrypted_blob",
        created_at=datetime.utcnow(),
    )
    db.add(cred)
    db.flush()
    agent.credentials_id = cred.id
    db.commit()


def _setup_lead_source(db, agent: AgentUser) -> None:
    """Precondition 2: set a non-empty enabled_lead_source_ids on AgentPreferences."""
    prefs = (
        db.query(AgentPreferences)
        .filter(AgentPreferences.agent_user_id == agent.id)
        .first()
    )
    if prefs is None:
        prefs = AgentPreferences(
            agent_user_id=agent.id,
            created_at=datetime.utcnow(),
        )
        db.add(prefs)
    prefs.enabled_lead_source_ids = json.dumps([1])
    db.commit()


def _setup_automation(db, agent: AgentUser) -> None:
    """Precondition 3: create a BuyerAutomationConfig for the agent."""
    config = BuyerAutomationConfig(
        agent_user_id=agent.id,
        name="Test Config",
        created_at=datetime.utcnow(),
    )
    db.add(config)
    db.commit()


_TEMPLATE_TYPES = ["INITIAL_INVITE", "POST_HOT", "POST_WARM", "POST_NURTURE"]


def _setup_templates(db, agent: AgentUser) -> None:
    """Precondition 4: create all 4 active AgentTemplate records."""
    for ttype in _TEMPLATE_TYPES:
        tmpl = AgentTemplate(
            agent_user_id=agent.id,
            template_type=ttype,
            subject=f"Subject for {ttype}",
            body=f"Body for {ttype}",
            is_active=True,
            created_at=datetime.utcnow(),
        )
        db.add(tmpl)
    db.commit()


_SETUP_FNS = [_setup_gmail, _setup_lead_source, _setup_automation, _setup_templates]


# ---------------------------------------------------------------------------
# Property 9: Onboarding Completeness Gate
# ---------------------------------------------------------------------------


class TestProperty9OnboardingCompletenessGate:
    """
    Property 9: Onboarding Completeness Gate
    **Validates: Requirements 9.4**

    `onboarding_completed` is set to TRUE if and only if all 4 preconditions
    hold simultaneously:
      1. gmail_connected   — agent.credentials_id IS NOT NULL
      2. lead_source_selected — AgentPreferences.enabled_lead_source_ids is non-empty JSON list
      3. automation_configured — BuyerAutomationConfig exists for agent
      4. templates_active  — all 4 template types have is_active=True AgentTemplate records
    """

    @given(
        gmail=st.booleans(),
        lead_source=st.booleans(),
        automation=st.booleans(),
        templates=st.booleans(),
    )
    @settings(
        max_examples=16,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
    )
    def test_completeness_gate_iff_all_preconditions(
        self,
        gmail: bool,
        lead_source: bool,
        automation: bool,
        templates: bool,
    ):
        """
        Property 9: Onboarding Completeness Gate
        **Validates: Requirements 9.4**

        For any combination of the 4 boolean preconditions:
        - If ALL 4 are True  → POST /complete returns 200 with onboarding_completed=True
        - If ANY is False    → POST /complete returns 400 with error="PRECONDITIONS_NOT_MET"
          and the checklist reflects the actual state of each precondition.
        """
        Base.metadata.create_all(bind=engine)
        db = TestingSessionLocal()
        try:
            agent, token = _create_agent_with_session(db)

            # Set up only the preconditions that are True
            flags = [gmail, lead_source, automation, templates]
            for flag, setup_fn in zip(flags, _SETUP_FNS):
                if flag:
                    setup_fn(db, agent)

            all_met = all(flags)

            with TestClient(app, raise_server_exceptions=False) as c:
                resp = c.post(
                    COMPLETE_URL,
                    cookies={AGENT_SESSION_COOKIE: token},
                )

            if all_met:
                assert resp.status_code == 200, (
                    f"Expected 200 when all preconditions met, got {resp.status_code}. "
                    f"flags=({gmail}, {lead_source}, {automation}, {templates}). "
                    f"body={resp.text}"
                )
                body = resp.json()
                assert body["onboarding_completed"] is True, (
                    f"Expected onboarding_completed=True, got {body}"
                )
            else:
                assert resp.status_code == 400, (
                    f"Expected 400 when preconditions not all met, got {resp.status_code}. "
                    f"flags=({gmail}, {lead_source}, {automation}, {templates}). "
                    f"body={resp.text}"
                )
                body = resp.json()
                assert body["error"] == "PRECONDITIONS_NOT_MET", (
                    f"Expected error='PRECONDITIONS_NOT_MET', got {body}"
                )
                checklist = body["checklist"]
                assert checklist["gmail_connected"] == gmail, (
                    f"checklist.gmail_connected={checklist['gmail_connected']} "
                    f"but expected {gmail}"
                )
                assert checklist["lead_source_selected"] == lead_source, (
                    f"checklist.lead_source_selected={checklist['lead_source_selected']} "
                    f"but expected {lead_source}"
                )
                assert checklist["automation_configured"] == automation, (
                    f"checklist.automation_configured={checklist['automation_configured']} "
                    f"but expected {automation}"
                )
                assert checklist["templates_active"] == templates, (
                    f"checklist.templates_active={checklist['templates_active']} "
                    f"but expected {templates}"
                )
        finally:
            db.close()

    @given(
        gmail=st.booleans(),
        lead_source=st.booleans(),
        automation=st.booleans(),
        templates=st.booleans(),
    )
    @settings(
        max_examples=16,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
    )
    def test_onboarding_completed_not_set_unless_all_preconditions_met(
        self,
        gmail: bool,
        lead_source: bool,
        automation: bool,
        templates: bool,
    ):
        """
        Property 9: Onboarding Completeness Gate
        **Validates: Requirements 9.4**

        `onboarding_completed` is NEVER set to True in the DB unless all 4
        preconditions hold. Conversely, when all 4 hold it IS set to True.
        """
        Base.metadata.create_all(bind=engine)
        db = TestingSessionLocal()
        try:
            agent, token = _create_agent_with_session(db)

            flags = [gmail, lead_source, automation, templates]
            for flag, setup_fn in zip(flags, _SETUP_FNS):
                if flag:
                    setup_fn(db, agent)

            all_met = all(flags)

            with TestClient(app, raise_server_exceptions=False) as c:
                c.post(COMPLETE_URL, cookies={AGENT_SESSION_COOKIE: token})

            # Re-fetch agent from DB to check persisted state
            db.expire_all()
            refreshed = db.query(AgentUser).filter(AgentUser.id == agent.id).first()

            if all_met:
                assert refreshed.onboarding_completed is True, (
                    f"Expected onboarding_completed=True in DB when all preconditions met. "
                    f"flags=({gmail}, {lead_source}, {automation}, {templates})"
                )
            else:
                assert refreshed.onboarding_completed is False, (
                    f"Expected onboarding_completed=False in DB when preconditions not all met. "
                    f"flags=({gmail}, {lead_source}, {automation}, {templates})"
                )
        finally:
            db.close()
