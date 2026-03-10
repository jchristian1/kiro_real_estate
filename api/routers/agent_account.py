"""
Agent account/Gmail management routes.

Provides:
- GET    /api/v1/agent/account/gmail          — Gmail connection status
- POST   /api/v1/agent/account/gmail/test     — Test stored credentials via IMAP
- PUT    /api/v1/agent/account/gmail          — Update Gmail credentials (test first)
- DELETE /api/v1/agent/account/gmail          — Disconnect Gmail, stop watcher
- PATCH  /api/v1/agent/account/watcher        — Toggle watcher (403 if admin-locked)
- PUT    /api/v1/agent/account/preferences    — Update service_area, timezone, quiet hours

Requirements: 16.1, 16.2, 16.3, 16.4, 16.5, 16.6
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, SecretStr
from sqlalchemy.orm import Session

from api.dependencies.agent_auth import get_current_agent
from api.main import get_db
from api.services.credential_encryption import decrypt_app_password, encrypt_app_password
from api.services.imap_service import (
    IMAPRateLimitError,
    check_and_record_imap_attempt,
    test_imap_connection,
)
from gmail_lead_sync.agent_models import AgentPreferences, AgentUser
from gmail_lead_sync.models import Credentials

router = APIRouter(prefix="/agent/account", tags=["Agent Account"])


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class GmailStatusResponse(BaseModel):
    """GET /agent/account/gmail response."""

    connected: bool
    gmail_address: Optional[str]
    last_sync: Optional[datetime]
    watcher_enabled: bool
    watcher_admin_locked: bool


class GmailTestResponse(BaseModel):
    """POST /agent/account/gmail/test response."""

    ok: bool
    error: Optional[str] = None


class GmailUpdateRequest(BaseModel):
    """PUT /agent/account/gmail request body."""

    gmail_address: str = Field(..., min_length=1, max_length=255)
    app_password: SecretStr = Field(..., min_length=1)


class GmailUpdateResponse(BaseModel):
    """PUT /agent/account/gmail response."""

    connected: bool
    gmail_address: str


class GmailDisconnectResponse(BaseModel):
    """DELETE /agent/account/gmail response."""

    ok: bool
    watcher_stopped: bool


class WatcherToggleRequest(BaseModel):
    """PATCH /agent/account/watcher request body."""

    enabled: bool


class WatcherToggleResponse(BaseModel):
    """PATCH /agent/account/watcher response."""

    watcher_enabled: bool


class PreferencesUpdateRequest(BaseModel):
    """PUT /agent/account/preferences request body."""

    service_area: Optional[str] = None
    timezone: Optional[str] = Field(default=None, max_length=100)
    quiet_hours_start: Optional[str] = Field(default=None, description="HH:MM format")
    quiet_hours_end: Optional[str] = Field(default=None, description="HH:MM format")


class PreferencesUpdateResponse(BaseModel):
    """PUT /agent/account/preferences response."""

    ok: bool


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_or_create_prefs(agent: AgentUser, db: Session) -> AgentPreferences:
    """Return the agent's AgentPreferences, creating one if it doesn't exist."""
    prefs = (
        db.query(AgentPreferences)
        .filter(AgentPreferences.agent_user_id == agent.id)
        .first()
    )
    if prefs is None:
        prefs = AgentPreferences(
            agent_user_id=agent.id,
            created_at=datetime.utcnow(),
        )
        db.add(prefs)
        db.flush()
    return prefs


def _parse_time(value: Optional[str]):
    """Parse "HH:MM" string into datetime.time, or return None."""
    if value is None:
        return None
    try:
        from datetime import datetime as _dt
        return _dt.strptime(value, "%H:%M").time()
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# GET /agent/account/gmail
# ---------------------------------------------------------------------------


@router.get(
    "/gmail",
    response_model=GmailStatusResponse,
    summary="Get Gmail connection status for the authenticated agent",
)
def get_gmail_status(
    db: Session = Depends(get_db),
    agent: AgentUser = Depends(get_current_agent),
):
    """
    Return Gmail connection status, watcher state, and admin lock flag.

    - connected=True if agent.credentials_id is not null and the credentials record exists.
    - gmail_address from credentials.email_encrypted (stored as plaintext display value).
    - watcher_enabled from AgentPreferences.watcher_enabled (default True).
    - watcher_admin_locked from AgentPreferences.watcher_admin_override (default False).

    Requirements: 16.1
    """
    prefs = _get_or_create_prefs(agent, db)
    db.commit()

    connected = False
    gmail_address: Optional[str] = None

    if agent.credentials_id is not None:
        creds = (
            db.query(Credentials)
            .filter(Credentials.id == agent.credentials_id)
            .first()
        )
        if creds is not None:
            connected = True
            # email_encrypted stores the Gmail address as plaintext for display
            gmail_address = creds.email_encrypted

    return GmailStatusResponse(
        connected=connected,
        gmail_address=gmail_address,
        last_sync=None,  # last_sync tracking not yet implemented in watcher
        watcher_enabled=prefs.watcher_enabled,
        watcher_admin_locked=prefs.watcher_admin_override,
    )


# ---------------------------------------------------------------------------
# POST /agent/account/gmail/test
# ---------------------------------------------------------------------------


@router.post(
    "/gmail/test",
    response_model=GmailTestResponse,
    summary="Test the currently stored Gmail credentials via live IMAP",
)
def test_gmail_connection(
    db: Session = Depends(get_db),
    agent: AgentUser = Depends(get_current_agent),
):
    """
    Perform a live IMAP test using the agent's stored (encrypted) credentials.

    - If no credentials are stored: return { ok: false, error: "NO_CREDENTIALS" }.
    - Decrypts the stored app_password and calls test_imap_connection.
    - Returns { ok: true } on success or { ok: false, error: <code> } on failure.
    - app_password is never included in logs or responses.

    Requirements: 16.2, 19.4
    """
    if agent.credentials_id is None:
        return GmailTestResponse(ok=False, error="NO_CREDENTIALS")

    creds = (
        db.query(Credentials)
        .filter(Credentials.id == agent.credentials_id)
        .first()
    )
    if creds is None:
        return GmailTestResponse(ok=False, error="NO_CREDENTIALS")

    try:
        app_password = decrypt_app_password(creds.app_password_encrypted)
    except (ValueError, EnvironmentError):
        return GmailTestResponse(ok=False, error="DECRYPTION_FAILED")

    result = test_imap_connection(creds.email_encrypted, app_password)

    if result["success"]:
        return GmailTestResponse(ok=True)
    else:
        return GmailTestResponse(ok=False, error=result["error"])


# ---------------------------------------------------------------------------
# PUT /agent/account/gmail
# ---------------------------------------------------------------------------


@router.put(
    "/gmail",
    response_model=GmailUpdateResponse,
    summary="Update Gmail credentials — tests new credentials before persisting",
)
def update_gmail_credentials(
    body: GmailUpdateRequest,
    db: Session = Depends(get_db),
    agent: AgentUser = Depends(get_current_agent),
):
    """
    Test new credentials first; persist only if the IMAP test passes.

    1. Check rate limit — 429 if exceeded.
    2. Test new credentials via live IMAP.
    3. If test fails: return 422 with { error: <IMAP_ERROR_CODE> }.
    4. If test passes: encrypt app_password, update/create credentials record,
       set agent.credentials_id.

    Requirements: 16.3, 19.1, 19.4
    """
    # Rate limit check
    try:
        check_and_record_imap_attempt(agent.id)
    except IMAPRateLimitError as exc:
        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            content={"error": "RATE_LIMITED", "retry_after_seconds": exc.retry_after_seconds},
        )

    # Test new credentials
    result = test_imap_connection(
        body.gmail_address, body.app_password.get_secret_value()
    )

    if not result["success"]:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={"error": result["error"]},
        )

    # Encrypt and persist
    encrypted_password = encrypt_app_password(body.app_password.get_secret_value())

    if agent.credentials_id is not None:
        creds = (
            db.query(Credentials)
            .filter(Credentials.id == agent.credentials_id)
            .first()
        )
        if creds is not None:
            creds.email_encrypted = body.gmail_address
            creds.app_password_encrypted = encrypted_password
        else:
            # Stale FK — create a new record
            creds = Credentials(
                agent_id=str(agent.id),
                email_encrypted=body.gmail_address,
                app_password_encrypted=encrypted_password,
            )
            db.add(creds)
            db.flush()
            agent.credentials_id = creds.id
    else:
        creds = Credentials(
            agent_id=str(agent.id),
            email_encrypted=body.gmail_address,
            app_password_encrypted=encrypted_password,
        )
        db.add(creds)
        db.flush()
        agent.credentials_id = creds.id

    db.commit()

    return GmailUpdateResponse(connected=True, gmail_address=body.gmail_address)


# ---------------------------------------------------------------------------
# DELETE /agent/account/gmail
# ---------------------------------------------------------------------------


@router.delete(
    "/gmail",
    response_model=GmailDisconnectResponse,
    summary="Disconnect Gmail — clears credentials and stops watcher",
)
def disconnect_gmail(
    db: Session = Depends(get_db),
    agent: AgentUser = Depends(get_current_agent),
):
    """
    Clear agent.credentials_id and disable the watcher.

    - Sets agent.credentials_id = None.
    - Sets AgentPreferences.watcher_enabled = False.
    - Returns { ok: true, watcher_stopped: true }.

    Requirements: 16.4
    """
    agent.credentials_id = None

    prefs = _get_or_create_prefs(agent, db)
    prefs.watcher_enabled = False

    db.commit()

    return GmailDisconnectResponse(ok=True, watcher_stopped=True)


# ---------------------------------------------------------------------------
# PATCH /agent/account/watcher
# ---------------------------------------------------------------------------


@router.patch(
    "/watcher",
    response_model=WatcherToggleResponse,
    summary="Toggle the Gmail watcher on or off",
    responses={
        403: {"description": "Watcher is admin-locked"},
    },
)
def toggle_watcher(
    body: WatcherToggleRequest,
    db: Session = Depends(get_db),
    agent: AgentUser = Depends(get_current_agent),
):
    """
    Enable or disable the Gmail watcher for the authenticated agent.

    - If AgentPreferences.watcher_admin_override = True: return 403 with
      { error: "ADMIN_LOCKED" } regardless of the requested enabled value.
    - Otherwise: update watcher_enabled and return the new state.

    Requirements: 16.5, 16.6
    """
    prefs = _get_or_create_prefs(agent, db)
    db.commit()

    if prefs.watcher_admin_override:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": "ADMIN_LOCKED"},
        )

    prefs.watcher_enabled = body.enabled
    db.commit()

    return WatcherToggleResponse(watcher_enabled=prefs.watcher_enabled)


# ---------------------------------------------------------------------------
# PUT /agent/account/preferences
# ---------------------------------------------------------------------------


@router.put(
    "/preferences",
    response_model=PreferencesUpdateResponse,
    summary="Update agent service area, timezone, and quiet hours",
)
def update_preferences(
    body: PreferencesUpdateRequest,
    db: Session = Depends(get_db),
    agent: AgentUser = Depends(get_current_agent),
):
    """
    Update agent profile and preference fields.

    - Updates AgentUser.service_area and AgentUser.timezone if provided.
    - Updates AgentPreferences.quiet_hours_start and quiet_hours_end if provided.
    - Creates AgentPreferences if it doesn't exist.

    Requirements: 16.5 (preferences management)
    """
    now = datetime.utcnow()

    # Update AgentUser fields
    if body.service_area is not None:
        agent.service_area = body.service_area
    if body.timezone is not None:
        agent.timezone = body.timezone
    agent.updated_at = now

    # Update AgentPreferences fields
    prefs = _get_or_create_prefs(agent, db)

    if body.quiet_hours_start is not None:
        prefs.quiet_hours_start = _parse_time(body.quiet_hours_start)
    if body.quiet_hours_end is not None:
        prefs.quiet_hours_end = _parse_time(body.quiet_hours_end)

    prefs.updated_at = now

    db.commit()

    return PreferencesUpdateResponse(ok=True)
