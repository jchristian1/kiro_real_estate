"""
PipelineActionRuleService — CRUD, reordering, and evaluation
for pipeline automation rules and their action steps.

Business rules:
- trigger_type must be "on_event" or "on_stage_enter".
- condition_type must be "bucket_is", "stage_is", or "always".
- Each step's action_type must be a valid ActionType enum value.
- action_config_json must be valid JSON for each step.
- Rules are ordered by position ascending; reorder uses a single bulk UPDATE.
- evaluate_rules returns matching ENABLED rules in ascending position order.

Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 5.7, 5.8, 5.9, 12.5, 13.6
"""

import json
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session, joinedload

from api.models.pipeline_models import (
    ActionType,
    PipelineActionRule,
    PipelineActionRuleStep,
    PipelineStage,
)
from api.models.pipeline_schemas import (
    PipelineActionRuleCreate,
    PipelineActionRuleStepCreate,
    PipelineActionRuleUpdate,
)

VALID_TRIGGER_TYPES = {"on_event", "on_stage_enter"}
VALID_CONDITION_TYPES = {"bucket_is", "stage_is", "always"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_rule_for_pipeline(
    db: Session, rule_id: int, pipeline_id: int
) -> PipelineActionRule:
    """Return the rule only if it belongs to *pipeline_id*, else raise 404."""
    rule = (
        db.query(PipelineActionRule)
        .options(joinedload(PipelineActionRule.steps))
        .filter(
            PipelineActionRule.id == rule_id,
            PipelineActionRule.pipeline_id == pipeline_id,
        )
        .first()
    )
    if rule is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Pipeline action rule not found.",
        )
    return rule


def _validate_trigger_type(trigger_type: str) -> None:
    if trigger_type not in VALID_TRIGGER_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"trigger_type must be one of {sorted(VALID_TRIGGER_TYPES)}.",
        )


def _validate_condition_type(condition_type: str) -> None:
    if condition_type not in VALID_CONDITION_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"condition_type must be one of {sorted(VALID_CONDITION_TYPES)}.",
        )


def _validate_steps(steps: list[PipelineActionRuleStepCreate]) -> None:
    """Validate action_type enum and action_config_json for each step."""
    valid_action_types = {e.value for e in ActionType}
    for i, step in enumerate(steps):
        if step.action_type.value not in valid_action_types:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Step {i}: invalid action_type '{step.action_type}'.",
            )
        try:
            json.loads(step.action_config_json)
        except (json.JSONDecodeError, ValueError):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Step {i}: action_config_json is not valid JSON.",
            )


def _create_steps(
    db: Session, rule_id: int, steps: list[PipelineActionRuleStepCreate]
) -> None:
    """Bulk-insert step rows for *rule_id*."""
    for step in steps:
        db.add(
            PipelineActionRuleStep(
                rule_id=rule_id,
                action_type=step.action_type,
                action_config_json=step.action_config_json,
                position=step.position,
            )
        )


# ---------------------------------------------------------------------------
# Public service functions
# ---------------------------------------------------------------------------


def list_rules(db: Session, pipeline_id: int) -> list[PipelineActionRule]:
    """Return all rules for *pipeline_id* ordered by position ascending, with steps eager-loaded.

    Always queries the DB directly — no in-memory cache — so that rules saved
    via the API are immediately visible to background processes (watcher, etc.).

    Requirements: 5.1, 13.6
    """
    return (
        db.query(PipelineActionRule)
        .options(joinedload(PipelineActionRule.steps))
        .filter(PipelineActionRule.pipeline_id == pipeline_id)
        .order_by(PipelineActionRule.position.asc())
        .all()
    )


def create_rule(
    db: Session, pipeline_id: int, data: PipelineActionRuleCreate
) -> PipelineActionRule:
    """Create a new automation rule with its steps within *pipeline_id*.

    Requirements: 5.2, 5.3, 5.4, 5.5, 12.5
    """
    _validate_trigger_type(data.trigger_type)
    _validate_condition_type(data.condition_type)
    _validate_steps(data.steps)

    rule = PipelineActionRule(
        pipeline_id=pipeline_id,
        name=data.name,
        trigger_type=data.trigger_type,
        trigger_stage_id=data.trigger_stage_id,
        trigger_event_type=data.trigger_event_type,
        condition_type=data.condition_type,
        condition_value=data.condition_value,
        is_enabled=data.is_enabled,
        position=data.position,
    )
    db.add(rule)
    db.flush()

    _create_steps(db, rule.id, data.steps)
    db.commit()

    return (
        db.query(PipelineActionRule)
        .options(joinedload(PipelineActionRule.steps))
        .filter(PipelineActionRule.id == rule.id)
        .one()
    )


def update_rule(
    db: Session,
    rule_id: int,
    pipeline_id: int,
    data: PipelineActionRuleUpdate,
) -> PipelineActionRule:
    """Update an existing rule, optionally replacing all its steps.

    Requirements: 5.3, 5.4, 5.5, 12.5
    """
    rule = _get_rule_for_pipeline(db, rule_id, pipeline_id)
    update_fields = data.model_dump(exclude_unset=True)

    if "trigger_type" in update_fields:
        _validate_trigger_type(update_fields["trigger_type"])

    if "condition_type" in update_fields:
        _validate_condition_type(update_fields["condition_type"])

    update_fields.pop("steps", None)
    steps_data: Optional[list[PipelineActionRuleStepCreate]] = data.steps

    if steps_data is not None:
        _validate_steps(steps_data)

    for field, value in update_fields.items():
        setattr(rule, field, value)

    if steps_data is not None:
        db.query(PipelineActionRuleStep).filter(
            PipelineActionRuleStep.rule_id == rule_id
        ).delete(synchronize_session="fetch")
        _create_steps(db, rule_id, steps_data)

    db.commit()

    return (
        db.query(PipelineActionRule)
        .options(joinedload(PipelineActionRule.steps))
        .filter(PipelineActionRule.id == rule_id)
        .one()
    )


def delete_rule(db: Session, rule_id: int, pipeline_id: int) -> None:
    """Delete a rule (cascade deletes its steps).

    Requirements: 5.7
    """
    rule = _get_rule_for_pipeline(db, rule_id, pipeline_id)
    db.delete(rule)
    db.commit()


def reorder_rules(
    db: Session, pipeline_id: int, ordered_ids: list[int]
) -> list[PipelineActionRule]:
    """Reorder rules by assigning position = index+1 for each ID in *ordered_ids*.

    Requirements: 5.8, 13.6
    """
    existing = (
        db.query(PipelineActionRule.id)
        .filter(PipelineActionRule.pipeline_id == pipeline_id)
        .all()
    )
    existing_ids = {row.id for row in existing}
    invalid = [rid for rid in ordered_ids if rid not in existing_ids]
    if invalid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Rule ID(s) {invalid} do not belong to pipeline {pipeline_id}.",
        )

    mappings = [
        {"id": rid, "position": idx + 1}
        for idx, rid in enumerate(ordered_ids)
    ]
    db.bulk_update_mappings(PipelineActionRule, mappings)
    db.commit()

    return list_rules(db, pipeline_id)


def evaluate_rules(
    db: Session,
    pipeline_id: int,
    trigger_event: str,
    lead,
) -> list[PipelineActionRule]:
    """Return matching ENABLED rules for *lead* in ascending position order.

    A rule matches when:
    - It is enabled (is_enabled=True).
    - Its trigger matches: trigger_event_type == trigger_event (on_event) OR
      trigger_stage_id == lead.current_stage_id (on_stage_enter).
    - Its condition is satisfied:
        - "always": always matches.
        - "bucket_is": lead.score_bucket matches condition_value (case-insensitive).
        - "stage_is": the stage with key == condition_value has id == lead.current_stage_id.

    Requirements: 5.6, 5.9
    """
    rules = list_rules(db, pipeline_id)

    matching: list[PipelineActionRule] = []
    for rule in rules:
        if not rule.is_enabled:
            continue

        # --- Trigger check ---
        if rule.trigger_type == "on_event":
            if rule.trigger_event_type != trigger_event:
                continue
        elif rule.trigger_type == "on_stage_enter":
            if rule.trigger_stage_id != getattr(lead, "current_stage_id", None):
                continue
        else:
            continue

        # --- Condition check ---
        if rule.condition_type == "always":
            pass  # always matches
        elif rule.condition_type == "bucket_is":
            lead_bucket = getattr(lead, "score_bucket", None)
            if lead_bucket is None:
                continue
            if lead_bucket.upper() != (rule.condition_value or "").upper():
                continue
        elif rule.condition_type == "stage_is":
            stage = (
                db.query(PipelineStage)
                .filter(
                    PipelineStage.pipeline_id == pipeline_id,
                    PipelineStage.key == rule.condition_value,
                )
                .first()
            )
            if stage is None:
                continue
            if stage.id != getattr(lead, "current_stage_id", None):
                continue
        else:
            continue

        matching.append(rule)

    return matching
