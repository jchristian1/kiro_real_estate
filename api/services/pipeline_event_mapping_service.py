"""
PipelineEventMappingService — upsert, query, and cache management for pipeline event mappings.

Business rules:
- At most one mapping per (pipeline_id, event_type) pair (upsert semantics).
- target_stage_id must belong to the same pipeline (HTTP 400 if not).
- list_mappings returns one entry per BuiltInEventType, including disabled ones.
- In-memory cache keyed by pipeline_id; invalidated on any write.
- On stage deletion: auto-disable affected mappings (set is_enabled=False).

Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 12.1, 13.6
"""

from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from api.models.pipeline_models import (
    BuiltInEventType,
    Pipeline,
    PipelineEventMapping,
    PipelineStage,
)

# ---------------------------------------------------------------------------
# In-memory cache: pipeline_id -> list[PipelineEventMapping]
# ---------------------------------------------------------------------------

_cache: dict[int, list[PipelineEventMapping]] = {}


def _invalidate_cache(pipeline_id: int) -> None:
    """Remove the cached entry for *pipeline_id*."""
    _cache.pop(pipeline_id, None)


def _get_pipeline_company_id(db: Session, pipeline_id: int) -> int:
    """Return the company_id for *pipeline_id*, raising 404 if not found."""
    pipeline = db.query(Pipeline).filter(Pipeline.id == pipeline_id).first()
    if pipeline is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Pipeline not found.",
        )
    return pipeline.company_id


def _invalidate_cache_for_company(db: Session, pipeline_id: int) -> None:
    """Invalidate cache for all pipelines belonging to the same company as *pipeline_id*."""
    company_id = _get_pipeline_company_id(db, pipeline_id)
    pipeline_ids = (
        db.query(Pipeline.id)
        .filter(Pipeline.company_id == company_id)
        .all()
    )
    for (pid,) in pipeline_ids:
        _invalidate_cache(pid)


def _validate_stage_belongs_to_pipeline(
    db: Session, stage_id: int, pipeline_id: int
) -> None:
    """Raise HTTP 400 if *stage_id* does not belong to *pipeline_id*."""
    stage = (
        db.query(PipelineStage)
        .filter(PipelineStage.id == stage_id, PipelineStage.pipeline_id == pipeline_id)
        .first()
    )
    if stage is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Stage {stage_id} does not belong to pipeline {pipeline_id}.",
        )


# ---------------------------------------------------------------------------
# Public service functions
# ---------------------------------------------------------------------------


def list_mappings(db: Session, pipeline_id: int) -> list[PipelineEventMapping]:
    """Return all event mappings for *pipeline_id*, one per BuiltInEventType.

    Results are served from the in-memory cache when available.

    Requirements: 4.1, 4.5, 13.6
    """
    if pipeline_id in _cache:
        return _cache[pipeline_id]

    mappings = (
        db.query(PipelineEventMapping)
        .filter(PipelineEventMapping.pipeline_id == pipeline_id)
        .all()
    )
    _cache[pipeline_id] = mappings
    return mappings


def get_mapping(
    db: Session, pipeline_id: int, event_type: BuiltInEventType
) -> Optional[PipelineEventMapping]:
    """Return the mapping for *(pipeline_id, event_type)*, or None if absent.

    Requirements: 4.2
    """
    return (
        db.query(PipelineEventMapping)
        .filter(
            PipelineEventMapping.pipeline_id == pipeline_id,
            PipelineEventMapping.event_type == event_type,
        )
        .first()
    )


def upsert_mapping(
    db: Session,
    pipeline_id: int,
    event_type: BuiltInEventType,
    target_stage_id: int,
    is_enabled: bool,
) -> PipelineEventMapping:
    """Create or update the mapping for *(pipeline_id, event_type)*.

    Validates that *target_stage_id* belongs to *pipeline_id*.
    Invalidates the in-memory cache for the pipeline's company after writing.

    Requirements: 4.2, 4.3, 13.6
    """
    _validate_stage_belongs_to_pipeline(db, target_stage_id, pipeline_id)

    mapping = get_mapping(db, pipeline_id, event_type)

    if mapping is not None:
        mapping.target_stage_id = target_stage_id
        mapping.is_enabled = is_enabled
    else:
        mapping = PipelineEventMapping(
            pipeline_id=pipeline_id,
            event_type=event_type,
            target_stage_id=target_stage_id,
            is_enabled=is_enabled,
        )
        db.add(mapping)

    db.commit()
    db.refresh(mapping)

    _invalidate_cache_for_company(db, pipeline_id)
    return mapping


def disable_mappings_for_stage(db: Session, stage_id: int) -> None:
    """Set is_enabled=False on all mappings targeting *stage_id*.

    Called when a stage is deleted to prevent stale event routing.
    Invalidates the cache for all affected pipelines.

    Requirements: 4.4, 12.1
    """
    affected_pipeline_ids = (
        db.query(PipelineEventMapping.pipeline_id)
        .filter(PipelineEventMapping.target_stage_id == stage_id)
        .distinct()
        .all()
    )

    db.query(PipelineEventMapping).filter(
        PipelineEventMapping.target_stage_id == stage_id
    ).update({"is_enabled": False}, synchronize_session="fetch")

    db.commit()

    for (pid,) in affected_pipeline_ids:
        _invalidate_cache(pid)
