"""
PostgreSQL watcher coordination upsert tests — Phase 6C.

Validates that the dialect-aware INSERT ... ON CONFLICT DO UPDATE upserts
in WatcherControlRepository and WatcherStatusRepository behave correctly
on a real Postgres instance.

These tests mirror tests/unit/test_watcher_coordination.py but run against
Postgres instead of SQLite, exercising the `pg_insert` code path that was
previously untested.

Run:
    export POSTGRES_TEST_URL=postgresql://user:pass@localhost:5432/test_db
    pytest tests/postgres/test_pg_watcher_coordination.py -v

Skipped automatically when POSTGRES_TEST_URL is not set.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta

import pytest

pytestmark = pytest.mark.postgres


def _uid() -> str:
    return f"agent_{uuid.uuid4().hex[:12]}"


class TestPgWatcherControlRepository:
    """WatcherControlRepository upserts on real Postgres."""

    def test_set_desired_status_creates_row(self, pg_session):
        from api.repositories.watcher_coordination_repository import WatcherControlRepository
        repo = WatcherControlRepository(pg_session)
        agent_id = _uid()
        row = repo.set_desired_status(agent_id, "running")
        assert row.agent_id == agent_id
        assert row.desired_status == "running"

    def test_set_desired_status_upserts_not_duplicates(self, pg_session):
        """ON CONFLICT DO UPDATE must produce exactly one row."""
        from api.repositories.watcher_coordination_repository import WatcherControlRepository
        from api.models.watcher_state_models import WatcherControl
        repo = WatcherControlRepository(pg_session)
        agent_id = _uid()
        repo.set_desired_status(agent_id, "running")
        repo.set_desired_status(agent_id, "stopped")
        count = pg_session.query(WatcherControl).filter_by(agent_id=agent_id).count()
        assert count == 1

    def test_set_desired_status_last_write_wins(self, pg_session):
        """Second write must overwrite desired_status."""
        from api.repositories.watcher_coordination_repository import WatcherControlRepository
        repo = WatcherControlRepository(pg_session)
        agent_id = _uid()
        repo.set_desired_status(agent_id, "running")
        row = repo.set_desired_status(agent_id, "stopped")
        assert row.desired_status == "stopped"

    def test_request_sync_sets_timestamp(self, pg_session):
        from api.repositories.watcher_coordination_repository import WatcherControlRepository
        repo = WatcherControlRepository(pg_session)
        agent_id = _uid()
        before = datetime.utcnow() - timedelta(seconds=1)
        row = repo.request_sync(agent_id)
        assert row.sync_requested_at is not None
        assert row.sync_requested_at >= before

    def test_request_sync_preserves_desired_status(self, pg_session):
        """request_sync must not overwrite an existing desired_status."""
        from api.repositories.watcher_coordination_repository import WatcherControlRepository
        repo = WatcherControlRepository(pg_session)
        agent_id = _uid()
        repo.set_desired_status(agent_id, "stopped")
        row = repo.request_sync(agent_id)
        assert row.desired_status == "stopped"
        assert row.sync_requested_at is not None

    def test_request_sync_idempotent(self, pg_session):
        """Two request_sync calls must not create two rows."""
        from api.repositories.watcher_coordination_repository import WatcherControlRepository
        from api.models.watcher_state_models import WatcherControl
        repo = WatcherControlRepository(pg_session)
        agent_id = _uid()
        repo.request_sync(agent_id)
        repo.request_sync(agent_id)
        count = pg_session.query(WatcherControl).filter_by(agent_id=agent_id).count()
        assert count == 1

    def test_clear_sync_request_nulls_timestamp(self, pg_session):
        from api.repositories.watcher_coordination_repository import WatcherControlRepository
        repo = WatcherControlRepository(pg_session)
        agent_id = _uid()
        repo.request_sync(agent_id)
        repo.clear_sync_request(agent_id)
        row = repo.get(agent_id)
        assert row.sync_requested_at is None

    def test_list_all_returns_multiple_rows(self, pg_session):
        from api.repositories.watcher_coordination_repository import WatcherControlRepository
        repo = WatcherControlRepository(pg_session)
        ids = [_uid() for _ in range(3)]
        for aid in ids:
            repo.set_desired_status(aid, "running")
        rows = repo.list_all()
        found = {r.agent_id for r in rows}
        assert set(ids) <= found


class TestPgWatcherStatusRepository:
    """WatcherStatusRepository upserts on real Postgres."""

    def test_upsert_creates_row(self, pg_session):
        from api.repositories.watcher_coordination_repository import WatcherStatusRepository
        repo = WatcherStatusRepository(pg_session)
        agent_id = _uid()
        now = datetime.utcnow()
        row = repo.upsert(agent_id, status="running", last_heartbeat=now)
        assert row.agent_id == agent_id
        assert row.status == "running"

    def test_upsert_does_not_duplicate(self, pg_session):
        """ON CONFLICT DO UPDATE must produce exactly one row."""
        from api.repositories.watcher_coordination_repository import WatcherStatusRepository
        from api.models.watcher_state_models import WatcherStatus
        repo = WatcherStatusRepository(pg_session)
        agent_id = _uid()
        repo.upsert(agent_id, status="running")
        repo.upsert(agent_id, status="stopped", error="crash")
        count = pg_session.query(WatcherStatus).filter_by(agent_id=agent_id).count()
        assert count == 1

    def test_upsert_last_write_wins(self, pg_session):
        from api.repositories.watcher_coordination_repository import WatcherStatusRepository
        repo = WatcherStatusRepository(pg_session)
        agent_id = _uid()
        repo.upsert(agent_id, status="running")
        row = repo.upsert(agent_id, status="stopped", error="timeout")
        assert row.status == "stopped"
        assert row.error == "timeout"

    def test_upsert_idempotent_same_status(self, pg_session):
        """Writing the same status twice must not create two rows."""
        from api.repositories.watcher_coordination_repository import WatcherStatusRepository
        from api.models.watcher_state_models import WatcherStatus
        repo = WatcherStatusRepository(pg_session)
        agent_id = _uid()
        repo.upsert(agent_id, status="running")
        repo.upsert(agent_id, status="running")
        count = pg_session.query(WatcherStatus).filter_by(agent_id=agent_id).count()
        assert count == 1

    def test_get_returns_none_for_unknown(self, pg_session):
        from api.repositories.watcher_coordination_repository import WatcherStatusRepository
        repo = WatcherStatusRepository(pg_session)
        assert repo.get(_uid()) is None

    def test_list_all_returns_multiple_rows(self, pg_session):
        from api.repositories.watcher_coordination_repository import WatcherStatusRepository
        repo = WatcherStatusRepository(pg_session)
        ids = [_uid() for _ in range(3)]
        for aid in ids:
            repo.upsert(aid, status="running")
        rows = repo.list_all()
        found = {r.agent_id for r in rows}
        assert set(ids) <= found
