"""
Security integration tests (PR A1 — gmail/IMAP tests removed).

Verifies:
- Cross-agent 403 on leads, templates, preferences
- Template header injection: subject with \\n returns 422

Requirements: 14.7, 18.2
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, StaticPool
from sqlalchemy.orm import sessionmaker

from gmail_lead_sync.models import Base, Lead
from gmail_lead_sync.agent_models import AgentUser
from api.main import app, get_db


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def db_engine():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)


@pytest.fixture
def db_session(db_engine):
    SessionLocal = sessionmaker(bind=db_engine)
    session = SessionLocal()
    yield session
    session.close()


@pytest.fixture
def client(db_session):
    def override_get_db():
        try:
            yield db_session
        finally:
            pass
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app, raise_server_exceptions=True) as c:
        yield c
    app.dependency_overrides.clear()


def _create_agent_in_db(db_session, email="agent@sec.com", password="securepass123", full_name="Sec Agent"):
    """Create an agent directly in the DB and log in via the login endpoint."""
    import bcrypt
    from datetime import datetime
    existing = db_session.query(AgentUser).filter_by(email=email).first()
    if existing:
        return existing
    password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    agent = AgentUser(
        email=email,
        password_hash=password_hash,
        full_name=full_name,
        onboarding_completed=True,
        created_at=datetime.utcnow(),
    )
    db_session.add(agent)
    db_session.commit()
    db_session.refresh(agent)
    return agent


def _login(client, email="agent@sec.com", password="securepass123"):
    r = client.post("/api/v1/agent/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, f"Login failed: {r.text}"
    return r.json()


# ── app_password never in responses ──────────────────────────────────────────
# TestCredentialNeverExposed and TestImapRateLimiting removed in PR A1.
# The gmail onboarding endpoint (POST /agent/onboarding/gmail) no longer exists.
# Credential security is now tested at the admin panel level.


# ── Cross-agent isolation ─────────────────────────────────────────────────────

class TestCrossAgentIsolation:

    def _setup_two_agents(self, client, db_session):
        """Create two agents directly in DB, log in as agent2. Return agent1's lead id."""
        import secrets as _secrets

        agent1 = _create_agent_in_db(db_session, "agent1@sec.com", "pass1111111", "Agent One")
        lead = Lead(
            name="Agent1 Lead",
            phone="555-0001",
            source_email="leads@test.com",
            lead_source_id=1,
            gmail_uid=f"uid-{_secrets.token_hex(8)}",
            agent_user_id=agent1.id,
        )
        db_session.add(lead)
        db_session.commit()
        db_session.refresh(lead)
        lead_id = lead.id

        _create_agent_in_db(db_session, "agent2@sec.com", "pass2222222", "Agent Two")
        _login(client, "agent2@sec.com", "pass2222222")
        return lead_id

    def test_cross_agent_lead_detail_returns_403(self, client, db_session):
        lead_id = self._setup_two_agents(client, db_session)
        # Now logged in as agent2 — try to access agent1's lead
        r = client.get(f"/api/v1/agent/leads/{lead_id}")
        assert r.status_code == 403

    def test_cross_agent_lead_status_update_returns_403(self, client, db_session):
        lead_id = self._setup_two_agents(client, db_session)
        r = client.patch(f"/api/v1/agent/leads/{lead_id}/status", json={"status": "CONTACTED"})
        assert r.status_code == 403

    def test_cross_agent_lead_note_returns_403(self, client, db_session):
        lead_id = self._setup_two_agents(client, db_session)
        r = client.post(f"/api/v1/agent/leads/{lead_id}/notes", json={"text": "Hacked"})
        assert r.status_code == 403

    def test_leads_inbox_only_returns_own_leads(self, client, db_session):
        self._setup_two_agents(client, db_session)
        # Agent2 inbox should be empty (no leads assigned to agent2)
        r = client.get("/api/v1/agent/leads")
        assert r.status_code == 200
        leads = r.json()["leads"]
        agent2 = db_session.query(AgentUser).filter_by(email="agent2@sec.com").first()
        for lead in leads:
            assert lead["agent_user_id"] == agent2.id


# ── Template header injection ─────────────────────────────────────────────────

class TestTemplateHeaderInjection:

    def test_subject_with_newline_returns_422(self, client, db_session):
        """Requirements 14.7: subject containing \\n must be rejected."""
        _create_agent_in_db(db_session)
        _login(client)

        r = client.put("/api/v1/agent/templates/by-type/INITIAL_INVITE", json={
            "subject": "Hello\nBcc: attacker@evil.com",
            "body": "Normal body",
            "tone": "PROFESSIONAL",
        })
        assert r.status_code == 422

    def test_subject_with_carriage_return_returns_422(self, client, db_session):
        _create_agent_in_db(db_session)
        _login(client)

        r = client.put("/api/v1/agent/templates/by-type/INITIAL_INVITE", json={
            "subject": "Hello\rBcc: attacker@evil.com",
            "body": "Normal body",
            "tone": "PROFESSIONAL",
        })
        assert r.status_code == 422

    def test_valid_subject_accepted(self, client, db_session):
        _create_agent_in_db(db_session)
        _login(client)

        r = client.put("/api/v1/agent/templates/by-type/INITIAL_INVITE", json={
            "subject": "Hi {lead_name}, I saw your inquiry",
            "body": "Hello {lead_name}, I am {agent_name}.",
            "tone": "PROFESSIONAL",
        })
        assert r.status_code == 200
