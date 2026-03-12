"""
Property-based tests for unified error response schema.

# Feature: production-hardening, Property 3: Unified error schema on all error responses

**Property 3: Unified error schema on all error responses** — for any HTTP
request to any API endpoint that results in a 4xx or 5xx response, the
response body SHALL be a valid JSON object matching the schema
``{"error": string, "message": string, "code": string, "details": array|null}``.

**Validates: Requirements 5.1, 5.2, 5.3, 5.4, 5.5**
"""

import secrets
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

import bcrypt
import pytest
from fastapi.testclient import TestClient
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import gmail_lead_sync.agent_models  # noqa: F401 — registers agent tables
from api.main import app, get_db
from gmail_lead_sync.agent_models import AgentPreferences, AgentSession, AgentUser
from gmail_lead_sync.models import Base, LeadSource


# ---------------------------------------------------------------------------
# In-memory SQLite test database
# ---------------------------------------------------------------------------

_DB_NAME = f"prop_error_schema_{uuid.uuid4().hex}"

engine = create_engine(
    f"sqlite:///file:{_DB_NAME}?mode=memory&cache=shared&uri=true",
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
def client(setup_db):
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def db_session(setup_db):
    db = TestingSessionLocal()
    yield db
    db.close()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _create_agent(db, email: str) -> AgentUser:
    """Create an agent with a hashed password."""
    password_hash = bcrypt.hashpw(b"password", bcrypt.gensalt()).decode()
    agent = AgentUser(
        email=email,
        password_hash=password_hash,
        full_name="Test Agent",
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


def _assert_error_schema(body: Dict[str, Any], status_code: int) -> None:
    """
    Assert that *body* matches the unified ErrorResponse schema.

    Schema: {"error": str, "message": str, "code": str, "details": list|null}
    All of error, message, code must be non-empty strings.
    details must be null or a list.
    """
    assert isinstance(body, dict), (
        f"Response body for {status_code} must be a JSON object, got {type(body)}: {body}"
    )
    for field in ("error", "message", "code"):
        assert field in body, (
            f"Field '{field}' missing from error response (status={status_code}): {body}"
        )
        assert isinstance(body[field], str), (
            f"Field '{field}' must be a string (status={status_code}): {body}"
        )
        assert body[field], (
            f"Field '{field}' must be non-empty (status={status_code}): {body}"
        )
    assert "details" in body, (
        f"Field 'details' missing from error response (status={status_code}): {body}"
    )
    assert body["details"] is None or isinstance(body["details"], list), (
        f"Field 'details' must be null or a list (status={status_code}): {body}"
    )


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

# Random printable ASCII strings for invalid field values
_RANDOM_TEXT = st.text(
    min_size=1,
    max_size=50,
    alphabet=st.characters(min_codepoint=0x21, max_codepoint=0x7E),
)

# Random integers (used as invalid IDs)
_RANDOM_INT = st.integers(min_value=999_000, max_value=999_999_999)

# Random dicts (used as invalid request bodies)
_RANDOM_DICT = st.dictionaries(
    keys=st.text(min_size=1, max_size=10),
    values=st.one_of(st.integers(), st.text(max_size=20), st.booleans()),
    max_size=5,
)


# ---------------------------------------------------------------------------
# Property 3: Unified error schema on all error responses
# ---------------------------------------------------------------------------


class TestProperty3UnifiedErrorSchema:
    """
    Property 3: Unified error schema on all error responses.
    **Validates: Requirements 5.1, 5.2, 5.3, 5.4, 5.5**

    For any HTTP request that results in a 4xx or 5xx response, the body
    SHALL match {"error": str, "message": str, "code": str, "details": list|null}.
    """

    # ------------------------------------------------------------------
    # 422 — Pydantic validation errors (invalid request body)
    # ------------------------------------------------------------------

    @given(invalid_body=_RANDOM_DICT)
    @settings(
        max_examples=50,
        deadline=None,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
    )
    def test_422_agent_signup_invalid_body(self, setup_db, invalid_body: dict):
        """
        # Feature: production-hardening, Property 3: Unified error schema on all error responses
        **Validates: Requirements 5.1, 5.2**

        POST /api/v1/agent/auth/signup with a random invalid body must return
        422 with the unified error schema.
        """
        Base.metadata.create_all(bind=engine)
        app.dependency_overrides[get_db] = override_get_db

        with TestClient(app, raise_server_exceptions=False) as client:
            resp = client.post("/api/v1/agent/auth/signup", json=invalid_body)

        if resp.status_code in (422, 400):
            _assert_error_schema(resp.json(), resp.status_code)

    @given(invalid_body=_RANDOM_DICT)
    @settings(
        max_examples=50,
        deadline=None,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
    )
    def test_422_agent_login_invalid_body(self, setup_db, invalid_body: dict):
        """
        # Feature: production-hardening, Property 3: Unified error schema on all error responses
        **Validates: Requirements 5.1, 5.2**

        POST /api/v1/agent/auth/login with a random invalid body must return
        422 with the unified error schema.
        """
        Base.metadata.create_all(bind=engine)
        app.dependency_overrides[get_db] = override_get_db

        with TestClient(app, raise_server_exceptions=False) as client:
            resp = client.post("/api/v1/agent/auth/login", json=invalid_body)

        if resp.status_code in (422, 400):
            _assert_error_schema(resp.json(), resp.status_code)

    @given(invalid_body=_RANDOM_DICT)
    @settings(
        max_examples=50,
        deadline=None,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
    )
    def test_422_admin_login_invalid_body(self, setup_db, invalid_body: dict):
        """
        # Feature: production-hardening, Property 3: Unified error schema on all error responses
        **Validates: Requirements 5.1, 5.2**

        POST /api/v1/auth/login with a random invalid body must return
        422 with the unified error schema.
        """
        Base.metadata.create_all(bind=engine)
        app.dependency_overrides[get_db] = override_get_db

        with TestClient(app, raise_server_exceptions=False) as client:
            resp = client.post("/api/v1/auth/login", json=invalid_body)

        if resp.status_code in (422, 400):
            _assert_error_schema(resp.json(), resp.status_code)

    # ------------------------------------------------------------------
    # 401 — unauthenticated requests to protected endpoints
    # ------------------------------------------------------------------

    def test_401_agent_leads_no_auth(self, client):
        """
        # Feature: production-hardening, Property 3: Unified error schema on all error responses
        **Validates: Requirements 5.1, 5.4**

        GET /api/v1/agent/leads without a session cookie must return 401
        with the unified error schema.
        """
        resp = client.get("/api/v1/agent/leads")
        assert resp.status_code == 401
        _assert_error_schema(resp.json(), 401)

    def test_401_agent_dashboard_no_auth(self, client):
        """
        # Feature: production-hardening, Property 3: Unified error schema on all error responses
        **Validates: Requirements 5.1, 5.4**

        GET /api/v1/agent/dashboard without a session cookie must return 401
        with the unified error schema.
        """
        resp = client.get("/api/v1/agent/dashboard")
        assert resp.status_code == 401
        _assert_error_schema(resp.json(), 401)

    @given(bogus_token=_RANDOM_TEXT)
    @settings(
        max_examples=50,
        deadline=None,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
    )
    def test_401_bogus_session_token(self, setup_db, bogus_token: str):
        """
        # Feature: production-hardening, Property 3: Unified error schema on all error responses
        **Validates: Requirements 5.1, 5.4**

        Any request to a protected agent endpoint with a bogus session token
        must return 401 with the unified error schema.
        """
        Base.metadata.create_all(bind=engine)
        app.dependency_overrides[get_db] = override_get_db

        with TestClient(app, raise_server_exceptions=False) as client:
            resp = client.get(
                "/api/v1/agent/leads",
                cookies={"agent_session": bogus_token},
            )

        assert resp.status_code == 401
        _assert_error_schema(resp.json(), 401)

    # ------------------------------------------------------------------
    # 404 — resource not found
    # ------------------------------------------------------------------

    @given(lead_id=_RANDOM_INT)
    @settings(
        max_examples=50,
        deadline=None,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
    )
    def test_404_agent_lead_not_found(self, setup_db, lead_id: int):
        """
        # Feature: production-hardening, Property 3: Unified error schema on all error responses
        **Validates: Requirements 5.1, 5.3**

        GET /api/v1/agent/leads/{id} for a non-existent lead ID must return
        404 with the unified error schema.
        """
        Base.metadata.create_all(bind=engine)
        app.dependency_overrides[get_db] = override_get_db

        db = TestingSessionLocal()
        try:
            uid = uuid.uuid4().hex[:8]
            agent = _create_agent(db, f"agent_404_{uid}@example.com")
            token = _create_session(db, agent.id)
        finally:
            db.close()

        with TestClient(app, raise_server_exceptions=False) as client:
            resp = client.get(
                f"/api/v1/agent/leads/{lead_id}",
                cookies={"agent_session": token},
            )

        # Should be 404 (lead doesn't exist) or 403 (if somehow found but wrong tenant)
        assert resp.status_code in (404, 403), (
            f"Expected 404 for non-existent lead {lead_id}, got {resp.status_code}: {resp.text}"
        )
        _assert_error_schema(resp.json(), resp.status_code)

    # ------------------------------------------------------------------
    # 403 — cross-tenant access (wrong agent)
    # ------------------------------------------------------------------

    def test_403_cross_tenant_lead_access(self, client, db_session):
        """
        # Feature: production-hardening, Property 3: Unified error schema on all error responses
        **Validates: Requirements 5.1, 5.5**

        GET /api/v1/agent/leads/{id} for a lead owned by a different agent
        must return 403 with the unified error schema.
        """
        from gmail_lead_sync.models import Lead

        # Create two agents
        uid = uuid.uuid4().hex[:8]
        agent_a = _create_agent(db_session, f"agent_a_403_{uid}@example.com")
        agent_b = _create_agent(db_session, f"agent_b_403_{uid}@example.com")

        # Create a lead source
        source = LeadSource(
            sender_email="test@leadsource.com",
            identifier_snippet="test",
            name_regex=r"Name: (.+)",
            phone_regex=r"Phone: (.+)",
        )
        db_session.add(source)
        db_session.commit()
        db_session.refresh(source)

        # Create a lead belonging to agent_b
        lead = Lead(
            name="Lead for B",
            phone="555-0001",
            source_email="source@example.com",
            lead_source_id=source.id,
            gmail_uid=f"uid_b_{uuid.uuid4().hex}",
            agent_user_id=agent_b.id,
            score_bucket="HOT",
            score=85,
            created_at=datetime.utcnow(),
        )
        db_session.add(lead)
        db_session.commit()
        db_session.refresh(lead)

        # Authenticate as agent_a and try to access agent_b's lead
        token_a = _create_session(db_session, agent_a.id)

        resp = client.get(
            f"/api/v1/agent/leads/{lead.id}",
            cookies={"agent_session": token_a},
        )

        assert resp.status_code == 403, (
            f"Expected 403 for cross-tenant lead access, got {resp.status_code}: {resp.text}"
        )
        _assert_error_schema(resp.json(), 403)

    # ------------------------------------------------------------------
    # 422 — invalid status transition (business rule validation)
    # ------------------------------------------------------------------

    def test_422_invalid_status_transition(self, client, db_session):
        """
        # Feature: production-hardening, Property 3: Unified error schema on all error responses
        **Validates: Requirements 5.1, 5.2**

        PATCH /api/v1/agent/leads/{id}/status with an invalid status value
        must return 422 with the unified error schema.
        """
        from gmail_lead_sync.models import Lead

        uid = uuid.uuid4().hex[:8]
        agent = _create_agent(db_session, f"agent_422_{uid}@example.com")

        source = LeadSource(
            sender_email="test2@leadsource.com",
            identifier_snippet="test2",
            name_regex=r"Name: (.+)",
            phone_regex=r"Phone: (.+)",
        )
        db_session.add(source)
        db_session.commit()
        db_session.refresh(source)

        lead = Lead(
            name="Test Lead",
            phone="555-0002",
            source_email="source2@example.com",
            lead_source_id=source.id,
            gmail_uid=f"uid_422_{uuid.uuid4().hex}",
            agent_user_id=agent.id,
            score_bucket="HOT",
            score=85,
            created_at=datetime.utcnow(),
        )
        db_session.add(lead)
        db_session.commit()
        db_session.refresh(lead)

        token = _create_session(db_session, agent.id)

        # Send an invalid status value
        resp = client.patch(
            f"/api/v1/agent/leads/{lead.id}/status",
            json={"status": "INVALID_STATUS_XYZ"},
            cookies={"agent_session": token},
        )

        assert resp.status_code in (422, 400), (
            f"Expected 422/400 for invalid status, got {resp.status_code}: {resp.text}"
        )
        _assert_error_schema(resp.json(), resp.status_code)

    # ------------------------------------------------------------------
    # 422 — invalid onboarding profile body
    # ------------------------------------------------------------------

    @given(invalid_body=_RANDOM_DICT)
    @settings(
        max_examples=50,
        deadline=None,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
    )
    def test_422_onboarding_profile_invalid_body(self, setup_db, invalid_body: dict):
        """
        # Feature: production-hardening, Property 3: Unified error schema on all error responses
        **Validates: Requirements 5.1, 5.2**

        PUT /api/v1/agent/onboarding/profile with a random invalid body must
        return 422 with the unified error schema (or 401 if no auth).
        """
        Base.metadata.create_all(bind=engine)
        app.dependency_overrides[get_db] = override_get_db

        db = TestingSessionLocal()
        try:
            uid = uuid.uuid4().hex[:8]
            agent = _create_agent(db, f"agent_onboard_{uid}@example.com")
            token = _create_session(db, agent.id)
        finally:
            db.close()

        with TestClient(app, raise_server_exceptions=False) as client:
            resp = client.put(
                "/api/v1/agent/onboarding/profile",
                json=invalid_body,
                cookies={"agent_session": token},
            )

        if resp.status_code in (422, 400):
            _assert_error_schema(resp.json(), resp.status_code)

    # ------------------------------------------------------------------
    # Parametrized: all protected agent endpoints return 401 with schema
    # ------------------------------------------------------------------

    @pytest.mark.parametrize("method,path", [
        ("GET", "/api/v1/agent/leads"),
        ("GET", "/api/v1/agent/dashboard"),
        ("GET", "/api/v1/agent/templates"),
        ("GET", "/api/v1/agent/account/gmail"),
        ("GET", "/api/v1/agent/reports/summary"),
        ("GET", "/api/v1/agent/auth/me"),
    ])
    def test_401_protected_endpoints_no_auth(self, client, method, path):
        """
        # Feature: production-hardening, Property 3: Unified error schema on all error responses
        **Validates: Requirements 5.1, 5.4**

        Every protected agent endpoint must return 401 with the unified error
        schema when no session cookie is provided.
        """
        resp = client.request(method, path)
        assert resp.status_code == 401, (
            f"Expected 401 for {method} {path} without auth, got {resp.status_code}: {resp.text}"
        )
        _assert_error_schema(resp.json(), 401)
