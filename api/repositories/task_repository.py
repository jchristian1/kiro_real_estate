"""
Task repository — persistence and querying for the Task domain.

Tenant isolation is enforced at the query level: every method that reads
or writes tasks filters by agent_user_id derived from the authenticated
session. The repository never trusts user-supplied IDs directly.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from api.models.task_models import Task


class TaskRepository:
    """Data-access layer for Task records.

    All methods are scoped to agent_user_id to enforce tenant isolation.
    """

    def __init__(self, db: Session) -> None:
        self._db = db

    # ------------------------------------------------------------------
    # Reads
    # ------------------------------------------------------------------

    def get_by_id(self, task_id: int, agent_user_id: int) -> Optional[Task]:
        """Return a task only if it belongs to the given agent."""
        return (
            self._db.query(Task)
            .filter(Task.id == task_id, Task.agent_user_id == agent_user_id)
            .first()
        )

    def list_for_lead(
        self,
        lead_id: int,
        agent_user_id: int,
        status: Optional[str] = None,
    ) -> list[Task]:
        """Return all tasks for a lead, scoped to the agent.

        Optionally filter by status ('open' or 'done').
        Ordered by created_at ascending (oldest first).
        """
        q = (
            self._db.query(Task)
            .filter(Task.lead_id == lead_id, Task.agent_user_id == agent_user_id)
        )
        if status is not None:
            q = q.filter(Task.status == status)
        return q.order_by(Task.created_at.asc()).all()

    # ------------------------------------------------------------------
    # Writes
    # ------------------------------------------------------------------

    def create(
        self,
        lead_id: int,
        agent_user_id: int,
        title: str,
        description: Optional[str] = None,
        due_at: Optional[datetime] = None,
        source: str = "manual",
    ) -> Task:
        """Create and persist a new task."""
        task = Task(
            lead_id=lead_id,
            agent_user_id=agent_user_id,
            title=title,
            description=description,
            due_at=due_at,
            source=source,
            status="open",
            created_at=datetime.utcnow(),
        )
        self._db.add(task)
        self._db.commit()
        self._db.refresh(task)
        return task

    def update(
        self,
        task_id: int,
        agent_user_id: int,
        title: Optional[str] = None,
        description: Optional[str] = None,
        due_at: Optional[datetime] = None,
        status: Optional[str] = None,
    ) -> Optional[Task]:
        """Update a task after verifying ownership.

        Returns the updated task, or None if not found / wrong agent.
        """
        task = self.get_by_id(task_id, agent_user_id)
        if task is None:
            return None

        now = datetime.utcnow()
        if title is not None:
            task.title = title
        if description is not None:
            task.description = description
        if due_at is not None:
            task.due_at = due_at
        if status is not None:
            task.status = status
            if status == "done" and task.completed_at is None:
                task.completed_at = now
            elif status == "open":
                task.completed_at = None
        task.updated_at = now

        self._db.commit()
        self._db.refresh(task)
        return task

    def delete(self, task_id: int, agent_user_id: int) -> bool:
        """Delete a task after verifying ownership.

        Returns True if deleted, False if not found / wrong agent.
        """
        task = self.get_by_id(task_id, agent_user_id)
        if task is None:
            return False
        self._db.delete(task)
        self._db.commit()
        return True
