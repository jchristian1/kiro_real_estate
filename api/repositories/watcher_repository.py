"""
Watcher repository — all SQLAlchemy queries for watcher configuration.

Watcher configuration is stored in AgentPreferences (watcher_enabled,
watcher_admin_override).  All methods are scoped to agent_user_id.

Requirements: 6.4, 7.1, 7.2
"""

from typing import Optional

from pydantic import BaseModel
from sqlalchemy.orm import Session

from gmail_lead_sync.agent_models import AgentPreferences, AgentUser


# ---------------------------------------------------------------------------
# Data transfer objects (no FastAPI imports — framework-agnostic)
# ---------------------------------------------------------------------------


class WatcherConfigUpdate(BaseModel):
    """Fields that control watcher behaviour for an agent."""

    watcher_enabled: Optional[bool] = None
    watcher_admin_override: Optional[bool] = None


# ---------------------------------------------------------------------------
# Repository
# ---------------------------------------------------------------------------


class WatcherRepository:
    """Data-access layer for per-agent watcher configuration.

    Configuration is stored in ``AgentPreferences``.  All methods are
    scoped to ``agent_id`` (the ``AgentUser.id`` primary key).
    """

    def __init__(self, db: Session) -> None:
        self._db = db

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def get_config_by_agent_id(self, agent_id: int) -> Optional[AgentPreferences]:
        """Return the watcher config (AgentPreferences) for *agent_id*.

        Returns ``None`` if no preferences record exists for this agent.
        """
        return (
            self._db.query(AgentPreferences)
            .filter(AgentPreferences.agent_user_id == agent_id)
            .first()
        )

    def list_all(self, *, skip: int = 0, limit: int = 50) -> list[AgentPreferences]:
        """Return a paginated list of all agent watcher configs.

        For platform-admin use only — the caller is responsible for
        verifying the requesting user has the ``platform_admin`` role.
        """
        return (
            self._db.query(AgentPreferences)
            .join(AgentUser, AgentPreferences.agent_user_id == AgentUser.id)
            .order_by(AgentPreferences.agent_user_id)
            .offset(skip)
            .limit(limit)
            .all()
        )

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    def upsert_config(
        self, agent_id: int, data: WatcherConfigUpdate
    ) -> AgentPreferences:
        """Create or update the watcher config for *agent_id*.

        If no ``AgentPreferences`` row exists for this agent, one is created
        with default values before applying the update.  The ``agent_user_id``
        is always set from the caller-supplied ``agent_id``.
        """
        prefs = self.get_config_by_agent_id(agent_id)
        if prefs is None:
            prefs = AgentPreferences(agent_user_id=agent_id)
            self._db.add(prefs)

        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(prefs, field, value)

        self._db.commit()
        self._db.refresh(prefs)
        return prefs


# ---------------------------------------------------------------------------
# Preferences repository (added for router refactoring — task 8.2)
# ---------------------------------------------------------------------------


class AgentPreferencesRepository:
    """Data-access layer for AgentPreferences records."""

    def __init__(self, db: Session) -> None:
        self._db = db

    def get_or_create(self, agent_id: int) -> AgentPreferences:
        """Return existing preferences or create a new record for *agent_id*."""
        from datetime import datetime

        prefs = (
            self._db.query(AgentPreferences)
            .filter(AgentPreferences.agent_user_id == agent_id)
            .first()
        )
        if prefs is None:
            prefs = AgentPreferences(
                agent_user_id=agent_id,
                created_at=datetime.utcnow(),
            )
            self._db.add(prefs)
            self._db.flush()
        return prefs

    def get_config_by_agent_id(self, agent_id: int) -> Optional[AgentPreferences]:
        """Return preferences for *agent_id*, or None if not found."""
        return (
            self._db.query(AgentPreferences)
            .filter(AgentPreferences.agent_user_id == agent_id)
            .first()
        )

    def save(self, prefs: AgentPreferences) -> AgentPreferences:
        """Commit pending changes to *prefs* and return the refreshed record."""
        self._db.commit()
        self._db.refresh(prefs)
        return prefs
