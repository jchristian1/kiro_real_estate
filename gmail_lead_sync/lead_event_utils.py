"""
Shared utility for inserting LeadEvent records.

COMPATIBILITY SHIM — do not use in new code.

New code must call api.services.lead_activity.record_activity() directly,
which accepts the full structured event shape including company_id and
actor_source. This shim exists only for callers that predate Phase 3A and
have not been updated yet.

What this shim passes through to record_activity():
  - lead_id       → lead_id
  - event_type    → event_type
  - payload_dict  → metadata
  - agent_user_id → actor_id

What this shim does NOT pass through (callers must migrate to record_activity
to supply these):
  - company_id    (always None via this shim — tenant scoping lost)
  - actor_source  (always None via this shim)
  - occurred_at   (always defaults to utcnow)

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
    """Compatibility shim — delegates to record_activity().

    DO NOT USE IN NEW CODE. Call record_activity() directly so that
    company_id and actor_source are properly supplied.

    This shim intentionally omits company_id and actor_source because
    legacy callers do not have that context. Events written via this shim
    will not appear in company-scoped timeline queries until the caller
    is migrated to record_activity().
    """
    from api.services.lead_activity import record_activity

    record_activity(
        db,
        lead_id=lead_id,
        event_type=event_type,
        actor_id=agent_user_id,
        metadata=payload_dict,
        # company_id and actor_source intentionally omitted —
        # legacy callers do not have this context.
    )
