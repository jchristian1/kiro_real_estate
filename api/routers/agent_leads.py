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

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, field_validator
from sqlalchemy.orm import Session

from api.dependencies.agent_auth import get_current_agent
from api.dependencies.db import get_db
from api.repositories import LeadRepository
from api.repositories.lead_repository import LeadEventWriteRepository
from api.repositories.watcher_repository import WatcherRepository
from gmail_lead_sync.agent_models import AgentUser
from api.dependencies.auth import require_role
from api.models.pipeline_schemas import AgentLeadPipelineResponse
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


class StageInfo(BaseModel):
    """Current pipeline stage for a lead — sourced from the unified read model."""
    stage_id: int
    stage_name: str
    stage_key: str
    stage_color: str
    stage_category: str
    stage_entered_at: Optional[datetime]


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
    stage: Optional[StageInfo]
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
    - Delegates assembly to lead_detail_service.assemble_lead_detail().
    - Timeline is sourced from LeadActivityRepository (Phase 3C).
    - Rendered emails and notes are extracted from the unified timeline.

    Requirements: 12.1, 12.2, 12.3, 18.2
    """
    from api.exceptions import AuthorizationException, NotFoundException
    from api.models.error_models import ErrorCode
    from api.services.lead_detail_service import assemble_lead_detail

    now = datetime.utcnow()
    lead_repo = LeadRepository(db)
    prefs_repo = WatcherRepository(db)

    # Verify existence and tenant ownership before assembling
    lead = lead_repo.get_by_agent_id_str(lead_id)
    if lead is None:
        raise NotFoundException(message="Lead not found", code=ErrorCode.NOT_FOUND_LEAD)

    if lead.agent_user_id != agent.id:
        raise AuthorizationException(
            message="Access to this lead is not permitted",
            code=ErrorCode.AUTH_FORBIDDEN,
        )

    # Aging annotation
    prefs = prefs_repo.get_config_by_agent_id(agent.id)
    sla_minutes_hot: int = prefs.sla_minutes_hot if prefs else 5
    is_aging = False
    bucket_val = getattr(lead, "score_bucket", None) or ""
    if bucket_val == "HOT" and lead.last_agent_action_at is None and lead.created_at:
        is_aging = (now - lead.created_at) > timedelta(minutes=sla_minutes_hot)
    elif bucket_val == "WARM" and lead.created_at:
        is_aging = (now - lead.created_at) > timedelta(hours=24)

    # Delegate to assembler
    detail = assemble_lead_detail(db, lead_id=lead_id, company_id=getattr(lead, "company_id", None))
    if detail is None:
        raise NotFoundException(message="Lead not found", code=ErrorCode.NOT_FOUND_LEAD)

    # Build EnrichedLead from assembler — score/bucket come from qualification summary
    qual = detail.qualification
    enriched = EnrichedLead(
        id=detail.core.id,
        name=detail.core.name,
        phone=detail.core.phone,
        score=qual.score if qual else None,
        score_bucket=qual.bucket if qual else None,
        current_state=detail.core.agent_current_state,
        source=detail.core.lead_source_name,
        address=detail.core.property_address,
        listing_url=detail.core.listing_url,
        created_at=detail.core.created_at,
        last_agent_action_at=detail.core.last_agent_action_at,
        is_aging=is_aging,
    )

    # Scoring breakdown — sourced entirely from assembler qualification summary
    scoring_breakdown: Optional[ScoringBreakdown] = None
    if qual is not None and qual.breakdown:
        scoring_breakdown = ScoringBreakdown(
            total=qual.score,
            factors=[
                ScoreFactor(label=f.label, points=f.points, met=f.met)
                for f in qual.breakdown
            ],
        )

    # Build timeline, rendered_emails, notes from unified activity timeline
    timeline: List[TimelineEvent] = []
    rendered_emails: List[RenderedEmail] = []
    notes: List[NoteItem] = []

    for entry in detail.timeline:
        timeline.append(
            TimelineEvent(
                id=entry.id,
                event_type=entry.event_type,
                payload=entry.metadata or None,
                created_at=entry.occurred_at,
            )
        )

        # Extract rendered emails from legacy INVITE_SENT / POST_EMAIL_SENT events
        if entry.event_type in ("INVITE_SENT", "POST_EMAIL_SENT") and entry.metadata:
            rendered_emails.append(
                RenderedEmail(
                    type=entry.event_type,
                    subject=entry.metadata.get("subject", ""),
                    body=entry.metadata.get("body", ""),
                    sent_at=entry.occurred_at,
                )
            )

        # Extract notes from NOTE_ADDED events
        if entry.event_type == "NOTE_ADDED" and entry.metadata:
            notes.append(
                NoteItem(
                    text=entry.metadata.get("text", ""),
                    created_at=entry.occurred_at,
                )
            )

    return LeadDetailResponse(
        lead=enriched,
        stage=StageInfo(
            stage_id=detail.stage.stage_id,
            stage_name=detail.stage.stage_name,
            stage_key=detail.stage.stage_key,
            stage_color=detail.stage.stage_color,
            stage_category=detail.stage.stage_category,
            stage_entered_at=detail.stage.stage_entered_at,
        ) if detail.stage else None,
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

    # Idempotency: if already in target state, return success without creating duplicate event
    if current == new_status or current_for_transition == new_status:
        return StatusUpdateResponse(
            ok=True,
            current_state=lead.agent_current_state,
            updated_at=datetime.utcnow(),
        )

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
        "from_state": current,  # preserve original state name (e.g. 'NEW', not None)
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
    # Uses LeadActivityRepository — the canonical read boundary for LeadEvent.
    if not events:
        from api.repositories.lead_activity_repository import LeadActivityRepository
        activity_repo = LeadActivityRepository(db)
        lead_events = [
            ev for ev in activity_repo.get_timeline(lead_id=lead_id)
            if ev.event_type == "STATUS_CHANGED"
        ]
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


@router.get(
    "/leads/{lead_id}/pipeline",
    response_model=AgentLeadPipelineResponse,
    summary="Get pipeline stage info for a lead",
)
def get_lead_pipeline(
    lead_id: int,
    db: Session = Depends(get_db),
    agent: AgentUser = Depends(get_current_agent),
):
    """
    Return pipeline stage info for a lead visible to the authenticated agent.

    Enforces tenant isolation: the lead must belong to the agent's company.
    Returns pipeline name, current stage, all stages, lifecycle events, and history.

    Requirements: 10.5, 10.6, 10.7
    """
    from api.exceptions import NotFoundException
    from api.models.error_models import ErrorCode
    from api.models.pipeline_schemas import (
        AgentLeadPipelineResponse,
        LeadStageHistoryResponse,
        PipelineStageResponse,
    )
    from api.services.lead_stage_service import get_current_stage, get_stage_history
    from api.services.pipeline_service import get_active_pipeline
    from api.services.pipeline_stage_service import list_stages
    from gmail_lead_sync.models import Lead

    lead = db.query(Lead).filter(Lead.id == lead_id).first()
    if lead is None:
        raise NotFoundException(message="Lead not found", code=ErrorCode.NOT_FOUND_LEAD)

    # Tenant isolation: use same pattern as get_lead_detail — check agent_user_id.
    # Fall back to company_id comparison for leads not directly owned by this agent.
    lead_agent_id = getattr(lead, "agent_user_id", None)
    agent_company_id = getattr(agent, "company_id", None)
    lead_company_id = getattr(lead, "company_id", None)

    owned_by_agent = lead_agent_id == agent.id
    same_company = (agent_company_id is not None) and (lead_company_id == agent_company_id)

    if not owned_by_agent and not same_company:
        raise NotFoundException(message="Lead not found", code=ErrorCode.NOT_FOUND_LEAD)

    pipeline = get_active_pipeline(db, agent_company_id) if agent_company_id else None
    if pipeline is None:
        return AgentLeadPipelineResponse(
            pipeline_name="",
            current_stage=None,
            stage_entered_at=None,
            stages=[],
            lifecycle=[],
            stage_history=[],
        )

    current_stage = get_current_stage(db, lead_id)
    stages = list_stages(db, pipeline.id)
    history = get_stage_history(db, lead_id)

    from api.models.pipeline_models import PipelineStage as _PipelineStage

    # Build a stage id->name lookup for lifecycle labels.
    stage_name_map = {s.id: s.name for s in stages}

    # Build lifecycle: one entry per history event with stage name and timestamp.
    lifecycle = [
        {
            "event": f"Entered {stage_name_map.get(h.to_stage_id, str(h.to_stage_id))}",
            "timestamp": h.created_at.isoformat() if h.created_at else None,
            "source": h.change_source.value if hasattr(h.change_source, "value") else h.change_source,
        }
        for h in history
    ]

    return AgentLeadPipelineResponse(
        pipeline_name=pipeline.name,
        current_stage=PipelineStageResponse.model_validate(current_stage) if current_stage else None,
        stage_entered_at=getattr(lead, "stage_entered_at", None),
        stages=[PipelineStageResponse.model_validate(s) for s in stages],
        lifecycle=lifecycle,
        stage_history=[LeadStageHistoryResponse.model_validate(h) for h in history],
    )
