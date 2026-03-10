"""
Agent leads inbox route.

Provides:
- GET /api/v1/agent/leads — urgency-sorted lead list with filters, aging
  annotation, and pagination at 25 leads per page.

Requirements: 11.1, 11.2, 11.3, 11.4, 11.5, 11.6, 11.7
"""

import math
from datetime import datetime, timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from api.dependencies.agent_auth import get_current_agent
from api.main import get_db
from gmail_lead_sync.agent_models import AgentPreferences, AgentUser
from gmail_lead_sync.models import Lead

router = APIRouter(prefix="/agent", tags=["Agent Leads"])

PAGE_SIZE = 25

# Urgency sort key: HOT=0, WARM=1, NURTURE=2, None/unknown=3
_BUCKET_ORDER = {"HOT": 0, "WARM": 1, "NURTURE": 2}


# ---------------------------------------------------------------------------
# Pydantic response models
# ---------------------------------------------------------------------------


class LeadCard(BaseModel):
    """A single lead entry in the leads inbox response."""

    id: int
    name: str
    score: Optional[int]
    score_bucket: Optional[str]
    current_state: Optional[str]
    source: Optional[str]
    address: Optional[str]
    created_at: datetime
    last_agent_action_at: Optional[datetime]
    is_aging: bool


class LeadsResponse(BaseModel):
    """GET /agent/leads response."""

    leads: List[LeadCard]
    total: int
    page: int
    page_size: int
    total_pages: int


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------


@router.get(
    "/leads",
    response_model=LeadsResponse,
    summary="Agent leads inbox — urgency sort, filters, aging annotation, pagination",
)
def get_leads(
    bucket: Optional[str] = Query(
        default=None,
        description="Filter by score bucket: HOT, WARM, or NURTURE",
    ),
    status: Optional[str] = Query(
        default=None,
        description=(
            "Filter by agent state: NEW, CONTACTED, APPOINTMENT_SET, LOST, or CLOSED"
        ),
    ),
    search: Optional[str] = Query(
        default=None,
        description="Search term matched against name, property_address, lead_source_name",
    ),
    page: int = Query(default=1, ge=1, description="Page number (1-indexed)"),
    db: Session = Depends(get_db),
    agent: AgentUser = Depends(get_current_agent),
):
    """
    Return a paginated, urgency-sorted list of leads for the authenticated agent.

    Sorting (Requirement 11.1):
      HOT leads first, then WARM, then NURTURE.  Within each bucket leads are
      ordered by created_at DESC (newest first).

    Filters (Requirement 11.2, 11.3):
      - bucket: restrict to one score bucket
      - status: restrict to one agent_current_state value
      - search: case-insensitive LIKE match on name, property_address,
        lead_source_name

    Aging annotation (Requirements 11.5, 11.6):
      - HOT: is_aging = True when last_agent_action_at IS NULL AND
        (NOW() - created_at) > sla_minutes_hot
      - WARM: is_aging = True when (NOW() - created_at) > 24 hours
      - NURTURE: is_aging = False

    Pagination (Requirement 11.4):
      25 leads per page; page param is 1-indexed.

    Tenant isolation (Requirement 11.7):
      All queries are scoped by agent_user_id.
    """
    now = datetime.utcnow()

    # ------------------------------------------------------------------
    # Resolve AgentPreferences for SLA (Requirement 11.5)
    # ------------------------------------------------------------------
    prefs: Optional[AgentPreferences] = (
        db.query(AgentPreferences)
        .filter(AgentPreferences.agent_user_id == agent.id)
        .first()
    )
    sla_minutes_hot: int = prefs.sla_minutes_hot if prefs else 5

    # ------------------------------------------------------------------
    # Base query — tenant isolation (Requirement 11.7)
    # ------------------------------------------------------------------
    query = db.query(Lead).filter(Lead.agent_user_id == agent.id)

    # ------------------------------------------------------------------
    # Bucket filter (Requirement 11.2)
    # ------------------------------------------------------------------
    if bucket and bucket.upper() != "ALL":
        query = query.filter(Lead.score_bucket == bucket.upper())

    # ------------------------------------------------------------------
    # Status filter (Requirement 11.2)
    # ------------------------------------------------------------------
    if status and status.upper() != "ALL":
        query = query.filter(Lead.agent_current_state == status.upper())

    # ------------------------------------------------------------------
    # Search filter (Requirement 11.3) — case-insensitive LIKE
    # ------------------------------------------------------------------
    if search and search.strip():
        term = f"%{search.strip()}%"
        query = query.filter(
            Lead.name.ilike(term)
            | Lead.property_address.ilike(term)
            | Lead.lead_source_name.ilike(term)
        )

    # ------------------------------------------------------------------
    # Fetch all matching leads for Python-side urgency sort
    # (SQLite CASE on nullable enum columns is unreliable via SQLAlchemy)
    # ------------------------------------------------------------------
    all_leads: List[Lead] = query.all()

    # ------------------------------------------------------------------
    # Urgency sort: HOT=0, WARM=1, NURTURE=2, None=3 (Requirement 11.1)
    # Secondary sort: created_at DESC (newest first within bucket)
    # ------------------------------------------------------------------
    all_leads.sort(
        key=lambda lead: (
            _BUCKET_ORDER.get(lead.score_bucket or "", 3),
            -(lead.created_at.timestamp() if lead.created_at else 0),
        )
    )

    total = len(all_leads)
    total_pages = max(1, math.ceil(total / PAGE_SIZE))

    # ------------------------------------------------------------------
    # Pagination (Requirement 11.4)
    # ------------------------------------------------------------------
    start = (page - 1) * PAGE_SIZE
    end = start + PAGE_SIZE
    page_leads = all_leads[start:end]

    # ------------------------------------------------------------------
    # Aging annotation (Requirements 11.5, 11.6)
    # ------------------------------------------------------------------
    warm_aging_threshold = timedelta(hours=24)
    sla_threshold = timedelta(minutes=sla_minutes_hot)

    lead_cards: List[LeadCard] = []
    for lead in page_leads:
        is_aging = False
        bucket_val = lead.score_bucket or ""

        if bucket_val == "HOT":
            # Requirement 11.5
            if lead.last_agent_action_at is None and lead.created_at is not None:
                age = now - lead.created_at
                is_aging = age > sla_threshold
        elif bucket_val == "WARM":
            # Requirement 11.6
            if lead.created_at is not None:
                age = now - lead.created_at
                is_aging = age > warm_aging_threshold

        lead_cards.append(
            LeadCard(
                id=lead.id,
                name=lead.name or "",
                score=lead.score,
                score_bucket=lead.score_bucket,
                current_state=lead.agent_current_state,
                source=lead.lead_source_name,
                address=lead.property_address,
                created_at=lead.created_at,
                last_agent_action_at=lead.last_agent_action_at,
                is_aging=is_aging,
            )
        )

    return LeadsResponse(
        leads=lead_cards,
        total=total,
        page=page,
        page_size=PAGE_SIZE,
        total_pages=total_pages,
    )
