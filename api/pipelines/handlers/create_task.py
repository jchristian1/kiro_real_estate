"""
Pipeline handler adapter: create_task action type.

This adapter bridges the pipeline executor to the task service.
It is intentionally thin — all business logic lives in task_service.

Config keys expected in action_config_json:
    title       (str, required)  — task title; supports {lead_name} placeholder
    description (str, optional)  — task description
    source      (str, optional)  — defaults to "pipeline"

Example action_config_json:
    {"title": "Follow up with {lead_name}", "description": "Call within 24h"}
"""

from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from api.pipelines.handlers.base import ActionHandler, ActionResult

logger = logging.getLogger(__name__)


class CreateTaskHandler:
    """Pipeline adapter that creates a task via task_service."""

    def execute(
        self,
        db: Session,
        lead_id: int,
        config: dict,
        context: dict,
    ) -> ActionResult:
        try:
            from api.services.task_service import create_task as _create_task
            from gmail_lead_sync.models import Lead

            title = config.get("title", "Follow up")
            description = config.get("description")

            # Resolve lead to get agent_user_id
            lead = db.query(Lead).filter(Lead.id == lead_id).first()
            if lead is None or lead.agent_user_id is None:
                return ActionResult(
                    success=False,
                    error=f"create_task: lead {lead_id} not found or has no agent_user_id",
                )

            # Substitute {lead_name} placeholder if present
            if "{lead_name}" in title:
                title = title.replace("{lead_name}", lead.name or "")
            if description and "{lead_name}" in description:
                description = description.replace("{lead_name}", lead.name or "")

            task = _create_task(
                db,
                lead_id=lead_id,
                agent_user_id=lead.agent_user_id,
                title=title,
                description=description,
                due_at=None,
            )
            return ActionResult(
                success=True,
                metadata={"task_id": task.id, "title": task.title},
            )

        except Exception as exc:
            logger.error(
                "create_task handler failed: lead_id=%s error=%s",
                lead_id, exc, exc_info=True,
            )
            return ActionResult(success=False, error=str(exc))
