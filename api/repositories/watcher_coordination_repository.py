"""
Repository for DB-backed watcher coordination (Phase 5C).

Two responsibilities:
  - WatcherControlRepository: API writes desired state; worker reads it
  - WatcherStatusRepository:  Worker writes live status; API reads it

All methods are synchronous SQLAlchemy — called from both the sync API
layer and the worker's asyncio.to_thread() reconciliation loop.

Phase 6B: write paths use dialect-aware upserts (INSERT ... ON CONFLICT DO UPDATE)
so they are safe under PostgreSQL concurrency with multiple API workers.
SQLite 3.24+ supports the same ON CONFLICT syntax, so a single code path covers
both dialects.
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from api.models.watcher_state_models import WatcherControl, WatcherStatus


def _dialect_name(db: Session) -> str:
    return db.bind.dialect.name if db.bind is not None else db.get_bind().dialect.name


# ---------------------------------------------------------------------------
# Control (desired state) — written by API, read by worker
# ---------------------------------------------------------------------------


class WatcherControlRepository:
    """Read/write the desired watcher state for each agent."""

    def __init__(self, db: Session) -> None:
        self._db = db

    def get(self, agent_id: str) -> Optional[WatcherControl]:
        return (
            self._db.query(WatcherControl)
            .filter(WatcherControl.agent_id == agent_id)
            .first()
        )

    def list_all(self) -> List[WatcherControl]:
        return self._db.query(WatcherControl).all()

    def set_desired_status(self, agent_id: str, desired_status: str) -> WatcherControl:
        """
        Upsert the desired status for an agent ("running" or "stopped").

        Uses INSERT ... ON CONFLICT DO UPDATE so concurrent API workers cannot
        race on the same agent_id row.
        """
        now = datetime.utcnow()
        self._upsert_control(
            agent_id=agent_id,
            desired_status=desired_status,
            updated_at=now,
            # sync_requested_at is not touched — preserve existing value
        )
        return self.get(agent_id)

    def request_sync(self, agent_id: str) -> WatcherControl:
        """
        Set sync_requested_at to now so the worker triggers an immediate sync.

        Uses INSERT ... ON CONFLICT DO UPDATE so concurrent API workers cannot
        race on the same agent_id row.
        """
        now = datetime.utcnow()
        self._upsert_control(
            agent_id=agent_id,
            desired_status="running",  # default for new rows; existing rows keep their value
            sync_requested_at=now,
            updated_at=now,
            preserve_desired_status=True,
        )
        return self.get(agent_id)

    def clear_sync_request(self, agent_id: str) -> None:
        """Worker calls this after acting on a sync request."""
        row = self.get(agent_id)
        if row and row.sync_requested_at is not None:
            row.sync_requested_at = None
            row.updated_at = datetime.utcnow()
            self._db.commit()

    # ------------------------------------------------------------------
    # Internal upsert helper
    # ------------------------------------------------------------------

    def _upsert_control(
        self,
        agent_id: str,
        desired_status: str,
        updated_at: datetime,
        sync_requested_at: Optional[datetime] = None,
        preserve_desired_status: bool = False,
    ) -> None:
        """
        Dialect-aware upsert for watcher_control.

        On INSERT (new row): sets all provided columns.
        On CONFLICT (existing row):
          - always updates updated_at
          - updates sync_requested_at if provided
          - updates desired_status only when preserve_desired_status=False
        """
        dialect = _dialect_name(self._db)

        insert_values: dict = {
            "agent_id": agent_id,
            "desired_status": desired_status,
            "updated_at": updated_at,
        }
        if sync_requested_at is not None:
            insert_values["sync_requested_at"] = sync_requested_at

        # Columns to update on conflict
        update_values: dict = {"updated_at": updated_at}
        if not preserve_desired_status:
            update_values["desired_status"] = desired_status
        if sync_requested_at is not None:
            update_values["sync_requested_at"] = sync_requested_at

        if dialect == "postgresql":
            stmt = (
                pg_insert(WatcherControl)
                .values(**insert_values)
                .on_conflict_do_update(
                    index_elements=["agent_id"],
                    set_=update_values,
                )
            )
        else:
            # SQLite 3.24+ supports the same ON CONFLICT syntax
            stmt = (
                sqlite_insert(WatcherControl)
                .values(**insert_values)
                .on_conflict_do_update(
                    index_elements=["agent_id"],
                    set_=update_values,
                )
            )

        self._db.execute(stmt)
        self._db.commit()


# ---------------------------------------------------------------------------
# Status (live state) — written by worker, read by API
# ---------------------------------------------------------------------------


class WatcherStatusRepository:
    """Read/write the live watcher status for each agent."""

    def __init__(self, db: Session) -> None:
        self._db = db

    def get(self, agent_id: str) -> Optional[WatcherStatus]:
        return (
            self._db.query(WatcherStatus)
            .filter(WatcherStatus.agent_id == agent_id)
            .first()
        )

    def list_all(self) -> List[WatcherStatus]:
        return self._db.query(WatcherStatus).all()

    def upsert(
        self,
        agent_id: str,
        *,
        status: str,
        last_heartbeat: Optional[datetime] = None,
        last_sync: Optional[datetime] = None,
        started_at: Optional[datetime] = None,
        error: Optional[str] = None,
    ) -> WatcherStatus:
        """
        Create or update the live status row for an agent.

        Uses INSERT ... ON CONFLICT DO UPDATE so the worker never races
        with itself if multiple reconciliation cycles overlap.
        """
        now = datetime.utcnow()
        dialect = _dialect_name(self._db)

        insert_values: dict = {
            "agent_id": agent_id,
            "status": status,
            "error": error,
            "updated_at": now,
        }
        if last_heartbeat is not None:
            insert_values["last_heartbeat"] = last_heartbeat
        if last_sync is not None:
            insert_values["last_sync"] = last_sync
        if started_at is not None:
            insert_values["started_at"] = started_at

        # On conflict: update everything that was provided
        update_values: dict = {"status": status, "error": error, "updated_at": now}
        if last_heartbeat is not None:
            update_values["last_heartbeat"] = last_heartbeat
        if last_sync is not None:
            update_values["last_sync"] = last_sync
        if started_at is not None:
            update_values["started_at"] = started_at

        if dialect == "postgresql":
            stmt = (
                pg_insert(WatcherStatus)
                .values(**insert_values)
                .on_conflict_do_update(
                    index_elements=["agent_id"],
                    set_=update_values,
                )
            )
        else:
            stmt = (
                sqlite_insert(WatcherStatus)
                .values(**insert_values)
                .on_conflict_do_update(
                    index_elements=["agent_id"],
                    set_=update_values,
                )
            )

        self._db.execute(stmt)
        self._db.commit()

        # Re-fetch to return the current row (upsert doesn't return ORM objects)
        return self.get(agent_id)
