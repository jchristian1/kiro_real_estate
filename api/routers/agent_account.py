"""
Agent account management routes (PR A1 — Gmail/watcher endpoints removed).

Remaining endpoints:
- PUT /api/v1/agent/account/preferences  — update personal preferences

Removed in PR A1 (company owns inbox/watcher, not agents):
- GET    /agent/account/gmail
- POST   /agent/account/gmail/test
- PUT    /agent/account/gmail
- DELETE /agent/account/gmail
- PATCH  /agent/account/watcher

Requirements: 16.5
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from api.dependencies.auth import get_current_agent
from api.dependencies.db import get_db
from gmail_lead_sync.agent_models import AgentPreferences, AgentUser

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/agent/account", tags=["Agent Account"])


class PreferencesUpdateRequest(BaseModel):
    service_area: Optional[str] = None
    timezone: Optional[str] = None
    quiet_hours_start: Optional[str] = None
    quiet_hours_end: Optional[str] = None


class PreferencesUpdateResponse(BaseModel):
    ok: bool


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


@router.put("/preferences", response_model=PreferencesUpdateResponse)
def update_preferences(
    body: PreferencesUpdateRequest,
    agent: AgentUser = Depends(get_current_agent),
    db: Session = Depends(get_db),
):
    """Update agent personal preferences (timezone, service area, quiet hours)."""
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
