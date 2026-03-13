"""
Agent leads inbox and lead detail routes.

Provides:
- GET /api/v1/agent/leads — urgency-sorted lead list with filters, aging
  annotation, and pagination at 25 leads per page.
- GET /api/v1/agent/leads/{id} — enriched lead detail with scoring breakdown,
  timeline, rendered emails, and notes.
- PATCH /api/v1/agent/leads/{id}/status — state transition with event logging.
- POST /api/v1/agent/leads/{id}/notes — persist note with event logging.

Requirements: 11.1–11.7, 12.1–12.6, 18.2, 20.1, 20.3
"""

import json
import math
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from pydantic import BaseModel, field_validator
from sqlalchemy.orm import Session

from api.dependencies.agent_auth import get_current_agent
from api.main import get_db
from api.repositories import LeadRepository
from api.repositories.lead_repository import LeadEventWriteRepository
from api.repositories.watcher_repository import AgentPreferencesRepository, WatcherRepository
from gmail_lead_sync.agent_models import AgentUser
from api.dependencies.auth import require_role
from api.utils.sanitization import sanitize_string

router = APIRouter(prefix="/agent", tags=["Agent Leads"], dependencies=[Depends(require_role("agent"))])

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

    prefs_repo = WatcherRepository(db)
    lead_repo = LeadRepository(db)

    prefs = prefs_repo.get_config_by_agent_id(agent.id)
    sla_minutes_hot: int = prefs.sla_minutes_hot if prefs else 5

    all_leads = lead_repo.list_for_tenant_with_filters(
        tenant_id=agent.id,
        bucket=bucket,
        status=status,
        search=search,
    )

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


# ---------------------------------------------------------------------------
# Valid state transitions (Requirement 12.6)
# ---------------------------------------------------------------------------
VALID_TRANSITIONS: Dict[Optional[str], List[str]] = {
    None: ["CONTACTED", "APPOINTMENT_SET", "LOST"],
    "NEW": ["CONTACTED", "APPOINTMENT_SET", "LOST"],
    "INVITE_SENT": ["CONTACTED", "APPOINTMENT_SET", "LOST"],
    "FORM_SUBMITTED": ["CONTACTED", "APPOINTMENT_SET", "LOST"],
    "SCORED": ["CONTACTED", "APPOINTMENT_SET", "LOST"],
    "CONTACTED": ["APPOINTMENT_SET", "LOST", "CLOSED"],
    "APPOINTMENT_SET": ["CONTACTED", "LOST", "CLOSED"],
    "LOST": ["CONTACTED"],
    "CLOSED": [],
}

# Map agent-facing status values to internal agent_current_state values
STATUS_TO_STATE = {
    "CONTACTED": "CONTACTED",
    "APPOINTMENT_SET": "APPOINTMENT_SET",
    "LOST": "LOST",
    "CLOSED": "CLOSED",
}

# Map internal state to LeadEvent type
STATE_TO_EVENT = {
    "CONTACTED": "AGENT_CONTACTED",
    "APPOINTMENT_SET": "APPOINTMENT_SET",
    "LOST": "LEAD_LOST",
    "CLOSED": "LEAD_CLOSED",
}


# ---------------------------------------------------------------------------
# Additional Pydantic models
# ---------------------------------------------------------------------------


class ScoreFactor(BaseModel):
    label: str
    points: int
    met: bool


class ScoringBreakdown(BaseModel):
    total: int
    factors: List[ScoreFactor]


class TimelineEvent(BaseModel):
    id: int
    event_type: str
    payload: Optional[Dict[str, Any]]
    created_at: datetime


class RenderedEmail(BaseModel):
    type: str
    subject: str
    body: str
    sent_at: Optional[datetime]


class NoteItem(BaseModel):
    text: str
    created_at: datetime


class EnrichedLead(BaseModel):
    id: int
    name: str
    phone: Optional[str]
    score: Optional[int]
    score_bucket: Optional[str]
    current_state: Optional[str]
    source: Optional[str]
    address: Optional[str]
    listing_url: Optional[str]
    created_at: datetime
    last_agent_action_at: Optional[datetime]
    is_aging: bool


class LeadDetailResponse(BaseModel):
    lead: EnrichedLead
    scoring_breakdown: Optional[ScoringBreakdown]
    timeline: List[TimelineEvent]
    rendered_emails: List[RenderedEmail]
    notes: List[NoteItem]


class StatusUpdateRequest(BaseModel):
    status: str
    note: Optional[str] = None


class StatusUpdateResponse(BaseModel):
    ok: bool
    current_state: str
    updated_at: datetime


class NoteRequest(BaseModel):
    text: str

    @field_validator("text", mode="before")
    @classmethod
    def sanitize_html(cls, v: str) -> str:
        """Strip HTML tags from note text to prevent stored XSS. Requirements: 11.4"""
        if isinstance(v, str):
            return sanitize_string(v)
        return v


class NoteResponse(BaseModel):
    note_id: int
    text: str
    created_at: datetime


class LeadStateTransitionResponse(BaseModel):
    """A single state transition event."""
    id: int
    from_state: Optional[str]
    to_state: str
    occurred_at: datetime
    actor_type: str
    actor_id: Optional[int]
    metadata: Optional[Dict[str, Any]]


class LeadEventsResponse(BaseModel):
    """GET /agent/leads/{lead_id}/events response."""
    lead_id: int
    events: List[LeadStateTransitionResponse]


# ---------------------------------------------------------------------------
# GET /agent/leads/{id}
# ---------------------------------------------------------------------------


@router.get(
    "/leads/{lead_id}",
    response_model=LeadDetailResponse,
    summary="Enriched lead detail — scoring breakdown, timeline, rendered emails, notes",
)
def get_lead_detail(
    lead_id: int,
    db: Session = Depends(get_db),
    agent: AgentUser = Depends(get_current_agent),
):
    """
    Return enriched detail for a single lead.

    - Returns 403 if the lead belongs to a different agent (Requirement 18.2).
    - Scoring breakdown is parsed from the JSON score_breakdown column.
    - Timeline is the full ordered list of lead_events for this lead.
    - Rendered emails are extracted from INVITE_SENT / POST_EMAIL_SENT events.
    - Notes are extracted from NOTE_ADDED events.

    Requirements: 12.1, 12.2, 12.3, 18.2
    """
    now = datetime.utcnow()

    lead_repo = LeadRepository(db)
    event_write_repo = LeadEventWriteRepository(db)
    prefs_repo = WatcherRepository(db)

    lead = lead_repo.get_by_agent_id_str(lead_id)
    if lead is None:
        from api.exceptions import NotFoundException
        from api.models.error_models import ErrorCode
        raise NotFoundException(
            message="Lead not found",
            code=ErrorCode.NOT_FOUND_LEAD,
        )

    # Tenant isolation — 403 for cross-agent access (Requirement 18.2)
    if lead.agent_user_id != agent.id:
        from api.exceptions import AuthorizationException
        from api.models.error_models import ErrorCode
        raise AuthorizationException(
            message="Access to this lead is not permitted",
            code=ErrorCode.AUTH_FORBIDDEN,
        )

    # Aging annotation
    prefs = prefs_repo.get_config_by_agent_id(agent.id)
    sla_minutes_hot: int = prefs.sla_minutes_hot if prefs else 5
    is_aging = False
    bucket_val = lead.score_bucket or ""
    if bucket_val == "HOT" and lead.last_agent_action_at is None and lead.created_at:
        is_aging = (now - lead.created_at) > timedelta(minutes=sla_minutes_hot)
    elif bucket_val == "WARM" and lead.created_at:
        is_aging = (now - lead.created_at) > timedelta(hours=24)

    enriched = EnrichedLead(
        id=lead.id,
        name=lead.name or "",
        phone=getattr(lead, "phone", None),
        score=lead.score,
        score_bucket=lead.score_bucket,
        current_state=lead.agent_current_state,
        source=lead.lead_source_name,
        address=lead.property_address,
        listing_url=lead.listing_url,
        created_at=lead.created_at,
        last_agent_action_at=lead.last_agent_action_at,
        is_aging=is_aging,
    )

    # Scoring breakdown from JSON column
    scoring_breakdown: Optional[ScoringBreakdown] = None
    if lead.score_breakdown:
        try:
            raw = json.loads(lead.score_breakdown)
            factors = [
                ScoreFactor(
                    label=f.get("label", ""),
                    points=f.get("points", 0),
                    met=f.get("met", False),
                )
                for f in raw.get("factors", [])
            ]
            scoring_breakdown = ScoringBreakdown(
                total=lead.score or 0,
                factors=factors,
            )
        except (json.JSONDecodeError, TypeError):
            pass

    # Timeline — all events ordered by created_at ASC
    events = event_write_repo.list_for_lead(lead_id)

    timeline: List[TimelineEvent] = []
    rendered_emails: List[RenderedEmail] = []
    notes: List[NoteItem] = []

    for ev in events:
        payload_dict: Optional[Dict[str, Any]] = None
        if ev.payload:
            try:
                payload_dict = json.loads(ev.payload)
            except (json.JSONDecodeError, TypeError):
                payload_dict = None

        timeline.append(
            TimelineEvent(
                id=ev.id,
                event_type=ev.event_type,
                payload=payload_dict,
                created_at=ev.created_at,
            )
        )

        # Extract rendered emails from INVITE_SENT / POST_EMAIL_SENT events
        if ev.event_type in ("INVITE_SENT", "POST_EMAIL_SENT") and payload_dict:
            rendered_emails.append(
                RenderedEmail(
                    type=ev.event_type,
                    subject=payload_dict.get("subject", ""),
                    body=payload_dict.get("body", ""),
                    sent_at=ev.created_at,
                )
            )

        # Extract notes from NOTE_ADDED events
        if ev.event_type == "NOTE_ADDED" and payload_dict:
            rendered_emails  # noqa — just referencing to avoid unused warning
            notes.append(
                NoteItem(
                    text=payload_dict.get("text", ""),
                    created_at=ev.created_at,
                )
            )

    return LeadDetailResponse(
        lead=enriched,
        scoring_breakdown=scoring_breakdown,
        timeline=timeline,
        rendered_emails=rendered_emails,
        notes=notes,
    )


# ---------------------------------------------------------------------------
# PATCH /agent/leads/{id}/status
# ---------------------------------------------------------------------------


@router.patch(
    "/leads/{lead_id}/status",
    response_model=StatusUpdateResponse,
    summary="Update lead status — validates transition, logs event",
)
def update_lead_status(
    lead_id: int,
    body: StatusUpdateRequest,
    db: Session = Depends(get_db),
    agent: AgentUser = Depends(get_current_agent),
):
    """
    Validate and apply a state transition for a lead.

    Valid transitions (Requirement 12.6):
      NEW / INVITE_SENT / FORM_SUBMITTED / SCORED → CONTACTED, APPOINTMENT_SET, LOST
      CONTACTED → APPOINTMENT_SET, LOST, CLOSED
      APPOINTMENT_SET → CONTACTED, LOST, CLOSED
      LOST → CONTACTED
      CLOSED → (none)

    On CONTACTED: sets last_agent_action_at (Requirement 12.4).
    Inserts STATUS_CHANGED event (Requirement 20.3).

    Requirements: 12.4, 12.6, 20.3
    """
    lead_repo = LeadRepository(db)
    event_write_repo = LeadEventWriteRepository(db)

    lead = lead_repo.get_by_agent_id_str(lead_id)
    if lead is None:
        from api.exceptions import NotFoundException
        from api.models.error_models import ErrorCode
        raise NotFoundException(
            message="Lead not found",
            code=ErrorCode.NOT_FOUND_LEAD,
        )

    if lead.agent_user_id != agent.id:
        from api.exceptions import AuthorizationException
        from api.models.error_models import ErrorCode
        raise AuthorizationException(
            message="Access to this lead is not permitted",
            code=ErrorCode.AUTH_FORBIDDEN,
        )

    new_status = body.status.upper()
    if new_status not in STATUS_TO_STATE:
        from api.exceptions import ValidationException
        from api.models.error_models import ErrorCode
        raise ValidationException(
            message=f"Unknown status '{body.status}'. Valid: CONTACTED, APPOINTMENT_SET, LOST, CLOSED",
            code=ErrorCode.VALIDATION_INVALID_VALUE,
        )

    current = lead.agent_current_state
    # Normalize 'NEW' to None — both represent the initial state
    current_for_transition = None if current == "NEW" else current
    allowed = VALID_TRANSITIONS.get(current_for_transition, VALID_TRANSITIONS.get(current, []))
    if new_status not in allowed:
        from api.exceptions import ValidationException
        from api.models.error_models import ErrorCode
        raise ValidationException(
            message=f"Transition from '{current}' to '{new_status}' is not allowed",
            code=ErrorCode.VALIDATION_INVALID_VALUE,
        )

    now = datetime.utcnow()

    # Insert STATUS_CHANGED event (Requirement 20.3)
    payload: Dict[str, Any] = {
        "from_state": current_for_transition,
        "to_state": new_status,
    }
    if body.note:
        payload["note"] = body.note

    lead = lead_repo.update_agent_state(
        lead_id=lead_id,
        tenant_id=agent.id,
        new_state=new_status,
        last_action_at=now if new_status == "CONTACTED" else None,
    )

    event_write_repo.create(
        lead_id=lead_id,
        agent_user_id=agent.id,
        event_type="STATUS_CHANGED",
        payload=json.dumps(payload),
        created_at=now,
    )

    return StatusUpdateResponse(
        ok=True,
        current_state=lead.agent_current_state,
        updated_at=now,
    )


# ---------------------------------------------------------------------------
# POST /agent/leads/{id}/notes
# ---------------------------------------------------------------------------


@router.post(
    "/leads/{lead_id}/notes",
    response_model=NoteResponse,
    status_code=201,
    summary="Add a note to a lead — persists note and inserts NOTE_ADDED event",
)
def add_lead_note(
    lead_id: int,
    body: NoteRequest,
    db: Session = Depends(get_db),
    agent: AgentUser = Depends(get_current_agent),
):
    """
    Persist a note for a lead and insert a NOTE_ADDED event.

    Requirements: 12.5, 20.1
    """
    lead_repo = LeadRepository(db)
    event_write_repo = LeadEventWriteRepository(db)

    lead = lead_repo.get_by_agent_id_str(lead_id)
    if lead is None:
        from api.exceptions import NotFoundException
        from api.models.error_models import ErrorCode
        raise NotFoundException(
            message="Lead not found",
            code=ErrorCode.NOT_FOUND_LEAD,
        )

    if lead.agent_user_id != agent.id:
        from api.exceptions import AuthorizationException
        from api.models.error_models import ErrorCode
        raise AuthorizationException(
            message="Access to this lead is not permitted",
            code=ErrorCode.AUTH_FORBIDDEN,
        )

    now = datetime.utcnow()
    event = event_write_repo.create(
        lead_id=lead_id,
        agent_user_id=agent.id,
        event_type="NOTE_ADDED",
        payload=json.dumps({"text": body.text}),
        created_at=now,
    )

    return NoteResponse(
        note_id=event.id,
        text=body.text,
        created_at=event.created_at,
    )


# ---------------------------------------------------------------------------
# GET /agent/leads/{id}/events
# ---------------------------------------------------------------------------


@router.get(
    "/leads/{lead_id}/events",
    response_model=LeadEventsResponse,
    summary="Lead state transition history — chronological event log",
)
def get_lead_events(
    lead_id: int,
    db: Session = Depends(get_db),
    agent: AgentUser = Depends(get_current_agent),
):
    """
    Return all LeadStateTransition rows for a lead in chronological order.

    - Returns 403 if the lead belongs to a different agent (tenant scoping).
    - Events are ordered by occurred_at ascending (oldest first).
    - Metadata is parsed from JSON if present.

    Requirements: 8.7
    """
    lead_repo = LeadRepository(db)

    # Verify lead exists and belongs to the authenticated agent
    lead = lead_repo.get_by_id(lead_id, agent.id)
    if lead is None:
        from api.exceptions import NotFoundException
        from api.models.error_models import ErrorCode
        raise NotFoundException(
            message="Lead not found",
            code=ErrorCode.NOT_FOUND_LEAD,
        )

    # Fetch state transitions (already scoped to tenant in repository)
    transitions = lead_repo.get_lead_state_transitions(lead_id, agent.id)

    # Build response from LeadStateTransition records
    events: List[LeadStateTransitionResponse] = []
    for t in transitions:
        metadata_dict: Optional[Dict[str, Any]] = None
        if t.metadata_json:
            try:
                metadata_dict = json.loads(t.metadata_json)
            except (json.JSONDecodeError, TypeError):
                metadata_dict = None

        events.append(
            LeadStateTransitionResponse(
                id=t.id,
                from_state=t.from_state,
                to_state=t.to_state,
                occurred_at=t.occurred_at,
                actor_type=t.actor_type,
                actor_id=t.actor_id,
                metadata=metadata_dict,
            )
        )

    # Also include STATUS_CHANGED LeadEvent records (from agent-app state machine)
    if not events:
        from gmail_lead_sync.agent_models import LeadEvent
        lead_events = (
            db.query(LeadEvent)
            .filter(
                LeadEvent.lead_id == lead_id,
                LeadEvent.event_type == "STATUS_CHANGED",
            )
            .order_by(LeadEvent.created_at.asc())
            .all()
        )
        for ev in lead_events:
            payload_dict: Optional[Dict[str, Any]] = None
            if ev.payload:
                try:
                    payload_dict = json.loads(ev.payload)
                except (json.JSONDecodeError, TypeError):
                    payload_dict = {}
            from_state = payload_dict.get("from_state") if payload_dict else None
            to_state = payload_dict.get("to_state") if payload_dict else None
            events.append(
                LeadStateTransitionResponse(
                    id=ev.id,
                    from_state=from_state,
                    to_state=to_state,
                    occurred_at=ev.created_at,
                    actor_type="agent",
                    actor_id=ev.agent_user_id,
                    metadata=payload_dict,
                )
            )

    return LeadEventsResponse(
        lead_id=lead_id,
        events=events,
    )
