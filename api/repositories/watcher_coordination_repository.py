"""
Repository for DB-backed watcher coordination (Phase 5C).

Two responsibilities:
  - WatcherControlRepository: API writes desired state; worker reads it
  - WatcherStatusRepository:  Worker writes live status; API reads it

All methods are synchronous SQLAlchemy — called from both the sync API
layer and the worker's asyncio.to_thread() reconciliation loop.
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from sqlalchemy.orm import Session

from api.models.watcher_state_models import WatcherControl, WatcherStatus


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
        """Upsert the desired status for an agent ("running" or "stopped")."""
        row = self.get(agent_id)
        if row is None:
            row = WatcherControl(agent_id=agent_id)
            self._db.add(row)
        row.desired_status = desired_status
        row.updated_at = datetime.utcnow()
        self._db.commit()
        self._db.refresh(row)
        return row

    def request_sync(self, agent_id: str) -> WatcherControl:
        """Set sync_requested_at to now so the worker triggers an immediate sync."""
        row = self.get(agent_id)
        if row is None:
            row = WatcherControl(agent_id=agent_id, desired_status="running")
            self._db.add(row)
        row.sync_requested_at = datetime.utcnow()
        row.updated_at = datetime.utcnow()
        self._db.commit()
        self._db.refresh(row)
        return row

    def clear_sync_request(self, agent_id: str) -> None:
        """Worker calls this after acting on a sync request."""
        row = self.get(agent_id)
        if row and row.sync_requested_at is not None:
            row.sync_requested_at = None
            row.updated_at = datetime.utcnow()
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
        """Create or update the live status row for an agent."""
        row = self.get(agent_id)
        if row is None:
            row = WatcherStatus(agent_id=agent_id)
            self._db.add(row)
        row.status = status
        if last_heartbeat is not None:
            row.last_heartbeat = last_heartbeat
        if last_sync is not None:
            row.last_sync = last_sync
        if started_at is not None:
            row.started_at = started_at
        row.error = error
        row.updated_at = datetime.utcnow()
        self._db.commit()
        self._db.refresh(row)
        return row
