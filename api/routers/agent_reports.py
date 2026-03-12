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
from api.repositories import LeadRepository, LeadEventRepository
from gmail_lead_sync.agent_models import AgentUser
from api.dependencies.auth import require_role

router = APIRouter(prefix="/agent/reports", tags=["Agent Reports"], dependencies=[Depends(require_role("agent"))])

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

    All data is scoped to the authenticated agent (Requirement 17.3).

    Requirements: 17.1, 17.2, 17.3
    """
    if period not in _VALID_PERIODS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid period '{period}'. Must be one of: 7d, 30d, 90d.",
        )

    days = _VALID_PERIODS[period]
    period_end = datetime.utcnow()
    period_start = period_end - timedelta(days=days)

    lead_repo = LeadRepository(db)
    event_repo = LeadEventRepository(db)

    # Tenant-scoped leads for the period
    period_leads = lead_repo.list_for_tenant_filtered(
        tenant_id=agent.id,
        start_date=period_start,
    )

    # ------------------------------------------------------------------
    # leads_by_source
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
    # bucket_distribution
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
    # appointments_set
    # ------------------------------------------------------------------
    appointments_set = sum(
        1 for lead in period_leads if lead.agent_current_state == "APPOINTMENT_SET"
    )

    # ------------------------------------------------------------------
    # avg_response_time_minutes
    # ------------------------------------------------------------------
    lead_ids_in_period = {lead.id for lead in period_leads}

    contacted_events = event_repo.list_for_agent_in_period(
        agent_id=agent.id,
        event_type="AGENT_CONTACTED",
        lead_ids=lead_ids_in_period,
        start_date=period_start,
    )

    avg_response_time_minutes: Optional[float] = None

    if contacted_events:
        earliest_contacted: Dict[int, datetime] = {}
        for ev in contacted_events:
            existing = earliest_contacted.get(ev.lead_id)
            if existing is None or ev.created_at < existing:
                earliest_contacted[ev.lead_id] = ev.created_at

        contacted_lead_ids = list(earliest_contacted.keys())
        email_received_events = event_repo.list_by_lead_ids_and_type(
            lead_ids=contacted_lead_ids,
            event_type="EMAIL_RECEIVED",
        )

        earliest_received: Dict[int, datetime] = {}
        for ev in email_received_events:
            existing = earliest_received.get(ev.lead_id)
            if existing is None or ev.created_at < existing:
                earliest_received[ev.lead_id] = ev.created_at

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
