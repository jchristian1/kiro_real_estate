"""
Agent account management routes.

Endpoints:
- GET    /api/v1/agent/account/gmail          - Gmail connection status
- POST   /api/v1/agent/account/gmail/test     - test stored credentials
- PUT    /api/v1/agent/account/gmail          - update credentials
- DELETE /api/v1/agent/account/gmail          - disconnect Gmail
- PATCH  /api/v1/agent/account/watcher        - toggle watcher
- PUT    /api/v1/agent/account/preferences    - update preferences

Requirements: 16.1-16.6
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from api.dependencies.auth import get_current_agent
from api.dependencies.db import get_db
from api.services.credential_encryption import (
    encrypt_app_password,
    decrypt_app_password,
    GmailCredentialUpdateRequest,
)
from api.services.imap_service import test_imap_connection
from gmail_lead_sync.agent_models import AgentPreferences, AgentUser
from gmail_lead_sync.models import Credentials

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/agent/account", tags=["Agent Account"])


class GmailStatusResponse(BaseModel):
    connected: bool
    gmail_address: Optional[str] = None
    last_sync: Optional[str] = None
    watcher_enabled: bool = True
    watcher_admin_locked: bool = False


class TestGmailResponse(BaseModel):
    ok: bool
    error: Optional[str] = None
    message: Optional[str] = None


class GmailConnectResponse(BaseModel):
    connected: bool
    gmail_address: str
    last_sync: Optional[str] = None


class DeleteGmailResponse(BaseModel):
    ok: bool
    watcher_stopped: bool


class WatcherPatchRequest(BaseModel):
    enabled: bool


class WatcherPatchResponse(BaseModel):
    watcher_enabled: bool


class PreferencesUpdateRequest(BaseModel):
    service_area: Optional[str] = None
    timezone: Optional[str] = None
    quiet_hours_start: Optional[str] = None
    quiet_hours_end: Optional[str] = None


class PreferencesUpdateResponse(BaseModel):
    ok: bool


def _get_credentials(db: Session, agent: AgentUser) -> Optional[Credentials]:
    if agent.credentials_id is None:
        return None
    return db.query(Credentials).filter(Credentials.id == agent.credentials_id).first()


def _get_or_create_prefs(db: Session, agent: AgentUser) -> AgentPreferences:
    prefs = db.query(AgentPreferences).filter(
        AgentPreferences.agent_user_id == agent.id
    ).first()
    if prefs is None:
        prefs = AgentPreferences(
            agent_user_id=agent.id,
            created_at=datetime.utcnow(),
        )
        db.add(prefs)
        db.flush()
    return prefs


@router.get("/gmail", response_model=GmailStatusResponse)
def get_gmail_status(
    agent: AgentUser = Depends(get_current_agent),
    db: Session = Depends(get_db),
):
    creds = _get_credentials(db, agent)
    prefs = db.query(AgentPreferences).filter(
        AgentPreferences.agent_user_id == agent.id
    ).first()

    watcher_enabled = prefs.watcher_enabled if prefs else True
    watcher_admin_locked = prefs.watcher_admin_override if prefs else False

    if creds is None:
        return GmailStatusResponse(
            connected=False,
            watcher_enabled=watcher_enabled,
            watcher_admin_locked=watcher_admin_locked,
        )

    return GmailStatusResponse(
        connected=True,
        gmail_address=creds.email_encrypted,
        last_sync=None,
        watcher_enabled=watcher_enabled,
        watcher_admin_locked=watcher_admin_locked,
    )


@router.post("/gmail/test", response_model=TestGmailResponse)
def test_gmail_connection(
    agent: AgentUser = Depends(get_current_agent),
    db: Session = Depends(get_db),
):
    creds = _get_credentials(db, agent)
    if creds is None:
        return TestGmailResponse(ok=False, error="NO_CREDENTIALS")

    try:
        plaintext_password = decrypt_app_password(creds.app_password_encrypted)
    except Exception as exc:
        logger.error("Failed to decrypt credentials for agent %s: %s", agent.id, exc)
        return TestGmailResponse(ok=False, error="DECRYPTION_FAILED")

    result = test_imap_connection(creds.email_encrypted, plaintext_password)

    if result.get("success"):
        return TestGmailResponse(ok=True)
    else:
        return TestGmailResponse(
            ok=False,
            error=result.get("error"),
            message=result.get("message"),
        )


@router.put("/gmail", response_model=GmailConnectResponse)
def update_gmail_credentials(
    body: GmailCredentialUpdateRequest,
    agent: AgentUser = Depends(get_current_agent),
    db: Session = Depends(get_db),
):
    plaintext = body.app_password.get_secret_value()
    result = test_imap_connection(body.gmail_address, plaintext)

    if not result.get("success"):
        from fastapi.responses import JSONResponse
        imap_error = result.get("error", "IMAP_FAILED")
        imap_message = result.get("message", "IMAP connection failed")
        return JSONResponse(
            status_code=422,
            content={
                "error": imap_error,
                "message": imap_message,
                "code": imap_error,
                "details": None,
            },
        )

    encrypted = encrypt_app_password(plaintext)

    existing_creds = _get_credentials(db, agent)
    if existing_creds is not None:
        existing_creds.email_encrypted = body.gmail_address
        existing_creds.app_password_encrypted = encrypted
        db.commit()
    else:
        creds = Credentials(
            agent_id=str(agent.id),
            email_encrypted=body.gmail_address,
            app_password_encrypted=encrypted,
        )
        db.add(creds)
        db.flush()
        agent.credentials_id = creds.id
        db.commit()

    return GmailConnectResponse(
        connected=True,
        gmail_address=body.gmail_address,
        last_sync=None,
    )


@router.delete("/gmail", response_model=DeleteGmailResponse)
def delete_gmail_connection(
    agent: AgentUser = Depends(get_current_agent),
    db: Session = Depends(get_db),
):
    agent.credentials_id = None

    prefs = db.query(AgentPreferences).filter(
        AgentPreferences.agent_user_id == agent.id
    ).first()
    if prefs is not None:
        prefs.watcher_enabled = False

    db.commit()

    return DeleteGmailResponse(ok=True, watcher_stopped=True)


@router.patch("/watcher", response_model=WatcherPatchResponse)
def patch_watcher(
    body: WatcherPatchRequest,
    agent: AgentUser = Depends(get_current_agent),
    db: Session = Depends(get_db),
):
    prefs = _get_or_create_prefs(db, agent)

    if prefs.watcher_admin_override:
        raise HTTPException(
            status_code=403,
            detail={"error": "ADMIN_LOCKED", "message": "Watcher is locked by admin"},
        )

    prefs.watcher_enabled = body.enabled
    db.commit()

    return WatcherPatchResponse(watcher_enabled=prefs.watcher_enabled)


@router.put("/preferences", response_model=PreferencesUpdateResponse)
def update_preferences(
    body: PreferencesUpdateRequest,
    agent: AgentUser = Depends(get_current_agent),
    db: Session = Depends(get_db),
):
    from datetime import time as dt_time

    if body.service_area is not None:
        agent.service_area = body.service_area
    if body.timezone is not None:
        agent.timezone = body.timezone

    if body.quiet_hours_start is not None or body.quiet_hours_end is not None:
        prefs = _get_or_create_prefs(db, agent)
        if body.quiet_hours_start is not None:
            h, m = map(int, body.quiet_hours_start.split(":"))
            prefs.quiet_hours_start = dt_time(h, m)
        if body.quiet_hours_end is not None:
            h, m = map(int, body.quiet_hours_end.split(":"))
            prefs.quiet_hours_end = dt_time(h, m)

    db.commit()
    return PreferencesUpdateResponse(ok=True)
