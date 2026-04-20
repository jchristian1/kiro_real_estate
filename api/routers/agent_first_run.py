"""
Agent first-run route (PR A2).

Single endpoint:
- PUT /api/v1/agent/first-run/profile  — persist profile, set onboarding_completed=True

The /agent/onboarding prefix and all step-counter logic are removed.
Template customisation is available at /agent/templates (agent_settings.py).

Requirements: 4.1, 4.3
"""

from typing import Optional

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from api.dependencies.agent_auth import get_current_agent
from api.dependencies.db import get_db
from gmail_lead_sync.agent_models import AgentUser
from api.dependencies.auth import require_role

router = APIRouter(
    prefix="/agent/first-run",
    tags=["Agent First Run"],
    dependencies=[Depends(require_role("agent"))],
)


class ProfileRequest(BaseModel):
    full_name: str = Field(..., min_length=1, max_length=255)
    phone: Optional[str] = Field(default=None, max_length=50)
    timezone: str = Field(default="UTC", max_length=100)
    service_area: Optional[str] = Field(default=None)


class ProfileResponse(BaseModel):
    ok: bool


class ErrorResponse(BaseModel):
    error: str


@router.put(
    "/profile",
    status_code=status.HTTP_200_OK,
    response_model=ProfileResponse,
    responses={401: {"model": ErrorResponse, "description": "Missing or invalid session"}},
)
def update_profile(
    body: ProfileRequest,
    db: Session = Depends(get_db),
    agent: AgentUser = Depends(get_current_agent),
):
    """
    Persist agent profile fields and mark first-run complete.

    Sets onboarding_completed=True so the agent is redirected to the
    workspace on next load. Can be called again to update profile fields.
    """
    from api.repositories.agent_repository import AgentRepository

    agent_repo = AgentRepository(db)
    agent_repo.update_profile(
        agent=agent,
        full_name=body.full_name,
        phone=body.phone,
        timezone=body.timezone if body.timezone else "UTC",
        service_area=body.service_area,
    )

    return ProfileResponse(ok=True)
