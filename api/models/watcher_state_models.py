"""
SQLAlchemy models for DB-backed watcher coordination (Phase 5C).

Two tables:
  watcher_control  — API writes desired state; worker reads and reconciles
  watcher_status   — Worker writes live status; API reads for status endpoints

Design principles:
  - API expresses intent (desired_status, sync_requested_at)
  - Worker reconciles intent against running state
  - Status is eventually-consistent (worker heartbeat every ~10s)
  - No Redis, no queues — DB is the coordination bus
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, String, Text
from sqlalchemy.orm import declarative_base

from gmail_lead_sync.models import Base


class WatcherControl(Base):
    """
    Desired-state record written by the API process.

    The worker polls this table and starts/stops watchers to match
    ``desired_status``.  When ``sync_requested_at`` is newer than the
    worker's last-seen value for this agent, the worker triggers an
    immediate sync cycle.

    One row per agent_id.  Upserted by the API on every control action.
    """

    __tablename__ = "watcher_control"

    id = Column(Integer, primary_key=True)
    agent_id = Column(String(64), nullable=False, unique=True, index=True)

    # "running" | "stopped"
    desired_status = Column(String(16), nullable=False, default="running")

    # Set to utcnow() by the API when a manual sync is requested.
    # Worker clears this (sets to NULL) after acting on it.
    sync_requested_at = Column(DateTime, nullable=True)

    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class WatcherStatus(Base):
    """
    Live status written by the worker process.

    The API reads this table to serve the /watchers/status endpoint.
    One row per agent_id.  Upserted by the worker on every heartbeat.
    """

    __tablename__ = "watcher_status"

    id = Column(Integer, primary_key=True)
    agent_id = Column(String(64), nullable=False, unique=True, index=True)

    # "running" | "stopped" | "failed" | "starting"
    status = Column(String(16), nullable=False, default="stopped")

    last_heartbeat = Column(DateTime, nullable=True)
    last_sync = Column(DateTime, nullable=True)
    started_at = Column(DateTime, nullable=True)
    error = Column(Text, nullable=True)

    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow)
