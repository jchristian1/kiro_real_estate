"""
Agent settings routes — templates CRUD and automation config.

Provides:
- GET    /api/v1/agent/templates                      — list all templates grouped by type
- POST   /api/v1/agent/templates                      — create a new named template
- PUT    /api/v1/agent/templates/{id}                 — update template by ID
- POST   /api/v1/agent/templates/{id}/activate        — set as active for its type
- DELETE /api/v1/agent/templates/{id}                 — delete template by ID
- POST   /api/v1/agent/templates/{type}/preview       — render with sample lead data
- GET    /api/v1/agent/automation                     — get automation config
- PUT    /api/v1/agent/automation                     — update automation config

Requirements: 14.1, 14.2, 14.3, 14.4, 15.1, 15.2, 15.3
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from api.dependencies.agent_auth import get_current_agent
from api.main import get_db
from api.repositories.template_repository import (
    AutomationConfigRepository,
    AutomationConfigUpdate,
    TemplateCreate,
    TemplateRepository,
    TemplateUpdate,
)
from api.repositories.watcher_repository import AgentPreferencesRepository
from api.services.template_renderer import render_template_str
from gmail_lead_sync.agent_models import AgentPreferences, AgentTemplate, AgentUser
from api.dependencies.auth import require_role

router = APIRouter(prefix="/agent", tags=["Agent Settings"], dependencies=[Depends(require_role("agent"))])

# ---------------------------------------------------------------------------
# Valid template types
# ---------------------------------------------------------------------------

VALID_TEMPLATE_TYPES = {"INITIAL_INVITE", "POST_HOT", "POST_WARM", "POST_NURTURE"}

TYPE_LABELS = {
    "INITIAL_INVITE": "Initial Outreach",
    "POST_HOT": "Post Form — Hot",
    "POST_WARM": "Post Form — Warm",
    "POST_NURTURE": "Post Form — Nurture",
}

# ---------------------------------------------------------------------------
# Platform default templates (fallback when no agent override exists)
# ---------------------------------------------------------------------------

_PLATFORM_DEFAULTS: dict[str, dict[str, str]] = {
    "INITIAL_INVITE": {
        "subject": "Hi {lead_name}, let's find your perfect home",
        "body": (
            "Hi {lead_name},\n\n"
            "I'm {agent_name} and I'd love to help you find your next home.\n"
            "Please fill out this quick form so I can match you with the best options:\n"
            "{form_link}\n\n"
            "Feel free to reach me at {agent_phone} or {agent_email}.\n\n"
            "Best,\n{agent_name}"
        ),
    },
    "POST_HOT": {
        "subject": "Great news, {lead_name} — you're a top match!",
        "body": (
            "Hi {lead_name},\n\n"
            "Based on your answers, you're a great fit for several listings I have in mind.\n"
            "I'll be in touch very shortly to schedule a tour.\n\n"
            "— {agent_name} | {agent_phone}"
        ),
    },
    "POST_WARM": {
        "subject": "{lead_name}, here are some options for you",
        "body": (
            "Hi {lead_name},\n\n"
            "Thanks for completing the form. I've put together a few listings that match your criteria.\n"
            "Reply or call me at {agent_phone} when you're ready to take the next step.\n\n"
            "— {agent_name}"
        ),
    },
    "POST_NURTURE": {
        "subject": "Staying in touch, {lead_name}",
        "body": (
            "Hi {lead_name},\n\n"
            "Thanks for your interest. When you're ready to move forward, I'm here to help.\n"
            "You can reach me at {agent_email} or {agent_phone}.\n\n"
            "— {agent_name}"
        ),
    },
}

# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class TemplateItem(BaseModel):
    id: Optional[int] = None
    name: Optional[str] = None
    type: str
    subject: str
    body: str
    tone: Optional[str]
    is_custom: bool
    is_active: bool
    version: int
    updated_at: Optional[datetime]


class TemplatesListResponse(BaseModel):
    """GET /agent/templates — all templates grouped, with defaults injected."""
    templates: List[TemplateItem]


class TemplateCreateRequest(BaseModel):
    template_type: str = Field(..., description="INITIAL_INVITE | POST_HOT | POST_WARM | POST_NURTURE")
    name: str = Field(..., min_length=1, max_length=255)
    subject: str = Field(..., min_length=1, max_length=500)
    body: str = Field(..., min_length=1)
    tone: Optional[str] = Field(default=None, pattern=r"^(PROFESSIONAL|FRIENDLY|SHORT)$")
    activate: bool = Field(default=False, description="Set as active immediately")


class TemplateCreateResponse(BaseModel):
    ok: bool
    template_id: int
    version: int


class TemplateUpdateRequest(BaseModel):
    name: Optional[str] = Field(default=None, max_length=255)
    subject: Optional[str] = Field(default=None, min_length=1, max_length=500)
    body: Optional[str] = Field(default=None, min_length=1)
    tone: Optional[str] = Field(default=None, pattern=r"^(PROFESSIONAL|FRIENDLY|SHORT)$")


class TemplateUpdateResponse(BaseModel):
    ok: bool
    version: int


class ActivateResponse(BaseModel):
    ok: bool


class DeleteResponse(BaseModel):
    ok: bool
    reverted_to: str


class PreviewRequest(BaseModel):
    subject: str = Field(..., min_length=1, max_length=500)
    body: str = Field(..., min_length=1)


class PreviewResponse(BaseModel):
    subject_rendered: str
    body_rendered: str


# Legacy save request (kept for backward compat with onboarding step)
class TemplateSaveRequest(BaseModel):
    subject: str = Field(..., min_length=1, max_length=500)
    body: str = Field(..., min_length=1)
    tone: Optional[str] = Field(default=None, pattern=r"^(PROFESSIONAL|FRIENDLY|SHORT)$")


class TemplateSaveResponse(BaseModel):
    ok: bool
    template_id: int
    version: int


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _validate_type(template_type: str) -> str:
    upper = template_type.upper()
    if upper not in VALID_TEMPLATE_TYPES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": "INVALID_TEMPLATE_TYPE", "valid": sorted(VALID_TEMPLATE_TYPES)},
        )
    return upper


def _deactivate_type(agent_id: int, tmpl_type: str, db: Session) -> None:
    """Set is_active=False for all templates of this type for this agent."""
    repo = TemplateRepository(db)
    repo.deactivate_type(agent_id, tmpl_type)


# ---------------------------------------------------------------------------
# GET /agent/templates
# ---------------------------------------------------------------------------


@router.get("/templates", response_model=TemplatesListResponse)
def list_templates(
    db: Session = Depends(get_db),
    agent: AgentUser = Depends(get_current_agent),
):
    """
    Return all templates for the agent.
    For each pipeline type, if no custom templates exist, inject the platform default
    as a virtual entry (id=None, is_custom=False, is_active=True).
    """
    rows: list[AgentTemplate] = TemplateRepository(db).list_for_agent(agent.id)

    # Group by type
    by_type: dict[str, list[AgentTemplate]] = {t: [] for t in VALID_TEMPLATE_TYPES}
    for row in rows:
        by_type[row.template_type].append(row)

    items: List[TemplateItem] = []
    for tmpl_type in ("INITIAL_INVITE", "POST_HOT", "POST_WARM", "POST_NURTURE"):
        type_rows = by_type[tmpl_type]
        has_active_db = any(r.is_active for r in type_rows)

        # Always inject the platform default as a read-only entry (id=None)
        default = _PLATFORM_DEFAULTS[tmpl_type]
        items.append(TemplateItem(
            id=None,
            name="Platform Default",
            type=tmpl_type,
            subject=default["subject"],
            body=default["body"],
            tone="PROFESSIONAL",
            is_custom=False,
            is_active=not has_active_db,  # active only when no DB template is active
            version=0,
            updated_at=None,
        ))

        # Add ALL DB templates for this type (both legacy and user-created)
        for row in type_rows:
            items.append(TemplateItem(
                id=row.id,
                name=row.name or "My Template",
                type=tmpl_type,
                subject=row.subject,
                body=row.body,
                tone=row.tone,
                is_custom=True,
                is_active=row.is_active,
                version=row.version,
                updated_at=row.updated_at,
            ))

    return TemplatesListResponse(templates=items)


# ---------------------------------------------------------------------------
# POST /agent/templates  — create new named template
# ---------------------------------------------------------------------------


@router.post("/templates", response_model=TemplateCreateResponse, status_code=201)
def create_template(
    body: TemplateCreateRequest,
    db: Session = Depends(get_db),
    agent: AgentUser = Depends(get_current_agent),
):
    tmpl_type = _validate_type(body.template_type)

    if body.activate:
        _deactivate_type(agent.id, tmpl_type, db)

    repo = TemplateRepository(db)
    new_tmpl = repo.create(
        agent.id,
        TemplateCreate(
            template_type=tmpl_type,
            name=body.name,
            subject=body.subject,
            body=body.body,
            tone=body.tone or "PROFESSIONAL",
            is_active=body.activate,
        ),
    )
    return TemplateCreateResponse(ok=True, template_id=new_tmpl.id, version=new_tmpl.version)


# ---------------------------------------------------------------------------
# PUT /agent/templates/{id}  — update by ID
# ---------------------------------------------------------------------------


@router.put("/templates/{template_id}", response_model=TemplateUpdateResponse)
def update_template(
    template_id: int,
    body: TemplateUpdateRequest,
    db: Session = Depends(get_db),
    agent: AgentUser = Depends(get_current_agent),
):
    repo = TemplateRepository(db)
    row = repo.update(
        template_id,
        agent.id,
        TemplateUpdate(name=body.name, subject=body.subject, body=body.body, tone=body.tone),
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Template not found")
    return TemplateUpdateResponse(ok=True, version=row.version)


# ---------------------------------------------------------------------------
# POST /agent/templates/{id}/activate  — set as active for its type
# ---------------------------------------------------------------------------


@router.post("/templates/{template_id}/activate", response_model=ActivateResponse)
def activate_template(
    template_id: int,
    db: Session = Depends(get_db),
    agent: AgentUser = Depends(get_current_agent),
):
    repo = TemplateRepository(db)
    row = repo.activate(template_id, agent.id)
    if row is None:
        raise HTTPException(status_code=404, detail="Template not found")
    return ActivateResponse(ok=True)


# ---------------------------------------------------------------------------
# DELETE /agent/templates/{id}  — delete by ID
# ---------------------------------------------------------------------------


@router.delete("/templates/{template_id}", response_model=DeleteResponse)
def delete_template_by_id(
    template_id: int,
    db: Session = Depends(get_db),
    agent: AgentUser = Depends(get_current_agent),
):
    repo = TemplateRepository(db)
    row = repo.delete(template_id, agent.id)
    if row is None:
        raise HTTPException(status_code=404, detail="Template not found")

    was_active = row.is_active
    tmpl_type = row.template_type

    # If deleted template was active, activate the most recent remaining one
    if was_active:
        remaining = repo.get_most_recent_for_type(agent.id, tmpl_type)
        if remaining:
            repo.activate(remaining.id, agent.id)

    return DeleteResponse(ok=True, reverted_to="platform_default" if was_active else "n/a")


# ---------------------------------------------------------------------------
# Legacy DELETE /agent/templates/{type}  — revert by type (backward compat)
# ---------------------------------------------------------------------------


@router.delete("/templates/by-type/{template_type}", response_model=DeleteResponse)
def delete_template_by_type(
    template_type: str,
    db: Session = Depends(get_db),
    agent: AgentUser = Depends(get_current_agent),
):
    tmpl_type = _validate_type(template_type)
    TemplateRepository(db).delete_by_type(agent.id, tmpl_type)
    return DeleteResponse(ok=True, reverted_to="platform_default")


# ---------------------------------------------------------------------------
# POST /agent/templates/{type}/preview
# ---------------------------------------------------------------------------

_SAMPLE_CONTEXT = {
    "lead_name": "Alex Johnson",
    "form_link": "https://app.example.com/form/123",
}


@router.post("/templates/{template_type}/preview", response_model=PreviewResponse)
def preview_template(
    template_type: str,
    body: PreviewRequest,
    db: Session = Depends(get_db),
    agent: AgentUser = Depends(get_current_agent),
):
    _validate_type(template_type)
    context = {
        **_SAMPLE_CONTEXT,
        "agent_name": agent.full_name or "",
        "agent_phone": agent.phone or "",
        "agent_email": agent.email or "",
    }
    rendered = render_template_str(body.subject, body.body, context)
    return PreviewResponse(subject_rendered=rendered["subject"], body_rendered=rendered["body"])


# ---------------------------------------------------------------------------
# Legacy PUT /agent/templates/{type}  — upsert by type (backward compat for onboarding)
# ---------------------------------------------------------------------------


@router.put("/templates/{template_type}", response_model=TemplateSaveResponse)
def save_template_by_type(
    template_type: str,
    body: TemplateSaveRequest,
    db: Session = Depends(get_db),
    agent: AgentUser = Depends(get_current_agent),
):
    """Legacy upsert — used by onboarding step. Creates or updates the active template for a type."""
    tmpl_type = _validate_type(template_type)

    repo = TemplateRepository(db)
    existing = repo.get_active_for_type(agent.id, tmpl_type)

    if existing is None:
        new_tmpl = repo.create(
            agent.id,
            TemplateCreate(
                template_type=tmpl_type,
                name="My Template",
                subject=body.subject,
                body=body.body,
                tone=body.tone or "PROFESSIONAL",
                is_active=True,
            ),
        )
        return TemplateSaveResponse(ok=True, template_id=new_tmpl.id, version=new_tmpl.version)
    else:
        updated = repo.update(
            existing.id,
            agent.id,
            TemplateUpdate(subject=body.subject, body=body.body, tone=body.tone),
        )
        if updated is None:
            updated = existing
        return TemplateSaveResponse(ok=True, template_id=updated.id, version=updated.version)



# ---------------------------------------------------------------------------
# Platform default automation values
# ---------------------------------------------------------------------------

_PLATFORM_DEFAULT_CONFIG = {
    "id": 0,
    "hot_threshold": 80,
    "warm_threshold": 50,
    "enable_tour_question": True,
    "weight_timeline": 25,
    "weight_preapproval": 30,
    "weight_phone_provided": 15,
    "weight_tour_interest": 20,
    "weight_budget_match": 10,
    "sla_minutes_hot": 5,
    "form_link_template": None,
}


# ---------------------------------------------------------------------------
# Pydantic models for automation endpoints
# ---------------------------------------------------------------------------


class AutomationConfigOut(BaseModel):
    """Serialized BuyerAutomationConfig fields."""

    id: int
    hot_threshold: int
    warm_threshold: int
    enable_tour_question: bool
    weight_timeline: int
    weight_preapproval: int
    weight_phone_provided: int
    weight_tour_interest: int
    weight_budget_match: int
    sla_minutes_hot: int
    form_link_template: Optional[str]


class AvailableQuestion(BaseModel):
    key: str
    label: str
    enabled: bool


class AutomationGetResponse(BaseModel):
    """GET /agent/automation response."""

    config: AutomationConfigOut
    is_platform_default: bool
    available_questions: List[AvailableQuestion]


class AutomationUpdateRequest(BaseModel):
    """PUT /agent/automation request body."""

    hot_threshold: Optional[int] = Field(default=None, ge=60, le=95)
    warm_threshold: Optional[int] = Field(default=None, ge=1)
    enable_tour_question: Optional[bool] = None
    weight_timeline: Optional[int] = None
    weight_preapproval: Optional[int] = None
    weight_phone_provided: Optional[int] = None
    weight_tour_interest: Optional[int] = None
    weight_budget_match: Optional[int] = None
    sla_minutes_hot: Optional[int] = Field(default=None, ge=1, le=120)


class AutomationUpdateResponse(BaseModel):
    """PUT /agent/automation response."""

    ok: bool
    config_id: int


# ---------------------------------------------------------------------------
# Helper: build available_questions list
# ---------------------------------------------------------------------------


def _build_available_questions(enable_tour_question: bool) -> List[AvailableQuestion]:
    return [
        AvailableQuestion(key="timeline", label="Timeline < 3 months", enabled=True),
        AvailableQuestion(key="preapproval", label="Pre-approved", enabled=True),
        AvailableQuestion(key="phone_provided", label="Phone provided", enabled=True),
        AvailableQuestion(key="tour_interest", label="Wants tour", enabled=enable_tour_question),
        AvailableQuestion(key="budget_match", label="Budget in range", enabled=True),
    ]


# ---------------------------------------------------------------------------
# GET /agent/automation
# ---------------------------------------------------------------------------


@router.get(
    "/automation",
    response_model=AutomationGetResponse,
    summary="Get the agent's buyer automation configuration",
)
def get_automation(
    db: Session = Depends(get_db),
    agent: AgentUser = Depends(get_current_agent),
):
    """
    Return the agent's BuyerAutomationConfig.

    - If the agent has a linked BuyerAutomationConfig (via AgentPreferences.buyer_automation_config_id),
      return it with is_platform_default=False.
    - Otherwise return platform default values with is_platform_default=True.
    - available_questions always lists the 5 scoring factors; tour_interest enabled
      reflects enable_tour_question from the config.

    Requirements: 15.1
    """
    auto_repo = AutomationConfigRepository(db)
    prefs, config_row = auto_repo.get_for_agent_via_prefs(agent.id)

    if config_row is not None:
        # Use sla_minutes_hot from prefs if available, else from config default
        sla = prefs.sla_minutes_hot if prefs else 5
        config_out = AutomationConfigOut(
            id=config_row.id,
            hot_threshold=config_row.hot_threshold,
            warm_threshold=config_row.warm_threshold,
            enable_tour_question=config_row.enable_tour_question,
            weight_timeline=config_row.weight_timeline,
            weight_preapproval=config_row.weight_preapproval,
            weight_phone_provided=config_row.weight_phone_provided,
            weight_tour_interest=config_row.weight_tour_interest,
            weight_budget_match=config_row.weight_budget_match,
            sla_minutes_hot=sla,
            form_link_template=config_row.form_link_template,
        )
        return AutomationGetResponse(
            config=config_out,
            is_platform_default=False,
            available_questions=_build_available_questions(config_row.enable_tour_question),
        )
    else:
        # Return platform defaults
        d = _PLATFORM_DEFAULT_CONFIG
        config_out = AutomationConfigOut(
            id=d["id"],
            hot_threshold=d["hot_threshold"],
            warm_threshold=d["warm_threshold"],
            enable_tour_question=d["enable_tour_question"],
            weight_timeline=d["weight_timeline"],
            weight_preapproval=d["weight_preapproval"],
            weight_phone_provided=d["weight_phone_provided"],
            weight_tour_interest=d["weight_tour_interest"],
            weight_budget_match=d["weight_budget_match"],
            sla_minutes_hot=d["sla_minutes_hot"],
            form_link_template=d["form_link_template"],
        )
        return AutomationGetResponse(
            config=config_out,
            is_platform_default=True,
            available_questions=_build_available_questions(d["enable_tour_question"]),
        )


# ---------------------------------------------------------------------------
# PUT /agent/automation
# ---------------------------------------------------------------------------


@router.put(
    "/automation",
    response_model=AutomationUpdateResponse,
    summary="Create or update the agent's buyer automation configuration",
)
def update_automation(
    body: AutomationUpdateRequest,
    db: Session = Depends(get_db),
    agent: AgentUser = Depends(get_current_agent),
):
    """
    Create or update the agent's BuyerAutomationConfig.

    - If the agent already has a BuyerAutomationConfig: update it in place.
    - If not: create a new one and link it via AgentPreferences.buyer_automation_config_id
      (creating AgentPreferences if it doesn't exist).
    - Also syncs sla_minutes_hot, enable_tour_question, hot_threshold, warm_threshold
      onto AgentPreferences when provided.

    Requirements: 15.2, 15.3
    """
    auto_repo = AutomationConfigRepository(db)
    prefs, config_row = auto_repo.upsert_for_agent(
        agent_id=agent.id,
        data=AutomationConfigUpdate(
            hot_threshold=body.hot_threshold,
            warm_threshold=body.warm_threshold,
            enable_tour_question=body.enable_tour_question,
            weight_timeline=body.weight_timeline,
            weight_preapproval=body.weight_preapproval,
            weight_phone_provided=body.weight_phone_provided,
            weight_tour_interest=body.weight_tour_interest,
            weight_budget_match=body.weight_budget_match,
            sla_minutes_hot=body.sla_minutes_hot,
        ),
        platform_defaults=_PLATFORM_DEFAULT_CONFIG,
    )

    return AutomationUpdateResponse(ok=True, config_id=config_row.id)

# ---------------------------------------------------------------------------
# Sources settings endpoint
# ---------------------------------------------------------------------------

import json as _json  # noqa: E402


class SourcePrefsResponse(BaseModel):
    enabled_lead_source_ids: list[int]


@router.get(
    "/settings/sources",
    response_model=SourcePrefsResponse,
    summary="Get the agent's enabled lead source IDs",
)
def get_sources(
    db: Session = Depends(get_db),
    agent: AgentUser = Depends(get_current_agent),
):
    """Return the agent's saved enabled_lead_source_ids from AgentPreferences."""
    prefs_repo = AgentPreferencesRepository(db)
    prefs: Optional[AgentPreferences] = prefs_repo.get_or_create(agent.id)
    if prefs is None or prefs.enabled_lead_source_ids is None:
        return SourcePrefsResponse(enabled_lead_source_ids=[])
    try:
        ids = _json.loads(prefs.enabled_lead_source_ids)
        return SourcePrefsResponse(enabled_lead_source_ids=ids if isinstance(ids, list) else [])
    except Exception:
        return SourcePrefsResponse(enabled_lead_source_ids=[])
