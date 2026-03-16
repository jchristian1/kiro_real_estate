"""
Pagination dependency.

Provides `PaginationParams` and `get_pagination` — a reusable FastAPI
dependency that parses and validates `skip` / `limit` query parameters.

Usage:
    from api.dependencies.pagination import get_pagination, PaginationParams

    @router.get("/items")
    def list_items(pagination: PaginationParams = Depends(get_pagination)):
        return db.query(Item).offset(pagination.skip).limit(pagination.limit).all()

Requirements: 7.4
"""

from dataclasses import dataclass

from fastapi import Query


@dataclass
class PaginationParams:
    """Validated pagination parameters."""

    skip: int = 0
    limit: int = 50


def get_pagination(
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(50, ge=1, le=1000, description="Maximum number of records to return"),
) -> PaginationParams:
    """
    Parse and validate pagination query parameters.

    - ``skip`` must be ≥ 0 (default 0).
    - ``limit`` must be between 1 and 1000 inclusive (default 50).

    Returns a :class:`PaginationParams` dataclass instance.

    Requirements: 7.4
    """
    return PaginationParams(skip=skip, limit=limit)
