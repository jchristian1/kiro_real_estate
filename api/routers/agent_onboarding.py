"""
Agent onboarding routes.

Provides:
- PUT /api/v1/agent/onboarding/profile  — persist profile fields, advance onboarding_step to 2

Requirements: 4.1, 4.3
"""

from typing import Optional

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from api.dependencies.agent_auth import get_current_agent
from api.main import get_db
from gmail_lead_sync.agent_models import AgentUser
from gmail_lead_sync.models import Company

router = APIRouter(prefix="/agent/onboarding", tags=["Agent Onboarding"])


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class ProfileRequest(BaseModel):
    """PUT /onboarding/profile request body."""
    full_name: str = Field(..., min_length=1, max_length=255)
    phone: Optional[str] = Field(default=None, max_length=50)
    timezone: str = Field(default="UTC", max_length=100)
    service_area: Optional[str] = Field(default=None)
    company_join_code: Optional[str] = Field(default=None)


class ProfileResponse(BaseModel):
    """PUT /onboarding/profile success response."""
    ok: bool
    onboarding_step: int


class ErrorResponse(BaseModel):
    """Generic error response."""
    error: str


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.put(
    "/profile",
    status_code=status.HTTP_200_OK,
    response_model=ProfileResponse,
    responses={
        401: {"model": ErrorResponse, "description": "Missing or invalid session"},
    },
)
def update_profile(
    body: ProfileRequest,
    db: Session = Depends(get_db),
    agent: AgentUser = Depends(get_current_agent),
):
    """
    Persist agent profile fields and advance onboarding_step to 2.

    - Persists full_name, phone, timezone, service_area to the AgentUser record.
    - If company_join_code is provided, looks up the company by name and
      associates the agent (sets agent_user.company_id).
    - Advances onboarding_step to 2.
    - Requires valid agent session.

    Requirements: 4.1, 4.3
    """
    agent.full_name = body.full_name
    agent.phone = body.phone
    agent.timezone = body.timezone if body.timezone else "UTC"
    agent.service_area = body.service_area

    # Associate with company if join code provided (Requirement 4.3)
    if body.company_join_code:
        company = (
            db.query(Company)
            .filter(Company.name == body.company_join_code)
            .first()
        )
        if company:
            agent.company_id = company.id

    # Advance onboarding step (Requirement 4.1)
    if agent.onboarding_step < 2:
        agent.onboarding_step = 2

    db.commit()
    db.refresh(agent)

    return ProfileResponse(ok=True, onboarding_step=agent.onboarding_step)
