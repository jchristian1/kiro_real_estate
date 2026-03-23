"""
Shared utility for inserting LeadEvent records into the audit trail.

DEPRECATED: New code should call api.services.lead_activity.record_activity()
directly. This module is kept as a shim for existing callers that have not
been updated yet.

Requirements: 20.1, 20.2
"""

from __future__ import annotations

import logging
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
    """Insert a single LeadEvent record.

    Deprecated shim — delegates to api.services.lead_activity.record_activity().
    Existing callers continue to work unchanged.

    New code should call record_activity() directly with the full structured
    event shape (company_id, actor_source, metadata).
    """
    from api.services.lead_activity import record_activity

    record_activity(
        db,
        lead_id=lead_id,
        event_type=event_type,
        actor_id=agent_user_id,
        metadata=payload_dict,
    )
