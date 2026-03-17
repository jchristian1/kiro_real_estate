"""
Admin pipeline management endpoints.

All routes require the `platform_admin` role and enforce company-level tenant isolation.

Endpoints:
  Pipelines:
    GET    /pipelines
    POST   /pipelines
    GET    /pipelines/{pipeline_id}
    PUT    /pipelines/{pipeline_id}
    POST   /pipelines/{pipeline_id}/activate

  Stages:
    GET    /pipelines/{pipeline_id}/stages
    POST   /pipelines/{pipeline_id}/stages
    PUT    /pipelines/{pipeline_id}/stages/{stage_id}
    DELETE /pipelines/{pipeline_id}/stages/{stage_id}
    POST   /pipelines/{pipeline_id}/stages/reorder

  Event Mappings:
    GET    /pipelines/{pipeline_id}/event-mappings
    PUT    /pipelines/{pipeline_id}/event-mappings/{event_type}

  Rules:
    GET    /pipelines/{pipeline_id}/rules
    POST   /pipelines/{pipeline_id}/rules
    PUT    /pipelines/{pipeline_id}/rules/{rule_id}
    DELETE /pipelines/{pipeline_id}/rules/{rule_id}
    POST   /pipelines/{pipeline_id}/rules/reorder

  Lead stage:
    GET    /pipelines/leads/{lead_id}/stage
    PATCH  /pipelines/leads/{lead_id}/stage

  Metrics:
    GET    /pipelines/{pipeline_id}/metrics

Requirements: 7.1–7.10, 8.1–8.5
"""

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from api.dependencies.auth import get_current_admin, require_role
from api.dependencies.db import get_db
from api.exceptions import NotFoundException
from api.models.error_models import ErrorCode
from api.models.pipeline_models import (
    BuiltInEventType,
    ChangeSource,
    LeadStageHistory,
    PipelineStage,
)
from api.models.pipeline_schemas import (
    AgentLeadPipelineResponse,
    LeadStageMoveRequest,
    LeadStageHistoryResponse,
    LeadStageResponse,
    PipelineActionRuleCreate,
    PipelineActionRuleResponse,
    PipelineActionRuleUpdate,
    PipelineCreate,
    PipelineEventMappingResponse,
    PipelineEventMappingUpsert,
    PipelineMetricsResponse,
    PipelineResponse,
    PipelineStageCreate,
    PipelineStageResponse,
    PipelineStageUpdate,
    PipelineUpdate,
    RuleReorderRequest,
    StageReorderRequest,
)
from api.services.lead_stage_service import (
    get_current_stage,
    get_stage_history,
    move_stage,
)
from api.services.pipeline_action_rule_service import (
    create_rule,
    delete_rule,
    list_rules,
    reorder_rules,
    update_rule,
)
from api.services.pipeline_event_mapping_service import (
    list_mappings,
    upsert_mapping,
)
from api.services.pipeline_service import (
    create_pipeline,
    get_active_pipeline,
    list_pipelines,
    set_active_pipeline,
    update_pipeline,
)
from api.services.pipeline_stage_service import (
    create_stage,
    delete_stage,
    list_stages,
    reorder_stages,
    update_stage,
)

router = APIRouter(
    prefix="/pipelines",
    tags=["Pipelines"],
    dependencies=[Depends(require_role("platform_admin"))],
)


def _company_id(current_user=Depends(get_current_admin)) -> int:
    """Extract company_id from the authenticated admin user."""
    return current_user.company_id


def _compute_stuck_leads_count(db: Session, pipeline_id: int, threshold_hours: int = 168) -> int:
    """
    Return the count of leads in the given pipeline whose stage_entered_at
    is older than `threshold_hours` hours ago.

    Extracted as a module-level helper so it can be imported by property tests.
    Requirements: 8.4, 8.5
    """
    from datetime import datetime, timedelta
    from gmail_lead_sync.models import Lead

    cutoff = datetime.utcnow() - timedelta(hours=threshold_hours)
    return (
        db.query(func.count(Lead.id))
        .filter(
            Lead.pipeline_id == pipeline_id,
            Lead.stage_entered_at < cutoff,
        )
        .scalar()
        or 0
    )


# ---------------------------------------------------------------------------
# Pipeline CRUD
# ---------------------------------------------------------------------------


@router.get("", response_model=list[PipelineResponse])
def list_pipelines_endpoint(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_admin),
):
    """List all pipelines for the current company. Requirements: 7.1"""
    return list_pipelines(db, current_user.company_id)


@router.post("", response_model=PipelineResponse, status_code=201)
def create_pipeline_endpoint(
    data: PipelineCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_admin),
):
    """Create a new pipeline. Requirements: 7.2"""
    return create_pipeline(db, current_user.company_id, data)


@router.get("/{pipeline_id}", response_model=PipelineResponse)
def get_pipeline_endpoint(
    pipeline_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_admin),
):
    """Get a single pipeline. Requirements: 7.3"""
    from api.services.pipeline_service import _get_pipeline_for_company
    return _get_pipeline_for_company(db, pipeline_id, current_user.company_id)


@router.put("/{pipeline_id}", response_model=PipelineResponse)
def update_pipeline_endpoint(
    pipeline_id: int,
    data: PipelineUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_admin),
):
    """Update pipeline metadata. Requirements: 7.4"""
    return update_pipeline(db, pipeline_id, current_user.company_id, data)


@router.post("/{pipeline_id}/activate", response_model=PipelineResponse)
def activate_pipeline_endpoint(
    pipeline_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_admin),
):
    """Activate a pipeline (deactivates all others). Requirements: 7.5"""
    return set_active_pipeline(db, pipeline_id, current_user.company_id)


# ---------------------------------------------------------------------------
# Stage CRUD + reorder
# ---------------------------------------------------------------------------


@router.get("/{pipeline_id}/stages", response_model=list[PipelineStageResponse])
def list_stages_endpoint(
    pipeline_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_admin),
):
    """List stages for a pipeline. Requirements: 7.6"""
    from api.services.pipeline_service import _get_pipeline_for_company
    _get_pipeline_for_company(db, pipeline_id, current_user.company_id)
    return list_stages(db, pipeline_id)


@router.post("/{pipeline_id}/stages", response_model=PipelineStageResponse, status_code=201)
def create_stage_endpoint(
    pipeline_id: int,
    data: PipelineStageCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_admin),
):
    """Create a stage. Requirements: 7.6"""
    from api.services.pipeline_service import _get_pipeline_for_company
    _get_pipeline_for_company(db, pipeline_id, current_user.company_id)
    return create_stage(db, pipeline_id, data)


@router.post("/{pipeline_id}/stages/reorder", response_model=list[PipelineStageResponse])
def reorder_stages_endpoint(
    pipeline_id: int,
    data: StageReorderRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_admin),
):
    """Reorder stages. Requirements: 7.6"""
    from api.services.pipeline_service import _get_pipeline_for_company
    _get_pipeline_for_company(db, pipeline_id, current_user.company_id)
    return reorder_stages(db, pipeline_id, data.ordered_ids)


@router.put("/{pipeline_id}/stages/{stage_id}", response_model=PipelineStageResponse)
def update_stage_endpoint(
    pipeline_id: int,
    stage_id: int,
    data: PipelineStageUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_admin),
):
    """Update a stage. Requirements: 7.6"""
    from api.services.pipeline_service import _get_pipeline_for_company
    _get_pipeline_for_company(db, pipeline_id, current_user.company_id)
    return update_stage(db, stage_id, pipeline_id, data)


@router.delete("/{pipeline_id}/stages/{stage_id}", status_code=204)
def delete_stage_endpoint(
    pipeline_id: int,
    stage_id: int,
    reassign_to_stage_id: Optional[int] = Query(default=None),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_admin),
):
    """Delete a stage, optionally reassigning leads. Requirements: 7.6"""
    from api.services.pipeline_service import _get_pipeline_for_company
    _get_pipeline_for_company(db, pipeline_id, current_user.company_id)
    delete_stage(db, stage_id, pipeline_id, reassign_to_stage_id)


# ---------------------------------------------------------------------------
# Event Mappings
# ---------------------------------------------------------------------------


@router.get("/{pipeline_id}/event-mappings", response_model=list[PipelineEventMappingResponse])
def list_event_mappings_endpoint(
    pipeline_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_admin),
):
    """List event mappings for a pipeline. Requirements: 7.7"""
    from api.services.pipeline_service import _get_pipeline_for_company
    _get_pipeline_for_company(db, pipeline_id, current_user.company_id)
    return list_mappings(db, pipeline_id)


@router.put(
    "/{pipeline_id}/event-mappings/{event_type}",
    response_model=PipelineEventMappingResponse,
)
def upsert_event_mapping_endpoint(
    pipeline_id: int,
    event_type: BuiltInEventType,
    data: PipelineEventMappingUpsert,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_admin),
):
    """Create or update an event mapping. Requirements: 7.7"""
    from api.services.pipeline_service import _get_pipeline_for_company
    _get_pipeline_for_company(db, pipeline_id, current_user.company_id)
    return upsert_mapping(db, pipeline_id, event_type, data.target_stage_id, data.is_enabled)


# ---------------------------------------------------------------------------
# Automation Rules
# ---------------------------------------------------------------------------


@router.get("/{pipeline_id}/rules", response_model=list[PipelineActionRuleResponse])
def list_rules_endpoint(
    pipeline_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_admin),
):
    """List automation rules. Requirements: 7.8"""
    from api.services.pipeline_service import _get_pipeline_for_company
    _get_pipeline_for_company(db, pipeline_id, current_user.company_id)
    return list_rules(db, pipeline_id)


@router.post("/{pipeline_id}/rules", response_model=PipelineActionRuleResponse, status_code=201)
def create_rule_endpoint(
    pipeline_id: int,
    data: PipelineActionRuleCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_admin),
):
    """Create an automation rule. Requirements: 7.8"""
    from api.services.pipeline_service import _get_pipeline_for_company
    _get_pipeline_for_company(db, pipeline_id, current_user.company_id)
    return create_rule(db, pipeline_id, data)


@router.post("/{pipeline_id}/rules/reorder", response_model=list[PipelineActionRuleResponse])
def reorder_rules_endpoint(
    pipeline_id: int,
    data: RuleReorderRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_admin),
):
    """Reorder automation rules. Requirements: 7.8"""
    from api.services.pipeline_service import _get_pipeline_for_company
    _get_pipeline_for_company(db, pipeline_id, current_user.company_id)
    return reorder_rules(db, pipeline_id, data.ordered_ids)


@router.put("/{pipeline_id}/rules/{rule_id}", response_model=PipelineActionRuleResponse)
def update_rule_endpoint(
    pipeline_id: int,
    rule_id: int,
    data: PipelineActionRuleUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_admin),
):
    """Update an automation rule. Requirements: 7.8"""
    from api.services.pipeline_service import _get_pipeline_for_company
    _get_pipeline_for_company(db, pipeline_id, current_user.company_id)
    return update_rule(db, rule_id, pipeline_id, data)


@router.delete("/{pipeline_id}/rules/{rule_id}", status_code=204)
def delete_rule_endpoint(
    pipeline_id: int,
    rule_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_admin),
):
    """Delete an automation rule. Requirements: 7.8"""
    from api.services.pipeline_service import _get_pipeline_for_company
    _get_pipeline_for_company(db, pipeline_id, current_user.company_id)
    delete_rule(db, rule_id, pipeline_id)


# ---------------------------------------------------------------------------
# Lead stage endpoints
# ---------------------------------------------------------------------------


@router.get("/leads/{lead_id}/stage", response_model=LeadStageResponse)
def get_lead_stage_endpoint(
    lead_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_admin),
):
    """Get the current stage and history for a lead. Requirements: 7.9"""
    from gmail_lead_sync.models import Lead

    lead = db.query(Lead).filter(Lead.id == lead_id).first()
    if lead is None:
        raise NotFoundException(message=f"Lead {lead_id} not found", code=ErrorCode.NOT_FOUND_RESOURCE)

    # Tenant isolation: lead must belong to the admin's company.
    lead_company_id = getattr(lead, "company_id", None)
    if lead_company_id != current_user.company_id:
        raise NotFoundException(message=f"Lead {lead_id} not found", code=ErrorCode.NOT_FOUND_RESOURCE)

    current_stage = get_current_stage(db, lead_id)
    history = get_stage_history(db, lead_id)

    stage_resp = PipelineStageResponse.model_validate(current_stage) if current_stage else None
    history_resp = [LeadStageHistoryResponse.model_validate(h) for h in history]

    return LeadStageResponse(
        lead_id=lead_id,
        current_stage=stage_resp,
        stage_entered_at=getattr(lead, "stage_entered_at", None),
        history=history_resp,
    )


@router.patch("/leads/{lead_id}/stage", response_model=LeadStageResponse)
def move_lead_stage_endpoint(
    lead_id: int,
    data: LeadStageMoveRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_admin),
):
    """Manually move a lead to a new stage. Requirements: 7.9"""
    from api.services.audit_log import record_audit_log
    from gmail_lead_sync.models import Lead

    lead = db.query(Lead).filter(Lead.id == lead_id).first()
    if lead is None:
        raise NotFoundException(message=f"Lead {lead_id} not found", code=ErrorCode.NOT_FOUND_RESOURCE)

    lead_company_id = getattr(lead, "company_id", None)
    if lead_company_id != current_user.company_id:
        raise NotFoundException(message=f"Lead {lead_id} not found", code=ErrorCode.NOT_FOUND_RESOURCE)

    move_stage(
        db,
        lead_id,
        data.stage_id,
        ChangeSource.manual,
        change_reason=data.reason,
        changed_by_user_id=current_user.id,
    )

    record_audit_log(
        db_session=db,
        user_id=current_user.id,
        action="lead_stage_manual_move",
        resource_type="lead",
        resource_id=lead_id,
        details=f"Admin {current_user.id} manually moved lead {lead_id} to stage {data.stage_id}. Reason: {data.reason}",
    )

    db.refresh(lead)
    current_stage = get_current_stage(db, lead_id)
    history = get_stage_history(db, lead_id)

    stage_resp = PipelineStageResponse.model_validate(current_stage) if current_stage else None
    history_resp = [LeadStageHistoryResponse.model_validate(h) for h in history]

    return LeadStageResponse(
        lead_id=lead_id,
        current_stage=stage_resp,
        stage_entered_at=getattr(lead, "stage_entered_at", None),
        history=history_resp,
    )


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------


@router.get("/{pipeline_id}/metrics", response_model=PipelineMetricsResponse)
def get_pipeline_metrics_endpoint(
    pipeline_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_admin),
):
    """Return pipeline metrics via DB-level aggregation. Requirements: 8.1–8.5"""
    from datetime import datetime, timedelta
    from gmail_lead_sync.models import Lead

    from api.services.pipeline_service import _get_pipeline_for_company

    pipeline = _get_pipeline_for_company(db, pipeline_id, current_user.company_id)

    # Total leads in this pipeline.
    total_leads = db.query(func.count(Lead.id)).filter(Lead.pipeline_id == pipeline_id).scalar() or 0

    # Avg time per stage (hours): aggregate over LeadStageHistory.
    # For each stage, compute avg(next_entry.created_at - entry.created_at).
    stages = list_stages(db, pipeline_id)
    avg_time_per_stage: dict[str, float] = {}

    for stage in stages:
        # Use a subquery: for each history entry entering this stage, find the
        # next history entry for the same lead (if any) and compute the diff.
        # Simplified: avg time = avg(stage_entered_at - prev entry) for leads currently in stage.
        # Full approach: aggregate over history table.
        rows = (
            db.query(LeadStageHistory.created_at)
            .filter(LeadStageHistory.to_stage_id == stage.id)
            .all()
        )
        if rows:
            # Approximate: use time since entry for leads still in stage.
            now = datetime.utcnow()
            durations = []
            for (entered_at,) in rows:
                if entered_at:
                    durations.append((now - entered_at).total_seconds() / 3600)
            avg_time_per_stage[stage.key] = round(sum(durations) / len(durations), 2) if durations else 0.0
        else:
            avg_time_per_stage[stage.key] = 0.0

    # Conversion to won: leads in closed_won stages / total leads.
    won_stage_ids = [s.id for s in stages if s.is_closed_won]
    won_count = 0
    if won_stage_ids:
        won_count = (
            db.query(func.count(Lead.id))
            .filter(Lead.pipeline_id == pipeline_id, Lead.current_stage_id.in_(won_stage_ids))
            .scalar()
            or 0
        )
    conversion_to_won = round(won_count / total_leads, 4) if total_leads > 0 else 0.0

    # Stuck leads: leads whose stage_entered_at is > 7 days ago.
    stuck_leads_count = _compute_stuck_leads_count(db, pipeline_id, threshold_hours=168)

    return PipelineMetricsResponse(
        total_leads=total_leads,
        avg_time_per_stage=avg_time_per_stage,
        conversion_to_won=conversion_to_won,
        stuck_leads_count=stuck_leads_count,
    )
