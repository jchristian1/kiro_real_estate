"""
Unit tests for the public health endpoint (api/routers/public_health.py).

Verifies:
- All required response fields are present
- HTTP 200 when database is reachable
- HTTP 503 when database is unreachable
- active_watchers count reflects running watchers only
- watchers dict contains per-agent status and last_heartbeat
- No authentication required

Phase 5C+: watcher status is read from watcher_status DB table.

Requirements: 1.6, 2.3, 2.5
"""

import pytest
from datetime import datetime
from unittest.mock import Mock, patch
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from gmail_lead_sync.models import Base
from api.models.watcher_state_models import WatcherStatus
from api.main import app
from api.routers.public_health import get_db


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
def client(db):
    def override_db():
        yield db

    app.dependency_overrides[get_db] = override_db

    with TestClient(app) as c:
        yield c

    app.dependency_overrides.clear()


def _make_row(agent_id: str, status: str, last_heartbeat=None) -> WatcherStatus:
    row = WatcherStatus()
    row.agent_id = agent_id
    row.status = status
    row.last_heartbeat = last_heartbeat
    row.updated_at = datetime.utcnow()
    return row


def _patch_status(rows):
    return patch(
        "api.routers.public_health.WatcherStatusRepository.list_all",
        return_value=rows,
    )


# ---------------------------------------------------------------------------
# Response shape
# ---------------------------------------------------------------------------

def test_response_has_all_required_fields(client):
    with _patch_status([]):
        resp = client.get("/api/v1/health")
    assert resp.status_code == 200
    data = resp.json()
    assert "status" in data
    assert "database" in data
    assert "active_watchers" in data
    assert "errors_last_24h" in data
    assert "watchers" in data


def test_database_field_is_connected_string(client):
    with _patch_status([]):
        resp = client.get("/api/v1/health")
    assert resp.status_code == 200
    assert resp.json()["database"] == "connected"


def test_status_healthy_when_no_issues(client):
    with _patch_status([]):
        resp = client.get("/api/v1/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "healthy"


# ---------------------------------------------------------------------------
# HTTP 503 on DB error
# ---------------------------------------------------------------------------

def test_503_when_database_unreachable():
    def broken_db():
        mock_db = Mock()
        mock_db.execute.side_effect = Exception("DB down")
        yield mock_db

    app.dependency_overrides[get_db] = broken_db

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

def test_active_watchers_counts_only_running(client):
    rows = [
        _make_row("agent_1", "running"),
        _make_row("agent_2", "stopped"),
        _make_row("agent_3", "failed"),
        _make_row("agent_4", "running"),
    ]
    with _patch_status(rows):
        resp = client.get("/api/v1/health")
    assert resp.status_code == 200
    assert resp.json()["active_watchers"] == 2


def test_active_watchers_zero_when_none_running(client):
    rows = [_make_row("agent_1", "stopped")]
    with _patch_status(rows):
        resp = client.get("/api/v1/health")
    assert resp.status_code == 200
    assert resp.json()["active_watchers"] == 0


# ---------------------------------------------------------------------------
# watchers dict
# ---------------------------------------------------------------------------

def test_watchers_dict_contains_per_agent_info(client):
    hb = datetime(2024, 6, 1, 12, 0, 0)
    rows = [_make_row("agent_42", "running", hb)]
    with _patch_status(rows):
        resp = client.get("/api/v1/health")
    assert resp.status_code == 200
    watchers = resp.json()["watchers"]
    assert "agent_42" in watchers
    assert watchers["agent_42"]["status"] == "running"
    assert watchers["agent_42"]["last_heartbeat"] is not None


def test_watchers_last_heartbeat_can_be_null(client):
    rows = [_make_row("agent_99", "stopped", None)]
    with _patch_status(rows):
        resp = client.get("/api/v1/health")
    assert resp.status_code == 200
    assert resp.json()["watchers"]["agent_99"]["last_heartbeat"] is None


# ---------------------------------------------------------------------------
# Degraded status
# ---------------------------------------------------------------------------

def test_status_degraded_when_watcher_failed(client):
    rows = [
        _make_row("agent_1", "running"),
        _make_row("agent_2", "failed"),
    ]
    with _patch_status(rows):
        resp = client.get("/api/v1/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "degraded"


# ---------------------------------------------------------------------------
# No authentication required
# ---------------------------------------------------------------------------

def test_no_auth_required():
    def override_db():
        session = _TestSession()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_db

    with _patch_status([]):
        with TestClient(app) as c:
            resp = c.get("/api/v1/health")

    app.dependency_overrides.clear()

    assert resp.status_code == 200
