"""
Agent dashboard route.

Provides:
- GET /api/v1/agent/dashboard — HOT lead summaries, aging leads,
  response_time_today_minutes, watcher_status; all scoped by agent_user_id.

Requirements: 10.1, 10.2, 10.3, 10.4, 10.5
"""

from datetime import datetime, date
from typing import List, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from api.dependencies.agent_auth import get_current_agent
from api.main import get_db
from gmail_lead_sync.agent_models import AgentPreferences, AgentUser, LeadEvent
from gmail_lead_sync.models import Lead

router = APIRouter(prefix="/agent", tags=["Agent Dashboard"])

# ---------------------------------------------------------------------------
# Pydantic response models
# ---------------------------------------------------------------------------

class HotLeadSummary(BaseModel):
    """Summary of a HOT lead for the dashboard."""
    id: int
    name: str
    score: Optional[int]
    source: Optional[str]
    address: Optional[str]
    created_at: datetime


class AgingLeadSummary(BaseModel):
    """Summary of an aging HOT lead for the dashboard."""
    id: int
    name: str
    score: Optional[int]
    minutes_since_created: float


class DashboardResponse(BaseModel):
    """GET /agent/dashboard response."""
    hot_lead_count: int
    hot_leads: List[HotLeadSummary]
    aging_lead_count: int
    aging_leads: List[AgingLeadSummary]
    response_time_today_minutes: Optional[float]
    watcher_status: str


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------

@router.get(
    "/dashboard",
    response_model=DashboardResponse,
    summary="Agent dashboard — HOT leads, aging leads, response time, watcher status",
)
def get_dashboard(
    db: Session = Depends(get_db),
    agent: AgentUser = Depends(get_current_agent),
):
    """
    Return the agent's dashboard data.

    - HOT leads: all leads with score_bucket == 'HOT' belonging to this agent.
    - Aging HOT leads: HOT leads where last_agent_action_at IS NULL and
      (NOW() - created_at) > sla_minutes_hot minutes.
    - response_time_today_minutes: mean of (AGENT_CONTACTED.created_at -
      EMAIL_RECEIVED.created_at) for leads contacted today.
    - watcher_status: derived from AgentPreferences.watcher_enabled.

    All queries are scoped by agent_user_id (Requirement 10.2).

    Requirements: 10.1, 10.2, 10.3, 10.4, 10.5
    """
    now = datetime.utcnow()

    # ------------------------------------------------------------------
    # Resolve AgentPreferences (for SLA and watcher_enabled)
    # ------------------------------------------------------------------
    prefs: Optional[AgentPreferences] = (
        db.query(AgentPreferences)
        .filter(AgentPreferences.agent_user_id == agent.id)
        .first()
    )
    sla_minutes_hot: int = prefs.sla_minutes_hot if prefs else 5

    # Requirement 10.5: watcher_status from watcher_enabled flag
    if prefs is None:
        watcher_status = "stopped"
    elif prefs.watcher_enabled:
        watcher_status = "running"
    else:
        watcher_status = "stopped"

    # ------------------------------------------------------------------
    # HOT leads — scoped by agent_user_id (Requirement 10.2)
    # ------------------------------------------------------------------
    hot_leads_rows: List[Lead] = (
        db.query(Lead)
        .filter(
            Lead.agent_user_id == agent.id,
            Lead.score_bucket == "HOT",
        )
        .all()
    )

    hot_lead_summaries: List[HotLeadSummary] = []
    aging_lead_summaries: List[AgingLeadSummary] = []

    for lead in hot_leads_rows:
        hot_lead_summaries.append(
            HotLeadSummary(
                id=lead.id,
                name=lead.name or "",
                score=lead.score,
                source=lead.lead_source_name,
                address=lead.property_address,
                created_at=lead.created_at,
            )
        )

        # Requirement 10.3: aging = no agent action AND age > sla_minutes_hot
        if lead.last_agent_action_at is None and lead.created_at is not None:
            age_minutes = (now - lead.created_at).total_seconds() / 60.0
            if age_minutes > sla_minutes_hot:
                aging_lead_summaries.append(
                    AgingLeadSummary(
                        id=lead.id,
                        name=lead.name or "",
                        score=lead.score,
                        minutes_since_created=round(age_minutes, 2),
                    )
                )

    # ------------------------------------------------------------------
    # Response time today (Requirement 10.4)
    # ------------------------------------------------------------------
    today_start = datetime.combine(date.today(), datetime.min.time())

    # Find all AGENT_CONTACTED events for this agent today
    contacted_events: List[LeadEvent] = (
        db.query(LeadEvent)
        .filter(
            LeadEvent.agent_user_id == agent.id,
            LeadEvent.event_type == "AGENT_CONTACTED",
            LeadEvent.created_at >= today_start,
        )
        .all()
    )

    response_times: List[float] = []
    for contacted_event in contacted_events:
        # Find the corresponding EMAIL_RECEIVED event for the same lead
        email_received_event: Optional[LeadEvent] = (
            db.query(LeadEvent)
            .filter(
                LeadEvent.lead_id == contacted_event.lead_id,
                LeadEvent.event_type == "EMAIL_RECEIVED",
            )
            .order_by(LeadEvent.created_at.asc())
            .first()
        )
        if email_received_event is not None:
            diff_minutes = (
                contacted_event.created_at - email_received_event.created_at
            ).total_seconds() / 60.0
            response_times.append(diff_minutes)

    response_time_today: Optional[float] = None
    if response_times:
        response_time_today = round(sum(response_times) / len(response_times), 2)

    return DashboardResponse(
        hot_lead_count=len(hot_lead_summaries),
        hot_leads=hot_lead_summaries,
        aging_lead_count=len(aging_lead_summaries),
        aging_leads=aging_lead_summaries,
        response_time_today_minutes=response_time_today,
        watcher_status=watcher_status,
    )
