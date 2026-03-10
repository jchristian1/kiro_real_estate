"""
Agent onboarding routes.

Provides:
- PUT /api/v1/agent/onboarding/profile  — persist profile fields, advance onboarding_step to 2
- POST /api/v1/agent/onboarding/gmail   — test IMAP, encrypt and persist credentials, advance step to 3

Requirements: 4.1, 4.3, 5.1, 5.2, 5.3, 5.4, 5.5, 5.6
"""

from typing import Optional

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, SecretStr
from sqlalchemy.orm import Session

from api.dependencies.agent_auth import get_current_agent
from api.main import get_db
from api.services.credential_encryption import encrypt_app_password
from api.services.imap_service import (
    IMAPRateLimitError,
    check_and_record_imap_attempt,
    test_imap_connection,
)
from gmail_lead_sync.agent_models import AgentUser
from gmail_lead_sync.models import Company, Credentials

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


class GmailRequest(BaseModel):
    """POST /onboarding/gmail request body."""
    gmail_address: str = Field(..., min_length=1, max_length=255)
    app_password: SecretStr = Field(..., min_length=1)
    imap_folder: Optional[str] = Field(default="INBOX")


class GmailResponse(BaseModel):
    """POST /onboarding/gmail success response."""
    connected: bool
    gmail_address: str
    last_sync: Optional[str] = None


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


@router.post(
    "/gmail",
    status_code=status.HTTP_200_OK,
    response_model=GmailResponse,
    responses={
        401: {"model": ErrorResponse, "description": "Missing or invalid session"},
        422: {"description": "IMAP connection failed with structured error code"},
        429: {"description": "Rate limit exceeded"},
    },
)
def connect_gmail(
    body: GmailRequest,
    db: Session = Depends(get_db),
    agent: AgentUser = Depends(get_current_agent),
):
    """
    Test IMAP connection, encrypt and persist Gmail credentials on success.

    1. Check rate limit — 429 with retry_after_seconds if exceeded.
    2. Test live IMAP connection using provided credentials.
    3. On success: encrypt app_password, persist to credentials table,
       link credentials_id on agent_user, advance onboarding_step to 3.
    4. On IMAP failure: return 422 with structured error code and message.

    Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6
    """
    # Step 1: Rate limit check (Requirement 5.7)
    try:
        check_and_record_imap_attempt(agent.id)
    except IMAPRateLimitError as exc:
        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            content={"error": "RATE_LIMITED", "retry_after_seconds": exc.retry_after_seconds},
        )

    # Step 2: Live IMAP test (Requirement 5.1)
    result = test_imap_connection(body.gmail_address, body.app_password.get_secret_value())

    if not result["success"]:
        # Return 422 with structured error code (Requirements 5.3–5.6)
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={"error": result["error"], "message": result["message"]},
        )

    # Step 3: Encrypt and persist credentials (Requirement 5.2, 19.1)
    encrypted_password = encrypt_app_password(body.app_password.get_secret_value())
    # Gmail address is not sensitive but we store it as-is for display
    encrypted_email = body.gmail_address  # stored plaintext for display; password is encrypted

    if agent.credentials_id is not None:
        # Update existing credentials record
        creds = db.query(Credentials).filter(Credentials.id == agent.credentials_id).first()
        if creds is not None:
            creds.email_encrypted = encrypted_email
            creds.app_password_encrypted = encrypted_password
        else:
            # Stale FK — create a new record
            creds = Credentials(
                agent_id=str(agent.id),
                email_encrypted=encrypted_email,
                app_password_encrypted=encrypted_password,
            )
            db.add(creds)
            db.flush()
            agent.credentials_id = creds.id
    else:
        creds = Credentials(
            agent_id=str(agent.id),
            email_encrypted=encrypted_email,
            app_password_encrypted=encrypted_password,
        )
        db.add(creds)
        db.flush()
        agent.credentials_id = creds.id

    # Advance onboarding step to 3
    if agent.onboarding_step < 3:
        agent.onboarding_step = 3

    db.commit()

    return GmailResponse(
        connected=True,
        gmail_address=body.gmail_address,
        last_sync=None,
    )


# ---------------------------------------------------------------------------
# Sources endpoint
# ---------------------------------------------------------------------------

import json as _json


class SourcesRequest(BaseModel):
    """PUT /onboarding/sources request body."""
    enabled_lead_source_ids: list[int]


class SourcesResponse(BaseModel):
    """PUT /onboarding/sources success response."""
    ok: bool
    onboarding_step: int


@router.put(
    "/sources",
    status_code=status.HTTP_200_OK,
    response_model=SourcesResponse,
    responses={
        401: {"model": ErrorResponse, "description": "Missing or invalid session"},
    },
)
def update_sources(
    body: SourcesRequest,
    db: Session = Depends(get_db),
    agent: AgentUser = Depends(get_current_agent),
):
    """
    Persist enabled_lead_source_ids and advance onboarding_step to 4.

    - Creates AgentPreferences record if one does not yet exist.
    - Serialises the list as a JSON string into enabled_lead_source_ids.
    - Advances onboarding_step to 4 if currently less than 4.
    - Returns {"ok": true, "onboarding_step": 4}.

    Requirements: 6.2
    """
    from gmail_lead_sync.agent_models import AgentPreferences

    # Upsert AgentPreferences
    prefs = agent.preferences
    if prefs is None:
        prefs = AgentPreferences(agent_user_id=agent.id)
        db.add(prefs)

    prefs.enabled_lead_source_ids = _json.dumps(body.enabled_lead_source_ids)

    # Advance onboarding step
    if agent.onboarding_step < 4:
        agent.onboarding_step = 4

    db.commit()

    return SourcesResponse(ok=True, onboarding_step=4)
