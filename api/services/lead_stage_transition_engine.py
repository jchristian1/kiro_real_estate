"""
LeadStageTransitionEngine — Pipeline execution engine.

Receives BuiltInEventType events, resolves event-to-stage mappings, evaluates
automation rules, and executes action steps.  This is the single coordination
point for pipeline stage transitions and rule execution.

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

import json
import logging
from typing import Optional

from sqlalchemy.orm import Session

from api.models.pipeline_models import (
    BuiltInEventType,
    ChangeSource,
    PipelineStage,
)
from api.services.audit_log import record_audit_log
from api.services.communications import (
    get_smtp_credentials,
    render_admin_template,
    send_email,
)
from api.services.lead_stage_service import assign_initial_stage, move_stage
from api.services.pipeline_action_rule_service import evaluate_rules
from api.services.pipeline_event_mapping_service import get_mapping
from api.services.pipeline_service import get_active_pipeline

logger = logging.getLogger(__name__)

_SYSTEM_USER_ID = 0


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _get_company_id(db: Session, lead_id: int) -> Optional[int]:
    """Resolve company_id for a lead via direct column, lead_source, or agent_user."""
    from gmail_lead_sync.models import Lead

    lead = db.query(Lead).filter(Lead.id == lead_id).first()
    if lead is None:
        return None

    company_id = getattr(lead, "company_id", None)
    if company_id:
        return company_id

    lead_source = getattr(lead, "lead_source", None)
    if lead_source is not None:
        source_company_id = getattr(lead_source, "company_id", None)
        if source_company_id:
            return source_company_id

    agent_user = getattr(lead, "agent_user", None)
    if agent_user is not None:
        agent_company_id = getattr(agent_user, "company_id", None)
        if agent_company_id:
            return agent_company_id

    return None


def _get_default_stage(db: Session, pipeline_id: int) -> Optional[PipelineStage]:
    return (
        db.query(PipelineStage)
        .filter(
            PipelineStage.pipeline_id == pipeline_id,
            PipelineStage.is_default.is_(True),
        )
        .first()
    )


def _get_lead_and_tenant(db: Session, lead_id: int):
    """Return (lead, tenant_id) or raise ValueError."""
    from gmail_lead_sync.models import Lead

    lead = db.query(Lead).filter(Lead.id == lead_id).first()
    if lead is None:
        raise ValueError(f"Lead {lead_id} not found")
    tenant_id = _get_company_id(db, lead_id)
    if tenant_id is None:
        raise ValueError(f"Cannot resolve company_id for lead {lead_id}")
    return lead, tenant_id


# ---------------------------------------------------------------------------
# Step execution
# ---------------------------------------------------------------------------


def _execute_step(
    db: Session,
    lead_id: int,
    pipeline_id: int,
    rule_id: int,
    step,
    context: dict,
) -> Optional[int]:
    """Execute a single automation rule step.

    Returns the new stage_id if a move_to_stage action was performed, else None.
    Raises on failure so the caller can catch and log it.
    """
    action_type = (
        step.action_type.value
        if hasattr(step.action_type, "value")
        else step.action_type
    )
    config: dict = {}
    try:
        config = json.loads(step.action_config_json)
    except (json.JSONDecodeError, TypeError):
        pass

    if action_type in ("send_email_template", "send_bucket_followup_email"):
        template_id = config.get("template_id")
        if template_id is None:
            raise ValueError(f"{action_type}: missing template_id in action_config_json")
        lead, tenant_id = _get_lead_and_tenant(db, lead_id)
        subject, body = render_admin_template(db, template_id, lead, tenant_id)
        from_email, app_password = get_smtp_credentials(db, tenant_id)
        send_email(lead.source_email, subject, body, from_email, app_password)
        logger.info(
            "Pipeline action: %s sent lead_id=%s template_id=%s",
            action_type, lead_id, template_id,
        )

    elif action_type == "send_qualification_form":
        lead, tenant_id = _get_lead_and_tenant(db, lead_id)
        from gmail_lead_sync.preapproval.handlers import on_buyer_lead_email_received
        on_buyer_lead_email_received(
            db=db,
            tenant_id=tenant_id,
            lead_id=lead_id,
            parsed_metadata=context,
        )
        logger.info(
            "Pipeline action: send_qualification_form sent lead_id=%s tenant_id=%s",
            lead_id, tenant_id,
        )

    elif action_type == "move_to_stage":
        stage_id = config.get("stage_id")
        if stage_id is None:
            raise ValueError("move_to_stage: missing stage_id in action_config_json")
        move_stage(db, lead_id, int(stage_id), ChangeSource.automation)
        logger.info(
            "Pipeline action: move_to_stage lead_id=%s stage_id=%s",
            lead_id, stage_id,
        )
        return int(stage_id)

    else:
        logger.warning(
            "Unknown action_type '%s' for step %s in rule %s — skipping",
            action_type, step.id, rule_id,
        )

    return None


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
    5. Evaluate and execute automation rules (Req 6.5).
    6. On step failure: log to audit log and continue (Req 6.6, 12.3, 12.4).
    7. Write audit log entries for all transitions and actions (Req 6.8).
    """
    from gmail_lead_sync.models import Lead

    lead = db.query(Lead).filter(Lead.id == lead_id).first()
    if lead is None:
        logger.warning("fire_event: lead %s not found, skipping", lead_id)
        return

    company_id = _get_company_id(db, lead_id)
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
            try:
                new_stage = _execute_step(db, lead_id, pipeline_id, rule.id, step, context)
                record_audit_log(
                    db_session=db,
                    user_id=_SYSTEM_USER_ID,
                    action="pipeline_action_executed",
                    resource_type="pipeline_action_rule_step",
                    resource_id=step.id,
                    details=(
                        f"Rule {rule.id} ('{rule.name}') step {step.id} "
                        f"action_type='{step.action_type.value if hasattr(step.action_type, 'value') else step.action_type}' "
                        f"executed for lead {lead_id} on event '{event_type.value}'"
                    ),
                )
                if new_stage is not None and new_stage not in processed_stage_enters:
                    processed_stage_enters.add(new_stage)
                    stages_to_process.append(new_stage)
            except Exception as exc:
                _log_step_failure(db, rule, step, lead_id, event_type.value, str(exc))

    # on_stage_enter rules for each stage entered this cycle (including chained moves)
    for entered_stage_id in stages_to_process:
        if entered_stage_id is None:
            continue
        db.refresh(lead)
        stage_enter_rules = evaluate_rules(
            db, pipeline_id, event_type.value, lead,
            stage_just_entered_id=entered_stage_id,
        )
        for rule in stage_enter_rules:
            steps = sorted(rule.steps, key=lambda s: s.position)
            for step in steps:
                try:
                    new_stage = _execute_step(
                        db, lead_id, pipeline_id, rule.id, step, context
                    )
                    record_audit_log(
                        db_session=db,
                        user_id=_SYSTEM_USER_ID,
                        action="pipeline_action_executed",
                        resource_type="pipeline_action_rule_step",
                        resource_id=step.id,
                        details=(
                            f"Rule {rule.id} ('{rule.name}') step {step.id} "
                            f"action_type='{step.action_type.value if hasattr(step.action_type, 'value') else step.action_type}' "
                            f"executed for lead {lead_id} on stage_enter {entered_stage_id}"
                        ),
                    )
                    if new_stage is not None and new_stage not in processed_stage_enters:
                        processed_stage_enters.add(new_stage)
                        stages_to_process.append(new_stage)
                except Exception as exc:
                    _log_step_failure(
                        db, rule, step, lead_id,
                        f"stage_enter:{entered_stage_id}", str(exc),
                    )


def _log_step_failure(db, rule, step, lead_id, trigger_label, error_msg):
    action_type_label = (
        step.action_type.value
        if hasattr(step.action_type, "value")
        else step.action_type
    )
    logger.error(
        "Pipeline action step failed: rule_id=%s step_id=%s lead_id=%s error=%s",
        rule.id, step.id, lead_id, error_msg,
    )
    record_audit_log(
        db_session=db,
        user_id=_SYSTEM_USER_ID,
        action="pipeline_action_failed",
        resource_type="pipeline_action_rule_step",
        resource_id=step.id,
        details=(
            f"Rule {rule.id} step {step.id} (action_type='{action_type_label}') "
            f"FAILED for lead {lead_id} on {trigger_label}: {error_msg}"
        ),
    )
