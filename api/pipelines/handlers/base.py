"""
Base types for pipeline action handlers.

ActionResult — structured return value from every handler.
ActionHandler — Protocol that all concrete handlers must satisfy.
resolve_lead_company_id — shared helper used by all handlers.

Adding a new action type:
1. Create api/pipelines/handlers/<name>.py implementing ActionHandler.
2. Register it in api/pipelines/executor.py _REGISTRY.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional, Protocol

from sqlalchemy.orm import Session


@dataclass
class ActionResult:
    """Structured result returned by every action handler.

    Attributes:
        success:       True if the action completed without error.
        new_stage_id:  Set by move_to_stage handlers; None for all others.
        metadata:      Optional handler-specific data (template_id used, etc.).
        error:         Error message if success=False.
    """
    success: bool
    new_stage_id: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


class ActionHandler(Protocol):
    """Protocol every concrete handler must satisfy."""

    def execute(
        self,
        db: Session,
        lead_id: int,
        config: dict,
        context: dict,
    ) -> ActionResult:
        """Execute the action and return a structured result.

        Args:
            db:       Active DB session.
            lead_id:  Target lead.
            config:   Parsed action_config_json dict.
            context:  Pipeline event context (tenant_id, source_email, etc.).

        Returns:
            ActionResult — never raises; errors are captured in result.error.
        """
        ...


def resolve_lead_company_id(db: Session, lead_id: int) -> Optional[int]:
    """Resolve company_id for a lead via direct column, lead_source, or agent_user.

    Shared by all action handlers — do not duplicate this logic in individual
    handler files.
    """
    from gmail_lead_sync.models import Lead

    lead = db.query(Lead).filter(Lead.id == lead_id).first()
    if lead is None:
        return None
    company_id = getattr(lead, "company_id", None)
    if company_id:
        return company_id
    lead_source = getattr(lead, "lead_source", None)
    if lead_source is not None:
        cid = getattr(lead_source, "company_id", None)
        if cid:
            return cid
    agent_user = getattr(lead, "agent_user", None)
    if agent_user is not None:
        cid = getattr(agent_user, "company_id", None)
        if cid:
            return cid
    return None
