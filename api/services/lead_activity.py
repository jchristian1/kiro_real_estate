"""
Lead activity service — single write boundary for the lead activity model.

This is the ONLY place that creates LeadEvent records for Phase 3A+ activity
event types. All modules that need to record lead activity should call
record_activity() from here.

Why this is separate from audit_log.py
───────────────────────────────────────
audit_log.py / AuditLog table:
  - Compliance and admin trail
  - Scoped to admin users (user_id FK to users table)
  - Records system/admin operations on any resource type
  - Not lead-specific; not queryable as a lead timeline
  - Append-only for regulatory/debugging purposes

lead_activity.py / LeadEvent table:
  - Operational timeline for a single lead
  - Scoped to a lead_id (and optionally company_id for tenant reads)
  - Records what happened to THIS lead from any actor
  - Designed to be read as a chronological timeline in the agent UI
  - Append-only for data integrity

They serve different consumers and different queries. Do not merge them.

Activity event types (Phase 3A):
  lead_created, lead_stage_changed, response_email_sent,
  qualification_form_sent, qualification_form_submitted,
  qualification_bucket_assigned, manual_admin_action,
  manual_agent_action, pipeline_action_executed

Legacy event types (pre-Phase-3A, still valid):
  EMAIL_RECEIVED, LEAD_PARSED, INVITE_CREATED, INVITE_SENT,
  FORM_SUBMITTED, LEAD_SCORED, POST_EMAIL_SENT, AGENT_CONTACTED,
  APPOINTMENT_SET, LEAD_LOST, LEAD_CLOSED, NOTE_ADDED,
  STATUS_CHANGED, WATCHER_TOGGLED
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any, Optional

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Structured activity event shape
# ---------------------------------------------------------------------------
# Every call to record_activity() produces a LeadEvent row with this shape:
#
#   lead_id       int           — target lead (required)
#   event_type    str           — one of the valid enum values (required)
#   occurred_at   datetime      — when the event happened (defaults to utcnow)
#   company_id    int | None    — tenant scoping (recommended for new events)
#   actor_source  str | None    — "system" | "pipeline" | "agent" | "admin" | "qualification"
#   actor_id      int | None    — numeric reference to the acting entity (e.g. agent_user_id)
#   metadata      dict | None   — structured context (stored as metadata_json)
#
# The legacy `payload` column is NOT written by this service.
# New code must use `metadata` (stored in metadata_json).
# ---------------------------------------------------------------------------


def record_activity(
    db: Session,
    *,
    lead_id: int,
    event_type: str,
    company_id: Optional[int] = None,
    actor_source: Optional[str] = None,
    actor_id: Optional[int] = None,
    metadata: Optional[dict[str, Any]] = None,
    occurred_at: Optional[datetime] = None,
) -> None:
    """Append a lead activity event to the lead's operational timeline.

    This is an append-only operation — existing records are never modified.
    Failures are logged but never propagate to the caller (activity recording
    must not break the main execution path).

    Args:
        db:           Active SQLAlchemy session.
        lead_id:      Target lead (required).
        event_type:   One of the valid LeadEvent event_type enum values.
        company_id:   Tenant ID for multi-tenant reads (recommended).
        actor_source: Who/what caused the event.
                      One of: "system", "pipeline", "agent", "admin", "qualification".
        actor_id:     Optional numeric reference to the acting entity.
        metadata:     Structured context dict (stored as JSON in metadata_json).
        occurred_at:  Event timestamp; defaults to utcnow if not provided.
    """
    from gmail_lead_sync.agent_models import LeadEvent

    try:
        event = LeadEvent(
            lead_id=lead_id,
            company_id=company_id,
            event_type=event_type,
            actor_source=actor_source,
            actor_id=actor_id,
            metadata_json=json.dumps(metadata) if metadata is not None else None,
            created_at=occurred_at or datetime.utcnow(),
        )
        db.add(event)
        db.flush()
        logger.debug(
            "lead_activity: recorded event_type=%s lead_id=%d company_id=%s actor=%s",
            event_type, lead_id, company_id, actor_source,
        )
    except Exception as exc:
        logger.error(
            "lead_activity: failed to record event_type=%s lead_id=%d: %s",
            event_type, lead_id, exc, exc_info=True,
        )
