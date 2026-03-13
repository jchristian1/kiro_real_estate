"""
Property-based tests for security headers on all responses.

# Feature: production-hardening, Property 16: Security headers present on all responses

**Property 16: Security headers present on all responses** — for any HTTP
response from the API, the response SHALL include all three headers:
``X-Content-Type-Options: nosniff``, ``X-Frame-Options: DENY``, and
``Referrer-Policy: strict-origin-when-cross-origin``.

**Validates: Requirements 11.5**
"""

import uuid

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

_DB_NAME = f"prop_security_headers_{uuid.uuid4().hex}"

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

REQUIRED_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "strict-origin-when-cross-origin",
}


@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    app.dependency_overrides[get_db] = override_get_db
    yield
    Base.metadata.drop_all(bind=engine)
    app.dependency_overrides.pop(get_db, None)


@pytest.fixture
def client(setup_db):
    return TestClient(app, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _assert_security_headers(response) -> None:
    """Assert all three required security headers are present with correct values."""
    for header_name, expected_value in REQUIRED_HEADERS.items():
        actual = response.headers.get(header_name)
        assert actual is not None, (
            f"Security header '{header_name}' missing from response "
            f"(status={response.status_code}, path={response.url})"
        )
        assert actual == expected_value, (
            f"Security header '{header_name}' has wrong value: "
            f"expected '{expected_value}', got '{actual}'"
        )


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

# Known API endpoint paths to test
_KNOWN_PATHS = [
    "/api/v1/health",
    "/api/v1/auth/login",
    "/api/v1/agent/auth/login",
    "/api/v1/agent/auth/me",
    "/api/v1/agent/leads",
    "/api/v1/agent/dashboard",
    "/api/v1/leads",
    "/api/v1",
]

_known_path_strategy = st.sampled_from(_KNOWN_PATHS)

# Random path segments to generate arbitrary endpoint paths
_path_segment = st.text(
    alphabet=st.characters(whitelist_categories=("Ll", "Lu", "Nd"), whitelist_characters="-_"),
    min_size=1,
    max_size=12,
)
_random_path_strategy = st.lists(_path_segment, min_size=1, max_size=4).map(
    lambda parts: "/api/v1/" + "/".join(parts)
)


# ---------------------------------------------------------------------------
# Property 16: Security headers present on all responses
# ---------------------------------------------------------------------------


class TestProperty16SecurityHeadersOnAllResponses:
    """
    Property 16: Security headers present on all responses.
    **Validates: Requirements 11.5**
    """

    @given(path=_known_path_strategy)
    @settings(
        max_examples=100,
        deadline=None,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
    )
    def test_security_headers_on_known_endpoints(self, setup_db, path: str):
        """
        # Feature: production-hardening, Property 16: Security headers present on all responses
        **Validates: Requirements 11.5**

        For any known API endpoint path, the response SHALL include all three
        required security headers regardless of the HTTP status code.
        """
        Base.metadata.create_all(bind=engine)
        app.dependency_overrides[get_db] = override_get_db

        with TestClient(app, raise_server_exceptions=False) as client:
            resp = client.get(path)

        _assert_security_headers(resp)

    @given(path=_random_path_strategy)
    @settings(
        max_examples=50,
        deadline=None,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
    )
    def test_security_headers_on_random_api_paths(self, setup_db, path: str):
        """
        # Feature: production-hardening, Property 16: Security headers present on all responses
        **Validates: Requirements 11.5**

        For any random API path (even non-existent ones returning 404), the
        response SHALL include all three required security headers.
        """
        Base.metadata.create_all(bind=engine)
        app.dependency_overrides[get_db] = override_get_db

        with TestClient(app, raise_server_exceptions=False) as client:
            resp = client.get(path)

        _assert_security_headers(resp)

    def test_security_headers_on_401_response(self, client):
        """
        # Feature: production-hardening, Property 16: Security headers present on all responses
        **Validates: Requirements 11.5**

        A 401 Unauthorized response SHALL include all three security headers.
        """
        resp = client.get("/api/v1/agent/leads")
        assert resp.status_code == 401
        _assert_security_headers(resp)

    def test_security_headers_on_health_endpoint(self, client):
        """
        # Feature: production-hardening, Property 16: Security headers present on all responses
        **Validates: Requirements 11.5**

        The public health endpoint SHALL include all three security headers.
        """
        resp = client.get("/api/v1/health")
        assert resp.status_code == 200
        _assert_security_headers(resp)

    def test_security_headers_on_422_response(self, client):
        """
        # Feature: production-hardening, Property 16: Security headers present on all responses
        **Validates: Requirements 11.5**

        A 422 Unprocessable Entity response SHALL include all three security headers.
        """
        resp = client.post("/api/v1/auth/login", json={"bad": "body"})
        assert resp.status_code in (422, 400)
        _assert_security_headers(resp)

    @pytest.mark.parametrize("method,path,body", [
        ("GET", "/api/v1/health", None),
        ("GET", "/api/v1/agent/leads", None),
        ("POST", "/api/v1/auth/login", {"username": "x", "password": "y"}),
        ("POST", "/api/v1/agent/auth/login", {"email": "x@x.com", "password": "pass"}),
        ("GET", "/api/v1/agent/auth/me", None),
    ])
    def test_security_headers_across_methods_and_endpoints(
        self, client, method, path, body
    ):
        """
        # Feature: production-hardening, Property 16: Security headers present on all responses
        **Validates: Requirements 11.5**

        Security headers SHALL be present on responses from various HTTP methods
        and endpoint types (public, protected, auth).
        """
        if body:
            resp = client.request(method, path, json=body)
        else:
            resp = client.request(method, path)

        _assert_security_headers(resp)
