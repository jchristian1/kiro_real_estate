"""
Unit tests for repository-level tenant scoping.

Verifies that LeadRepository and CredentialRepository enforce tenant
isolation at the query layer — not just at the route layer.

Requirements: 6.1, 6.4
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from gmail_lead_sync.agent_models import AgentUser  # noqa: F401 — registers agent tables
from gmail_lead_sync.models import Base, Credentials, LeadSource

from api.repositories.lead_repository import LeadCreate, LeadRepository, LeadUpdate
from api.repositories.credential_repository import (
    CredentialCreate,
    CredentialRepository,
    CredentialUpdate,
)


# ---------------------------------------------------------------------------
# In-memory SQLite engine (shared connection via StaticPool)
# ---------------------------------------------------------------------------

engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def reset_db():
    """Create all tables before each test and drop them after."""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def db():
    """Yield a database session and close it after the test."""
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def two_agents(db):
    """Create two AgentUser rows and return (agent_a, agent_b)."""
    agent_a = AgentUser(
        email="agent_a@example.com",
        password_hash="hashed_a",
        full_name="Agent A",
    )
    agent_b = AgentUser(
        email="agent_b@example.com",
        password_hash="hashed_b",
        full_name="Agent B",
    )
    db.add_all([agent_a, agent_b])
    db.commit()
    db.refresh(agent_a)
    db.refresh(agent_b)
    return agent_a, agent_b


@pytest.fixture()
def lead_source(db):
    """Create a minimal LeadSource row required by the Lead FK."""
    ls = LeadSource(
        sender_email="leads@test.com",
        identifier_snippet="Lead",
        name_regex=r"Name:\s*(.+)",
        phone_regex=r"Phone:\s*([\d-]+)",
    )
    db.add(ls)
    db.commit()
    db.refresh(ls)
    return ls


# ---------------------------------------------------------------------------
# LeadRepository — tenant scoping tests
# ---------------------------------------------------------------------------


class TestLeadRepositoryTenantScoping:
    """LeadRepository must filter by tenant_id on every read and write."""

    def test_get_by_id_returns_lead_for_correct_tenant(self, db, two_agents, lead_source):
        agent_a, _ = two_agents
        repo = LeadRepository(db)
        lead = repo.create(
            LeadCreate(
                name="Alice",
                phone="555-0001",
                source_email="leads@test.com",
                lead_source_id=lead_source.id,
                gmail_uid="uid-001",
            ),
            tenant_id=agent_a.id,
        )

        result = repo.get_by_id(lead.id, tenant_id=agent_a.id)

        assert result is not None
        assert result.id == lead.id

    def test_get_by_id_returns_none_for_wrong_tenant(self, db, two_agents, lead_source):
        agent_a, agent_b = two_agents
        repo = LeadRepository(db)
        lead = repo.create(
            LeadCreate(
                name="Alice",
                phone="555-0001",
                source_email="leads@test.com",
                lead_source_id=lead_source.id,
                gmail_uid="uid-002",
            ),
            tenant_id=agent_a.id,
        )

        result = repo.get_by_id(lead.id, tenant_id=agent_b.id)

        assert result is None

    def test_list_for_tenant_returns_own_leads(self, db, two_agents, lead_source):
        agent_a, _ = two_agents
        repo = LeadRepository(db)
        repo.create(
            LeadCreate(
                name="Alice",
                phone="555-0001",
                source_email="leads@test.com",
                lead_source_id=lead_source.id,
                gmail_uid="uid-003",
            ),
            tenant_id=agent_a.id,
        )

        results = repo.list_for_tenant(tenant_id=agent_a.id)

        assert len(results) == 1
        assert results[0].agent_user_id == agent_a.id

    def test_list_for_tenant_excludes_other_tenant_leads(self, db, two_agents, lead_source):
        agent_a, agent_b = two_agents
        repo = LeadRepository(db)
        repo.create(
            LeadCreate(
                name="Alice",
                phone="555-0001",
                source_email="leads@test.com",
                lead_source_id=lead_source.id,
                gmail_uid="uid-004",
            ),
            tenant_id=agent_a.id,
        )

        results = repo.list_for_tenant(tenant_id=agent_b.id)

        assert results == []

    def test_update_returns_none_for_wrong_tenant(self, db, two_agents, lead_source):
        agent_a, agent_b = two_agents
        repo = LeadRepository(db)
        lead = repo.create(
            LeadCreate(
                name="Alice",
                phone="555-0001",
                source_email="leads@test.com",
                lead_source_id=lead_source.id,
                gmail_uid="uid-005",
            ),
            tenant_id=agent_a.id,
        )

        result = repo.update(lead.id, tenant_id=agent_b.id, data=LeadUpdate(name="Hacked"))

        assert result is None

    def test_update_does_not_modify_lead_on_wrong_tenant(self, db, two_agents, lead_source):
        agent_a, agent_b = two_agents
        repo = LeadRepository(db)
        lead = repo.create(
            LeadCreate(
                name="Alice",
                phone="555-0001",
                source_email="leads@test.com",
                lead_source_id=lead_source.id,
                gmail_uid="uid-006",
            ),
            tenant_id=agent_a.id,
        )

        repo.update(lead.id, tenant_id=agent_b.id, data=LeadUpdate(name="Hacked"))

        # Verify the original lead is unchanged
        unchanged = repo.get_by_id(lead.id, tenant_id=agent_a.id)
        assert unchanged is not None
        assert unchanged.name == "Alice"


# ---------------------------------------------------------------------------
# CredentialRepository — tenant scoping tests
# ---------------------------------------------------------------------------


class TestCredentialRepositoryTenantScoping:
    """CredentialRepository must scope every operation to the owning agent_id."""

    def _create_creds_for(self, db, agent_id: str) -> Credentials:
        repo = CredentialRepository(db)
        return repo.create(
            CredentialCreate(
                email_encrypted="enc_email_a",
                app_password_encrypted="enc_pass_a",
            ),
            agent_id=agent_id,
        )

    def test_get_by_agent_id_returns_own_credentials(self, db):
        self._create_creds_for(db, "agent-001")
        repo = CredentialRepository(db)

        result = repo.get_by_agent_id("agent-001")

        assert result is not None
        assert result.agent_id == "agent-001"

    def test_get_by_agent_id_returns_none_for_other_agent(self, db):
        self._create_creds_for(db, "agent-001")
        repo = CredentialRepository(db)

        result = repo.get_by_agent_id("agent-002")

        assert result is None

    def test_update_returns_none_for_agent_without_credentials(self, db):
        self._create_creds_for(db, "agent-001")
        repo = CredentialRepository(db)

        result = repo.update("agent-002", CredentialUpdate(display_name="Hacked"))

        assert result is None

    def test_update_does_not_modify_other_agents_credentials(self, db):
        self._create_creds_for(db, "agent-001")
        repo = CredentialRepository(db)

        repo.update("agent-002", CredentialUpdate(email_encrypted="hacked"))

        # agent-001's record must be untouched
        original = repo.get_by_agent_id("agent-001")
        assert original is not None
        assert original.email_encrypted == "enc_email_a"

    def test_delete_returns_false_for_agent_without_credentials(self, db):
        self._create_creds_for(db, "agent-001")
        repo = CredentialRepository(db)

        result = repo.delete("agent-002")

        assert result is False

    def test_delete_does_not_remove_other_agents_credentials(self, db):
        self._create_creds_for(db, "agent-001")
        repo = CredentialRepository(db)

        repo.delete("agent-002")

        # agent-001's record must still exist
        still_there = repo.get_by_agent_id("agent-001")
        assert still_there is not None
