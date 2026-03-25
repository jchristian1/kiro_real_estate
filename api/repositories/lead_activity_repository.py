"""
Lead activity repository — read boundary for the lead activity model.

All queries against the lead_events table for timeline/activity purposes
go through this class. Do not query LeadEvent directly from routers or services.

Phase 3A: read-layer foundation only.
Later phases will add richer filtering, pagination, and projection.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Optional

from sqlalchemy.orm import Session

from gmail_lead_sync.agent_models import LeadEvent


class LeadActivityRepository:
    """Read boundary for lead activity (LeadEvent) records."""

    def __init__(self, db: Session) -> None:
        self._db = db

    def get_timeline(
        self,
        lead_id: int,
        *,
        limit: int = 100,
        before: Optional[datetime] = None,
    ) -> list[LeadEvent]:
        """Return activity events for a lead ordered by created_at ascending.

        Args:
            lead_id: Target lead.
            limit:   Maximum number of events to return (default 100).
            before:  If provided, return only events before this timestamp.
        """
        q = (
            self._db.query(LeadEvent)
            .filter(LeadEvent.lead_id == lead_id)
        )
        if before is not None:
            q = q.filter(LeadEvent.created_at < before)
        return (
            q.order_by(LeadEvent.created_at.asc())
            .limit(limit)
            .all()
        )

    def get_company_timeline(
        self,
        company_id: int,
        *,
        limit: int = 200,
        before: Optional[datetime] = None,
        event_types: Optional[list[str]] = None,
    ) -> list[LeadEvent]:
        """Return activity events for all leads belonging to a company.

        Ordered by created_at descending (most recent first) for dashboard use.

        Args:
            company_id:  Tenant ID.
            limit:       Maximum number of events to return.
            before:      If provided, return only events before this timestamp.
            event_types: If provided, filter to only these event_type values.
        """
        q = (
            self._db.query(LeadEvent)
            .filter(LeadEvent.company_id == company_id)
        )
        if before is not None:
            q = q.filter(LeadEvent.created_at < before)
        if event_types:
            q = q.filter(LeadEvent.event_type.in_(event_types))
        return (
            q.order_by(LeadEvent.created_at.desc())
            .limit(limit)
            .all()
        )

    def count_events_since(
        self,
        lead_id: int,
        event_type: str,
        since: datetime,
    ) -> int:
        """Return the count of events of a given type for a lead since a timestamp.

        Useful for idempotency checks (e.g. "has a form invite already been sent?").
        """
        return (
            self._db.query(LeadEvent)
            .filter(
                LeadEvent.lead_id == lead_id,
                LeadEvent.event_type == event_type,
                LeadEvent.created_at >= since,
            )
            .count()
        )


def parse_activity_metadata(event: LeadEvent) -> dict[str, Any]:
    """Parse the metadata_json field of a LeadEvent into a dict.

    Returns an empty dict if metadata_json is None or invalid JSON.
    Falls back to parsing the legacy `payload` field if metadata_json is absent.
    """
    if event.metadata_json:
        try:
            return json.loads(event.metadata_json)
        except (json.JSONDecodeError, TypeError):
            return {}
    if event.payload:
        try:
            return json.loads(event.payload)
        except (json.JSONDecodeError, TypeError):
            return {}
    return {}
