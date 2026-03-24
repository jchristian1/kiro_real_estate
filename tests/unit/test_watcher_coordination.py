"""
Unit tests for Phase 5C DB-backed watcher coordination.

Tests:
- WatcherControlRepository: set_desired_status, request_sync, clear_sync_request
- WatcherStatusRepository: upsert, list_all, get
- admin_watchers endpoints: start, stop, sync, status (DB-backed, no in-memory registry)
- worker reconciliation: _reconcile_sync starts/stops watchers per desired state
"""

from __future__ import annotations

from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


# ---------------------------------------------------------------------------
# In-memory SQLite fixture
# ---------------------------------------------------------------------------


@pytest.fixture()
def db_session():
    """
    Provide a fresh in-memory SQLite session with only the coordination tables.

    We create the two Phase 5C tables directly from their Table objects to
    avoid FK resolution errors from unrelated tables in the shared metadata.
    """
    from api.models.watcher_state_models import WatcherControl, WatcherStatus

    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    # Create only the two coordination tables — no FK dependencies
    WatcherControl.__table__.create(bind=engine, checkfirst=True)
    WatcherStatus.__table__.create(bind=engine, checkfirst=True)

    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()
    engine.dispose()


# ---------------------------------------------------------------------------
# WatcherControlRepository
# ---------------------------------------------------------------------------


class TestWatcherControlRepository:
    def test_set_desired_status_creates_row(self, db_session):
        from api.repositories.watcher_coordination_repository import WatcherControlRepository
        repo = WatcherControlRepository(db_session)
        row = repo.set_desired_status("agent-1", "running")
        assert row.agent_id == "agent-1"
        assert row.desired_status == "running"

    def test_set_desired_status_updates_existing(self, db_session):
        from api.repositories.watcher_coordination_repository import WatcherControlRepository
        repo = WatcherControlRepository(db_session)
        repo.set_desired_status("agent-1", "running")
        row = repo.set_desired_status("agent-1", "stopped")
        assert row.desired_status == "stopped"
        # Only one row
        from api.models.watcher_state_models import WatcherControl
        assert db_session.query(WatcherControl).count() == 1

    def test_request_sync_sets_timestamp(self, db_session):
        from api.repositories.watcher_coordination_repository import WatcherControlRepository
        repo = WatcherControlRepository(db_session)
        before = datetime.utcnow() - timedelta(seconds=1)
        row = repo.request_sync("agent-2")
        assert row.sync_requested_at is not None
        assert row.sync_requested_at >= before

    def test_clear_sync_request_nulls_timestamp(self, db_session):
        from api.repositories.watcher_coordination_repository import WatcherControlRepository
        repo = WatcherControlRepository(db_session)
        repo.request_sync("agent-3")
        repo.clear_sync_request("agent-3")
        row = repo.get("agent-3")
        assert row.sync_requested_at is None

    def test_list_all_returns_all_rows(self, db_session):
        from api.repositories.watcher_coordination_repository import WatcherControlRepository
        repo = WatcherControlRepository(db_session)
        repo.set_desired_status("a1", "running")
        repo.set_desired_status("a2", "stopped")
        rows = repo.list_all()
        assert len(rows) == 2


# ---------------------------------------------------------------------------
# WatcherStatusRepository
# ---------------------------------------------------------------------------


class TestWatcherStatusRepository:
    def test_upsert_creates_row(self, db_session):
        from api.repositories.watcher_coordination_repository import WatcherStatusRepository
        repo = WatcherStatusRepository(db_session)
        now = datetime.utcnow()
        row = repo.upsert("agent-1", status="running", last_heartbeat=now)
        assert row.agent_id == "agent-1"
        assert row.status == "running"
        assert row.last_heartbeat == now

    def test_upsert_updates_existing(self, db_session):
        from api.repositories.watcher_coordination_repository import WatcherStatusRepository
        repo = WatcherStatusRepository(db_session)
        repo.upsert("agent-1", status="running")
        row = repo.upsert("agent-1", status="stopped", error="connection lost")
        assert row.status == "stopped"
        assert row.error == "connection lost"
        from api.models.watcher_state_models import WatcherStatus
        assert db_session.query(WatcherStatus).count() == 1

    def test_list_all_returns_all_rows(self, db_session):
        from api.repositories.watcher_coordination_repository import WatcherStatusRepository
        repo = WatcherStatusRepository(db_session)
        repo.upsert("a1", status="running")
        repo.upsert("a2", status="stopped")
        rows = repo.list_all()
        assert len(rows) == 2

    def test_get_returns_none_for_unknown_agent(self, db_session):
        from api.repositories.watcher_coordination_repository import WatcherStatusRepository
        repo = WatcherStatusRepository(db_session)
        assert repo.get("unknown") is None


# ---------------------------------------------------------------------------
# admin_watchers endpoints (DB-backed, no in-memory registry)
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# admin_watchers router logic (unit-level, no HTTP stack)
# ---------------------------------------------------------------------------


class TestAdminWatchersRouterLogic:
    """
    Test the router functions directly, bypassing FastAPI auth middleware.

    These tests verify that the router correctly writes to watcher_control
    and reads from watcher_status — the DB coordination contract.
    """

    @pytest.mark.asyncio
    async def test_start_watcher_writes_desired_running(self, db_session):
        from api.routers.admin_watchers import start_watcher
        from api.repositories.watcher_coordination_repository import WatcherControlRepository
        from api.repositories import CredentialRepository

        mock_user = SimpleNamespace(id=1, role="admin", company_id=1)
        mock_creds = SimpleNamespace(id=10, company_id=1)

        with patch.object(CredentialRepository, "get_by_agent_id", return_value=mock_creds):
            with patch("api.routers.admin_watchers.record_audit_log"):
                resp = await start_watcher(
                    agent_id="agent-1",
                    db=db_session,
                    current_user=mock_user,
                )

        assert resp.agent_id == "agent-1"
        assert "requested" in resp.message.lower()

        ctrl_repo = WatcherControlRepository(db_session)
        row = ctrl_repo.get("agent-1")
        assert row is not None
        assert row.desired_status == "running"

    @pytest.mark.asyncio
    async def test_stop_watcher_writes_desired_stopped(self, db_session):
        from api.routers.admin_watchers import stop_watcher
        from api.repositories.watcher_coordination_repository import WatcherControlRepository
        from api.repositories import CredentialRepository

        mock_user = SimpleNamespace(id=1, role="admin", company_id=1)
        mock_creds = SimpleNamespace(id=10, company_id=1)

        with patch.object(CredentialRepository, "get_by_agent_id", return_value=mock_creds):
            with patch("api.routers.admin_watchers.record_audit_log"):
                resp = await stop_watcher(
                    agent_id="agent-1",
                    db=db_session,
                    current_user=mock_user,
                )

        assert resp.status == "stopping"

        ctrl_repo = WatcherControlRepository(db_session)
        row = ctrl_repo.get("agent-1")
        assert row is not None
        assert row.desired_status == "stopped"

    @pytest.mark.asyncio
    async def test_trigger_sync_sets_sync_requested_at(self, db_session):
        from api.routers.admin_watchers import trigger_sync
        from api.repositories.watcher_coordination_repository import WatcherControlRepository
        from api.repositories import CredentialRepository

        mock_user = SimpleNamespace(id=1, role="admin", company_id=1)
        mock_creds = SimpleNamespace(id=10, company_id=1)

        with patch.object(CredentialRepository, "get_by_agent_id", return_value=mock_creds):
            with patch("api.routers.admin_watchers.record_audit_log"):
                resp = await trigger_sync(
                    agent_id="agent-1",
                    db=db_session,
                    current_user=mock_user,
                )

        assert resp.sync_triggered is True

        ctrl_repo = WatcherControlRepository(db_session)
        row = ctrl_repo.get("agent-1")
        assert row is not None
        assert row.sync_requested_at is not None

    @pytest.mark.asyncio
    async def test_status_endpoint_reads_from_db(self, db_session):
        from api.routers.admin_watchers import get_all_watcher_statuses
        from api.repositories.watcher_coordination_repository import WatcherStatusRepository

        status_repo = WatcherStatusRepository(db_session)
        status_repo.upsert(
            "agent-42",
            status="running",
            last_heartbeat=datetime.utcnow(),
            last_sync=datetime.utcnow(),
        )

        mock_user = SimpleNamespace(id=1, role="admin", company_id=1)
        resp = await get_all_watcher_statuses(current_user=mock_user, db=db_session)

        agent_ids = [w.agent_id for w in resp.watchers]
        assert "agent-42" in agent_ids
        watcher = next(w for w in resp.watchers if w.agent_id == "agent-42")
        assert watcher.status == "running"

    @pytest.mark.asyncio
    async def test_start_watcher_404_for_unknown_agent(self, db_session):
        from api.routers.admin_watchers import start_watcher
        from api.repositories import CredentialRepository
        from api.exceptions import NotFoundException

        mock_user = SimpleNamespace(id=1, role="company_admin", company_id=1)

        with patch.object(CredentialRepository, "get_by_agent_id", return_value=None):
            with pytest.raises(NotFoundException):
                await start_watcher(
                    agent_id="unknown-agent",
                    db=db_session,
                    current_user=mock_user,
                )


# ---------------------------------------------------------------------------
# Worker reconciliation
# ---------------------------------------------------------------------------


class TestWorkerReconciliation:
    """Test _reconcile_sync starts/stops watchers per desired state."""

    def test_reconcile_starts_watcher_when_desired_running(self, db_session):
        from api.repositories.watcher_coordination_repository import WatcherControlRepository
        from api.services.watcher_registry import WatcherStatus as WS, WatcherInfo
        from worker.main import _reconcile_sync

        # Set desired state
        ctrl_repo = WatcherControlRepository(db_session)
        ctrl_repo.set_desired_status("agent-10", "running")

        # Mock registry with no running watcher
        mock_registry = MagicMock()
        mock_registry._watchers = {}  # no current watcher

        future = MagicMock()
        future.result.return_value = True

        with patch("asyncio.run_coroutine_threadsafe", return_value=future) as mock_rctf:
            with patch("asyncio.get_event_loop"):
                _reconcile_sync(mock_registry, lambda: db_session)

        # start_watcher should have been scheduled
        calls = [str(c) for c in mock_rctf.call_args_list]
        assert any("start_watcher" in c for c in calls)

    def test_reconcile_stops_watcher_when_desired_stopped(self, db_session):
        from api.repositories.watcher_coordination_repository import WatcherControlRepository
        from api.services.watcher_registry import WatcherStatus as WS, WatcherInfo
        from worker.main import _reconcile_sync

        ctrl_repo = WatcherControlRepository(db_session)
        ctrl_repo.set_desired_status("agent-11", "stopped")

        # Mock registry with a running watcher
        mock_info = MagicMock()
        mock_info.status = WS.RUNNING
        mock_info.last_heartbeat = None
        mock_info.last_sync = None
        mock_info.started_at = None
        mock_info.error = None

        mock_registry = MagicMock()
        mock_registry._watchers = {"agent-11": mock_info}

        future = MagicMock()
        future.result.return_value = True

        with patch("asyncio.run_coroutine_threadsafe", return_value=future) as mock_rctf:
            with patch("asyncio.get_event_loop"):
                _reconcile_sync(mock_registry, lambda: db_session)

        calls = [str(c) for c in mock_rctf.call_args_list]
        assert any("stop_watcher" in c for c in calls)

    def test_reconcile_clears_sync_request_after_acting(self, db_session):
        from api.repositories.watcher_coordination_repository import (
            WatcherControlRepository,
            WatcherStatusRepository,
        )
        from api.services.watcher_registry import WatcherStatus as WS
        from worker.main import _reconcile_sync

        ctrl_repo = WatcherControlRepository(db_session)
        ctrl_repo.set_desired_status("agent-12", "running")
        ctrl_repo.request_sync("agent-12")

        mock_info = MagicMock()
        mock_info.status = WS.RUNNING
        mock_info.last_heartbeat = None
        mock_info.last_sync = None
        mock_info.started_at = None
        mock_info.error = None

        mock_registry = MagicMock()
        mock_registry._watchers = {"agent-12": mock_info}

        future = MagicMock()
        future.result.return_value = True

        with patch("asyncio.run_coroutine_threadsafe", return_value=future):
            with patch("asyncio.get_event_loop"):
                _reconcile_sync(mock_registry, lambda: db_session)

        # sync_requested_at should be cleared
        row = ctrl_repo.get("agent-12")
        assert row.sync_requested_at is None

    def test_reconcile_writes_status_to_db(self, db_session):
        from api.repositories.watcher_coordination_repository import WatcherStatusRepository
        from api.services.watcher_registry import WatcherStatus as WS
        from worker.main import _reconcile_sync

        now = datetime.utcnow()
        mock_info = MagicMock()
        mock_info.status = WS.RUNNING
        mock_info.last_heartbeat = now
        mock_info.last_sync = now
        mock_info.started_at = now
        mock_info.error = None

        mock_registry = MagicMock()
        mock_registry._watchers = {"agent-20": mock_info}

        with patch("asyncio.run_coroutine_threadsafe"):
            with patch("asyncio.get_event_loop"):
                _reconcile_sync(mock_registry, lambda: db_session)

        status_repo = WatcherStatusRepository(db_session)
        row = status_repo.get("agent-20")
        assert row is not None
        assert row.status == "running"
