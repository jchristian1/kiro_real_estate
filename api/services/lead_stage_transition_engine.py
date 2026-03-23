"""
LeadStageTransitionEngine — Pipeline execution engine.

Receives BuiltInEventType events, resolves event-to-stage mappings, evaluates
automation rules, and dispatches action steps to the pipeline executor.

This module owns:
- Lead/company resolution
- Active pipeline lookup
- Initial stage assignment
- Event mapping application
- Rule evaluation and ordered step dispatch
- Audit logging for all transitions and actions

It does NOT own:
- How emails are sent (→ api/pipelines/handlers/send_email.py)
- How qualification forms are dispatched (→ api/pipelines/handlers/send_form.py)
- How stage mutations work (→ api/pipelines/handlers/move_stage.py)

Business rules:
- If no active pipeline exists for the lead's company, return silently (Req 6.2).
- If lead has no current_stage_id, assign the pipeline's default stage first (Req 6.7).
- Apply event mapping if it exists and is_enabled=True (Req 6.3).
- Skip event mapping if is_enabled=False (Req 6.4).
- Evaluate automation rules in ascending position order (Req 6.5).
- On action step failure: log to audit log and continue remaining steps (Req 6.6, 12.3, 12.4).
- Write audit log entry for every stage transition and every action executed (Req 6.8).

Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 6.7, 6.8, 12.3, 12.4
"""

from __future__ import annotations

import logging
from typing import Optional

from sqlalchemy.orm import Session

from api.models.pipeline_models import (
    BuiltInEventType,
    ChangeSource,
    PipelineStage,
)
from api.pipelines.handlers.base import resolve_lead_company_id
from api.services.audit_log import record_audit_log
from api.services.lead_stage_service import assign_initial_stage, move_stage
from api.services.pipeline_action_rule_service import evaluate_rules
from api.services.pipeline_event_mapping_service import get_mapping
from api.services.pipeline_service import get_active_pipeline

logger = logging.getLogger(__name__)

_SYSTEM_USER_ID = 0


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _get_default_stage(db: Session, pipeline_id: int) -> Optional[PipelineStage]:
    return (
        db.query(PipelineStage)
        .filter(
            PipelineStage.pipeline_id == pipeline_id,
            PipelineStage.is_default.is_(True),
        )
        .first()
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def fire_event(
    db: Session,
    lead_id: int,
    event_type: BuiltInEventType,
    context: dict,
) -> None:
    """Fire a lifecycle event for a lead.

    Steps:
    1. Load the lead and resolve its company_id.
    2. Look up the active pipeline; return silently if none (Req 6.2).
    3. If lead has no current_stage_id, assign the default stage (Req 6.7).
    4. Apply event mapping if enabled (Req 6.3/6.4).
    5. Evaluate and execute automation rules via the pipeline executor (Req 6.5).
    6. On step failure: log to audit log and continue (Req 6.6, 12.3, 12.4).
    7. Write audit log entries for all transitions and actions (Req 6.8).
    """
    from gmail_lead_sync.models import Lead

    lead = db.query(Lead).filter(Lead.id == lead_id).first()
    if lead is None:
        logger.warning("fire_event: lead %s not found, skipping", lead_id)
        return

    company_id = resolve_lead_company_id(db, lead_id)
    if company_id is None:
        logger.warning(
            "fire_event: cannot resolve company_id for lead %s, skipping", lead_id
        )
        return

    pipeline = get_active_pipeline(db, company_id)
    if pipeline is None:
        return

    pipeline_id = pipeline.id

    # Assign initial stage if lead has none (Req 6.7)
    if lead.current_stage_id is None:
        default_stage = _get_default_stage(db, pipeline_id)
        if default_stage is not None:
            assign_initial_stage(db, lead_id, pipeline_id, default_stage.id)
            db.refresh(lead)
            record_audit_log(
                db_session=db,
                user_id=_SYSTEM_USER_ID,
                action="lead_stage_assigned",
                resource_type="lead",
                resource_id=lead_id,
                details=(
                    f"Lead {lead_id} assigned to initial stage {default_stage.id} "
                    f"('{default_stage.name}') in pipeline {pipeline_id} "
                    f"via event '{event_type.value}'"
                ),
            )
        else:
            logger.warning(
                "fire_event: pipeline %s has no default stage; "
                "skipping initial assignment for lead %s",
                pipeline_id, lead_id,
            )

    # Apply event mapping (Req 6.3, 6.4)
    mapping = get_mapping(db, pipeline_id, event_type)
    stage_entered: Optional[int] = None
    if mapping is not None and mapping.is_enabled:
        move_stage(db, lead_id, mapping.target_stage_id, ChangeSource.event)
        db.refresh(lead)
        stage_entered = mapping.target_stage_id
        record_audit_log(
            db_session=db,
            user_id=_SYSTEM_USER_ID,
            action="lead_stage_moved",
            resource_type="lead",
            resource_id=lead_id,
            details=(
                f"Lead {lead_id} moved to stage {mapping.target_stage_id} "
                f"via event mapping for '{event_type.value}' "
                f"in pipeline {pipeline_id}"
            ),
        )

    # Evaluate automation rules (Req 6.5)
    # Queue of stages entered this cycle (event mapping + chained move_to_stage actions).
    stages_to_process: list[Optional[int]] = [stage_entered]
    processed_stage_enters: set[int] = set()
    if stage_entered is not None:
        processed_stage_enters.add(stage_entered)

    # on_event rules
    on_event_rules = evaluate_rules(
        db, pipeline_id, event_type.value, lead, stage_just_entered_id=None
    )
    for rule in on_event_rules:
        steps = sorted(rule.steps, key=lambda s: s.position)
        for step in steps:
            result = _dispatch_step(db, lead_id, pipeline_id, rule, step, context, event_type.value)
            if result.new_stage_id is not None and result.new_stage_id not in processed_stage_enters:
                processed_stage_enters.add(result.new_stage_id)
                stages_to_process.append(result.new_stage_id)

    # on_stage_enter rules for each stage entered this cycle (including chained moves)
    for entered_stage_id in stages_to_process:
        if entered_stage_id is None:
            continue
        db.refresh(lead)
        stage_enter_rules = [
            r for r in evaluate_rules(
                db, pipeline_id, event_type.value, lead,
                stage_just_entered_id=entered_stage_id,
            )
            if r.trigger_type == "on_stage_enter"
        ]
        for rule in stage_enter_rules:
            steps = sorted(rule.steps, key=lambda s: s.position)
            for step in steps:
                result = _dispatch_step(
                    db, lead_id, pipeline_id, rule, step, context,
                    f"stage_enter:{entered_stage_id}",
                )
                if result.new_stage_id is not None and result.new_stage_id not in processed_stage_enters:
                    processed_stage_enters.add(result.new_stage_id)
                    stages_to_process.append(result.new_stage_id)


def _dispatch_step(db, lead_id, pipeline_id, rule, step, context, trigger_label):
    """Dispatch one step to the executor and handle audit logging."""
    from api.pipelines.executor import execute_step

    action_type_label = (
        step.action_type.value
        if hasattr(step.action_type, "value")
        else str(step.action_type)
    )

    result = execute_step(db, lead_id, pipeline_id, rule.id, step, context)

    if result.success:
        record_audit_log(
            db_session=db,
            user_id=_SYSTEM_USER_ID,
            action="pipeline_action_executed",
            resource_type="pipeline_action_rule_step",
            resource_id=step.id,
            details=(
                f"Rule {rule.id} ('{rule.name}') step {step.id} "
                f"action_type='{action_type_label}' "
                f"executed for lead {lead_id} on {trigger_label}"
            ),
        )
    else:
        logger.error(
            "Pipeline action step failed: rule_id=%s step_id=%s lead_id=%s error=%s",
            rule.id, step.id, lead_id, result.error,
        )
        record_audit_log(
            db_session=db,
            user_id=_SYSTEM_USER_ID,
            action="pipeline_action_failed",
            resource_type="pipeline_action_rule_step",
            resource_id=step.id,
            details=(
                f"Rule {rule.id} step {step.id} (action_type='{action_type_label}') "
                f"FAILED for lead {lead_id} on {trigger_label}: {result.error}"
            ),
        )

    return result
