"""
Pydantic schemas for the Pipelines feature API endpoints.

Defines request and response models for:
- Pipeline CRUD
- Pipeline Stage CRUD and reordering
- Lead Stage management and history
- Pipeline Event Mappings
- Pipeline Action Rules and Steps
- Pipeline Metrics
- Agent-facing pipeline view

Requirements: 7.1, 10.5
"""

from typing import Optional
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from api.models.pipeline_models import (
    ActionType,
    BuiltInEventType,
    ChangeSource,
    StageCategory,
)


# ---------------------------------------------------------------------------
# Pipeline schemas
# ---------------------------------------------------------------------------

class PipelineCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None


class PipelineUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = None
    is_active: Optional[bool] = None


class PipelineResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    company_id: int
    name: str
    description: Optional[str] = None
    is_active: bool
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# Pipeline Stage schemas
# ---------------------------------------------------------------------------

class PipelineStageCreate(BaseModel):
    name: str
    key: str
    color: str = Field(..., pattern=r'^#[0-9A-Fa-f]{6}$')
    category: StageCategory
    position: int
    is_default: bool = False
    is_closed_won: bool = False
    is_closed_lost: bool = False


class PipelineStageUpdate(BaseModel):
    name: Optional[str] = None
    key: Optional[str] = None
    color: Optional[str] = Field(None, pattern=r'^#[0-9A-Fa-f]{6}$')
    category: Optional[StageCategory] = None
    position: Optional[int] = None
    is_default: Optional[bool] = None
    is_closed_won: Optional[bool] = None
    is_closed_lost: Optional[bool] = None


class PipelineStageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    pipeline_id: int
    name: str
    key: str
    color: str
    category: StageCategory
    position: int
    is_default: bool
    is_closed_won: bool
    is_closed_lost: bool
    created_at: datetime
    updated_at: datetime


class StageReorderRequest(BaseModel):
    ordered_ids: list[int]


# ---------------------------------------------------------------------------
# Lead Stage schemas
# ---------------------------------------------------------------------------

class LeadStageMoveRequest(BaseModel):
    stage_id: int
    reason: Optional[str] = None


class LeadStageHistoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    lead_id: int
    from_stage_id: Optional[int] = None
    to_stage_id: int
    change_source: ChangeSource
    change_reason: Optional[str] = None
    changed_by_user_id: Optional[int] = None
    created_at: datetime


class LeadStageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    lead_id: int
    current_stage: Optional[PipelineStageResponse] = None
    stage_entered_at: Optional[datetime] = None
    history: list[LeadStageHistoryResponse] = []


# ---------------------------------------------------------------------------
# Pipeline Event Mapping schemas
# ---------------------------------------------------------------------------

class PipelineEventMappingUpsert(BaseModel):
    target_stage_id: int
    is_enabled: bool


class PipelineEventMappingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    pipeline_id: int
    event_type: BuiltInEventType
    target_stage_id: int
    is_enabled: bool
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# Pipeline Action Rule Step schemas
# ---------------------------------------------------------------------------

class PipelineActionRuleStepCreate(BaseModel):
    action_type: ActionType
    action_config_json: str
    position: int


class PipelineActionRuleStepResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    rule_id: int
    action_type: ActionType
    action_config_json: str
    position: int
    created_at: datetime


# ---------------------------------------------------------------------------
# Pipeline Action Rule schemas
# ---------------------------------------------------------------------------

class PipelineActionRuleCreate(BaseModel):
    name: str
    trigger_type: str
    trigger_stage_id: Optional[int] = None
    trigger_event_type: Optional[str] = None
    condition_type: str
    condition_value: Optional[str] = None
    is_enabled: bool = True
    position: int
    steps: list[PipelineActionRuleStepCreate] = []


class PipelineActionRuleUpdate(BaseModel):
    name: Optional[str] = None
    trigger_type: Optional[str] = None
    trigger_stage_id: Optional[int] = None
    trigger_event_type: Optional[str] = None
    condition_type: Optional[str] = None
    condition_value: Optional[str] = None
    is_enabled: Optional[bool] = None
    position: Optional[int] = None
    steps: Optional[list[PipelineActionRuleStepCreate]] = None


class PipelineActionRuleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    pipeline_id: int
    name: str
    trigger_type: str
    trigger_stage_id: Optional[int] = None
    trigger_event_type: Optional[str] = None
    condition_type: str
    condition_value: Optional[str] = None
    is_enabled: bool
    position: int
    steps: list[PipelineActionRuleStepResponse] = []
    created_at: datetime
    updated_at: datetime


class RuleReorderRequest(BaseModel):
    ordered_ids: list[int]


# ---------------------------------------------------------------------------
# Metrics schema
# ---------------------------------------------------------------------------

class PipelineMetricsResponse(BaseModel):
    total_leads: int
    avg_time_per_stage: dict[str, float]  # stage key -> hours
    conversion_to_won: float
    stuck_leads_count: int


# ---------------------------------------------------------------------------
# Agent-facing schema
# ---------------------------------------------------------------------------

class AgentLeadPipelineResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    pipeline_name: str
    current_stage: Optional[PipelineStageResponse] = None
    stage_entered_at: Optional[datetime] = None
    stages: list[PipelineStageResponse] = []
    lifecycle: list[dict] = []
    stage_history: list[LeadStageHistoryResponse] = []
