"""
Worker entry point — standalone watcher runtime.

This process owns the WatcherRegistry and all watcher lifecycle:
  - auto-start on boot for every credentialed agent
  - graceful shutdown on SIGTERM/SIGINT
  - auto-restart of failed watchers (via WatcherRegistry)

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
import os
import signal
import sys

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from api.config import load_config
from api.services.watcher_registry import WatcherRegistry
from gmail_lead_sync.credentials import EncryptedDBCredentialsStore

logger = logging.getLogger("worker")


def _setup_logging(log_level: str) -> None:
    import json
    from datetime import datetime

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


async def run() -> None:
    """Main worker coroutine — runs until SIGTERM/SIGINT."""
    config = load_config()
    _setup_logging(config.log_level)

    logger.info("Worker starting — DATABASE_URL=%s", config.database_url[:40])

    # Build DB session factory
    engine = create_engine(
        config.database_url,
        connect_args={"check_same_thread": False} if "sqlite" in config.database_url else {},
    )
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    # Build credentials store with a fresh short-lived session (not held forever)
    def _make_credentials_store():
        db = SessionLocal()
        return EncryptedDBCredentialsStore(db, encryption_key=config.encryption_key), db

    creds_store, creds_db = _make_credentials_store()

    registry = WatcherRegistry(
        get_db_session=SessionLocal,
        credentials_store=creds_store,
    )

    # Graceful shutdown on SIGTERM / SIGINT
    stop_event = asyncio.Event()

    def _handle_signal(sig):
        logger.info("Worker received signal %s — shutting down", sig.name)
        stop_event.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, _handle_signal, sig)

    # Auto-start watchers
    try:
        await _auto_start_watchers(registry, SessionLocal)
    except Exception as exc:
        logger.warning("Auto-start watchers failed: %s", exc)

    logger.info("Worker running — waiting for shutdown signal")
    await stop_event.wait()

    # Graceful shutdown
    logger.info("Worker shutting down — stopping all watchers")
    try:
        await registry.stop_all()
    except Exception as exc:
        logger.error("Error stopping watchers during shutdown: %s", exc, exc_info=True)
    finally:
        try:
            creds_db.close()
        except Exception:
            pass

    logger.info("Worker stopped")


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()
