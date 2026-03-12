"""
Property-based tests for watcher heartbeat reflected in health endpoint.

# Feature: production-hardening, Property 11: Watcher heartbeat reflected in health endpoint

**Property 11: Watcher heartbeat reflected in health endpoint** — for any
running watcher, after each completed polling cycle the ``last_heartbeat``
field in the health endpoint response for that agent SHALL be updated to a
timestamp within the last ``SYNC_INTERVAL_SECONDS + 30`` seconds.

**Validates: Requirements 10.6**
"""

import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import gmail_lead_sync.agent_models  # noqa: F401 — registers agent tables
from api.main import app, get_db
from api.routers.public_health import _get_registry
from gmail_lead_sync.models import Base


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Default SYNC_INTERVAL_SECONDS from config (300s) + 30s tolerance
_SYNC_INTERVAL_SECONDS = 300
_HEARTBEAT_TOLERANCE_SECONDS = _SYNC_INTERVAL_SECONDS + 30  # 330s


# ---------------------------------------------------------------------------
# In-memory SQLite test database
# ---------------------------------------------------------------------------

_DB_NAME = f"prop_watcher_heartbeat_{uuid.uuid4().hex}"

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
    app.dependency_overrides.pop(_get_registry, None)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_mock_registry(agent_id: str, last_heartbeat: Optional[datetime]):
    """
    Build a mock WatcherRegistry that returns a single running watcher with
    the given last_heartbeat timestamp.
    """
    mock_registry = MagicMock()

    heartbeat_iso = last_heartbeat.isoformat() if last_heartbeat else None

    mock_registry.get_all_statuses = AsyncMock(
        return_value={
            agent_id: {
                "agent_id": agent_id,
                "status": "running",
                "last_heartbeat": heartbeat_iso,
                "last_sync": heartbeat_iso,
                "error": None,
                "started_at": None,
                "retry_count": 0,
                "last_error": None,
            }
        }
    )
    return mock_registry


def _seconds_ago(n: int) -> datetime:
    """Return a UTC datetime n seconds in the past."""
    return datetime.now(timezone.utc) - timedelta(seconds=n)


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

# Heartbeat timestamps: anywhere from 0 to SYNC_INTERVAL_SECONDS + 29 seconds ago
# (i.e., within the valid window)
_recent_heartbeat_strategy = st.integers(
    min_value=0,
    max_value=_SYNC_INTERVAL_SECONDS + 29,
).map(lambda secs: _seconds_ago(secs))

# Stale heartbeat timestamps: older than SYNC_INTERVAL_SECONDS + 30 seconds
_stale_heartbeat_strategy = st.integers(
    min_value=_SYNC_INTERVAL_SECONDS + 31,
    max_value=_SYNC_INTERVAL_SECONDS + 3600,
).map(lambda secs: _seconds_ago(secs))


# ---------------------------------------------------------------------------
# Property 11: Watcher heartbeat reflected in health endpoint
# ---------------------------------------------------------------------------


class TestProperty11WatcherHeartbeatInHealthEndpoint:
    """
    Property 11: Watcher heartbeat reflected in health endpoint.
    **Validates: Requirements 10.6**
    """

    @given(heartbeat=_recent_heartbeat_strategy)
    @settings(
        max_examples=100,
        deadline=None,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
    )
    def test_recent_heartbeat_appears_in_health_response(
        self, setup_db, heartbeat: datetime
    ):
        """
        # Feature: production-hardening, Property 11: Watcher heartbeat reflected in health endpoint
        **Validates: Requirements 10.6**

        When a watcher's last_heartbeat is within SYNC_INTERVAL_SECONDS + 30
        seconds, the health endpoint SHALL include that heartbeat timestamp in
        the response for that agent.
        """
        agent_id = f"agent_{uuid.uuid4().hex[:8]}"
        mock_registry = _make_mock_registry(agent_id, heartbeat)

        with patch("api.routers.public_health._get_registry", return_value=lambda: mock_registry):
            with TestClient(app, raise_server_exceptions=False) as client:
                resp = client.get("/api/v1/health")

        assert resp.status_code == 200, (
            f"Expected 200 from health endpoint, got {resp.status_code}: {resp.text}"
        )
        body = resp.json()

        assert "watchers" in body, f"'watchers' key missing from health response: {body}"
        assert agent_id in body["watchers"], (
            f"agent_id '{agent_id}' not found in watchers: {body['watchers']}"
        )

        watcher_entry = body["watchers"][agent_id]
        assert watcher_entry.get("last_heartbeat") is not None, (
            f"last_heartbeat is null for agent {agent_id} even though heartbeat was set"
        )

        # Parse the returned timestamp and verify it is within the tolerance window
        returned_ts_str = watcher_entry["last_heartbeat"]
        returned_ts = datetime.fromisoformat(returned_ts_str.replace("Z", "+00:00"))

        # Make heartbeat timezone-aware for comparison
        if heartbeat.tzinfo is None:
            heartbeat_aware = heartbeat.replace(tzinfo=timezone.utc)
        else:
            heartbeat_aware = heartbeat

        now = datetime.now(timezone.utc)
        age_seconds = (now - returned_ts).total_seconds()

        assert age_seconds <= _HEARTBEAT_TOLERANCE_SECONDS, (
            f"Heartbeat for agent {agent_id} is {age_seconds:.1f}s old, "
            f"exceeds tolerance of {_HEARTBEAT_TOLERANCE_SECONDS}s"
        )

    @given(heartbeat=_recent_heartbeat_strategy)
    @settings(
        max_examples=100,
        deadline=None,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
    )
    def test_heartbeat_timestamp_is_iso_string_in_response(
        self, setup_db, heartbeat: datetime
    ):
        """
        # Feature: production-hardening, Property 11: Watcher heartbeat reflected in health endpoint
        **Validates: Requirements 10.6**

        The last_heartbeat value in the health response SHALL be a parseable
        ISO 8601 timestamp string.
        """
        agent_id = f"agent_{uuid.uuid4().hex[:8]}"
        mock_registry = _make_mock_registry(agent_id, heartbeat)

        with patch("api.routers.public_health._get_registry", return_value=lambda: mock_registry):
            with TestClient(app, raise_server_exceptions=False) as client:
                resp = client.get("/api/v1/health")

        assert resp.status_code == 200
        body = resp.json()
        watcher_entry = body.get("watchers", {}).get(agent_id, {})
        ts_str = watcher_entry.get("last_heartbeat")

        assert ts_str is not None, "last_heartbeat should not be null for a running watcher"
        # Should be parseable as ISO 8601
        try:
            datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
        except ValueError as exc:
            pytest.fail(
                f"last_heartbeat '{ts_str}' is not a valid ISO 8601 timestamp: {exc}"
            )

    def test_no_heartbeat_returns_null_in_response(self, setup_db):
        """
        # Feature: production-hardening, Property 11: Watcher heartbeat reflected in health endpoint
        **Validates: Requirements 10.6**

        When a watcher has never emitted a heartbeat (last_heartbeat=None),
        the health endpoint SHALL return null for that agent's last_heartbeat.
        """
        agent_id = f"agent_{uuid.uuid4().hex[:8]}"
        mock_registry = _make_mock_registry(agent_id, last_heartbeat=None)

        with patch("api.routers.public_health._get_registry", return_value=lambda: mock_registry):
            with TestClient(app, raise_server_exceptions=False) as client:
                resp = client.get("/api/v1/health")

        assert resp.status_code == 200
        body = resp.json()
        watcher_entry = body.get("watchers", {}).get(agent_id, {})
        assert watcher_entry.get("last_heartbeat") is None, (
            f"Expected null last_heartbeat for watcher with no heartbeat, "
            f"got: {watcher_entry.get('last_heartbeat')}"
        )

    @given(
        agent_ids=st.lists(
            st.text(
                alphabet=st.characters(
                    whitelist_categories=("Ll", "Lu", "Nd"),
                    whitelist_characters="_",
                ),
                min_size=4,
                max_size=16,
            ),
            min_size=1,
            max_size=5,
            unique=True,
        ),
        seconds_ago=st.integers(min_value=0, max_value=_SYNC_INTERVAL_SECONDS + 29),
    )
    @settings(
        max_examples=50,
        deadline=None,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
    )
    def test_multiple_watchers_all_heartbeats_present(
        self, setup_db, agent_ids, seconds_ago: int
    ):
        """
        # Feature: production-hardening, Property 11: Watcher heartbeat reflected in health endpoint
        **Validates: Requirements 10.6**

        When multiple watchers are running, the health endpoint SHALL include
        a last_heartbeat entry for every agent, each within the tolerance window.
        """
        heartbeat = _seconds_ago(seconds_ago)
        heartbeat_iso = heartbeat.isoformat()

        all_statuses = {
            aid: {
                "agent_id": aid,
                "status": "running",
                "last_heartbeat": heartbeat_iso,
                "last_sync": heartbeat_iso,
                "error": None,
                "started_at": None,
                "retry_count": 0,
                "last_error": None,
            }
            for aid in agent_ids
        }

        mock_registry = MagicMock()
        mock_registry.get_all_statuses = AsyncMock(return_value=all_statuses)

        with patch("api.routers.public_health._get_registry", return_value=lambda: mock_registry):
            with TestClient(app, raise_server_exceptions=False) as client:
                resp = client.get("/api/v1/health")

        assert resp.status_code == 200
        body = resp.json()
        watchers = body.get("watchers", {})

        for aid in agent_ids:
            assert aid in watchers, (
                f"agent_id '{aid}' missing from health response watchers"
            )
            ts_str = watchers[aid].get("last_heartbeat")
            assert ts_str is not None, (
                f"last_heartbeat is null for agent '{aid}'"
            )
            returned_ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
            now = datetime.now(timezone.utc)
            age = (now - returned_ts).total_seconds()
            assert age <= _HEARTBEAT_TOLERANCE_SECONDS, (
                f"Heartbeat for agent '{aid}' is {age:.1f}s old, "
                f"exceeds tolerance of {_HEARTBEAT_TOLERANCE_SECONDS}s"
            )

    def test_health_response_includes_active_watcher_count(self, setup_db):
        """
        # Feature: production-hardening, Property 11: Watcher heartbeat reflected in health endpoint
        **Validates: Requirements 10.6**

        The health endpoint SHALL include an ``active_watchers`` count that
        reflects the number of running watchers.
        """
        agent_id = f"agent_{uuid.uuid4().hex[:8]}"
        heartbeat = _seconds_ago(10)
        mock_registry = _make_mock_registry(agent_id, heartbeat)

        with patch("api.routers.public_health._get_registry", return_value=lambda: mock_registry):
            with TestClient(app, raise_server_exceptions=False) as client:
                resp = client.get("/api/v1/health")

        assert resp.status_code == 200
        body = resp.json()
        assert "active_watchers" in body, (
            f"'active_watchers' key missing from health response: {body}"
        )
        assert body["active_watchers"] == 1, (
            f"Expected active_watchers=1, got {body['active_watchers']}"
        )
