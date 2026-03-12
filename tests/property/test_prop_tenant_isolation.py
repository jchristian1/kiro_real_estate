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


# ---------------------------------------------------------------------------
# Property 4: Tenant Isolation — Repository Layer
# ---------------------------------------------------------------------------


class TestProperty4TenantIsolationRepositoryLayer:
    """
    Property 4: Tenant Isolation — Repository Layer
    **Validates: Requirements 6.1, 6.2, 6.3, 6.4**

    For any repository method that queries tenant-scoped resources, the method
    must filter by tenant_id and return None or empty results when queried
    with a mismatched tenant_id.
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
    def test_lead_repository_get_by_id_enforces_tenant_scoping(
        self, setup_db, n_leads_a: int, n_leads_b: int
    ):
        """
        Property 4: Tenant Isolation — LeadRepository.get_by_id
        **Validates: Requirements 6.1, 6.2**

        For any lead belonging to agent_b, calling get_by_id with agent_a's
        tenant_id must return None.
        """
        from api.repositories.lead_repository import LeadRepository

        TestingSessionLocal = setup_db
        db = TestingSessionLocal()
        try:
            uid = uuid.uuid4().hex[:8]
            agent_a = _create_agent(db, f"repo_lead_a_{uid}@example.com")
            agent_b = _create_agent(db, f"repo_lead_b_{uid}@example.com")

            # Create leads for both agents
            leads_a = [_create_lead(db, agent_a.id, i) for i in range(n_leads_a)]
            leads_b = [_create_lead(db, agent_b.id, i) for i in range(n_leads_b)]

            repo = LeadRepository(db)

            # Verify agent_a can access their own leads
            for lead in leads_a:
                result = repo.get_by_id(lead.id, agent_a.id)
                assert result is not None, f"Agent A should access their own lead {lead.id}"
                assert result.id == lead.id

            # Verify agent_a CANNOT access agent_b's leads
            for lead in leads_b:
                result = repo.get_by_id(lead.id, agent_a.id)
                assert result is None, (
                    f"Cross-tenant leak: agent_a accessed agent_b's lead {lead.id}"
                )

            # Verify agent_b can access their own leads
            for lead in leads_b:
                result = repo.get_by_id(lead.id, agent_b.id)
                assert result is not None, f"Agent B should access their own lead {lead.id}"
                assert result.id == lead.id

            # Verify agent_b CANNOT access agent_a's leads
            for lead in leads_a:
                result = repo.get_by_id(lead.id, agent_b.id)
                assert result is None, (
                    f"Cross-tenant leak: agent_b accessed agent_a's lead {lead.id}"
                )
        finally:
            db.close()

    @given(
        n_leads_a=st.integers(min_value=1, max_value=5),
        n_leads_b=st.integers(min_value=1, max_value=5),
    )
    @settings(
        max_examples=20,
        deadline=None,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
    )
    def test_lead_repository_list_for_tenant_enforces_tenant_scoping(
        self, setup_db, n_leads_a: int, n_leads_b: int
    ):
        """
        Property 4: Tenant Isolation — LeadRepository.list_for_tenant
        **Validates: Requirements 6.1, 6.2**

        For any leads belonging to agent_a and agent_b, calling list_for_tenant
        with agent_a's tenant_id must return only agent_a's leads.
        """
        from api.repositories.lead_repository import LeadRepository

        TestingSessionLocal = setup_db
        db = TestingSessionLocal()
        try:
            uid = uuid.uuid4().hex[:8]
            agent_a = _create_agent(db, f"repo_list_a_{uid}@example.com")
            agent_b = _create_agent(db, f"repo_list_b_{uid}@example.com")

            # Create leads for both agents
            leads_a_ids = {_create_lead(db, agent_a.id, i).id for i in range(n_leads_a)}
            leads_b_ids = {_create_lead(db, agent_b.id, i).id for i in range(n_leads_b)}

            repo = LeadRepository(db)

            # Query agent_a's leads
            results_a = repo.list_for_tenant(agent_a.id, skip=0, limit=100)
            returned_ids_a = {lead.id for lead in results_a}

            # All returned leads must belong to agent_a
            assert returned_ids_a == leads_a_ids, (
                f"Agent A list mismatch: expected {leads_a_ids}, got {returned_ids_a}"
            )

            # No agent_b leads should appear
            cross_tenant_a = returned_ids_a & leads_b_ids
            assert not cross_tenant_a, (
                f"Cross-tenant leak: agent_b leads {cross_tenant_a} in agent_a's list"
            )

            # Query agent_b's leads
            results_b = repo.list_for_tenant(agent_b.id, skip=0, limit=100)
            returned_ids_b = {lead.id for lead in results_b}

            # All returned leads must belong to agent_b
            assert returned_ids_b == leads_b_ids, (
                f"Agent B list mismatch: expected {leads_b_ids}, got {returned_ids_b}"
            )

            # No agent_a leads should appear
            cross_tenant_b = returned_ids_b & leads_a_ids
            assert not cross_tenant_b, (
                f"Cross-tenant leak: agent_a leads {cross_tenant_b} in agent_b's list"
            )
        finally:
            db.close()

    @given(n_agents=st.integers(min_value=2, max_value=4))
    @settings(
        max_examples=15,
        deadline=None,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
    )
    def test_credential_repository_get_by_agent_id_enforces_tenant_scoping(
        self, setup_db, n_agents: int
    ):
        """
        Property 4: Tenant Isolation — CredentialRepository.get_by_agent_id
        **Validates: Requirements 6.4**

        For any credentials belonging to different agents, calling get_by_agent_id
        with one agent's ID must return only that agent's credentials.
        """
        from api.repositories.credential_repository import CredentialRepository, CredentialCreate

        TestingSessionLocal = setup_db
        db = TestingSessionLocal()
        try:
            uid = uuid.uuid4().hex[:8]
            agents = [
                _create_agent(db, f"repo_cred_{i}_{uid}@example.com")
                for i in range(n_agents)
            ]

            repo = CredentialRepository(db)

            # Create credentials for each agent
            for agent in agents:
                cred_data = CredentialCreate(
                    email_encrypted=f"encrypted_email_{agent.id}",
                    app_password_encrypted=f"encrypted_pass_{agent.id}",
                )
                repo.create(cred_data, f"agent_{agent.id}")

            # Verify each agent can only access their own credentials
            for agent in agents:
                result = repo.get_by_agent_id(f"agent_{agent.id}")
                assert result is not None, f"Agent {agent.id} should access their credentials"
                assert result.agent_id == f"agent_{agent.id}"
                assert result.email_encrypted == f"encrypted_email_{agent.id}"

                # Verify this agent cannot access other agents' credentials
                for other_agent in agents:
                    if other_agent.id != agent.id:
                        other_result = repo.get_by_agent_id(f"agent_{other_agent.id}")
                        # The query should return the OTHER agent's creds, not this agent's
                        if other_result is not None:
                            assert other_result.agent_id != f"agent_{agent.id}", (
                                f"Cross-tenant leak: agent {agent.id} accessed "
                                f"agent {other_agent.id}'s credentials"
                            )
        finally:
            db.close()

    @given(
        n_templates_a=st.integers(min_value=1, max_value=3),
        n_templates_b=st.integers(min_value=1, max_value=3),
    )
    @settings(
        max_examples=15,
        deadline=None,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
    )
    def test_template_repository_enforces_tenant_scoping(
        self, setup_db, n_templates_a: int, n_templates_b: int
    ):
        """
        Property 4: Tenant Isolation — TemplateRepository methods
        **Validates: Requirements 6.1, 6.2**

        For any templates belonging to agent_a and agent_b, repository methods
        must enforce tenant scoping and return None or empty results for
        cross-tenant access.
        """
        from api.repositories.template_repository import TemplateRepository, TemplateCreate

        TestingSessionLocal = setup_db
        db = TestingSessionLocal()
        try:
            uid = uuid.uuid4().hex[:8]
            agent_a = _create_agent(db, f"repo_tmpl_a_{uid}@example.com")
            agent_b = _create_agent(db, f"repo_tmpl_b_{uid}@example.com")

            repo = TemplateRepository(db)

            # Create templates for both agents
            templates_a = []
            for i in range(n_templates_a):
                tmpl_data = TemplateCreate(
                    template_type="INITIAL_INVITE",
                    name=f"Template A{i}",
                    subject=f"Subject A{i}",
                    body=f"Body A{i}",
                )
                tmpl = repo.create(agent_a.id, tmpl_data)
                templates_a.append(tmpl)

            templates_b = []
            for i in range(n_templates_b):
                tmpl_data = TemplateCreate(
                    template_type="INITIAL_INVITE",
                    name=f"Template B{i}",
                    subject=f"Subject B{i}",
                    body=f"Body B{i}",
                )
                tmpl = repo.create(agent_b.id, tmpl_data)
                templates_b.append(tmpl)

            # Test list_for_agent
            list_a = repo.list_for_agent(agent_a.id)
            list_a_ids = {t.id for t in list_a}
            expected_a_ids = {t.id for t in templates_a}
            assert list_a_ids == expected_a_ids, (
                f"Agent A template list mismatch: expected {expected_a_ids}, got {list_a_ids}"
            )

            list_b = repo.list_for_agent(agent_b.id)
            list_b_ids = {t.id for t in list_b}
            expected_b_ids = {t.id for t in templates_b}
            assert list_b_ids == expected_b_ids, (
                f"Agent B template list mismatch: expected {expected_b_ids}, got {list_b_ids}"
            )

            # Test get_by_id with cross-tenant access
            for tmpl_b in templates_b:
                result = repo.get_by_id(tmpl_b.id, agent_a.id)
                assert result is None, (
                    f"Cross-tenant leak: agent_a accessed agent_b's template {tmpl_b.id}"
                )

            for tmpl_a in templates_a:
                result = repo.get_by_id(tmpl_a.id, agent_b.id)
                assert result is None, (
                    f"Cross-tenant leak: agent_b accessed agent_a's template {tmpl_a.id}"
                )
        finally:
            db.close()

    @given(n_agents=st.integers(min_value=2, max_value=4))
    @settings(
        max_examples=15,
        deadline=None,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
    )
    def test_watcher_repository_enforces_tenant_scoping(
        self, setup_db, n_agents: int
    ):
        """
        Property 4: Tenant Isolation — WatcherRepository.get_config_by_agent_id
        **Validates: Requirements 6.3, 6.4**

        For any watcher configs belonging to different agents, calling
        get_config_by_agent_id with one agent's ID must return only that
        agent's config.
        """
        from api.repositories.watcher_repository import WatcherRepository, WatcherConfigUpdate

        TestingSessionLocal = setup_db
        db = TestingSessionLocal()
        try:
            uid = uuid.uuid4().hex[:8]
            agents = [
                _create_agent(db, f"repo_watch_{i}_{uid}@example.com")
                for i in range(n_agents)
            ]

            repo = WatcherRepository(db)

            # Create watcher configs for each agent
            for agent in agents:
                config_data = WatcherConfigUpdate(
                    watcher_enabled=True,
                    watcher_admin_override=False,
                )
                repo.upsert_config(agent.id, config_data)

            # Verify each agent can only access their own config
            for agent in agents:
                result = repo.get_config_by_agent_id(agent.id)
                assert result is not None, f"Agent {agent.id} should access their config"
                assert result.agent_user_id == agent.id

                # Verify querying with another agent's ID returns that agent's config, not this one
                for other_agent in agents:
                    if other_agent.id != agent.id:
                        other_result = repo.get_config_by_agent_id(other_agent.id)
                        if other_result is not None:
                            assert other_result.agent_user_id == other_agent.id, (
                                f"Config query returned wrong agent: expected {other_agent.id}, "
                                f"got {other_result.agent_user_id}"
                            )
        finally:
            db.close()

    @given(
        n_forms_a=st.integers(min_value=1, max_value=3),
        n_forms_b=st.integers(min_value=1, max_value=3),
    )
    @settings(
        max_examples=15,
        deadline=None,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
    )
    def test_form_template_repository_enforces_tenant_scoping(
        self, setup_db, n_forms_a: int, n_forms_b: int
    ):
        """
        Property 4: Tenant Isolation — FormTemplateRepository methods
        **Validates: Requirements 6.1, 6.2**

        For any form templates belonging to tenant_a and tenant_b, repository
        methods must enforce tenant scoping.
        """
        from api.repositories.buyer_leads_repository import FormTemplateRepository

        TestingSessionLocal = setup_db
        db = TestingSessionLocal()
        try:
            uid = uuid.uuid4().hex[:8]
            agent_a = _create_agent(db, f"repo_form_a_{uid}@example.com")
            agent_b = _create_agent(db, f"repo_form_b_{uid}@example.com")

            repo = FormTemplateRepository(db)

            # Create form templates for both tenants
            forms_a = []
            for i in range(n_forms_a):
                form = repo.create(agent_a.id, "BUYER_PREAPPROVAL", f"Form A{i}")
                forms_a.append(form)

            forms_b = []
            for i in range(n_forms_b):
                form = repo.create(agent_b.id, "BUYER_PREAPPROVAL", f"Form B{i}")
                forms_b.append(form)

            # Test list_for_tenant
            list_a = repo.list_for_tenant(agent_a.id)
            list_a_ids = {f.id for f in list_a}
            expected_a_ids = {f.id for f in forms_a}
            assert list_a_ids == expected_a_ids, (
                f"Tenant A form list mismatch: expected {expected_a_ids}, got {list_a_ids}"
            )

            list_b = repo.list_for_tenant(agent_b.id)
            list_b_ids = {f.id for f in list_b}
            expected_b_ids = {f.id for f in forms_b}
            assert list_b_ids == expected_b_ids, (
                f"Tenant B form list mismatch: expected {expected_b_ids}, got {list_b_ids}"
            )

            # Test get_by_id with cross-tenant access
            for form_b in forms_b:
                result = repo.get_by_id(form_b.id, agent_a.id)
                assert result is None, (
                    f"Cross-tenant leak: tenant_a accessed tenant_b's form {form_b.id}"
                )

            for form_a in forms_a:
                result = repo.get_by_id(form_a.id, agent_b.id)
                assert result is None, (
                    f"Cross-tenant leak: tenant_b accessed tenant_a's form {form_a.id}"
                )
        finally:
            db.close()

    @given(
        n_configs_a=st.integers(min_value=1, max_value=3),
        n_configs_b=st.integers(min_value=1, max_value=3),
    )
    @settings(
        max_examples=15,
        deadline=None,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
    )
    def test_scoring_config_repository_enforces_tenant_scoping(
        self, setup_db, n_configs_a: int, n_configs_b: int
    ):
        """
        Property 4: Tenant Isolation — ScoringConfigRepository methods
        **Validates: Requirements 6.1, 6.2**

        For any scoring configs belonging to tenant_a and tenant_b, repository
        methods must enforce tenant scoping.
        """
        from api.repositories.buyer_leads_repository import ScoringConfigRepository

        TestingSessionLocal = setup_db
        db = TestingSessionLocal()
        try:
            uid = uuid.uuid4().hex[:8]
            agent_a = _create_agent(db, f"repo_score_a_{uid}@example.com")
            agent_b = _create_agent(db, f"repo_score_b_{uid}@example.com")

            repo = ScoringConfigRepository(db)

            # Create scoring configs for both tenants
            configs_a = []
            for i in range(n_configs_a):
                config = repo.create(agent_a.id, "BUYER_PREAPPROVAL", f"Config A{i}")
                configs_a.append(config)

            configs_b = []
            for i in range(n_configs_b):
                config = repo.create(agent_b.id, "BUYER_PREAPPROVAL", f"Config B{i}")
                configs_b.append(config)

            # Test list_for_tenant
            list_a = repo.list_for_tenant(agent_a.id)
            list_a_ids = {c.id for c in list_a}
            expected_a_ids = {c.id for c in configs_a}
            assert list_a_ids == expected_a_ids, (
                f"Tenant A config list mismatch: expected {expected_a_ids}, got {list_a_ids}"
            )

            list_b = repo.list_for_tenant(agent_b.id)
            list_b_ids = {c.id for c in list_b}
            expected_b_ids = {c.id for c in configs_b}
            assert list_b_ids == expected_b_ids, (
                f"Tenant B config list mismatch: expected {expected_b_ids}, got {list_b_ids}"
            )

            # Test get_by_id with cross-tenant access
            for config_b in configs_b:
                result = repo.get_by_id(config_b.id, agent_a.id)
                assert result is None, (
                    f"Cross-tenant leak: tenant_a accessed tenant_b's config {config_b.id}"
                )

            for config_a in configs_a:
                result = repo.get_by_id(config_a.id, agent_b.id)
                assert result is None, (
                    f"Cross-tenant leak: tenant_b accessed tenant_a's config {config_a.id}"
                )
        finally:
            db.close()

    @given(
        n_templates_a=st.integers(min_value=1, max_value=3),
        n_templates_b=st.integers(min_value=1, max_value=3),
    )
    @settings(
        max_examples=15,
        deadline=None,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
    )
    def test_message_template_repository_enforces_tenant_scoping(
        self, setup_db, n_templates_a: int, n_templates_b: int
    ):
        """
        Property 4: Tenant Isolation — MessageTemplateRepository methods
        **Validates: Requirements 6.1, 6.2**

        For any message templates belonging to tenant_a and tenant_b, repository
        methods must enforce tenant scoping.
        """
        from api.repositories.buyer_leads_repository import MessageTemplateRepository

        TestingSessionLocal = setup_db
        db = TestingSessionLocal()
        try:
            uid = uuid.uuid4().hex[:8]
            agent_a = _create_agent(db, f"repo_msg_a_{uid}@example.com")
            agent_b = _create_agent(db, f"repo_msg_b_{uid}@example.com")

            repo = MessageTemplateRepository(db)

            # Create message templates for both tenants
            templates_a = []
            for i in range(n_templates_a):
                tmpl = repo.create(agent_a.id, "BUYER_PREAPPROVAL", f"msg_key_a{i}")
                templates_a.append(tmpl)

            templates_b = []
            for i in range(n_templates_b):
                tmpl = repo.create(agent_b.id, "BUYER_PREAPPROVAL", f"msg_key_b{i}")
                templates_b.append(tmpl)

            # Test list_for_tenant
            list_a = repo.list_for_tenant(agent_a.id)
            list_a_ids = {t.id for t in list_a}
            expected_a_ids = {t.id for t in templates_a}
            assert list_a_ids == expected_a_ids, (
                f"Tenant A message template list mismatch: expected {expected_a_ids}, got {list_a_ids}"
            )

            list_b = repo.list_for_tenant(agent_b.id)
            list_b_ids = {t.id for t in list_b}
            expected_b_ids = {t.id for t in templates_b}
            assert list_b_ids == expected_b_ids, (
                f"Tenant B message template list mismatch: expected {expected_b_ids}, got {list_b_ids}"
            )

            # Test get_by_id with cross-tenant access
            for tmpl_b in templates_b:
                result = repo.get_by_id(tmpl_b.id, agent_a.id)
                assert result is None, (
                    f"Cross-tenant leak: tenant_a accessed tenant_b's message template {tmpl_b.id}"
                )

            for tmpl_a in templates_a:
                result = repo.get_by_id(tmpl_a.id, agent_b.id)
                assert result is None, (
                    f"Cross-tenant leak: tenant_b accessed tenant_a's message template {tmpl_a.id}"
                )
        finally:
            db.close()
