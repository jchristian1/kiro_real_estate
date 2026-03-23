"""
Lead detail assembler — unified read model for a single lead.

This is the single place that composes a coherent lead detail object from
multiple data sources. Routers delegate to this service; they do not
assemble lead detail inline.

Sources composed:
  - Lead ORM (core identity, lifecycle flags, scoring columns)
  - PipelineStage ORM (current stage info)
  - FormSubmission + SubmissionScore (qualification summary)
  - LeadActivityRepository (activity timeline)

Design rules:
  - All fields are nullable where the data may not exist yet
  - Timeline uses LeadActivityRepository.get_timeline() — NOT LeadEventWriteRepository
  - Qualification summary reads from FormSubmission/SubmissionScore tables
  - Scoring breakdown reads from SubmissionScore.breakdown_json (preferred)
    and falls back to Lead.score_breakdown for legacy rows
  - This service never writes — read-only
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional

from sqlalchemy.orm import Session

from api.repositories.lead_activity_repository import (
    LeadActivityRepository,
    parse_activity_metadata,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Output shapes (dataclasses — no FastAPI dependency)
# ---------------------------------------------------------------------------


@dataclass
class LeadCoreInfo:
    id: int
    name: str
    phone: Optional[str]
    source_email: str
    created_at: datetime
    property_address: Optional[str]
    listing_url: Optional[str]
    lead_source_name: Optional[str]
    agent_current_state: Optional[str]
    last_agent_action_at: Optional[datetime]


@dataclass
class LeadStageInfo:
    stage_id: int
    stage_name: str
    stage_key: str
    stage_color: str
    stage_category: str
    stage_entered_at: Optional[datetime]


@dataclass
class ScoreFactorDetail:
    label: str
    points: int
    met: bool


@dataclass
class LeadQualificationSummary:
    score: int
    bucket: str
    explanation_text: Optional[str]
    breakdown: list[ScoreFactorDetail]
    submitted_at: Optional[datetime]
    invitation_sent_at: Optional[datetime]


@dataclass
class ActivityTimelineEntry:
    id: int
    event_type: str
    actor_source: Optional[str]
    metadata: dict[str, Any]
    occurred_at: datetime


@dataclass
class UnifiedLeadDetail:
    core: LeadCoreInfo
    stage: Optional[LeadStageInfo]
    qualification: Optional[LeadQualificationSummary]
    timeline: list[ActivityTimelineEntry]


# ---------------------------------------------------------------------------
# Assembler
# ---------------------------------------------------------------------------


def assemble_lead_detail(
    db: Session,
    lead_id: int,
    company_id: Optional[int] = None,
) -> Optional[UnifiedLeadDetail]:
    """Compose a UnifiedLeadDetail from all available data sources.

    Returns None if the lead does not exist.

    Args:
        db:         Active SQLAlchemy session.
        lead_id:    Target lead.
        company_id: Tenant ID — used to scope timeline queries.
                    Pass None only for platform-admin contexts.
    """
    from gmail_lead_sync.models import Lead
    from api.models.pipeline_models import PipelineStage
    from gmail_lead_sync.preapproval.models_preapproval import (
        FormSubmission,
        FormInvitation,
        SubmissionScore,
    )

    lead = db.query(Lead).filter(Lead.id == lead_id).first()
    if lead is None:
        return None

    # --- Core ---
    core = LeadCoreInfo(
        id=lead.id,
        name=lead.name or "",
        phone=getattr(lead, "phone", None),
        source_email=lead.source_email,
        created_at=lead.created_at,
        property_address=getattr(lead, "property_address", None),
        listing_url=getattr(lead, "listing_url", None),
        lead_source_name=getattr(lead, "lead_source_name", None),
        agent_current_state=getattr(lead, "agent_current_state", None),
        last_agent_action_at=getattr(lead, "last_agent_action_at", None),
    )

    # --- Stage ---
    stage: Optional[LeadStageInfo] = None
    current_stage_id = getattr(lead, "current_stage_id", None)
    if current_stage_id is not None:
        ps = db.query(PipelineStage).filter(PipelineStage.id == current_stage_id).first()
        if ps is not None:
            stage = LeadStageInfo(
                stage_id=ps.id,
                stage_name=ps.name,
                stage_key=ps.key,
                stage_color=ps.color,
                stage_category=ps.category.value if hasattr(ps.category, "value") else str(ps.category),
                stage_entered_at=getattr(lead, "stage_entered_at", None),
            )

    # --- Qualification summary ---
    qualification: Optional[LeadQualificationSummary] = None
    latest_submission = (
        db.query(FormSubmission)
        .filter(FormSubmission.lead_id == lead_id)
        .order_by(FormSubmission.submitted_at.desc())
        .first()
    )
    if latest_submission is not None:
        sub_score: Optional[SubmissionScore] = (
            db.query(SubmissionScore)
            .filter(SubmissionScore.submission_id == latest_submission.id)
            .first()
        )

        # Invitation sent_at — look up via invitation_id on the submission
        invitation_sent_at: Optional[datetime] = None
        if latest_submission.invitation_id is not None:
            inv = db.query(FormInvitation).filter(
                FormInvitation.id == latest_submission.invitation_id
            ).first()
            if inv is not None:
                invitation_sent_at = inv.sent_at

        if sub_score is not None:
            breakdown = _parse_breakdown(sub_score.breakdown_json)
            qualification = LeadQualificationSummary(
                score=sub_score.total_score,
                bucket=sub_score.bucket,
                explanation_text=sub_score.explanation_text,
                breakdown=breakdown,
                submitted_at=latest_submission.submitted_at,
                invitation_sent_at=invitation_sent_at,
            )
        else:
            # Submission exists but not yet scored — surface partial info
            # Fall back to Lead.score columns if available
            lead_score = getattr(lead, "score", None)
            lead_bucket = getattr(lead, "score_bucket", None)
            if lead_score is not None and lead_bucket is not None:
                breakdown = _parse_lead_score_breakdown(getattr(lead, "score_breakdown", None))
                qualification = LeadQualificationSummary(
                    score=lead_score,
                    bucket=lead_bucket,
                    explanation_text=None,
                    breakdown=breakdown,
                    submitted_at=latest_submission.submitted_at,
                    invitation_sent_at=invitation_sent_at,
                )

    # --- Timeline ---
    activity_repo = LeadActivityRepository(db)
    raw_events = activity_repo.get_timeline(lead_id=lead_id)
    timeline = [
        ActivityTimelineEntry(
            id=ev.id,
            event_type=ev.event_type,
            actor_source=ev.actor_source,
            metadata=parse_activity_metadata(ev),
            occurred_at=ev.created_at,
        )
        for ev in raw_events
    ]

    return UnifiedLeadDetail(
        core=core,
        stage=stage,
        qualification=qualification,
        timeline=timeline,
    )


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _parse_breakdown(breakdown_json: Optional[str]) -> list[ScoreFactorDetail]:
    """Parse SubmissionScore.breakdown_json into ScoreFactorDetail list."""
    if not breakdown_json:
        return []
    try:
        raw = json.loads(breakdown_json)
        factors = raw if isinstance(raw, list) else raw.get("factors", [])
        return [
            ScoreFactorDetail(
                label=f.get("label", ""),
                points=f.get("points", 0),
                met=f.get("met", False),
            )
            for f in factors
            if isinstance(f, dict)
        ]
    except (json.JSONDecodeError, TypeError):
        logger.warning("lead_detail_service: failed to parse breakdown_json")
        return []


def _parse_lead_score_breakdown(score_breakdown: Optional[str]) -> list[ScoreFactorDetail]:
    """Parse legacy Lead.score_breakdown JSON into ScoreFactorDetail list."""
    if not score_breakdown:
        return []
    try:
        raw = json.loads(score_breakdown)
        factors = raw.get("factors", [])
        return [
            ScoreFactorDetail(
                label=f.get("label", ""),
                points=f.get("points", 0),
                met=f.get("met", False),
            )
            for f in factors
            if isinstance(f, dict)
        ]
    except (json.JSONDecodeError, TypeError):
        return []
