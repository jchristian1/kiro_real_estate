"""
Audit log API endpoints.

This module provides REST API endpoints for viewing audit logs with
pagination and filtering capabilities.

Endpoints:
- GET /api/v1/audit-logs - List audit logs with pagination and filtering
"""

from typing import Optional
from datetime import datetime
from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from api.models.web_ui_models import User
from api.models.audit_models import AuditLogResponse, AuditLogListResponse
from api.repositories.audit_repository import AuditRepository


router = APIRouter()


def get_db_dependency():
    """Database dependency."""
    from api.main import SessionLocal
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_user_dependency(request: Request, db: Session = Depends(get_db_dependency)) -> User:
    """Authentication dependency."""
    from api.auth import get_current_user
    return get_current_user(request, db)


@router.get("/audit-logs", response_model=AuditLogListResponse)
def list_audit_logs(
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    per_page: int = Query(100, ge=1, le=500, description="Items per page"),
    action: Optional[str] = Query(None, description="Filter by action type"),
    user_id: Optional[int] = Query(None, description="Filter by user ID"),
    start_date: Optional[datetime] = Query(None, description="Filter by start date (ISO 8601)"),
    end_date: Optional[datetime] = Query(None, description="Filter by end date (ISO 8601)"),
    db: Session = Depends(get_db_dependency),
    current_user: User = Depends(get_current_user_dependency)
):
    """
    List audit logs with pagination and filtering.

    Requirements:
        - 7.1: Provide endpoints for retrieving Audit_Log records with pagination
        - 7.2: Support filtering Audit_Log by action type, user, and date range
        - 7.4: Display audit logs in a filterable table
    """
    offset = (page - 1) * per_page
    repo = AuditRepository(db)

    logs, total = repo.list_with_filters(
        action=action,
        user_id=user_id,
        start_date=start_date,
        end_date=end_date,
        skip=offset,
        limit=per_page,
    )

    pages = (total + per_page - 1) // per_page if total > 0 else 0

    log_responses = []
    for log in logs:
        user = repo.get_user_by_id(log.user_id)
        log_responses.append(
            AuditLogResponse(
                id=log.id,
                timestamp=log.timestamp,
                user_id=log.user_id,
                username=user.username if user else "Unknown",
                action=log.action,
                resource_type=log.resource_type,
                resource_id=log.resource_id,
                details=log.details
            )
        )

    return AuditLogListResponse(
        logs=log_responses,
        total=total,
        page=page,
        per_page=per_page,
        pages=pages
    )
