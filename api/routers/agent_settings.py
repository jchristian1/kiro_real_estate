"""
Agent settings routes — templates CRUD.

Provides:
- GET  /api/v1/agent/templates                    — list all 4 template types
- PUT  /api/v1/agent/templates/{type}             — create/update, increment version
- POST /api/v1/agent/templates/{type}/preview     — render with sample lead data
- DELETE /api/v1/agent/templates/{type}           — revert to platform default

Requirements: 14.1, 14.2, 14.3, 14.4
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from api.dependencies.agent_auth import get_current_agent
from api.main import get_db
from api.services.template_renderer import render_template_str
from gmail_lead_sync.agent_models import AgentTemplate, AgentUser

router = APIRouter(prefix="/agent", tags=["Agent Settings"])

# ---------------------------------------------------------------------------
# Valid template types
# ---------------------------------------------------------------------------

VALID_TEMPLATE_TYPES = {"INITIAL_INVITE", "POST_HOT", "POST_WARM", "POST_NURTURE"}

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
    """A single template entry in the GET /agent/templates response."""

    type: str
    subject: str
    body: str
    tone: Optional[str]
    is_custom: bool
    version: int
    updated_at: Optional[datetime]


class TemplatesListResponse(BaseModel):
    """GET /agent/templates response."""

    templates: List[TemplateItem]


class TemplateSaveRequest(BaseModel):
    """PUT /agent/templates/{type} request body."""

    subject: str = Field(..., min_length=1, max_length=500)
    body: str = Field(..., min_length=1)
    tone: Optional[str] = Field(default=None, pattern=r"^(PROFESSIONAL|FRIENDLY|SHORT)$")


class TemplateSaveResponse(BaseModel):
    """PUT /agent/templates/{type} response."""

    ok: bool
    template_id: int
    version: int


class PreviewRequest(BaseModel):
    """POST /agent/templates/{type}/preview request body."""

    subject: str = Field(..., min_length=1, max_length=500)
    body: str = Field(..., min_length=1)


class PreviewResponse(BaseModel):
    """POST /agent/templates/{type}/preview response."""

    subject_rendered: str
    body_rendered: str


class DeleteResponse(BaseModel):
    """DELETE /agent/templates/{type} response."""

    ok: bool
    reverted_to: str


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _validate_type(template_type: str) -> str:
    """Normalise and validate a template type path parameter."""
    upper = template_type.upper()
    if upper not in VALID_TEMPLATE_TYPES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": "INVALID_TEMPLATE_TYPE",
                "detail": (
                    f"'{template_type}' is not a valid template type. "
                    f"Valid types: {sorted(VALID_TEMPLATE_TYPES)}"
                ),
            },
        )
    return upper


# ---------------------------------------------------------------------------
# GET /agent/templates
# ---------------------------------------------------------------------------


@router.get(
    "/templates",
    response_model=TemplatesListResponse,
    summary="List all 4 template types for the authenticated agent",
)
def list_templates(
    db: Session = Depends(get_db),
    agent: AgentUser = Depends(get_current_agent),
):
    """
    Return all four template types for the agent.

    - is_custom=True if the agent has a saved override for that type.
    - is_custom=False if the agent is using the platform default.
    - When no override exists, returns the platform default subject/body.

    Requirements: 14.1
    """
    # Fetch all agent overrides in one query
    overrides: dict[str, AgentTemplate] = {
        row.template_type: row
        for row in db.query(AgentTemplate)
        .filter(AgentTemplate.agent_user_id == agent.id)
        .all()
    }

    items: List[TemplateItem] = []
    for tmpl_type in ("INITIAL_INVITE", "POST_HOT", "POST_WARM", "POST_NURTURE"):
        if tmpl_type in overrides:
            row = overrides[tmpl_type]
            items.append(
                TemplateItem(
                    type=tmpl_type,
                    subject=row.subject,
                    body=row.body,
                    tone=row.tone,
                    is_custom=True,
                    version=row.version,
                    updated_at=row.updated_at,
                )
            )
        else:
            default = _PLATFORM_DEFAULTS[tmpl_type]
            items.append(
                TemplateItem(
                    type=tmpl_type,
                    subject=default["subject"],
                    body=default["body"],
                    tone="PROFESSIONAL",
                    is_custom=False,
                    version=0,
                    updated_at=None,
                )
            )

    return TemplatesListResponse(templates=items)


# ---------------------------------------------------------------------------
# PUT /agent/templates/{type}
# ---------------------------------------------------------------------------


@router.put(
    "/templates/{template_type}",
    response_model=TemplateSaveResponse,
    summary="Create or update an agent template override, incrementing version",
)
def save_template(
    template_type: str,
    body: TemplateSaveRequest,
    db: Session = Depends(get_db),
    agent: AgentUser = Depends(get_current_agent),
):
    """
    Create or update the agent's template override for the given type.

    - If no override exists: create with version=1.
    - If override exists: update subject/body/tone and increment version by 1.
    - Returns 422 for invalid template type.

    Requirements: 14.2
    """
    tmpl_type = _validate_type(template_type)

    existing: Optional[AgentTemplate] = (
        db.query(AgentTemplate)
        .filter(
            AgentTemplate.agent_user_id == agent.id,
            AgentTemplate.template_type == tmpl_type,
        )
        .first()
    )

    now = datetime.utcnow()

    if existing is None:
        new_tmpl = AgentTemplate(
            agent_user_id=agent.id,
            template_type=tmpl_type,
            subject=body.subject,
            body=body.body,
            tone=body.tone or "PROFESSIONAL",
            is_active=True,
            version=1,
            created_at=now,
            updated_at=now,
        )
        db.add(new_tmpl)
        db.flush()
        db.commit()
        db.refresh(new_tmpl)
        return TemplateSaveResponse(ok=True, template_id=new_tmpl.id, version=new_tmpl.version)
    else:
        existing.subject = body.subject
        existing.body = body.body
        if body.tone is not None:
            existing.tone = body.tone
        existing.version = existing.version + 1
        existing.updated_at = now
        db.commit()
        db.refresh(existing)
        return TemplateSaveResponse(ok=True, template_id=existing.id, version=existing.version)


# ---------------------------------------------------------------------------
# POST /agent/templates/{type}/preview
# ---------------------------------------------------------------------------

_SAMPLE_CONTEXT = {
    "lead_name": "Alex Johnson",
    "form_link": "https://app.example.com/form/123",
}


@router.post(
    "/templates/{template_type}/preview",
    response_model=PreviewResponse,
    summary="Render a template with sample lead data",
)
def preview_template(
    template_type: str,
    body: PreviewRequest,
    db: Session = Depends(get_db),
    agent: AgentUser = Depends(get_current_agent),
):
    """
    Render the provided subject and body with sample lead data.

    Sample context:
      lead_name   = "Alex Johnson"
      agent_name  = agent.full_name
      agent_phone = agent.phone
      agent_email = agent.email
      form_link   = "https://app.example.com/form/123"

    Requirements: 14.3
    """
    _validate_type(template_type)

    context = {
        **_SAMPLE_CONTEXT,
        "agent_name": agent.full_name or "",
        "agent_phone": agent.phone or "",
        "agent_email": agent.email or "",
    }

    rendered = render_template_str(body.subject, body.body, context)
    return PreviewResponse(
        subject_rendered=rendered["subject"],
        body_rendered=rendered["body"],
    )


# ---------------------------------------------------------------------------
# DELETE /agent/templates/{type}
# ---------------------------------------------------------------------------


@router.delete(
    "/templates/{template_type}",
    response_model=DeleteResponse,
    summary="Delete agent template override, reverting to platform default",
)
def delete_template(
    template_type: str,
    db: Session = Depends(get_db),
    agent: AgentUser = Depends(get_current_agent),
):
    """
    Delete the agent's custom override for the given template type.

    - If an override exists, it is deleted.
    - If no override exists, returns 200 anyway (idempotent).
    - After deletion the agent falls back to the platform default.

    Requirements: 14.4
    """
    tmpl_type = _validate_type(template_type)

    existing: Optional[AgentTemplate] = (
        db.query(AgentTemplate)
        .filter(
            AgentTemplate.agent_user_id == agent.id,
            AgentTemplate.template_type == tmpl_type,
        )
        .first()
    )

    if existing is not None:
        db.delete(existing)
        db.commit()

    return DeleteResponse(ok=True, reverted_to="platform_default")
