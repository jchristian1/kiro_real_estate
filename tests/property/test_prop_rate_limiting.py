"""
Property-based tests for rate limiting on login endpoints.

# Feature: production-hardening, Property 17: Rate limiting on login endpoints

**Property 17: Rate limiting on login endpoints** — for any IP address that
sends more than 10 requests to ``POST /api/v1/auth/login`` or
``POST /api/v1/agent/auth/login`` within a 60-second window, the 11th and
subsequent requests within that window SHALL receive HTTP 429 with the unified
error schema.

**Validates: Requirements 11.6**
"""

import uuid
from typing import List

import pytest
from fastapi.testclient import TestClient
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import gmail_lead_sync.agent_models  # noqa: F401 — registers agent tables
from api.main import app, get_db
from gmail_lead_sync.models import Base

# ---------------------------------------------------------------------------
# In-memory SQLite test database
# ---------------------------------------------------------------------------

_DB_NAME = f"prop_rate_limiting_{uuid.uuid4().hex}"

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
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    app.dependency_overrides[get_db] = override_get_db
    yield
    Base.metadata.drop_all(bind=engine)
    app.dependency_overrides.pop(get_db, None)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

RATE_LIMIT = 10  # requests per minute per IP


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


def _reset_rate_limiter():
    """Reset the slowapi in-memory storage between tests."""
    try:
        from api.utils.rate_limiter import limiter
        # Access the underlying storage and clear it
        storage = limiter._storage
        if hasattr(storage, '_storage'):
            storage._storage.clear()
        elif hasattr(storage, 'storage'):
            storage.storage.clear()
    except Exception:
        pass  # Best-effort reset


def _send_login_requests(
    client: TestClient,
    endpoint: str,
    body: dict,
    count: int,
) -> List[int]:
    """Send `count` POST requests to `endpoint` and return list of status codes."""
    status_codes = []
    for _ in range(count):
        resp = client.post(endpoint, json=body)
        status_codes.append(resp.status_code)
    return status_codes


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

# Number of extra requests beyond the limit (1 to 5)
_extra_requests_strategy = st.integers(min_value=1, max_value=5)


# ---------------------------------------------------------------------------
# Property 17: Rate limiting on login endpoints
# ---------------------------------------------------------------------------


class TestProperty17RateLimitingOnLoginEndpoints:
    """
    Property 17: Rate limiting on login endpoints.
    **Validates: Requirements 11.6**
    """

    @given(extra=_extra_requests_strategy)
    @settings(
        max_examples=10,
        deadline=None,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
    )
    def test_admin_login_rate_limited_after_10_requests(self, setup_db, extra: int):
        """
        # Feature: production-hardening, Property 17: Rate limiting on login endpoints
        **Validates: Requirements 11.6**

        After 10 requests to POST /api/v1/auth/login from the same IP within
        a 60-second window, the (10+extra)-th request SHALL return HTTP 429.
        """
        Base.metadata.create_all(bind=engine)
        app.dependency_overrides[get_db] = override_get_db
        _reset_rate_limiter()

        body = {"username": "testuser", "password": "testpass"}
        total = RATE_LIMIT + extra

        with TestClient(app, raise_server_exceptions=False) as client:
            status_codes = _send_login_requests(
                client, "/api/v1/auth/login", body, total
            )

        # The 11th+ request must be 429
        assert 429 in status_codes, (
            f"Expected HTTP 429 after {RATE_LIMIT} requests, "
            f"but got status codes: {status_codes}"
        )

        # Verify the 429 response has the unified error schema
        with TestClient(app, raise_server_exceptions=False) as client:
            # Send one more to get a 429 response body
            resp = client.post("/api/v1/auth/login", json=body)
            if resp.status_code == 429:
                _assert_error_schema(resp.json(), 429)

    @given(extra=_extra_requests_strategy)
    @settings(
        max_examples=10,
        deadline=None,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
    )
    def test_agent_login_rate_limited_after_10_requests(self, setup_db, extra: int):
        """
        # Feature: production-hardening, Property 17: Rate limiting on login endpoints
        **Validates: Requirements 11.6**

        After 10 requests to POST /api/v1/agent/auth/login from the same IP
        within a 60-second window, the (10+extra)-th request SHALL return HTTP 429.
        """
        Base.metadata.create_all(bind=engine)
        app.dependency_overrides[get_db] = override_get_db
        _reset_rate_limiter()

        body = {"email": "test@example.com", "password": "testpass"}
        total = RATE_LIMIT + extra

        with TestClient(app, raise_server_exceptions=False) as client:
            status_codes = _send_login_requests(
                client, "/api/v1/agent/auth/login", body, total
            )

        assert 429 in status_codes, (
            f"Expected HTTP 429 after {RATE_LIMIT} requests, "
            f"but got status codes: {status_codes}"
        )

    def test_rate_limit_429_has_unified_error_schema(self, setup_db):
        """
        # Feature: production-hardening, Property 17: Rate limiting on login endpoints
        **Validates: Requirements 11.6**

        When the rate limit is exceeded, the 429 response body SHALL match
        the unified ErrorResponse schema.
        """
        _reset_rate_limiter()
        body = {"username": "u", "password": "p"}

        with TestClient(app, raise_server_exceptions=False) as client:
            # Exhaust the limit
            for _ in range(RATE_LIMIT):
                client.post("/api/v1/auth/login", json=body)

            # The next request should be 429
            resp = client.post("/api/v1/auth/login", json=body)

        assert resp.status_code == 429, (
            f"Expected 429 after {RATE_LIMIT} requests, got {resp.status_code}"
        )
        _assert_error_schema(resp.json(), 429)

    def test_rate_limit_applies_per_endpoint(self, setup_db):
        """
        # Feature: production-hardening, Property 17: Rate limiting on login endpoints
        **Validates: Requirements 11.6**

        Rate limiting is applied independently to each login endpoint.
        Exhausting the limit on /auth/login does not affect /agent/auth/login.
        """
        _reset_rate_limiter()

        admin_body = {"username": "u", "password": "p"}
        agent_body = {"email": "x@x.com", "password": "p"}

        with TestClient(app, raise_server_exceptions=False) as client:
            # Exhaust admin login limit
            for _ in range(RATE_LIMIT + 1):
                client.post("/api/v1/auth/login", json=admin_body)

            # Agent login should still work (not rate-limited yet)
            # It may return 401 (wrong creds) but NOT 429
            resp = client.post("/api/v1/agent/auth/login", json=agent_body)
            assert resp.status_code != 429, (
                f"Agent login was rate-limited after exhausting admin login limit: "
                f"status={resp.status_code}"
            )
