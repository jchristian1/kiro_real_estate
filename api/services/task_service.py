"""
Task service — business rules and lifecycle for the Task domain.

Rules enforced here (V1):
- Completing a task does NOT move the lead stage.
- Open tasks do NOT block lead stage movement.
- A task must belong to a lead that belongs to the requesting agent.
- Source defaults to 'manual' for agent-created tasks.

The architecture is future-ready for Option B (blocking tasks) but that
logic is NOT implemented here.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from api.exceptions import AuthorizationException, NotFoundException
from api.models.error_models import ErrorCode
from api.models.task_models import Task
from api.repositories.task_repository import TaskRepository

logger = logging.getLogger(__name__)


def _assert_lead_ownership(db: Session, lead_id: int, agent_user_id: int) -> None:
    """Raise NotFoundException if the lead doesn't exist or doesn't belong to the agent."""
    from gmail_lead_sync.models import Lead
    lead = (
        db.query(Lead)
        .filter(Lead.id == lead_id, Lead.agent_user_id == agent_user_id)
        .first()
    )
    if lead is None:
        raise NotFoundException(
            message=f"Lead {lead_id} not found",
            code=ErrorCode.NOT_FOUND_RESOURCE,
        )


def create_task(
    db: Session,
    lead_id: int,
    agent_user_id: int,
    title: str,
    description: Optional[str] = None,
    due_at: Optional[datetime] = None,
) -> Task:
    """Create a manual task for a lead.

    Validates lead ownership before creating.
    """
    _assert_lead_ownership(db, lead_id, agent_user_id)
    repo = TaskRepository(db)
    task = repo.create(
        lead_id=lead_id,
        agent_user_id=agent_user_id,
        title=title,
        description=description,
        due_at=due_at,
        source="manual",
    )
    logger.info("Task created: task_id=%s lead_id=%s agent_user_id=%s", task.id, lead_id, agent_user_id)
    return task


def list_tasks(
    db: Session,
    lead_id: int,
    agent_user_id: int,
    status: Optional[str] = None,
) -> list[Task]:
    """List tasks for a lead, scoped to the agent."""
    _assert_lead_ownership(db, lead_id, agent_user_id)
    repo = TaskRepository(db)
    return repo.list_for_lead(lead_id, agent_user_id, status=status)


def update_task(
    db: Session,
    task_id: int,
    agent_user_id: int,
    title: Optional[str] = None,
    description: Optional[str] = None,
    due_at: Optional[datetime] = None,
    status: Optional[str] = None,
) -> Task:
    """Update a task. Raises NotFoundException if not found or wrong agent."""
    repo = TaskRepository(db)
    task = repo.update(
        task_id=task_id,
        agent_user_id=agent_user_id,
        title=title,
        description=description,
        due_at=due_at,
        status=status,
    )
    if task is None:
        raise NotFoundException(
            message=f"Task {task_id} not found",
            code=ErrorCode.NOT_FOUND_RESOURCE,
        )
    logger.info("Task updated: task_id=%s agent_user_id=%s status=%s", task_id, agent_user_id, task.status)
    return task


def delete_task(db: Session, task_id: int, agent_user_id: int) -> None:
    """Delete a task. Raises NotFoundException if not found or wrong agent."""
    repo = TaskRepository(db)
    deleted = repo.delete(task_id, agent_user_id)
    if not deleted:
        raise NotFoundException(
            message=f"Task {task_id} not found",
            code=ErrorCode.NOT_FOUND_RESOURCE,
        )
    logger.info("Task deleted: task_id=%s agent_user_id=%s", task_id, agent_user_id)
