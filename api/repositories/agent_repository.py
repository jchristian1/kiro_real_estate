"""
Agent repository — all SQLAlchemy queries for the AgentUser domain.

Agents are top-level entities (not tenant-scoped), so no agent_id filter
is applied here.  RBAC enforcement is the responsibility of the router layer.

Requirements: 7.1, 7.2
"""

from typing import Optional

from pydantic import BaseModel
from sqlalchemy.orm import Session

from gmail_lead_sync.agent_models import AgentUser
from datetime import datetime


# ---------------------------------------------------------------------------
# Data transfer objects (no FastAPI imports — framework-agnostic)
# ---------------------------------------------------------------------------


class AgentCreate(BaseModel):
    """Fields required to create a new agent user."""

    email: str
    password_hash: str
    full_name: str
    phone: Optional[str] = None
    timezone: str = "UTC"
    service_area: Optional[str] = None
    company_id: Optional[int] = None
    role: str = "agent"


class AgentUpdate(BaseModel):
    """Fields that may be updated on an existing agent user."""

    full_name: Optional[str] = None
    phone: Optional[str] = None
    timezone: Optional[str] = None
    service_area: Optional[str] = None
    company_id: Optional[int] = None
    onboarding_completed: Optional[bool] = None
    onboarding_step: Optional[int] = None
    role: Optional[str] = None


# ---------------------------------------------------------------------------
# Repository
# ---------------------------------------------------------------------------


class AgentRepository:
    """Data-access layer for AgentUser records.

    Agents are platform-level entities — no tenant scoping is applied.
    """

    def __init__(self, db: Session) -> None:
        self._db = db

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def get_by_id(self, agent_id: int) -> Optional[AgentUser]:
        """Return the agent with the given primary key, or ``None``."""
        return self._db.query(AgentUser).filter(AgentUser.id == agent_id).first()

    def get_by_email(self, email: str) -> Optional[AgentUser]:
        """Return the agent with the given email address, or ``None``."""
        return self._db.query(AgentUser).filter(AgentUser.email == email).first()

    def list_all(self, *, skip: int = 0, limit: int = 50) -> list[AgentUser]:
        """Return a paginated list of all agent users."""
        return (
            self._db.query(AgentUser)
            .order_by(AgentUser.created_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    def create(self, data: AgentCreate) -> AgentUser:
        """Create and persist a new agent user."""
        agent = AgentUser(
            email=data.email,
            password_hash=data.password_hash,
            full_name=data.full_name,
            phone=data.phone,
            timezone=data.timezone,
            service_area=data.service_area,
            company_id=data.company_id,
            role=data.role,
        )
        self._db.add(agent)
        self._db.commit()
        self._db.refresh(agent)
        return agent

    def delete(self, agent_id: int) -> bool:
        """Delete an agent user by primary key.

        Returns ``True`` if deleted, ``False`` if not found.
        """
        agent = self.get_by_id(agent_id)
        if agent is None:
            return False
        self._db.delete(agent)
        self._db.commit()
        return True

    def update(self, agent_id: int, data: AgentUpdate) -> Optional[AgentUser]:
        """Update an agent user.

        Returns the updated agent, or ``None`` if not found.
        """
        agent = self.get_by_id(agent_id)
        if agent is None:
            return None

        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(agent, field, value)

        self._db.commit()
        self._db.refresh(agent)
        return agent

    def create_with_duplicate_check(
        self, email: str, password_hash: str, full_name: str
    ) -> tuple[Optional[AgentUser], bool]:
        """Create a new agent user, returning (agent_user, created).

        Returns (agent_user, True) on success.
        Returns (None, False) if the email already exists (IntegrityError).
        """
        from sqlalchemy.exc import IntegrityError

        agent_user = AgentUser(
            email=email,
            password_hash=password_hash,
            full_name=full_name,
            onboarding_step=0,
            onboarding_completed=False,
            created_at=datetime.utcnow(),
        )
        self._db.add(agent_user)
        try:
            self._db.flush()
        except IntegrityError:
            self._db.rollback()
            return None, False

        self._db.commit()
        self._db.refresh(agent_user)
        return agent_user, True

    def update_profile(
        self,
        agent: AgentUser,
        full_name: str,
        phone: Optional[str],
        timezone: str,
        service_area: Optional[str],
        company_id: Optional[int] = None,
    ) -> AgentUser:
        """Persist profile fields on *agent* and advance onboarding_step to at least 2."""
        agent.full_name = full_name
        agent.phone = phone
        agent.timezone = timezone if timezone else "UTC"
        agent.service_area = service_area
        if company_id is not None:
            agent.company_id = company_id
        if agent.onboarding_step < 2:
            agent.onboarding_step = 2
        self._db.commit()
        self._db.refresh(agent)
        return agent

    def advance_onboarding_step(self, agent: AgentUser, step: int) -> AgentUser:
        """Advance *agent.onboarding_step* to *step* if currently less than *step*."""
        if agent.onboarding_step < step:
            agent.onboarding_step = step
        self._db.commit()
        self._db.refresh(agent)
        return agent

    def complete_onboarding(self, agent: AgentUser) -> AgentUser:
        """Mark *agent* as onboarding_completed and commit."""
        agent.onboarding_completed = True
        self._db.commit()
        self._db.refresh(agent)
        return agent


# ---------------------------------------------------------------------------
# Session repository methods (added for router refactoring — task 8.2)
# ---------------------------------------------------------------------------


class AgentSessionRepository:
    """Data-access layer for AgentSession records."""

    def __init__(self, db: Session) -> None:
        self._db = db

    def get_valid_session(self, token: str) -> Optional["AgentSession"]:
        """Return a non-expired session by token, or ``None``."""
        from datetime import datetime
        from gmail_lead_sync.agent_models import AgentSession

        now = datetime.utcnow()
        return (
            self._db.query(AgentSession)
            .filter(AgentSession.id == token, AgentSession.expires_at > now)
            .first()
        )

    def create_session(self, agent_user_id: int, token: str, expires_at: "datetime") -> "AgentSession":
        """Create and persist a new session."""
        from datetime import datetime
        from gmail_lead_sync.agent_models import AgentSession

        now = datetime.utcnow()
        session = AgentSession(
            id=token,
            agent_user_id=agent_user_id,
            created_at=now,
            expires_at=expires_at,
            last_accessed=now,
        )
        self._db.add(session)
        self._db.commit()
        self._db.refresh(session)
        return session

    def delete_session(self, token: str) -> None:
        """Delete a session by token (logout)."""
        from gmail_lead_sync.agent_models import AgentSession

        self._db.query(AgentSession).filter(AgentSession.id == token).delete()
        self._db.commit()

    def get_agent_by_id(self, agent_user_id: int) -> Optional[AgentUser]:
        """Return the AgentUser for a session's agent_user_id."""
        return self._db.query(AgentUser).filter(AgentUser.id == agent_user_id).first()
