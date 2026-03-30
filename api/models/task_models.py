"""
ORM models for the Tasks domain.

A Task is a work item attached to a lead, owned by an agent.
Tasks are informational only in V1 — completing a task does NOT move
the lead stage, and open tasks do NOT block stage movement.

The architecture is future-ready for a later Option B where some tasks
could block stage exit, but that is NOT implemented here.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from gmail_lead_sync.models import Base


class TaskStatus(str):
    OPEN = "open"
    DONE = "done"


class TaskSource(str):
    MANUAL = "manual"    # created by agent
    PIPELINE = "pipeline"  # created by pipeline rule (future)


class Task(Base):
    """
    A work item attached to a lead.

    Tenant isolation: every query must filter by agent_user_id.
    lead_id is required — tasks are always scoped to a specific lead.
    """

    __tablename__ = "tasks"
    __table_args__ = (
        Index("ix_tasks_lead_id", "lead_id"),
        Index("ix_tasks_agent_user_id", "agent_user_id"),
        Index("ix_tasks_status", "status"),
    )

    id = Column(Integer, primary_key=True)

    # Tenant + lead scoping
    lead_id = Column(Integer, ForeignKey("leads.id"), nullable=False)
    agent_user_id = Column(Integer, ForeignKey("agent_users.id"), nullable=False)

    # Content
    title = Column(String(500), nullable=False)
    description = Column(Text, nullable=True)

    # Lifecycle
    status = Column(
        Enum("open", "done", name="task_status_enum"),
        nullable=False,
        default="open",
    )
    source = Column(
        Enum("manual", "pipeline", name="task_source_enum"),
        nullable=False,
        default="manual",
    )

    # Optional due date
    due_at = Column(DateTime, nullable=True)

    # Timestamps
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=True, onupdate=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)

    # Relationships
    lead = relationship("Lead", back_populates="tasks")
    agent_user = relationship("AgentUser", back_populates="tasks")
