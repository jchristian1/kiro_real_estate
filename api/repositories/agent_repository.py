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
