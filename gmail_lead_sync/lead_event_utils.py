"""
Shared utility for inserting LeadEvent records into the audit trail.

This module provides a single helper function used by the watcher pipeline
and preapproval handlers to insert immutable lead event records.

Requirements: 20.1, 20.2
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


def insert_lead_event(
    db: Session,
    lead_id: int,
    event_type: str,
    payload_dict: Optional[Dict[str, Any]] = None,
    agent_user_id: Optional[int] = None,
) -> None:
    """Insert a single LeadEvent record into the audit trail.

    This is an append-only operation — existing records are never modified.

    Args:
        db: SQLAlchemy session (must be active).
        lead_id: ID of the lead this event belongs to.
        event_type: One of the valid LeadEvent event_type enum values.
        payload_dict: Optional dict to serialize as JSON payload.
        agent_user_id: Optional FK to agent_users.id (nullable per schema).

    Requirements: 20.1, 20.2
    """
    from gmail_lead_sync.agent_models import LeadEvent  # local import to avoid circular deps

    try:
        event = LeadEvent(
            lead_id=lead_id,
            agent_user_id=agent_user_id,
            event_type=event_type,
            payload=json.dumps(payload_dict) if payload_dict is not None else None,
            created_at=datetime.utcnow(),
        )
        db.add(event)
        db.flush()  # write to DB within current transaction without committing
        logger.debug(
            "LeadEvent inserted: lead_id=%d event_type=%s agent_user_id=%s",
            lead_id,
            event_type,
            agent_user_id,
        )
    except Exception as exc:
        # Never let event insertion break the main pipeline
        logger.error(
            "Failed to insert LeadEvent (lead_id=%d event_type=%s): %s",
            lead_id,
            event_type,
            exc,
            exc_info=True,
        )
