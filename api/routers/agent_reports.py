"""
Agent reports routes.

Provides:
- GET /api/v1/agent/reports/summary — pipeline metrics summary for a given period

Requirements: 17.1, 17.2, 17.3
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from api.dependencies.agent_auth import get_current_agent
from api.main import get_db
from gmail_lead_sync.agent_models import AgentUser, LeadEvent
from gmail_lead_sync.models import Lead

router = APIRouter(prefix="/agent/reports", tags=["Agent Reports"])

# Valid period values mapped to number of days
_VALID_PERIODS: Dict[str, int] = {
    "7d": 7,
    "30d": 30,
    "90d": 90,
}


# ---------------------------------------------------------------------------
# Pydantic response models
# ---------------------------------------------------------------------------


class LeadsBySource(BaseModel):
    source: str
    count: int


class BucketDistribution(BaseModel):
    HOT: int
    WARM: int
    NURTURE: int


class ReportsSummaryResponse(BaseModel):
    leads_by_source: List[LeadsBySource]
    bucket_distribution: BucketDistribution
    avg_response_time_minutes: Optional[float]
    appointments_set: int
    period_start: datetime
    period_end: datetime


# ---------------------------------------------------------------------------
# GET /agent/reports/summary
# ---------------------------------------------------------------------------


@router.get(
    "/summary",
    response_model=ReportsSummaryResponse,
    summary="Pipeline metrics summary scoped to the authenticated agent",
)
def get_reports_summary(
    period: str = Query(
        default="30d",
        description="Reporting period: 7d, 30d, or 90d",
    ),
    db: Session = Depends(get_db),
    agent: AgentUser = Depends(get_current_agent),
):
    """
    Return a summary of pipeline metrics for the authenticated agent over the
    requested period.

    - leads_by_source: lead counts grouped by lead_source_name, sorted DESC.
    - bucket_distribution: HOT / WARM / NURTURE counts within the period.
    - avg_response_time_minutes: mean minutes between EMAIL_RECEIVED and the
      first AGENT_CONTACTED event for each lead that was contacted within the
      period; null when no data is available.
    - appointments_set: count of leads with agent_current_state == 'APPOINTMENT_SET'.
    - period_start / period_end: UTC datetimes bounding the query window.

    All data is scoped to the authenticated agent (Requirement 17.3).

    Requirements: 17.1, 17.2, 17.3
    """
    # Validate period (Requirement 17.2) — return 422 for unknown values
    if period not in _VALID_PERIODS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid period '{period}'. Must be one of: 7d, 30d, 90d.",
        )

    days = _VALID_PERIODS[period]
    period_end = datetime.utcnow()
    period_start = period_end - timedelta(days=days)

    # Base queryset — tenant isolation (Requirement 17.3)
    base_q = (
        db.query(Lead)
        .filter(
            Lead.agent_user_id == agent.id,
            Lead.created_at >= period_start,
        )
    )
    period_leads: List[Lead] = base_q.all()

    # ------------------------------------------------------------------
    # leads_by_source — group by lead_source_name, count, sort DESC
    # ------------------------------------------------------------------
    source_counts: Dict[str, int] = {}
    for lead in period_leads:
        src = lead.lead_source_name or "Unknown"
        source_counts[src] = source_counts.get(src, 0) + 1

    leads_by_source = [
        LeadsBySource(source=src, count=cnt)
        for src, cnt in sorted(source_counts.items(), key=lambda x: -x[1])
    ]

    # ------------------------------------------------------------------
    # bucket_distribution — count per score_bucket
    # ------------------------------------------------------------------
    bucket_counts: Dict[str, int] = {"HOT": 0, "WARM": 0, "NURTURE": 0}
    for lead in period_leads:
        bucket = lead.score_bucket
        if bucket in bucket_counts:
            bucket_counts[bucket] += 1

    bucket_distribution = BucketDistribution(
        HOT=bucket_counts["HOT"],
        WARM=bucket_counts["WARM"],
        NURTURE=bucket_counts["NURTURE"],
    )

    # ------------------------------------------------------------------
    # appointments_set — leads with agent_current_state == 'APPOINTMENT_SET'
    # ------------------------------------------------------------------
    appointments_set = sum(
        1 for lead in period_leads if lead.agent_current_state == "APPOINTMENT_SET"
    )

    # ------------------------------------------------------------------
    # avg_response_time_minutes
    #
    # For each lead that has an AGENT_CONTACTED event within the period:
    #   - Find the earliest EMAIL_RECEIVED event for that lead
    #   - Compute difference in minutes
    # Return the mean of all differences, rounded to 2 decimal places.
    # Return null if no data.
    # ------------------------------------------------------------------
    lead_ids_in_period = {lead.id for lead in period_leads}

    # Fetch all AGENT_CONTACTED events within the period for this agent's leads
    contacted_events: List[LeadEvent] = (
        db.query(LeadEvent)
        .filter(
            LeadEvent.agent_user_id == agent.id,
            LeadEvent.event_type == "AGENT_CONTACTED",
            LeadEvent.created_at >= period_start,
            LeadEvent.lead_id.in_(lead_ids_in_period),
        )
        .all()
    ) if lead_ids_in_period else []

    avg_response_time_minutes: Optional[float] = None

    if contacted_events:
        # Group AGENT_CONTACTED events by lead_id — keep earliest per lead
        earliest_contacted: Dict[int, datetime] = {}
        for ev in contacted_events:
            existing = earliest_contacted.get(ev.lead_id)
            if existing is None or ev.created_at < existing:
                earliest_contacted[ev.lead_id] = ev.created_at

        # For each lead with a contact event, find the earliest EMAIL_RECEIVED
        contacted_lead_ids = list(earliest_contacted.keys())
        email_received_events: List[LeadEvent] = (
            db.query(LeadEvent)
            .filter(
                LeadEvent.lead_id.in_(contacted_lead_ids),
                LeadEvent.event_type == "EMAIL_RECEIVED",
            )
            .all()
        )

        earliest_received: Dict[int, datetime] = {}
        for ev in email_received_events:
            existing = earliest_received.get(ev.lead_id)
            if existing is None or ev.created_at < existing:
                earliest_received[ev.lead_id] = ev.created_at

        # Compute differences in minutes
        diffs: List[float] = []
        for lead_id, contacted_at in earliest_contacted.items():
            received_at = earliest_received.get(lead_id)
            if received_at is not None:
                diff_minutes = (contacted_at - received_at).total_seconds() / 60.0
                if diff_minutes >= 0:
                    diffs.append(diff_minutes)

        if diffs:
            avg_response_time_minutes = round(sum(diffs) / len(diffs), 2)

    return ReportsSummaryResponse(
        leads_by_source=leads_by_source,
        bucket_distribution=bucket_distribution,
        avg_response_time_minutes=avg_response_time_minutes,
        appointments_set=appointments_set,
        period_start=period_start,
        period_end=period_end,
    )
