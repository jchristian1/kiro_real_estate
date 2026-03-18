"""
SQLAlchemy ORM models for the Pipelines feature.

Defines the database schema for:
- Pipeline: Named, ordered collection of stages per company
- PipelineStage: Individual steps within a pipeline
- LeadStageHistory: Immutable audit trail of lead stage transitions
- PipelineEventMapping: Maps lifecycle events to target stages
- PipelineActionRule: When/Then automation rules
- PipelineActionRuleStep: Individual action steps within a rule

Requirements: 13.1, 13.2, 13.3, 13.4, 13.5
"""

import enum
from datetime import datetime

from sqlalchemy import (
    Column, Integer, String, Text, Boolean, DateTime,
    ForeignKey, Index, UniqueConstraint, Enum
)
from sqlalchemy.orm import relationship

from gmail_lead_sync.models import Base


class StageCategory(str, enum.Enum):
    open = "open"
    in_progress = "in_progress"
    waiting = "waiting"
    won = "won"
    lost = "lost"


class ChangeSource(str, enum.Enum):
    system = "system"
    event = "event"
    automation = "automation"
    manual = "manual"


class BuiltInEventType(str, enum.Enum):
    lead_created = "lead_created"
    response_email_sent = "response_email_sent"
    qualification_form_sent = "qualification_form_sent"
    qualification_form_submitted = "qualification_form_submitted"
    qualification_bucket_hot = "qualification_bucket_hot"
    qualification_bucket_warm = "qualification_bucket_warm"
    qualification_bucket_nurture = "qualification_bucket_nurture"


class ActionType(str, enum.Enum):
    send_email_template = "send_email_template"
    send_qualification_form = "send_qualification_form"
    send_bucket_followup_email = "send_bucket_followup_email"
    move_to_stage = "move_to_stage"


class Pipeline(Base):
    """
    A named, ordered collection of stages representing a lead journey.
    Scoped to a single company; at most one pipeline may be active per company.
    """
    __tablename__ = 'pipelines'
    __table_args__ = (
        UniqueConstraint('company_id', 'name', name='uq_pipeline_company_name'),
    )

    id = Column(Integer, primary_key=True)
    company_id = Column(Integer, ForeignKey('companies.id'), nullable=False, index=True)
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    stages = relationship("PipelineStage", back_populates="pipeline", cascade="all, delete-orphan")
    event_mappings = relationship("PipelineEventMapping", back_populates="pipeline", cascade="all, delete-orphan")
    action_rules = relationship("PipelineActionRule", back_populates="pipeline", cascade="all, delete-orphan")


class PipelineStage(Base):
    """
    A single step within a pipeline with ordering, category, and display metadata.
    """
    __tablename__ = 'pipeline_stages'
    __table_args__ = (
        UniqueConstraint('pipeline_id', 'key', name='uq_pipeline_stage_key'),
    )

    id = Column(Integer, primary_key=True)
    pipeline_id = Column(Integer, ForeignKey('pipelines.id'), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    key = Column(String(100), nullable=False)  # slug, e.g. "new_lead"
    color = Column(String(7), nullable=False)   # hex color, e.g. "#3B82F6"
    category = Column(Enum(StageCategory), nullable=False)
    position = Column(Integer, nullable=False)  # 1-based ordering
    is_default = Column(Boolean, default=False, nullable=False)
    is_closed_won = Column(Boolean, default=False, nullable=False)
    is_closed_lost = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    pipeline = relationship("Pipeline", back_populates="stages")


class LeadStageHistory(Base):
    """
    Immutable audit trail of every stage transition a lead has undergone.
    Never deleted or modified after creation.
    """
    __tablename__ = 'lead_stage_history'
    __table_args__ = (
        Index('idx_lead_stage_history_lead_created', 'lead_id', 'created_at'),
    )

    id = Column(Integer, primary_key=True)
    lead_id = Column(Integer, ForeignKey('leads.id'), nullable=False)
    from_stage_id = Column(Integer, ForeignKey('pipeline_stages.id'), nullable=True)
    to_stage_id = Column(Integer, ForeignKey('pipeline_stages.id'), nullable=False)
    change_source = Column(Enum(ChangeSource), nullable=False)
    change_reason = Column(Text, nullable=True)
    changed_by_user_id = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    from_stage = relationship("PipelineStage", foreign_keys=[from_stage_id])
    to_stage = relationship("PipelineStage", foreign_keys=[to_stage_id])


class PipelineEventMapping(Base):
    """
    Maps a built-in platform lifecycle event to a target pipeline stage.
    At most one mapping per (pipeline_id, event_type) pair.
    """
    __tablename__ = 'pipeline_event_mappings'
    __table_args__ = (
        UniqueConstraint('pipeline_id', 'event_type', name='uq_pipeline_event_mapping'),
    )

    id = Column(Integer, primary_key=True)
    pipeline_id = Column(Integer, ForeignKey('pipelines.id'), nullable=False, index=True)
    event_type = Column(Enum(BuiltInEventType), nullable=False)
    target_stage_id = Column(Integer, ForeignKey('pipeline_stages.id'), nullable=False)
    is_enabled = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    pipeline = relationship("Pipeline", back_populates="event_mappings")
    target_stage = relationship("PipelineStage")


class PipelineActionRule(Base):
    """
    A When/Then automation rule with a trigger, optional condition, and action steps.
    Rules are evaluated in ascending position order.
    """
    __tablename__ = 'pipeline_action_rules'

    id = Column(Integer, primary_key=True)
    pipeline_id = Column(Integer, ForeignKey('pipelines.id'), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    trigger_type = Column(String(50), nullable=False)       # "on_event" | "on_stage_enter"
    trigger_stage_id = Column(Integer, ForeignKey('pipeline_stages.id'), nullable=True)
    trigger_event_type = Column(String(100), nullable=True)
    condition_type = Column(String(50), nullable=False)     # "bucket_is" | "stage_is" | "always"
    condition_value = Column(String(255), nullable=True)
    is_enabled = Column(Boolean, default=True, nullable=False)
    position = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    pipeline = relationship("Pipeline", back_populates="action_rules")
    trigger_stage = relationship("PipelineStage", foreign_keys=[trigger_stage_id])
    steps = relationship("PipelineActionRuleStep", back_populates="rule", cascade="all, delete-orphan",
                         order_by="PipelineActionRuleStep.position")


class PipelineActionRuleStep(Base):
    """
    A single action step within an automation rule.
    Steps are executed in ascending position order.
    """
    __tablename__ = 'pipeline_action_rule_steps'

    id = Column(Integer, primary_key=True)
    rule_id = Column(Integer, ForeignKey('pipeline_action_rules.id'), nullable=False, index=True)
    action_type = Column(Enum(ActionType), nullable=False)
    action_config_json = Column(Text, nullable=False)  # JSON: {template_id, stage_id, form_id, etc.}
    position = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    rule = relationship("PipelineActionRule", back_populates="steps")
