"""
Worker entry point — standalone watcher runtime.

This process owns the WatcherRegistry and all watcher lifecycle:
  - auto-start on boot for every credentialed agent
  - graceful shutdown on SIGTERM/SIGINT
  - auto-restart of failed watchers (via WatcherRegistry)
  - DB-backed coordination: polls watcher_control, writes watcher_status

It does NOT serve HTTP. It shares the same database as the API process
but owns no in-memory state that the API needs to read directly.

Run:
    python -m worker.main
    # or via docker-entrypoint:
    python worker/main.py

Environment variables (same as API):
    DATABASE_URL, ENCRYPTION_KEY, LOG_LEVEL, ENABLE_AUTO_RESTART
"""

from __future__ import annotations

import asyncio
import logging
import signal
from datetime import datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from api.config import load_config
from api.services.watcher_registry import WatcherRegistry, WatcherStatus
from gmail_lead_sync.credentials import EncryptedDBCredentialsStore

logger = logging.getLogger("worker")

# How often the reconciliation loop polls watcher_control and writes watcher_status
RECONCILE_INTERVAL_SECONDS = 10


def _setup_logging(log_level: str) -> None:
    import json

    class JSONFormatter(logging.Formatter):
        def format(self, record: logging.LogRecord) -> str:
            data = {
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "level": record.levelname,
                "logger": record.name,
                "message": record.getMessage(),
            }
            if record.exc_info:
                data["exception"] = self.formatException(record.exc_info)
            return json.dumps(data)

    handler = logging.StreamHandler()
    handler.setFormatter(JSONFormatter())

    for name in ("worker", "gmail_lead_sync", "api.services.watcher_registry"):
        lg = logging.getLogger(name)
        lg.setLevel(getattr(logging, log_level.upper(), logging.INFO))
        lg.addHandler(handler)
        lg.propagate = False


async def _auto_start_watchers(registry: WatcherRegistry, SessionLocal) -> None:
    """Start a watcher for every agent that has credentials configured."""
    from api.models.web_ui_models import User as _User
    from api.repositories.credential_repository import CredentialRepository

    db = SessionLocal()
    try:
        cred_repo = CredentialRepository(db)

        # Legacy admin-panel agents (users table, role='agent')
        agents = db.query(_User).filter(_User.role == "agent").all()
        for agent in agents:
            agent_id_str = str(agent.id)
            if cred_repo.get_by_agent_id(agent_id_str) is not None:
                started = await registry.start_watcher(agent_id_str)
                if started:
                    logger.info("Auto-started watcher for legacy agent %s", agent_id_str)

        # Agent-app users (agent_users table)
        try:
            from gmail_lead_sync.agent_models import AgentUser as _AgentUser, AgentPreferences as _AgentPrefs
            for au in db.query(_AgentUser).all():
                prefs = db.query(_AgentPrefs).filter(_AgentPrefs.agent_user_id == au.id).first()
                if prefs and not prefs.watcher_enabled:
                    continue
                agent_id_str = str(au.id)
                if cred_repo.get_by_agent_id(agent_id_str) is not None:
                    started = await registry.start_watcher(agent_id_str)
                    if started:
                        logger.info("Auto-started watcher for agent-app user %s", agent_id_str)
        except Exception as exc:
            logger.warning("Could not auto-start agent-app watchers: %s", exc)
    finally:
        db.close()


def _reconcile_sync(registry: WatcherRegistry, SessionLocal, loop) -> None:
    """
    Synchronous reconciliation — called via asyncio.to_thread().

    1. Read watcher_control rows and start/stop watchers to match desired_status.
    2. Act on pending sync requests.
    3. Write current in-memory watcher status back to watcher_status table.

    The event loop is passed in explicitly because this runs in a thread pool
    where asyncio.get_event_loop() is not available.
    """
    import asyncio as _asyncio
    from api.repositories.watcher_coordination_repository import (
        WatcherControlRepository,
        WatcherStatusRepository,
    )

    db = SessionLocal()
    try:
        ctrl_repo = WatcherControlRepository(db)
        status_repo = WatcherStatusRepository(db)

        # --- 1. Reconcile desired state ---
        for ctrl in ctrl_repo.list_all():
            agent_id = ctrl.agent_id
            current = registry._watchers.get(agent_id)
            current_status = current.status if current else None

            if ctrl.desired_status == "running":
                if current_status not in (WatcherStatus.RUNNING, WatcherStatus.STARTING):
                    future = _asyncio.run_coroutine_threadsafe(
                        registry.start_watcher(agent_id), loop
                    )
                    try:
                        started = future.result(timeout=5)
                        if started:
                            logger.info("Reconciler started watcher for agent %s", agent_id)
                    except Exception as exc:
                        logger.warning("Reconciler could not start watcher %s: %s", agent_id, exc)

            elif ctrl.desired_status == "stopped":
                if current_status in (WatcherStatus.RUNNING, WatcherStatus.STARTING):
                    future = _asyncio.run_coroutine_threadsafe(
                        registry.stop_watcher(agent_id), loop
                    )
                    try:
                        future.result(timeout=10)
                        logger.info("Reconciler stopped watcher for agent %s", agent_id)
                    except Exception as exc:
                        logger.warning("Reconciler could not stop watcher %s: %s", agent_id, exc)

            # --- 2. Act on pending sync requests ---
            if ctrl.sync_requested_at is not None:
                future = _asyncio.run_coroutine_threadsafe(
                    registry.trigger_sync(agent_id), loop
                )
                try:
                    triggered = future.result(timeout=5)
                    if triggered:
                        logger.info("Reconciler triggered sync for agent %s", agent_id)
                except Exception as exc:
                    logger.warning("Reconciler could not trigger sync for %s: %s", agent_id, exc)
                ctrl_repo.clear_sync_request(agent_id)

        # --- 3. Write live status to DB ---
        for agent_id, info in registry._watchers.items():
            try:
                status_repo.upsert(
                    agent_id,
                    status=info.status.value,
                    last_heartbeat=info.last_heartbeat,
                    last_sync=info.last_sync,
                    started_at=info.started_at,
                    error=info.error,
                )
            except Exception as exc:
                logger.warning("Could not write status for agent %s: %s", agent_id, exc)

    except Exception as exc:
        logger.warning("Reconciliation cycle failed: %s", exc)
    finally:
        db.close()


async def _reconciliation_loop(
    registry: WatcherRegistry,
    SessionLocal,
    stop_event: asyncio.Event,
) -> None:
    """
    Async loop that runs _reconcile_sync() every RECONCILE_INTERVAL_SECONDS.
    Exits cleanly when stop_event is set.
    """
    logger.info("Reconciliation loop started (interval=%ds)", RECONCILE_INTERVAL_SECONDS)
    loop = asyncio.get_running_loop()
    while not stop_event.is_set():
        try:
            await asyncio.to_thread(_reconcile_sync, registry, SessionLocal, loop)
        except Exception as exc:
            logger.warning("Reconciliation loop error: %s", exc)
        try:
            await asyncio.wait_for(
                asyncio.shield(stop_event.wait()),
                timeout=RECONCILE_INTERVAL_SECONDS,
            )
        except asyncio.TimeoutError:
            pass  # normal — keep looping
    logger.info("Reconciliation loop stopped")


async def run() -> None:
    """Main worker coroutine — runs until SIGTERM/SIGINT."""
    config = load_config()
    _setup_logging(config.log_level)

    logger.info("Worker starting — DATABASE_URL=%s", config.database_url[:40])

    if "sqlite" in config.database_url:
        logger.warning(
            "SQLite detected as the database backend. "
            "SQLite is not safe for multi-process deployments. "
            "The worker and API are both writing to the same SQLite file — "
            "this will cause 'database is locked' errors under any real load. "
            "Set DATABASE_URL to a PostgreSQL connection string."
        )

    # Build DB session factory — dialect-aware pool config.
    # pool_pre_ping prevents stale-connection 500s after a DB restart or
    # network interruption.  pool_recycle avoids hitting server-side
    # idle_in_transaction_session_timeout on long-running worker processes.
    if "sqlite" in config.database_url:
        engine = create_engine(
            config.database_url,
            connect_args={"check_same_thread": False},
        )
    else:
        engine = create_engine(
            config.database_url,
            pool_pre_ping=True,
            pool_recycle=1800,
        )
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    # Phase 6B: use a per-watcher credentials store factory instead of a single
    # long-lived session.  Each watcher task gets its own EncryptedDBCredentialsStore
    # backed by a fresh short-lived session that it owns and closes on exit.
    def _make_credentials_store() -> "EncryptedDBCredentialsStore":
        db = SessionLocal()
        return EncryptedDBCredentialsStore(db, encryption_key=config.encryption_key)

    registry = WatcherRegistry(
        get_db_session=SessionLocal,
        make_credentials_store=_make_credentials_store,
    )

    # Graceful shutdown on SIGTERM / SIGINT
    stop_event = asyncio.Event()

    def _handle_signal(sig):
        logger.info("Worker received signal %s — shutting down", sig.name)
        stop_event.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, _handle_signal, sig)

    # Auto-start watchers from DB state on boot
    try:
        await _auto_start_watchers(registry, SessionLocal)
    except Exception as exc:
        logger.warning("Auto-start watchers failed: %s", exc)

    # Start DB reconciliation loop
    reconcile_task = asyncio.create_task(
        _reconciliation_loop(registry, SessionLocal, stop_event)
    )

    logger.info("Worker running — waiting for shutdown signal")
    await stop_event.wait()

    # Graceful shutdown
    logger.info("Worker shutting down — stopping all watchers")
    reconcile_task.cancel()
    try:
        await reconcile_task
    except asyncio.CancelledError:
        pass

    try:
        await registry.stop_all()
    except Exception as exc:
        logger.error("Error stopping watchers during shutdown: %s", exc, exc_info=True)

    logger.info("Worker stopped")


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()
