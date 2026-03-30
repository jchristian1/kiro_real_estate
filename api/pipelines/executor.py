"""
Pipeline action executor.

Dispatches a PipelineActionRuleStep to the correct handler based on
action_type. The engine calls execute_step() — it does not know how
any individual action works.

Adding a new action type:
1. Create api/pipelines/handlers/<name>.py implementing ActionHandler.
2. Import and register it in _REGISTRY below.
"""

from __future__ import annotations

import json
import logging

from sqlalchemy.orm import Session

from api.pipelines.handlers.base import ActionHandler, ActionResult
from api.pipelines.handlers.move_stage import MoveToStageHandler
from api.pipelines.handlers.send_email import SendEmailTemplateHandler
from api.pipelines.handlers.send_form import SendQualificationFormHandler
from api.pipelines.handlers.create_task import CreateTaskHandler

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Handler registry — maps action_type string → handler instance
# ---------------------------------------------------------------------------

_send_email_handler = SendEmailTemplateHandler()
_send_form_handler = SendQualificationFormHandler()
_move_stage_handler = MoveToStageHandler()
_create_task_handler = CreateTaskHandler()

_REGISTRY: dict[str, ActionHandler] = {
    "send_email_template": _send_email_handler,
    "send_bucket_followup_email": _send_email_handler,
    "send_qualification_form": _send_form_handler,
    "move_to_stage": _move_stage_handler,
    "create_task": _create_task_handler,
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def execute_step(
    db: Session,
    lead_id: int,
    pipeline_id: int,
    rule_id: int,
    step,
    context: dict,
) -> ActionResult:
    """Dispatch a rule step to its registered handler.

    Always returns an ActionResult — never raises. Unknown action types
    produce a failed result so the engine can log and continue.

    Args:
        db:          Active DB session.
        lead_id:     Target lead.
        pipeline_id: Pipeline the rule belongs to (for logging).
        rule_id:     Rule the step belongs to (for logging).
        step:        PipelineActionRuleStep ORM instance.
        context:     Pipeline event context dict.

    Returns:
        ActionResult with success/failure and optional new_stage_id.
    """
    action_type: str = (
        step.action_type.value
        if hasattr(step.action_type, "value")
        else str(step.action_type)
    )

    config: dict = {}
    try:
        config = json.loads(step.action_config_json)
    except (json.JSONDecodeError, TypeError):
        pass

    handler = _REGISTRY.get(action_type)
    if handler is None:
        msg = (
            f"Unknown action_type '{action_type}' for step {step.id} "
            f"in rule {rule_id} (pipeline {pipeline_id}) — skipping"
        )
        logger.warning(msg)
        return ActionResult(success=False, error=msg)

    return handler.execute(db, lead_id, config, context)
