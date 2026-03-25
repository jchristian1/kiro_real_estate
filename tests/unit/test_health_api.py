"""
Unit tests for health check API endpoints.

Tests health monitoring functionality including:
- Database connection status checking
- Watcher status tracking (DB-backed, Phase 5C+)
- Error count from last 24 hours
- Overall system status determination

Requirements: 8.1, 8.3, 8.4, 8.6
"""

import pytest
from datetime import datetime
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from gmail_lead_sync.models import Base
from api.models.web_ui_models import User
from api.models.watcher_state_models import WatcherStatus
from api.main import app
from api.routers.public_health import get_db


# Test database setup
TEST_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture
def db_session():
    """Create a test database session."""
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


def _make_status_row(agent_id: str, status: str, last_heartbeat=None) -> WatcherStatus:
    row = WatcherStatus()
    row.agent_id = agent_id
    row.status = status
    row.last_heartbeat = last_heartbeat
    row.updated_at = datetime.utcnow()
    return row


@pytest.fixture
def client(db_session):
    """Create a test client with dependency overrides."""
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


@pytest.fixture
def test_user(db_session):
    user = User(username="testuser", password_hash="hashed_password", role="admin")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _patch_status_repo(rows):
    """Patch WatcherStatusRepository.list_all to return *rows*."""
    return patch(
        "api.routers.public_health.WatcherStatusRepository.list_all",
        return_value=rows,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_health_check_healthy_no_watchers(client):
    """Healthy when DB is up and no watchers registered."""
    with _patch_status_repo([]):
        response = client.get("/api/v1/health")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["database"] == "connected"
    assert data["active_watchers"] == 0
    assert data["watchers"] == {}


def test_health_check_healthy_running_watchers(client):
    """Healthy when all watchers are running."""
    hb = datetime(2024, 1, 15, 10, 0, 0)
    rows = [
        _make_status_row("1", "running", hb),
        _make_status_row("2", "running", hb),
    ]
    with _patch_status_repo(rows):
        response = client.get("/api/v1/health")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["active_watchers"] == 2
    assert "1" in data["watchers"]
    assert data["watchers"]["1"]["status"] == "running"
    assert data["watchers"]["1"]["last_heartbeat"] is not None


def test_health_check_degraded_failed_watcher(client):
    """Degraded when at least one watcher has failed status."""
    rows = [
        _make_status_row("1", "running"),
        _make_status_row("2", "failed"),
    ]
    with _patch_status_repo(rows):
        response = client.get("/api/v1/health")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "degraded"
    assert data["active_watchers"] == 1


def test_health_check_stopped_watchers_not_degraded(client):
    """Stopped watchers alone do not cause degraded status."""
    rows = [
        _make_status_row("1", "stopped"),
        _make_status_row("2", "stopped"),
    ]
    with _patch_status_repo(rows):
        response = client.get("/api/v1/health")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["active_watchers"] == 0


def test_health_check_database_unreachable(client):
    """Returns 503 when database is unreachable."""
    def bad_db():
        mock_db = MagicMock()
        mock_db.execute.side_effect = Exception("DB down")
        yield mock_db

    app.dependency_overrides[get_db] = bad_db
    response = client.get("/api/v1/health")
    app.dependency_overrides[get_db] = lambda: (yield TestingSessionLocal())

    assert response.status_code == 503
    data = response.json()
    assert data["database"] == "error"
    assert data["status"] == "degraded"


def test_health_check_no_auth_required(client):
    """Health endpoint must be accessible without authentication."""
    with _patch_status_repo([]):
        response = client.get("/api/v1/health")
    assert response.status_code == 200


def test_health_check_response_schema(client):
    """Response contains all required top-level fields."""
    with _patch_status_repo([]):
        response = client.get("/api/v1/health")

    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert "database" in data
    assert "active_watchers" in data
    assert "errors_last_24h" in data
    assert "watchers" in data


def test_health_check_watcher_heartbeat_format(client):
    """Heartbeat timestamps are ISO strings ending with Z."""
    hb = datetime(2024, 1, 15, 10, 0, 0)
    rows = [_make_status_row("42", "running", hb)]
    with _patch_status_repo(rows):
        response = client.get("/api/v1/health")

    data = response.json()
    hb_str = data["watchers"]["42"]["last_heartbeat"]
    assert hb_str is not None
    assert hb_str.endswith("Z")


def test_health_check_null_heartbeat(client):
    """Watchers with no heartbeat return null."""
    rows = [_make_status_row("99", "stopped", None)]
    with _patch_status_repo(rows):
        response = client.get("/api/v1/health")

    data = response.json()
    assert data["watchers"]["99"]["last_heartbeat"] is None


def test_health_check_status_repo_failure_is_graceful(client):
    """If watcher_status table query fails, health still returns 200."""
    with patch(
        "api.routers.public_health.WatcherStatusRepository.list_all",
        side_effect=Exception("table missing"),
    ):
        response = client.get("/api/v1/health")

    assert response.status_code == 200
    data = response.json()
    assert data["active_watchers"] == 0
    assert data["watchers"] == {}
