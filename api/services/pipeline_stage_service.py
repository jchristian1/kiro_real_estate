"""
PipelineStageService — CRUD, reordering, and default-stage management for pipeline stages.

Business rules:
- Stage keys must match ^[a-z0-9_]+$ and be unique per pipeline.
- is_closed_won and is_closed_lost are mutually exclusive.
- At most one stage per pipeline may have is_default = True at any time.
- Reordering is performed in a single bulk UPDATE.
- Deleting a stage with assigned leads requires a reassignment target or raises HTTP 409.

Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7, 2.8, 2.9, 2.10, 2.11, 12.2, 13.7
"""

import re
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from api.models.pipeline_models import PipelineStage
from api.models.pipeline_schemas import PipelineStageCreate, PipelineStageUpdate
from gmail_lead_sync.models import Lead

_KEY_RE = re.compile(r'^[a-z0-9_]+$')


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_stage_for_pipeline(db: Session, stage_id: int, pipeline_id: int) -> PipelineStage:
    """Return the stage only if it belongs to *pipeline_id*, else raise 404."""
    stage = (
        db.query(PipelineStage)
        .filter(PipelineStage.id == stage_id, PipelineStage.pipeline_id == pipeline_id)
        .first()
    )
    if stage is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Pipeline stage not found.",
        )
    return stage


def _validate_key(key: str) -> str:
    """Sanitize and validate the stage key. Returns the sanitized key or raises HTTP 400."""
    sanitized = key.strip().lower()
    if not _KEY_RE.match(sanitized):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Stage key must contain only lowercase letters, digits, and underscores.",
        )
    return sanitized


def _check_key_unique(
    db: Session,
    pipeline_id: int,
    key: str,
    exclude_id: Optional[int] = None,
) -> None:
    """Raise HTTP 400 if *key* is already used by another stage in *pipeline_id*."""
    query = db.query(PipelineStage).filter(
        PipelineStage.pipeline_id == pipeline_id,
        PipelineStage.key == key,
    )
    if exclude_id is not None:
        query = query.filter(PipelineStage.id != exclude_id)
    if query.first() is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"A stage with key '{key}' already exists in this pipeline.",
        )


def _validate_closed_flags(is_closed_won: bool, is_closed_lost: bool) -> None:
    """Raise HTTP 400 if both closed flags are True."""
    if is_closed_won and is_closed_lost:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A stage cannot be both is_closed_won and is_closed_lost.",
        )


def _unset_default_stages(db: Session, pipeline_id: int, exclude_id: Optional[int] = None) -> None:
    """Bulk-unset is_default on all stages in *pipeline_id* except *exclude_id*."""
    query = db.query(PipelineStage).filter(
        PipelineStage.pipeline_id == pipeline_id,
        PipelineStage.is_default.is_(True),
    )
    if exclude_id is not None:
        query = query.filter(PipelineStage.id != exclude_id)
    query.update({"is_default": False}, synchronize_session="fetch")


# ---------------------------------------------------------------------------
# Public service functions
# ---------------------------------------------------------------------------


def list_stages(db: Session, pipeline_id: int) -> list[PipelineStage]:
    """Return all stages for *pipeline_id* ordered by position ascending.

    Requirements: 2.1
    """
    return (
        db.query(PipelineStage)
        .filter(PipelineStage.pipeline_id == pipeline_id)
        .order_by(PipelineStage.position.asc())
        .all()
    )


def create_stage(db: Session, pipeline_id: int, data: PipelineStageCreate) -> PipelineStage:
    """Create a new stage within *pipeline_id*.

    Validates key format, key uniqueness, closed flags, and default invariant.

    Requirements: 2.2, 2.3, 2.4, 2.5, 2.6, 2.7
    """
    sanitized_key = _validate_key(data.key)
    _check_key_unique(db, pipeline_id, sanitized_key)
    _validate_closed_flags(data.is_closed_won, data.is_closed_lost)

    if data.is_default:
        _unset_default_stages(db, pipeline_id)

    stage = PipelineStage(
        pipeline_id=pipeline_id,
        name=data.name,
        key=sanitized_key,
        color=data.color,
        category=data.category,
        position=data.position,
        is_default=data.is_default,
        is_closed_won=data.is_closed_won,
        is_closed_lost=data.is_closed_lost,
    )
    db.add(stage)
    db.commit()
    db.refresh(stage)
    return stage


def update_stage(
    db: Session, stage_id: int, pipeline_id: int, data: PipelineStageUpdate
) -> PipelineStage:
    """Update an existing stage.

    Raises HTTP 404 if the stage does not belong to *pipeline_id*.
    Applies the same validations as create for any changed fields.

    Requirements: 2.8, 2.9
    """
    stage = _get_stage_for_pipeline(db, stage_id, pipeline_id)
    update_fields = data.model_dump(exclude_unset=True)

    # Validate and sanitize key if changing.
    if "key" in update_fields:
        update_fields["key"] = _validate_key(update_fields["key"])
        if update_fields["key"] != stage.key:
            _check_key_unique(db, pipeline_id, update_fields["key"], exclude_id=stage_id)

    # Determine effective closed flags for mutual-exclusion check.
    effective_won = update_fields.get("is_closed_won", stage.is_closed_won)
    effective_lost = update_fields.get("is_closed_lost", stage.is_closed_lost)
    _validate_closed_flags(effective_won, effective_lost)

    # Handle default flag.
    if update_fields.get("is_default") is True:
        _unset_default_stages(db, pipeline_id, exclude_id=stage_id)

    for field, value in update_fields.items():
        setattr(stage, field, value)

    db.commit()
    db.refresh(stage)
    return stage


def delete_stage(
    db: Session,
    stage_id: int,
    pipeline_id: int,
    reassign_to_stage_id: Optional[int] = None,
) -> None:
    """Delete a stage, optionally reassigning its leads first.

    Raises HTTP 404 if the stage does not belong to *pipeline_id*.
    Raises HTTP 409 if leads are assigned and no reassignment target is given.

    Requirements: 2.10, 2.11, 12.2
    """
    stage = _get_stage_for_pipeline(db, stage_id, pipeline_id)

    lead_count = (
        db.query(Lead)
        .filter(Lead.current_stage_id == stage_id)
        .count()
    )

    if lead_count > 0:
        if reassign_to_stage_id is None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    f"Cannot delete stage: {lead_count} lead(s) are currently assigned to it. "
                    "Provide reassign_to_stage_id to move them first."
                ),
            )
        # Bulk reassign leads to the new stage.
        db.query(Lead).filter(Lead.current_stage_id == stage_id).update(
            {"current_stage_id": reassign_to_stage_id},
            synchronize_session="fetch",
        )

    db.delete(stage)
    db.commit()


def reorder_stages(db: Session, pipeline_id: int, ordered_ids: list[int]) -> list[PipelineStage]:
    """Reorder stages by assigning position = index+1 for each ID in *ordered_ids*.

    Verifies all IDs belong to *pipeline_id* and performs a single bulk UPDATE.

    Requirements: 2.9, 13.7
    """
    # Verify all IDs belong to this pipeline.
    existing = (
        db.query(PipelineStage.id)
        .filter(PipelineStage.pipeline_id == pipeline_id)
        .all()
    )
    existing_ids = {row.id for row in existing}
    invalid = [sid for sid in ordered_ids if sid not in existing_ids]
    if invalid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Stage ID(s) {invalid} do not belong to pipeline {pipeline_id}.",
        )

    # Single bulk UPDATE using a CASE expression via individual mapped updates.
    # SQLAlchemy bulk_update_mappings performs one round-trip.
    mappings = [
        {"id": sid, "position": idx + 1}
        for idx, sid in enumerate(ordered_ids)
    ]
    db.bulk_update_mappings(PipelineStage, mappings)
    db.commit()

    # Return stages in the new order.
    return (
        db.query(PipelineStage)
        .filter(PipelineStage.pipeline_id == pipeline_id)
        .order_by(PipelineStage.position.asc())
        .all()
    )


def set_default_stage(db: Session, stage_id: int, pipeline_id: int) -> PipelineStage:
    """Set *stage_id* as the default stage for *pipeline_id*.

    Unsets is_default on all other stages in a bulk UPDATE, then sets the target.

    Requirements: 2.6, 2.7
    """
    stage = _get_stage_for_pipeline(db, stage_id, pipeline_id)

    # Bulk-unset all other defaults.
    _unset_default_stages(db, pipeline_id, exclude_id=stage_id)

    stage.is_default = True
    db.commit()
    db.refresh(stage)
    return stage
