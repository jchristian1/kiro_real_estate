"""
Base types for pipeline action handlers.

ActionResult — structured return value from every handler.
ActionHandler — Protocol that all concrete handlers must satisfy.

Adding a new action type:
1. Create api/pipelines/handlers/<name>.py implementing ActionHandler.
2. Register it in api/pipelines/executor.py _REGISTRY.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

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
