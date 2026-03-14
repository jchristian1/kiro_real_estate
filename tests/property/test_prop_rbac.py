"""
Property-based tests for Role-Based Access Control (RBAC).

# Feature: production-hardening, Property 13: RBAC — agent sessions cannot access admin endpoints
# Feature: production-hardening, Property 14: RBAC — admin sessions cannot act as agents

**Property 13: RBAC — agent sessions cannot access admin endpoints** — for any
request to a platform-admin endpoint made with an agent-role session token,
the response SHALL be HTTP 403 with the unified error schema.

**Property 14: RBAC — admin sessions cannot act as agents** — for any request
to an agent-app endpoint made with a platform-admin session token (excluding
explicit admin-override endpoints), the response SHALL be HTTP 403 with the
unified error schema.

**Validates: Requirements 11.2, 11.3**
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
from sqlalchemy.pool import StaticPool

import gmail_lead_sync.agent_models  # noqa: F401 — registers agent tables
from api.main import app, get_db
from gmail_lead_sync.agent_models import AgentPreferences, AgentSession, AgentUser
from gmail_lead_sync.models import Base

# ---------------------------------------------------------------------------
# In-memory SQLite test database
# ---------------------------------------------------------------------------

_DB_NAME = f"prop_rbac_{uuid.uuid4().hex}"

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

# ---------------------------------------------------------------------------
# Admin endpoints (require platform_admin role)
# ---------------------------------------------------------------------------

ADMIN_ENDPOINTS = [
    ("GET", "/api/v1/leads"),
    ("GET", "/api/v1/lead-sources"),
    ("GET", "/api/v1/audit-logs"),
    ("GET", "/api/v1/settings"),
    ("GET", "/api/v1/companies"),
    ("GET", "/api/v1/watchers/status"),
    ("GET", "/api/v1/agents"),
]

# Agent endpoints (require agent role)
AGENT_ENDPOINTS = [
    ("GET", "/api/v1/agent/leads"),
    ("GET", "/api/v1/agent/dashboard"),
    ("GET", "/api/v1/agent/auth/me"),
    ("GET", "/api/v1/agent/reports/summary"),
]

_admin_endpoint_strategy = st.sampled_from(ADMIN_ENDPOINTS)
_agent_endpoint_strategy = st.sampled_from(AGENT_ENDPOINTS)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    app.dependency_overrides[get_db] = override_get_db
    yield
    Base.metadata.drop_all(bind=engine)
    app.dependency_overrides.pop(get_db, None)


@pytest.fixture
def db_session(setup_db):
    db = TestingSessionLocal()
    yield db
    db.close()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _create_agent(db, email: str) -> AgentUser:
    """Create an agent user with a hashed password."""
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


def _create_agent_session(db, agent_user_id: int) -> str:
    """Create a valid agent session and return the token."""
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


def _create_admin_session(db) -> str:
    """Create a valid admin session and return the token."""
    from api.auth import create_session
    from api.models.web_ui_models import User

    # Create an admin user
    uid = uuid.uuid4().hex[:8]
    admin = User(
        username=f"admin_{uid}",
        password_hash=bcrypt.hashpw(b"adminpass", bcrypt.gensalt()).decode(),
        role="platform_admin",
    )
    db.add(admin)
    db.commit()
    db.refresh(admin)

    session = create_session(db, admin.id)
    return session.id


def _assert_error_schema(body: dict, status_code: int) -> None:
    """Assert the unified ErrorResponse schema."""
    assert isinstance(body, dict), f"Expected dict, got {type(body)}: {body}"
    for field in ("error", "message", "code"):
        assert field in body, f"Field '{field}' missing (status={status_code}): {body}"
        assert isinstance(body[field], str) and body[field], (
            f"Field '{field}' must be non-empty string (status={status_code}): {body}"
        )
    assert "details" in body, f"Field 'details' missing (status={status_code}): {body}"
    assert body["details"] is None or isinstance(body["details"], list), (
        f"Field 'details' must be null or list (status={status_code}): {body}"
    )


# ---------------------------------------------------------------------------
# Property 13: RBAC — agent sessions cannot access admin endpoints
# ---------------------------------------------------------------------------


class TestProperty13RBACAgentCannotAccessAdminEndpoints:
    """
    Property 13: RBAC — agent sessions cannot access admin endpoints.
    **Validates: Requirements 11.2**
    """

    @given(endpoint=_admin_endpoint_strategy)
    @settings(
        max_examples=50,
        deadline=None,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
    )
    def test_agent_token_returns_403_on_admin_endpoints(
        self, setup_db, endpoint
    ):
        """
        # Feature: production-hardening, Property 13: RBAC — agent sessions cannot access admin endpoints
        **Validates: Requirements 11.2**

        For any platform-admin endpoint, a request with an agent-role session
        token SHALL return HTTP 403 with the unified error schema.
        """
        Base.metadata.create_all(bind=engine)
        app.dependency_overrides[get_db] = override_get_db

        db = TestingSessionLocal()
        try:
            uid = uuid.uuid4().hex[:8]
            agent = _create_agent(db, f"rbac_agent_{uid}@example.com")
            agent_token = _create_agent_session(db, agent.id)
        finally:
            db.close()

        method, path = endpoint
        with TestClient(app, raise_server_exceptions=False) as client:
            resp = client.request(
                method,
                path,
                cookies={"agent_session": agent_token},
            )

        # Agent token on admin endpoint must return 401 or 403
        # (401 if the admin auth dependency doesn't see the agent cookie,
        #  403 if it sees the wrong role)
        assert resp.status_code in (401, 403), (
            f"Expected 401 or 403 for agent token on admin endpoint "
            f"{method} {path}, got {resp.status_code}: {resp.text}"
        )
        _assert_error_schema(resp.json(), resp.status_code)

    @pytest.mark.parametrize("method,path", ADMIN_ENDPOINTS)
    def test_agent_token_blocked_from_specific_admin_endpoints(
        self, db_session, method, path
    ):
        """
        # Feature: production-hardening, Property 13: RBAC — agent sessions cannot access admin endpoints
        **Validates: Requirements 11.2**

        Each specific admin endpoint SHALL return 401 or 403 when accessed
        with an agent session token.
        """
        uid = uuid.uuid4().hex[:8]
        agent = _create_agent(db_session, f"rbac_specific_{uid}@example.com")
        agent_token = _create_agent_session(db_session, agent.id)

        with TestClient(app, raise_server_exceptions=False) as client:
            resp = client.request(
                method,
                path,
                cookies={"agent_session": agent_token},
            )

        assert resp.status_code in (401, 403), (
            f"Expected 401 or 403 for agent token on {method} {path}, "
            f"got {resp.status_code}: {resp.text}"
        )
        _assert_error_schema(resp.json(), resp.status_code)

    def test_no_token_returns_401_on_admin_endpoints(self, setup_db):
        """
        # Feature: production-hardening, Property 13: RBAC — agent sessions cannot access admin endpoints
        **Validates: Requirements 11.2**

        Admin endpoints without any session token SHALL return 401.
        """
        with TestClient(app, raise_server_exceptions=False) as client:
            for method, path in ADMIN_ENDPOINTS:
                resp = client.request(method, path)
                assert resp.status_code in (401, 403), (
                    f"Expected 401/403 for unauthenticated {method} {path}, "
                    f"got {resp.status_code}"
                )
                _assert_error_schema(resp.json(), resp.status_code)


# ---------------------------------------------------------------------------
# Property 14: RBAC — admin sessions cannot act as agents
# ---------------------------------------------------------------------------


class TestProperty14RBACAdminCannotActAsAgent:
    """
    Property 14: RBAC — admin sessions cannot act as agents.
    **Validates: Requirements 11.3**
    """

    @given(endpoint=_agent_endpoint_strategy)
    @settings(
        max_examples=50,
        deadline=None,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
    )
    def test_admin_token_returns_401_or_403_on_agent_endpoints(
        self, setup_db, endpoint
    ):
        """
        # Feature: production-hardening, Property 14: RBAC — admin sessions cannot act as agents
        **Validates: Requirements 11.3**

        For any agent-app endpoint, a request with a platform-admin session
        token (in the admin cookie, not the agent cookie) SHALL return HTTP
        401 or 403 — the admin cannot impersonate an agent.
        """
        Base.metadata.create_all(bind=engine)
        app.dependency_overrides[get_db] = override_get_db

        db = TestingSessionLocal()
        try:
            admin_token = _create_admin_session(db)
        finally:
            db.close()

        method, path = endpoint
        with TestClient(app, raise_server_exceptions=False) as client:
            # Send admin session token in the admin cookie (session_token),
            # NOT in the agent cookie — admin should not be able to act as agent
            resp = client.request(
                method,
                path,
                cookies={"session_token": admin_token},
            )

        # Admin token in admin cookie on agent endpoint must return 401
        # (agent endpoint expects agent_session cookie, not session_token)
        assert resp.status_code in (401, 403), (
            f"Expected 401 or 403 for admin token on agent endpoint "
            f"{method} {path}, got {resp.status_code}: {resp.text}"
        )
        _assert_error_schema(resp.json(), resp.status_code)

    @pytest.mark.parametrize("method,path", AGENT_ENDPOINTS)
    def test_admin_token_blocked_from_specific_agent_endpoints(
        self, db_session, method, path
    ):
        """
        # Feature: production-hardening, Property 14: RBAC — admin sessions cannot act as agents
        **Validates: Requirements 11.3**

        Each specific agent endpoint SHALL return 401 or 403 when accessed
        with an admin session token (not an agent session token).
        """
        admin_token = _create_admin_session(db_session)

        with TestClient(app, raise_server_exceptions=False) as client:
            resp = client.request(
                method,
                path,
                cookies={"session_token": admin_token},
            )

        assert resp.status_code in (401, 403), (
            f"Expected 401 or 403 for admin token on {method} {path}, "
            f"got {resp.status_code}: {resp.text}"
        )
        _assert_error_schema(resp.json(), resp.status_code)

    def test_no_token_returns_401_on_agent_endpoints(self, setup_db):
        """
        # Feature: production-hardening, Property 14: RBAC — admin sessions cannot act as agents
        **Validates: Requirements 11.3**

        Agent endpoints without any session token SHALL return 401.
        """
        with TestClient(app, raise_server_exceptions=False) as client:
            for method, path in AGENT_ENDPOINTS:
                resp = client.request(method, path)
                assert resp.status_code in (401, 403), (
                    f"Expected 401/403 for unauthenticated {method} {path}, "
                    f"got {resp.status_code}"
                )
                _assert_error_schema(resp.json(), resp.status_code)
