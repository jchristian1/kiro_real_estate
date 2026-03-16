"""
Unit tests for the public health endpoint (api/routers/public_health.py).

Verifies:
- All required response fields are present
- HTTP 200 when database is reachable
- HTTP 503 when database is unreachable
- active_watchers count reflects running watchers only
- watchers dict contains per-agent status and last_heartbeat
- No authentication required

Requirements: 1.6, 2.3, 2.5
"""

import pytest
from unittest.mock import Mock, AsyncMock
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from gmail_lead_sync.models import Base
from api.main import app
from api.routers.public_health import _get_db, _get_registry


# ---------------------------------------------------------------------------
# Test DB setup
# ---------------------------------------------------------------------------

TEST_DB_URL = "sqlite:///:memory:"
_engine = create_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
_TestSession = sessionmaker(autocommit=False, autoflush=False, bind=_engine)


@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(bind=_engine)
    yield
    Base.metadata.drop_all(bind=_engine)


@pytest.fixture
def db():
    session = _TestSession()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def mock_registry():
    reg = Mock()
    reg.get_all_statuses = AsyncMock(return_value={})
    return reg


@pytest.fixture
def client(db, mock_registry):
    def override_db():
        yield db

    app.dependency_overrides[_get_db] = override_db
    app.dependency_overrides[_get_registry] = lambda: mock_registry

    with TestClient(app) as c:
        yield c

    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Response shape
# ---------------------------------------------------------------------------

def test_response_has_all_required_fields(client, mock_registry):
    """All spec-required top-level fields must be present."""
    mock_registry.get_all_statuses.return_value = {}

    resp = client.get("/api/v1/health")
    assert resp.status_code == 200

    data = resp.json()
    assert "status" in data
    assert "database" in data
    assert "active_watchers" in data
    assert "errors_last_24h" in data
    assert "watchers" in data


def test_database_field_is_connected_string(client, mock_registry):
    """database field must be the string 'connected' when DB is reachable."""
    mock_registry.get_all_statuses.return_value = {}

    resp = client.get("/api/v1/health")
    assert resp.status_code == 200
    assert resp.json()["database"] == "connected"


def test_status_healthy_when_no_issues(client, mock_registry):
    """status must be 'healthy' when DB is up and no failed watchers."""
    mock_registry.get_all_statuses.return_value = {}

    resp = client.get("/api/v1/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "healthy"


# ---------------------------------------------------------------------------
# HTTP 503 on DB error
# ---------------------------------------------------------------------------

def test_503_when_database_unreachable(mock_registry):
    """HTTP 503 must be returned when the database is unreachable."""
    def broken_db():
        mock_db = Mock()
        mock_db.execute.side_effect = Exception("DB down")
        yield mock_db

    app.dependency_overrides[_get_db] = broken_db
    app.dependency_overrides[_get_registry] = lambda: mock_registry

    with TestClient(app) as c:
        resp = c.get("/api/v1/health")

    app.dependency_overrides.clear()

    assert resp.status_code == 503
    data = resp.json()
    assert data["database"] == "error"
    assert data["status"] == "degraded"


# ---------------------------------------------------------------------------
# active_watchers count
# ---------------------------------------------------------------------------

def test_active_watchers_counts_only_running(client, mock_registry):
    """active_watchers must count only watchers with status 'running'."""
    mock_registry.get_all_statuses.return_value = {
        "agent_1": {"status": "running", "last_heartbeat": "2024-01-01T00:00:00Z"},
        "agent_2": {"status": "stopped", "last_heartbeat": None},
        "agent_3": {"status": "failed",  "last_heartbeat": "2024-01-01T00:00:00Z"},
        "agent_4": {"status": "running", "last_heartbeat": "2024-01-01T00:01:00Z"},
    }

    resp = client.get("/api/v1/health")
    assert resp.status_code == 200
    assert resp.json()["active_watchers"] == 2


def test_active_watchers_zero_when_none_running(client, mock_registry):
    mock_registry.get_all_statuses.return_value = {
        "agent_1": {"status": "stopped", "last_heartbeat": None},
    }

    resp = client.get("/api/v1/health")
    assert resp.status_code == 200
    assert resp.json()["active_watchers"] == 0


# ---------------------------------------------------------------------------
# watchers dict
# ---------------------------------------------------------------------------

def test_watchers_dict_contains_per_agent_info(client, mock_registry):
    """watchers dict must include status and last_heartbeat per agent."""
    mock_registry.get_all_statuses.return_value = {
        "agent_42": {"status": "running", "last_heartbeat": "2024-06-01T12:00:00Z"},
    }

    resp = client.get("/api/v1/health")
    assert resp.status_code == 200

    watchers = resp.json()["watchers"]
    assert "agent_42" in watchers
    assert watchers["agent_42"]["status"] == "running"
    assert watchers["agent_42"]["last_heartbeat"] == "2024-06-01T12:00:00Z"


def test_watchers_last_heartbeat_can_be_null(client, mock_registry):
    """last_heartbeat must be null when the watcher has never heartbeated."""
    mock_registry.get_all_statuses.return_value = {
        "agent_99": {"status": "stopped", "last_heartbeat": None},
    }

    resp = client.get("/api/v1/health")
    assert resp.status_code == 200
    assert resp.json()["watchers"]["agent_99"]["last_heartbeat"] is None


# ---------------------------------------------------------------------------
# Degraded status
# ---------------------------------------------------------------------------

def test_status_degraded_when_watcher_failed(client, mock_registry):
    """status must be 'degraded' when any watcher has status 'failed'."""
    mock_registry.get_all_statuses.return_value = {
        "agent_1": {"status": "running", "last_heartbeat": "2024-01-01T00:00:00Z"},
        "agent_2": {"status": "failed",  "last_heartbeat": None},
    }

    resp = client.get("/api/v1/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "degraded"


# ---------------------------------------------------------------------------
# No authentication required
# ---------------------------------------------------------------------------

def test_no_auth_required(mock_registry):
    """Endpoint must be accessible without any authentication headers."""
    def override_db():
        session = _TestSession()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[_get_db] = override_db
    app.dependency_overrides[_get_registry] = lambda: mock_registry

    with TestClient(app) as c:
        # No Authorization header, no cookies
        resp = c.get("/api/v1/health")

    app.dependency_overrides.clear()

    assert resp.status_code == 200
