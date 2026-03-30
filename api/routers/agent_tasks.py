"""
Agent task endpoints.

Provides:
- GET    /api/v1/agent/leads/{lead_id}/tasks          — list tasks for a lead
- POST   /api/v1/agent/leads/{lead_id}/tasks          — create a task for a lead
- PATCH  /api/v1/agent/tasks/{task_id}                — update a task
- DELETE /api/v1/agent/tasks/{task_id}                — delete a task

All endpoints require agent session authentication.
Tenant isolation is enforced: agents can only access their own tasks.
"""

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from api.dependencies.agent_auth import get_current_agent
from api.dependencies.auth import require_role
from api.dependencies.db import get_db
from api.models.task_schemas import (
    TaskCreateRequest,
    TaskCreateResponse,
    TaskListResponse,
    TaskResponse,
    TaskUpdateRequest,
)
from api.services import task_service
from gmail_lead_sync.agent_models import AgentUser

router = APIRouter(
    prefix="/agent",
    tags=["Agent Tasks"],
    dependencies=[Depends(require_role("agent"))],
)


@router.get(
    "/leads/{lead_id}/tasks",
    response_model=TaskListResponse,
    summary="List tasks for a lead",
)
def list_tasks(
    lead_id: int,
    status: Optional[str] = Query(
        default=None,
        description="Filter by status: open or done",
        pattern=r"^(open|done)$",
    ),
    db: Session = Depends(get_db),
    agent: AgentUser = Depends(get_current_agent),
) -> TaskListResponse:
    tasks = task_service.list_tasks(db, lead_id, agent.id, status=status)
    return TaskListResponse(tasks=tasks, total=len(tasks))


@router.post(
    "/leads/{lead_id}/tasks",
    response_model=TaskCreateResponse,
    status_code=201,
    summary="Create a task for a lead",
)
def create_task(
    lead_id: int,
    body: TaskCreateRequest,
    db: Session = Depends(get_db),
    agent: AgentUser = Depends(get_current_agent),
) -> TaskCreateResponse:
    task = task_service.create_task(
        db,
        lead_id=lead_id,
        agent_user_id=agent.id,
        title=body.title,
        description=body.description,
        due_at=body.due_at,
    )
    return TaskCreateResponse(ok=True, task=TaskResponse.model_validate(task))


@router.patch(
    "/tasks/{task_id}",
    response_model=TaskResponse,
    summary="Update a task",
)
def update_task(
    task_id: int,
    body: TaskUpdateRequest,
    db: Session = Depends(get_db),
    agent: AgentUser = Depends(get_current_agent),
) -> TaskResponse:
    task = task_service.update_task(
        db,
        task_id=task_id,
        agent_user_id=agent.id,
        title=body.title,
        description=body.description,
        due_at=body.due_at,
        status=body.status,
    )
    return TaskResponse.model_validate(task)


@router.delete(
    "/tasks/{task_id}",
    status_code=204,
    summary="Delete a task",
)
def delete_task(
    task_id: int,
    db: Session = Depends(get_db),
    agent: AgentUser = Depends(get_current_agent),
) -> None:
    task_service.delete_task(db, task_id=task_id, agent_user_id=agent.id)
