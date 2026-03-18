"""
PipelineService — CRUD and active-pipeline enforcement for the Pipelines feature.

Business rules:
- Pipeline names must be non-empty, max 100 chars, and unique per company.
- At most one pipeline per company may have is_active = True at any time.
- On activation, all other pipelines for the same company are set to is_active = False
  in a single bulk UPDATE.

Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6
"""

from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from api.models.pipeline_models import Pipeline
from api.models.pipeline_schemas import PipelineCreate, PipelineUpdate


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_pipeline_for_company(
    db: Session, pipeline_id: int, company_id: int
) -> Pipeline:
    """Return the pipeline only if it belongs to *company_id*, else raise 404."""
    pipeline = (
        db.query(Pipeline)
        .filter(Pipeline.id == pipeline_id, Pipeline.company_id == company_id)
        .first()
    )
    if pipeline is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Pipeline not found.",
        )
    return pipeline


def _check_name_unique(
    db: Session,
    company_id: int,
    name: str,
    exclude_id: Optional[int] = None,
) -> None:
    """Raise HTTP 400 if *name* is already used by another pipeline in *company_id*."""
    query = db.query(Pipeline).filter(
        Pipeline.company_id == company_id,
        Pipeline.name == name,
    )
    if exclude_id is not None:
        query = query.filter(Pipeline.id != exclude_id)
    if query.first() is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"A pipeline named '{name}' already exists for this company.",
        )


# ---------------------------------------------------------------------------
# Public service functions
# ---------------------------------------------------------------------------


def get_active_pipeline(db: Session, company_id: int) -> Optional[Pipeline]:
    """Return the single active pipeline for *company_id*, or None.

    Requirements: 1.1, 1.5
    """
    return (
        db.query(Pipeline)
        .filter(Pipeline.company_id == company_id, Pipeline.is_active.is_(True))
        .first()
    )


def list_pipelines(db: Session, company_id: int) -> list[Pipeline]:
    """Return all pipelines belonging to *company_id*.

    Requirements: 1.1, 1.6
    """
    return (
        db.query(Pipeline)
        .filter(Pipeline.company_id == company_id)
        .order_by(Pipeline.created_at.asc())
        .all()
    )


def create_pipeline(db: Session, company_id: int, data: PipelineCreate) -> Pipeline:
    """Create a new pipeline scoped to *company_id*.

    Validates:
    - name is non-empty and at most 100 chars (enforced by Pydantic schema).
    - name is unique within the company.

    Requirements: 1.1, 1.2, 1.3
    """
    _check_name_unique(db, company_id, data.name)

    pipeline = Pipeline(
        company_id=company_id,
        name=data.name,
        description=data.description,
        is_active=False,
    )
    db.add(pipeline)
    db.commit()
    db.refresh(pipeline)
    return pipeline


def update_pipeline(
    db: Session, pipeline_id: int, company_id: int, data: PipelineUpdate
) -> Pipeline:
    """Update metadata on an existing pipeline.

    Raises HTTP 404 if the pipeline does not belong to *company_id*.
    Raises HTTP 400 if the new name conflicts with another pipeline in the company.

    Requirements: 1.1, 1.2, 1.3
    """
    pipeline = _get_pipeline_for_company(db, pipeline_id, company_id)

    update_fields = data.model_dump(exclude_unset=True)

    # Validate name uniqueness if the name is being changed.
    if "name" in update_fields and update_fields["name"] != pipeline.name:
        _check_name_unique(db, company_id, update_fields["name"], exclude_id=pipeline_id)

    # is_active changes via update_pipeline are allowed but do NOT enforce the
    # single-active invariant — use set_active_pipeline for that.
    for field, value in update_fields.items():
        setattr(pipeline, field, value)

    db.commit()
    db.refresh(pipeline)
    return pipeline


def set_active_pipeline(db: Session, pipeline_id: int, company_id: int) -> Pipeline:
    """Activate *pipeline_id* and deactivate all other pipelines for *company_id*.

    The deactivation is performed in a single bulk UPDATE to satisfy the
    atomicity requirement (Requirement 1.4, 1.5).

    Raises HTTP 404 if the pipeline does not belong to *company_id*.

    Requirements: 1.4, 1.5
    """
    # Verify ownership first.
    pipeline = _get_pipeline_for_company(db, pipeline_id, company_id)

    # Bulk-deactivate all other pipelines for this company.
    db.query(Pipeline).filter(
        Pipeline.company_id == company_id,
        Pipeline.id != pipeline_id,
    ).update({"is_active": False}, synchronize_session="fetch")

    # Activate the target pipeline.
    pipeline.is_active = True
    db.commit()
    db.refresh(pipeline)
    return pipeline
