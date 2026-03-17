"""
LeadStageService — Stage assignment, transitions, and history for leads.

Business rules:
- assign_initial_stage creates the first LeadStageHistory entry (from_stage_id=None)
  and updates the lead's pipeline_id, current_stage_id, and stage_entered_at.
- move_stage records the current stage as from_stage_id, creates a new history entry,
  and updates current_stage_id and stage_entered_at. History is NEVER deleted or modified.
- get_current_stage returns the PipelineStage for the lead's current_stage_id, or None.
- get_stage_history returns all history entries ordered by created_at ascending.
- get_leads_in_stage returns all leads with current_stage_id matching the given stage.

Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7
"""

from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from api.models.pipeline_models import ChangeSource, LeadStageHistory, PipelineStage
from gmail_lead_sync.models import Lead


def assign_initial_stage(
    db: Session,
    lead_id: int,
    pipeline_id: int,
    stage_id: int,
) -> LeadStageHistory:
    """Assign a lead to its initial stage within a pipeline.

    Creates a LeadStageHistory entry with from_stage_id=None and
    change_source="system". Updates lead.pipeline_id, lead.current_stage_id,
    and lead.stage_entered_at.

    Requirements: 3.1, 3.2
    """
    now = datetime.utcnow()

    history = LeadStageHistory(
        lead_id=lead_id,
        from_stage_id=None,
        to_stage_id=stage_id,
        change_source=ChangeSource.system,
        created_at=now,
    )
    db.add(history)

    lead = db.query(Lead).filter(Lead.id == lead_id).first()
    if lead is not None:
        lead.pipeline_id = pipeline_id
        lead.current_stage_id = stage_id
        lead.stage_entered_at = now

    db.commit()
    db.refresh(history)
    return history


def move_stage(
    db: Session,
    lead_id: int,
    to_stage_id: int,
    change_source: ChangeSource,
    change_reason: Optional[str] = None,
    changed_by_user_id: Optional[int] = None,
) -> LeadStageHistory:
    """Move a lead from its current stage to a new stage.

    Records the current stage as from_stage_id in the new history entry.
    Updates lead.current_stage_id and lead.stage_entered_at.
    Existing history entries are NEVER deleted or modified.

    Requirements: 3.3, 3.4, 3.5
    """
    now = datetime.utcnow()

    lead = db.query(Lead).filter(Lead.id == lead_id).first()
    from_stage_id = lead.current_stage_id if lead is not None else None

    history = LeadStageHistory(
        lead_id=lead_id,
        from_stage_id=from_stage_id,
        to_stage_id=to_stage_id,
        change_source=change_source,
        change_reason=change_reason,
        changed_by_user_id=changed_by_user_id,
        created_at=now,
    )
    db.add(history)

    if lead is not None:
        lead.current_stage_id = to_stage_id
        lead.stage_entered_at = now

    db.commit()
    db.refresh(history)
    return history


def get_current_stage(db: Session, lead_id: int) -> Optional[PipelineStage]:
    """Return the PipelineStage for the lead's current_stage_id, or None.

    Requirements: 3.6
    """
    lead = db.query(Lead).filter(Lead.id == lead_id).first()
    if lead is None or lead.current_stage_id is None:
        return None
    return db.query(PipelineStage).filter(PipelineStage.id == lead.current_stage_id).first()


def get_stage_history(db: Session, lead_id: int) -> list[LeadStageHistory]:
    """Return all stage history entries for a lead ordered by created_at ascending.

    Requirements: 3.7
    """
    return (
        db.query(LeadStageHistory)
        .filter(LeadStageHistory.lead_id == lead_id)
        .order_by(LeadStageHistory.created_at.asc())
        .all()
    )


def get_leads_in_stage(db: Session, stage_id: int) -> list[Lead]:
    """Return all leads currently assigned to the given stage.

    Requirements: 3.5
    """
    return (
        db.query(Lead)
        .filter(Lead.current_stage_id == stage_id)
        .all()
    )
