"""
Lead repository — all SQLAlchemy queries for the Lead domain.

Tenant isolation is enforced at the query level: every tenant-scoped method
filters by agent_user_id derived from the authenticated session, never from
user-supplied request parameters.

Requirements: 6.1, 7.1, 7.2
"""

from typing import Optional
from datetime import datetime

from pydantic import BaseModel
from sqlalchemy.orm import Session

from gmail_lead_sync.models import Lead


# ---------------------------------------------------------------------------
# Data transfer objects (no FastAPI imports — framework-agnostic)
# ---------------------------------------------------------------------------


class LeadCreate(BaseModel):
    """Fields required to create a new lead."""

    name: str
    phone: str
    source_email: str
    lead_source_id: int
    gmail_uid: str
    agent_id: Optional[str] = None


class LeadUpdate(BaseModel):
    """Fields that may be updated on an existing lead."""

    name: Optional[str] = None
    phone: Optional[str] = None
    response_sent: Optional[bool] = None
    response_status: Optional[str] = None
    agent_id: Optional[str] = None


# ---------------------------------------------------------------------------
# Repository
# ---------------------------------------------------------------------------


class LeadRepository:
    """Data-access layer for Lead records.

    All tenant-scoped methods include an ``agent_user_id`` filter derived
    from the caller-supplied ``tenant_id`` argument.  The repository never
    trusts user-supplied IDs embedded in request bodies or path parameters —
    that responsibility belongs to the router/dependency layer.
    """

    def __init__(self, db: Session) -> None:
        self._db = db

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def get_by_id(self, lead_id: int, tenant_id: int) -> Optional[Lead]:
        """Return the lead only if it belongs to *tenant_id*.

        Filters by BOTH ``Lead.id`` AND ``Lead.agent_user_id`` so a tenant
        can never retrieve another tenant's record even if they guess the ID.

        Returns ``None`` when the lead does not exist or belongs to a
        different tenant.
        """
        return (
            self._db.query(Lead)
            .filter(Lead.id == lead_id, Lead.agent_user_id == tenant_id)
            .first()
        )

    def list_for_tenant(
        self, tenant_id: int, *, skip: int = 0, limit: int = 50
    ) -> list[Lead]:
        """Return a paginated list of leads scoped to *tenant_id*."""
        return (
            self._db.query(Lead)
            .filter(Lead.agent_user_id == tenant_id)
            .order_by(Lead.created_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    def list_all_with_tenant(self, *, skip: int = 0, limit: int = 50) -> list[Lead]:
        """Return leads across all tenants — for platform-admin use only.

        The caller is responsible for ensuring the requesting user has the
        ``platform_admin`` role before invoking this method.
        """
        return (
            self._db.query(Lead)
            .order_by(Lead.created_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    def create(self, data: LeadCreate, tenant_id: int) -> Lead:
        """Create a new lead scoped to *tenant_id*.

        The ``agent_user_id`` is always set from the caller-supplied
        ``tenant_id``, never from ``data``.
        """
        lead = Lead(
            name=data.name,
            phone=data.phone,
            source_email=data.source_email,
            lead_source_id=data.lead_source_id,
            gmail_uid=data.gmail_uid,
            agent_id=data.agent_id,
            agent_user_id=tenant_id,
            created_at=datetime.utcnow(),
        )
        self._db.add(lead)
        self._db.commit()
        self._db.refresh(lead)
        return lead

    def update(self, lead_id: int, tenant_id: int, data: LeadUpdate) -> Optional[Lead]:
        """Update a lead after verifying tenant ownership.

        Returns the updated lead, or ``None`` if the lead does not exist or
        belongs to a different tenant.  The tenant check is performed inside
        the query so no data from another tenant is ever loaded.
        """
        lead = self.get_by_id(lead_id, tenant_id)
        if lead is None:
            return None

        update_fields = data.model_dump(exclude_unset=True)
        for field, value in update_fields.items():
            setattr(lead, field, value)

        self._db.commit()
        self._db.refresh(lead)
        return lead
