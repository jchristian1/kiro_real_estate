"""
move_to_stage action handler.

Delegates to the lead stage service's public interface (move_stage).
Does not mutate lead state directly.

Config schema:
    { "stage_id": <int> }
"""

from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from api.models.pipeline_models import ChangeSource
from api.pipelines.handlers.base import ActionResult
from api.services.lead_stage_service import move_stage

logger = logging.getLogger(__name__)


class MoveToStageHandler:
    """Handles move_to_stage actions.

    Calls move_stage() from the lead stage service and returns the new
    stage_id in ActionResult.new_stage_id so the engine can chain
    on_stage_enter rules.
    """

    def execute(
        self,
        db: Session,
        lead_id: int,
        config: dict,
        context: dict,
    ) -> ActionResult:
        stage_id = config.get("stage_id")
        if stage_id is None:
            return ActionResult(
                success=False,
                error="move_to_stage: missing stage_id in action_config_json",
            )

        try:
            stage_id = int(stage_id)
        except (TypeError, ValueError):
            return ActionResult(
                success=False,
                error=f"move_to_stage: stage_id must be an integer, got {stage_id!r}",
            )

        try:
            move_stage(db, lead_id, stage_id, ChangeSource.automation)

            logger.info(
                "move_to_stage: lead_id=%s → stage_id=%s", lead_id, stage_id
            )
            return ActionResult(
                success=True,
                new_stage_id=stage_id,
                metadata={"stage_id": stage_id},
            )

        except Exception as exc:
            return ActionResult(success=False, error=str(exc))
