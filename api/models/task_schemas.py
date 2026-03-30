"""
Pydantic schemas for the Tasks domain.

Validation and serialization only — no business logic.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator

from api.utils.sanitization import sanitize_string


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------


class TaskCreateRequest(BaseModel):
    """POST /agent/leads/{lead_id}/tasks"""

    title: str = Field(..., min_length=1, max_length=500)
    description: Optional[str] = Field(default=None, max_length=2000)
    due_at: Optional[datetime] = None

    @field_validator("title", mode="before")
    @classmethod
    def sanitize_title(cls, v: str) -> str:
        return sanitize_string(v) if isinstance(v, str) else v

    @field_validator("description", mode="before")
    @classmethod
    def sanitize_description(cls, v: Optional[str]) -> Optional[str]:
        return sanitize_string(v) if isinstance(v, str) else v


class TaskUpdateRequest(BaseModel):
    """PATCH /agent/tasks/{task_id}"""

    title: Optional[str] = Field(default=None, min_length=1, max_length=500)
    description: Optional[str] = Field(default=None, max_length=2000)
    due_at: Optional[datetime] = None
    status: Optional[str] = Field(default=None, pattern=r"^(open|done)$")

    @field_validator("title", mode="before")
    @classmethod
    def sanitize_title(cls, v: Optional[str]) -> Optional[str]:
        return sanitize_string(v) if isinstance(v, str) else v

    @field_validator("description", mode="before")
    @classmethod
    def sanitize_description(cls, v: Optional[str]) -> Optional[str]:
        return sanitize_string(v) if isinstance(v, str) else v


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------


class TaskResponse(BaseModel):
    """Single task in any response."""

    id: int
    lead_id: int
    agent_user_id: int
    title: str
    description: Optional[str]
    status: str
    source: str
    due_at: Optional[datetime]
    created_at: datetime
    updated_at: Optional[datetime]
    completed_at: Optional[datetime]

    model_config = {"from_attributes": True}


class TaskListResponse(BaseModel):
    """GET /agent/leads/{lead_id}/tasks"""

    tasks: list[TaskResponse]
    total: int


class TaskCreateResponse(BaseModel):
    """POST /agent/leads/{lead_id}/tasks"""

    ok: bool
    task: TaskResponse
