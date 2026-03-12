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


    def list_with_filters(
        self,
        *,
        agent_id: Optional[str] = None,
        company_agent_ids: Optional[list[str]] = None,
        start_date: Optional["datetime"] = None,
        end_date: Optional["datetime"] = None,
        response_sent: Optional[bool] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[list[Lead], int]:
        """Return (leads, total_count) with optional filters — admin use only.

        Supports filtering by agent_id, a list of agent_ids (for company filter),
        date range, and response_sent status.
        """
        query = self._db.query(Lead)

        if agent_id:
            query = query.filter(Lead.agent_id == agent_id)
        if company_agent_ids is not None:
            query = query.filter(Lead.agent_id.in_(company_agent_ids))
        if start_date is not None:
            query = query.filter(Lead.created_at >= start_date)
        if end_date is not None:
            query = query.filter(Lead.created_at <= end_date)
        if response_sent is not None:
            query = query.filter(Lead.response_sent == response_sent)

        total = query.count()
        leads = query.order_by(Lead.created_at.desc()).offset(skip).limit(limit).all()
        return leads, total

    def get_by_agent_id_str(self, lead_id: int) -> Optional[Lead]:
        """Return a lead by primary key without tenant scoping — admin use only."""
        return self._db.query(Lead).filter(Lead.id == lead_id).first()

    def list_for_tenant_filtered(
        self,
        tenant_id: int,
        *,
        start_date: Optional["datetime"] = None,
        skip: int = 0,
        limit: int = 0,
    ) -> list[Lead]:
        """Return leads for *tenant_id* with optional date filter — no limit when limit=0."""
        query = (
            self._db.query(Lead)
            .filter(Lead.agent_user_id == tenant_id)
        )
        if start_date is not None:
            query = query.filter(Lead.created_at >= start_date)
        query = query.order_by(Lead.created_at.desc())
        if limit > 0:
            query = query.offset(skip).limit(limit)
        return query.all()

    def get_lead_state_transitions(self, lead_id: int, tenant_id: int) -> list:
        """Return all LeadStateTransition rows for a lead, scoped to tenant.

        Returns transitions ordered by occurred_at ascending (chronological order).
        Returns empty list if the lead doesn't exist or belongs to a different tenant.

        Requirements: 8.7
        """
        from gmail_lead_sync.preapproval.models_preapproval import LeadStateTransition

        # First verify the lead belongs to the tenant
        lead = self.get_by_id(lead_id, tenant_id)
        if lead is None:
            return []

        # Fetch transitions ordered chronologically
        return (
            self._db.query(LeadStateTransition)
            .filter(LeadStateTransition.lead_id == lead_id)
            .order_by(LeadStateTransition.occurred_at.asc())
            .all()
        )


# ---------------------------------------------------------------------------
# Lead event repository (added for router refactoring — task 8.2)
# ---------------------------------------------------------------------------


class LeadEventRepository:
    """Data-access layer for LeadEvent records."""

    def __init__(self, db: Session) -> None:
        self._db = db

    def list_for_agent_in_period(
        self,
        agent_id: int,
        event_type: str,
        lead_ids: set[int],
        start_date: "datetime",
    ) -> list:
        """Return events of *event_type* for *agent_id* within *lead_ids* since *start_date*."""
        from gmail_lead_sync.agent_models import LeadEvent

        if not lead_ids:
            return []
        return (
            self._db.query(LeadEvent)
            .filter(
                LeadEvent.agent_user_id == agent_id,
                LeadEvent.event_type == event_type,
                LeadEvent.created_at >= start_date,
                LeadEvent.lead_id.in_(lead_ids),
            )
            .all()
        )

    def list_by_lead_ids_and_type(
        self, lead_ids: list[int], event_type: str
    ) -> list:
        """Return events of *event_type* for the given *lead_ids*."""
        from gmail_lead_sync.agent_models import LeadEvent

        if not lead_ids:
            return []
        return (
            self._db.query(LeadEvent)
            .filter(
                LeadEvent.lead_id.in_(lead_ids),
                LeadEvent.event_type == event_type,
            )
            .all()
        )


    def list_for_tenant_with_filters(
        self,
        tenant_id: int,
        *,
        bucket: Optional[str] = None,
        status: Optional[str] = None,
        search: Optional[str] = None,
    ) -> list[Lead]:
        """Return all leads for *tenant_id* with optional bucket/status/search filters.

        Returns all matching leads (no pagination) for Python-side sorting.
        """
        query = self._db.query(Lead).filter(Lead.agent_user_id == tenant_id)

        if bucket and bucket.upper() != "ALL":
            query = query.filter(Lead.score_bucket == bucket.upper())
        if status and status.upper() != "ALL":
            query = query.filter(Lead.agent_current_state == status.upper())
        if search and search.strip():
            term = f"%{search.strip()}%"
            query = query.filter(
                Lead.name.ilike(term)
                | Lead.property_address.ilike(term)
                | Lead.lead_source_name.ilike(term)
            )

        return query.all()


class LeadEventWriteRepository:
    """Write-side repository for LeadEvent records."""

    def __init__(self, db: "Session") -> None:
        self._db = db

    def list_for_lead(self, lead_id: int) -> list:
        """Return all events for *lead_id* ordered by created_at ASC."""
        from gmail_lead_sync.agent_models import LeadEvent

        return (
            self._db.query(LeadEvent)
            .filter(LeadEvent.lead_id == lead_id)
            .order_by(LeadEvent.created_at.asc())
            .all()
        )

    def create(
        self,
        lead_id: int,
        agent_user_id: int,
        event_type: str,
        payload: Optional[str],
        created_at: "datetime",
    ):
        """Create and persist a new LeadEvent."""
        from gmail_lead_sync.agent_models import LeadEvent

        event = LeadEvent(
            lead_id=lead_id,
            agent_user_id=agent_user_id,
            event_type=event_type,
            payload=payload,
            created_at=created_at,
        )
        self._db.add(event)
        self._db.commit()
        self._db.refresh(event)
        return event

    def update_agent_state(
        self,
        lead_id: int,
        tenant_id: int,
        new_state: str,
        last_action_at: Optional["datetime"] = None,
    ) -> Optional[Lead]:
        """Update the agent_current_state (and optionally last_agent_action_at) for a lead.

        Returns the updated lead, or ``None`` if not found / wrong tenant.
        """
        lead = self.get_by_id(lead_id, tenant_id)
        if lead is None:
            return None

        lead.agent_current_state = new_state
        if last_action_at is not None:
            lead.last_agent_action_at = last_action_at

        self._db.commit()
        self._db.refresh(lead)
        return lead
