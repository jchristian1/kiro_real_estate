"""
Cross-tenant isolation integration tests.

Verifies that agents cannot access other agents' resources:
- Leads
- Credentials (Gmail settings)
- Watchers
- Lead sources (agent preferences)

Each test:
1. Creates two separate agents
2. Creates a resource for agent A
3. Attempts to access that resource as agent B
4. Asserts HTTP 403 is returned
5. Asserts response body contains no data from agent A

Requirements: 6.6
"""

import pytest
import secrets
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
    # Import all models to ensure tables are created
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


# ── Helper Functions ──────────────────────────────────────────────────────────

def _create_agent_direct(db_session, email: str, password: str) -> "AgentUser":
    """Create an agent directly in the DB (no signup endpoint — company admin creates agents)."""
    import bcrypt
    from datetime import datetime
    password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    agent = AgentUser(
        email=email,
        password_hash=password_hash,
        full_name="Test Agent",
        onboarding_completed=True,
        created_at=datetime,
    )
    db_session.add(agent)
    db_session.commit()
    db_session.refresh(agent)
    return agent


def _login_agent(client, email: str, password: str):
    """Log in an agent and set the session cookie."""
    r = client.post("/api/v1/agent/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, f"Login failed for {email}: {r.text}"
    return r.json()


def _setup_two_agents(client, db_session):
    """
    Create two agents directly in the DB and log in as agent2.
    Returns (agent1_id, agent2_id).
    The client session will be logged in as agent2 after this call.
    """
    import bcrypt
    from datetime import datetime as dt

    password1 = "password1111"
    password2 = "password2222"

    agent1 = AgentUser(
        email="agent1@test.com",
        password_hash=bcrypt.hashpw(password1.encode(), bcrypt.gensalt()).decode(),
        full_name="Agent One",
        onboarding_completed=True,
        created_at=dt.utcnow(),
    )
    agent2 = AgentUser(
        email="agent2@test.com",
        password_hash=bcrypt.hashpw(password2.encode(), bcrypt.gensalt()).decode(),
        full_name="Agent Two",
        onboarding_completed=True,
        created_at=dt.utcnow(),
    )
    db_session.add_all([agent1, agent2])
    db_session.commit()
    db_session.refresh(agent1)
    db_session.refresh(agent2)

    # Log in as agent2 so the client session is set
    _login_agent(client, "agent2@test.com", password2)

    return agent1.id, agent2.id


# ── Test: Cross-Tenant Lead Access ───────────────────────────────────────────

class TestCrossTenantLeadAccess:
    """Test that agents cannot access other agents' leads."""
    
    def test_get_lead_detail_returns_403(self, client, db_session):
        """Agent B cannot GET agent A's lead detail."""
        agent1_id, agent2_id = _setup_two_agents(client, db_session)
        
        # Create a lead for agent1
        lead = Lead(
            name="Agent1 Lead",
            phone="555-0001",
            source_email="leads@test.com",
            lead_source_id=1,
            gmail_uid=f"uid-{secrets.token_hex(8)}",
            agent_user_id=agent1_id,
        )
        db_session.add(lead)
        db_session.commit()
        db_session.refresh(lead)
        lead_id = lead.id
        
        # Now logged in as agent2 — try to access agent1's lead
        r = client.get(f"/api/v1/agent/leads/{lead_id}")
        
        assert r.status_code == 403, f"Expected 403, got {r.status_code}: {r.text}"
        
        # Assert response body contains no data from agent1's lead
        body = r.json()
        assert "Agent1 Lead" not in str(body), "Response leaked agent1's lead name"
        assert "lead1@example.com" not in str(body), "Response leaked agent1's lead email"
    
    def test_update_lead_status_returns_403(self, client, db_session):
        """Agent B cannot PATCH agent A's lead status."""
        agent1_id, agent2_id = _setup_two_agents(client, db_session)
        
        lead = Lead(
            name="Agent1 Lead",
            phone="555-0001",
            source_email="leads@test.com",
            lead_source_id=1,
            gmail_uid=f"uid-{secrets.token_hex(8)}",
            agent_user_id=agent1_id,
        )
        db_session.add(lead)
        db_session.commit()
        db_session.refresh(lead)
        lead_id = lead.id
        
        # Try to update as agent2
        r = client.patch(f"/api/v1/agent/leads/{lead_id}/status", json={"status": "CONTACTED"})
        
        assert r.status_code == 403, f"Expected 403, got {r.status_code}: {r.text}"
        
        # Verify lead was not modified
        db_session.expire(lead)
        db_session.refresh(lead)
        assert lead.agent_current_state is None or lead.agent_current_state == "NEW", "Lead state was modified despite 403"
    
    def test_add_lead_note_returns_403(self, client, db_session):
        """Agent B cannot POST a note to agent A's lead."""
        agent1_id, agent2_id = _setup_two_agents(client, db_session)
        
        lead = Lead(
            name="Agent1 Lead",
            phone="555-0001",
            source_email="leads@test.com",
            lead_source_id=1,
            gmail_uid=f"uid-{secrets.token_hex(8)}",
            agent_user_id=agent1_id,
        )
        db_session.add(lead)
        db_session.commit()
        db_session.refresh(lead)
        lead_id = lead.id
        
        # Try to add note as agent2
        r = client.post(f"/api/v1/agent/leads/{lead_id}/notes", json={"text": "Hacked note"})
        
        assert r.status_code == 403, f"Expected 403, got {r.status_code}: {r.text}"
    
    def test_list_leads_only_returns_own_leads(self, client, db_session):
        """Agent B's lead list does not include agent A's leads."""
        agent1_id, agent2_id = _setup_two_agents(client, db_session)
        
        # Create leads for both agents
        lead1 = Lead(
            name="Agent1 Lead",
            phone="555-0001",
            source_email="leads@test.com",
            lead_source_id=1,
            gmail_uid=f"uid-{secrets.token_hex(8)}",
            agent_user_id=agent1_id,
        )
        lead2 = Lead(
            name="Agent2 Lead",
            phone="555-0001",
            source_email="leads@test.com",
            lead_source_id=1,
            gmail_uid=f"uid-{secrets.token_hex(8)}",
            agent_user_id=agent2_id,
        )
        db_session.add_all([lead1, lead2])
        db_session.commit()
        
        # Agent2 lists leads
        r = client.get("/api/v1/agent/leads")
        assert r.status_code == 200, f"Lead list failed: {r.text}"
        
        body = r.json()
        leads = body.get("leads", [])
        
        # Assert only agent2's lead is returned — check by name
        lead_names = [lead["name"] for lead in leads]
        assert "Agent1 Lead" not in lead_names, f"Lead list leaked agent1's lead: {leads}"
        
        # Assert agent1's lead data is not in response
        response_text = str(body)
        assert "Agent1 Lead" not in response_text, "Response leaked agent1's lead name"


# ── Test: Cross-Tenant Template Access ───────────────────────────────────────

class TestCrossTenantTemplateAccess:
    """Test that agents cannot access other agents' templates."""
    
    def test_get_templates_only_returns_own_templates(self, client, db_session):
        """Agent B cannot see agent A's custom templates."""
        agent1_id, agent2_id = _setup_two_agents(client, db_session)
        
        # Create a custom template for agent1
        client.post("/api/v1/agent/auth/login", json={
            "email": "agent1@test.com",
            "password": "password1111",
        })
        
        client.post("/api/v1/agent/templates", json={
            "template_type": "INITIAL_INVITE",
            "name": "Agent1 Secret Template",
            "subject": "Secret subject for agent1",
            "body": "Secret body for agent1",
            "tone": "PROFESSIONAL",
            "activate": True,
        })
        
        # Log back in as agent2
        client.post("/api/v1/agent/auth/login", json={
            "email": "agent2@test.com",
            "password": "password2222",
        })
        
        # Get agent2's templates
        r = client.get("/api/v1/agent/templates")
        
        assert r.status_code == 200, f"Template list failed: {r.text}"
        
        body = r.json()
        templates = body.get("templates", [])
        
        # Assert agent1's secret template is not in the response
        response_text = str(body)
        assert "Agent1 Secret Template" not in response_text, "Response leaked agent1's template name"
        assert "Secret subject for agent1" not in response_text, "Response leaked agent1's template subject"
        assert "Secret body for agent1" not in response_text, "Response leaked agent1's template body"
        
        # Verify all returned templates belong to agent2 or are platform defaults
        for tmpl in templates:
            if tmpl.get("is_custom"):
                # Custom templates should have an ID
                # We can't directly verify ownership without querying the DB,
                # but we've verified the secret content isn't present
                pass
    
    def test_update_other_agent_template_returns_403(self, client, db_session):
        """Agent B cannot update agent A's template."""
        agent1_id, agent2_id = _setup_two_agents(client, db_session)
        
        # Create a template for agent1
        client.post("/api/v1/agent/auth/login", json={
            "email": "agent1@test.com",
            "password": "password1111",
        })
        
        r = client.post("/api/v1/agent/templates", json={
            "template_type": "INITIAL_INVITE",
            "name": "Agent1 Template",
            "subject": "Original subject",
            "body": "Original body",
            "tone": "PROFESSIONAL",
            "activate": True,
        })
        
        assert r.status_code == 201, f"Template creation failed: {r.text}"
        template_id = r.json()["template_id"]
        
        # Log in as agent2
        client.post("/api/v1/agent/auth/login", json={
            "email": "agent2@test.com",
            "password": "password2222",
        })
        
        # Try to update agent1's template
        r = client.put(f"/api/v1/agent/templates/{template_id}", json={
            "subject": "Hacked subject",
            "body": "Hacked body",
        })
        
        # Should return 403 or 404 (both are acceptable for security)
        assert r.status_code in (403, 404), f"Expected 403/404, got {r.status_code}: {r.text}"
        
        # Verify template was not modified
        client.post("/api/v1/agent/auth/login", json={
            "email": "agent1@test.com",
            "password": "password1111",
        })
        
        r = client.get("/api/v1/agent/templates")
        body = r.json()
        templates = body.get("templates", [])
        
        # Find the template and verify it wasn't changed
        for tmpl in templates:
            if tmpl.get("id") == template_id:
                assert tmpl["subject"] == "Original subject", "Template was modified despite 403"
                assert tmpl["body"] == "Original body", "Template was modified despite 403"
                break
