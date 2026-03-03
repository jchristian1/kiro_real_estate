"""
Audit log API endpoints.

This module provides REST API endpoints for viewing audit logs with
pagination and filtering capabilities.

Endpoints:
- GET /api/v1/audit-logs - List audit logs with pagination and filtering
"""

from typing import Optional, List
from datetime import datetime
from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session
from sqlalchemy import and_

from api.models.web_ui_models import AuditLog, User
from api.models.audit_models import AuditLogResponse, AuditLogListResponse


router = APIRouter()


# These will be imported from main.py when the router is included
# For testing, they can be overridden using app.dependency_overrides
def get_db_dependency():
    """Database dependency - will be overridden by main.py."""
    from api.main import get_db
    return get_db()


def get_current_user_dependency(request: Request, db: Session = Depends(get_db_dependency)) -> User:
    """Authentication dependency - will be overridden by main.py."""
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
    
    Supports filtering by:
    - action: Action type (e.g., 'agent_created', 'template_updated')
    - user_id: User who performed the action
    - start_date: Start of date range (inclusive)
    - end_date: End of date range (inclusive)
    
    Returns paginated results with total count.
    
    Requirements:
        - 7.1: Provide endpoints for retrieving Audit_Log records with pagination
        - 7.2: Support filtering Audit_Log by action type, user, and date range
        - 7.4: Display audit logs in a filterable table
    """
    # Build filter conditions
    filters = []
    
    if action:
        filters.append(AuditLog.action == action)
    
    if user_id:
        filters.append(AuditLog.user_id == user_id)
    
    if start_date:
        filters.append(AuditLog.timestamp >= start_date)
    
    if end_date:
        filters.append(AuditLog.timestamp <= end_date)
    
    # Build query with filters
    query = db.query(AuditLog)
    if filters:
        query = query.filter(and_(*filters))
    
    # Get total count
    total = query.count()
    
    # Calculate pagination
    offset = (page - 1) * per_page
    pages = (total + per_page - 1) // per_page if total > 0 else 0
    
    # Get paginated results, ordered by timestamp descending (most recent first)
    logs = query.order_by(AuditLog.timestamp.desc()).offset(offset).limit(per_page).all()
    
    # Convert to response models with username
    log_responses = []
    for log in logs:
        user = db.query(User).filter(User.id == log.user_id).first()
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
