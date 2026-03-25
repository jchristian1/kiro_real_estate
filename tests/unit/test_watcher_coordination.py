"""
Unit tests for Phase 5C/6B DB-backed watcher coordination.

Phase 6B additions:
- Upsert idempotency: repeated writes produce exactly one row
- Concurrent-write safety: two sequential writes produce one row with last value
- WatcherRegistry accepts make_credentials_store factory (no long-lived shared session)
"""

from __future__ import annotations

from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


@pytest.fixture()
def db_session():
    from api.models.watcher_state_models import WatcherControl, WatcherStatus
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    WatcherControl.__table__.create(bind=engine, checkfirst=True)
    WatcherStatus.__table__.create(bind=engine, checkfirst=True)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()
    engine.dispose()


class TestWatcherControlRepository:
    def test_set_desired_status_creates_row(self, db_session):
        from api.repositories.watcher_coordination_repository import WatcherControlRepository
        repo = WatcherControlRepository(db_session)
        row = repo.set_desired_status("agent-1", "running")
        assert row.agent_id == "agent-1"
        assert row.desired_status == "running"

    def test_set_desired_status_updates_existing(self, db_session):
        from api.repositories.watcher_coordination_repository import WatcherControlRepository
        from api.models.watcher_state_models import WatcherControl
        repo = WatcherControlRepository(db_session)
        repo.set_desired_status("agent-1", "running")
        row = repo.set_desired_status("agent-1", "stopped")
        assert row.desired_status == "stopped"
        assert db_session.query(WatcherControl).count() == 1

    def test_set_desired_status_idempotent(self, db_session):
        from api.repositories.watcher_coordination_repository import WatcherControlRepository
        from api.models.watcher_state_models import WatcherControl
        repo = WatcherControlRepository(db_session)
        repo.set_desired_status("agent-idem", "running")
        repo.set_desired_status("agent-idem", "running")
        assert db_session.query(WatcherControl).filter_by(agent_id="agent-idem").count() == 1

    def test_set_desired_status_concurrent_writes_last_wins(self, db_session):
        from api.repositories.watcher_coordination_repository import WatcherControlRepository
        from api.models.watcher_state_models import WatcherControl
        repo = WatcherControlRepository(db_session)
        repo.set_desired_status("agent-race", "running")
        repo.set_desired_status("agent-race", "stopped")
        rows = db_session.query(WatcherControl).filter_by(agent_id="agent-race").all()
        assert len(rows) == 1
        assert rows[0].desired_status == "stopped"

    def test_request_sync_sets_timestamp(self, db_session):
        from api.repositories.watcher_coordination_repository import WatcherControlRepository
        repo = WatcherControlRepository(db_session)
        before = datetime.utcnow() - timedelta(seconds=1)
        row = repo.request_sync("agent-2")
        assert row.sync_requested_at is not None
        assert row.sync_requested_at >= before

    def test_request_sync_does_not_overwrite_desired_status(self, db_session):
        from api.repositories.watcher_coordination_repository import WatcherControlRepository
        repo = WatcherControlRepository(db_session)
        repo.set_desired_status("agent-preserve", "stopped")
        row = repo.request_sync("agent-preserve")
        assert row.desired_status == "stopped"
        assert row.sync_requested_at is not None

    def test_request_sync_idempotent(self, db_session):
        from api.repositories.watcher_coordination_repository import WatcherControlRepository
        from api.models.watcher_state_models import WatcherControl
        repo = WatcherControlRepository(db_session)
        repo.request_sync("agent-sync-idem")
        repo.request_sync("agent-sync-idem")
        assert db_session.query(WatcherControl).filter_by(agent_id="agent-sync-idem").count() == 1

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
        from api.models.watcher_state_models import WatcherStatus
        repo = WatcherStatusRepository(db_session)
        repo.upsert("agent-1", status="running")
        row = repo.upsert("agent-1", status="stopped", error="connection lost")
        assert row.status == "stopped"
        assert row.error == "connection lost"
        assert db_session.query(WatcherStatus).count() == 1

    def test_upsert_idempotent(self, db_session):
        from api.repositories.watcher_coordination_repository import WatcherStatusRepository
        from api.models.watcher_state_models import WatcherStatus
        repo = WatcherStatusRepository(db_session)
        repo.upsert("agent-idem", status="running")
        repo.upsert("agent-idem", status="running")
        assert db_session.query(WatcherStatus).filter_by(agent_id="agent-idem").count() == 1

    def test_upsert_concurrent_writes_last_wins(self, db_session):
        from api.repositories.watcher_coordination_repository import WatcherStatusRepository
        from api.models.watcher_state_models import WatcherStatus
        repo = WatcherStatusRepository(db_session)
        repo.upsert("agent-race", status="running")
        repo.upsert("agent-race", status="stopped", error="crash")
        rows = db_session.query(WatcherStatus).filter_by(agent_id="agent-race").all()
        assert len(rows) == 1
        assert rows[0].status == "stopped"
        assert rows[0].error == "crash"

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


class TestWatcherRegistryFactory:
    def test_registry_accepts_make_credentials_store(self):
        from api.services.watcher_registry import WatcherRegistry

        def _factory():
            store = MagicMock()
            store.db_session = MagicMock()
            return store

        registry = WatcherRegistry(get_db_session=MagicMock(), make_credentials_store=_factory)
        assert registry.make_credentials_store is _factory
        assert registry.credentials_store is None

    def test_registry_raises_without_any_store(self):
        from api.services.watcher_registry import WatcherRegistry
        with pytest.raises(ValueError, match="credentials_store"):
            WatcherRegistry(get_db_session=MagicMock())

    def test_registry_still_accepts_legacy_credentials_store(self):
        from api.services.watcher_registry import WatcherRegistry
        mock_store = MagicMock()
        registry = WatcherRegistry(get_db_session=MagicMock(), credentials_store=mock_store)
        assert registry.credentials_store is mock_store
        assert registry.make_credentials_store is None


class TestAdminWatchersRouterLogic:
    @pytest.mark.asyncio
    async def test_start_watcher_writes_desired_running(self, db_session):
        from api.routers.admin_watchers import start_watcher
        from api.repositories.watcher_coordination_repository import WatcherControlRepository
        from api.repositories import CredentialRepository
        mock_user = SimpleNamespace(id=1, role="admin", company_id=1)
        mock_creds = SimpleNamespace(id=10, company_id=1)
        with patch.object(CredentialRepository, "get_by_agent_id", return_value=mock_creds):
            with patch("api.routers.admin_watchers.record_audit_log"):
                resp = await start_watcher(agent_id="agent-1", db=db_session, current_user=mock_user)
        assert resp.agent_id == "agent-1"
        assert "requested" in resp.message.lower()
        row = WatcherControlRepository(db_session).get("agent-1")
        assert row is not None and row.desired_status == "running"

    @pytest.mark.asyncio
    async def test_start_watcher_idempotent(self, db_session):
        from api.routers.admin_watchers import start_watcher
        from api.repositories import CredentialRepository
        from api.models.watcher_state_models import WatcherControl
        mock_user = SimpleNamespace(id=1, role="admin", company_id=1)
        mock_creds = SimpleNamespace(id=10, company_id=1)
        with patch.object(CredentialRepository, "get_by_agent_id", return_value=mock_creds):
            with patch("api.routers.admin_watchers.record_audit_log"):
                await start_watcher(agent_id="agent-idem", db=db_session, current_user=mock_user)
                await start_watcher(agent_id="agent-idem", db=db_session, current_user=mock_user)
        assert db_session.query(WatcherControl).filter_by(agent_id="agent-idem").count() == 1

    @pytest.mark.asyncio
    async def test_stop_watcher_writes_desired_stopped(self, db_session):
        from api.routers.admin_watchers import stop_watcher
        from api.repositories.watcher_coordination_repository import WatcherControlRepository
        from api.repositories import CredentialRepository
        mock_user = SimpleNamespace(id=1, role="admin", company_id=1)
        mock_creds = SimpleNamespace(id=10, company_id=1)
        with patch.object(CredentialRepository, "get_by_agent_id", return_value=mock_creds):
            with patch("api.routers.admin_watchers.record_audit_log"):
                resp = await stop_watcher(agent_id="agent-1", db=db_session, current_user=mock_user)
        assert resp.status == "stopping"
        row = WatcherControlRepository(db_session).get("agent-1")
        assert row is not None and row.desired_status == "stopped"

    @pytest.mark.asyncio
    async def test_trigger_sync_sets_sync_requested_at(self, db_session):
        from api.routers.admin_watchers import trigger_sync
        from api.repositories.watcher_coordination_repository import WatcherControlRepository
        from api.repositories import CredentialRepository
        mock_user = SimpleNamespace(id=1, role="admin", company_id=1)
        mock_creds = SimpleNamespace(id=10, company_id=1)
        with patch.object(CredentialRepository, "get_by_agent_id", return_value=mock_creds):
            with patch("api.routers.admin_watchers.record_audit_log"):
                resp = await trigger_sync(agent_id="agent-1", db=db_session, current_user=mock_user)
        assert resp.sync_triggered is True
        row = WatcherControlRepository(db_session).get("agent-1")
        assert row is not None and row.sync_requested_at is not None

    @pytest.mark.asyncio
    async def test_status_endpoint_reads_from_db(self, db_session):
        from api.routers.admin_watchers import get_all_watcher_statuses
        from api.repositories.watcher_coordination_repository import WatcherStatusRepository
        WatcherStatusRepository(db_session).upsert(
            "agent-42", status="running",
            last_heartbeat=datetime.utcnow(), last_sync=datetime.utcnow(),
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
                await start_watcher(agent_id="unknown-agent", db=db_session, current_user=mock_user)


class TestWorkerReconciliation:
    def test_reconcile_starts_watcher_when_desired_running(self, db_session):
        from api.repositories.watcher_coordination_repository import WatcherControlRepository
        from api.services.watcher_registry import WatcherStatus as WS
        from worker.main import _reconcile_sync
        WatcherControlRepository(db_session).set_desired_status("agent-10", "running")
        mock_registry = MagicMock()
        mock_registry._watchers = {}
        future = MagicMock()
        future.result.return_value = True
        with patch("asyncio.run_coroutine_threadsafe", return_value=future) as mock_rctf:
            with patch("asyncio.get_event_loop"):
                _reconcile_sync(mock_registry, lambda: db_session)
        calls = [str(c) for c in mock_rctf.call_args_list]
        assert any("start_watcher" in c for c in calls)

    def test_reconcile_stops_watcher_when_desired_stopped(self, db_session):
        from api.repositories.watcher_coordination_repository import WatcherControlRepository
        from api.services.watcher_registry import WatcherStatus as WS
        from worker.main import _reconcile_sync
        WatcherControlRepository(db_session).set_desired_status("agent-11", "stopped")
        mock_info = MagicMock()
        mock_info.status = WS.RUNNING
        mock_info.last_heartbeat = mock_info.last_sync = mock_info.started_at = mock_info.error = None
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
        from api.repositories.watcher_coordination_repository import WatcherControlRepository
        from api.services.watcher_registry import WatcherStatus as WS
        from worker.main import _reconcile_sync
        ctrl_repo = WatcherControlRepository(db_session)
        ctrl_repo.set_desired_status("agent-12", "running")
        ctrl_repo.request_sync("agent-12")
        mock_info = MagicMock()
        mock_info.status = WS.RUNNING
        mock_info.last_heartbeat = mock_info.last_sync = mock_info.started_at = mock_info.error = None
        mock_registry = MagicMock()
        mock_registry._watchers = {"agent-12": mock_info}
        future = MagicMock()
        future.result.return_value = True
        with patch("asyncio.run_coroutine_threadsafe", return_value=future):
            with patch("asyncio.get_event_loop"):
                _reconcile_sync(mock_registry, lambda: db_session)
        assert ctrl_repo.get("agent-12").sync_requested_at is None

    def test_reconcile_writes_status_to_db(self, db_session):
        from api.repositories.watcher_coordination_repository import WatcherStatusRepository
        from api.services.watcher_registry import WatcherStatus as WS
        from worker.main import _reconcile_sync
        now = datetime.utcnow()
        mock_info = MagicMock()
        mock_info.status = WS.RUNNING
        mock_info.last_heartbeat = mock_info.last_sync = mock_info.started_at = now
        mock_info.error = None
        mock_registry = MagicMock()
        mock_registry._watchers = {"agent-20": mock_info}
        with patch("asyncio.run_coroutine_threadsafe"):
            with patch("asyncio.get_event_loop"):
                _reconcile_sync(mock_registry, lambda: db_session)
        row = WatcherStatusRepository(db_session).get("agent-20")
        assert row is not None and row.status == "running"

    def test_reconcile_status_upsert_idempotent(self, db_session):
        """Running reconcile twice must not create duplicate status rows."""
        from api.services.watcher_registry import WatcherStatus as WS
        from api.models.watcher_state_models import WatcherStatus as WatcherStatusModel
        from worker.main import _reconcile_sync
        now = datetime.utcnow()
        mock_info = MagicMock()
        mock_info.status = WS.RUNNING
        mock_info.last_heartbeat = mock_info.last_sync = mock_info.started_at = now
        mock_info.error = None
        mock_registry = MagicMock()
        mock_registry._watchers = {"agent-idem-status": mock_info}
        for _ in range(2):
            with patch("asyncio.run_coroutine_threadsafe"):
                with patch("asyncio.get_event_loop"):
                    _reconcile_sync(mock_registry, lambda: db_session)
        count = db_session.query(WatcherStatusModel).filter_by(agent_id="agent-idem-status").count()
        assert count == 1
