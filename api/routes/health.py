"""
Health monitoring API endpoints.

This module provides REST API endpoints for system health monitoring:
- Health check endpoint with database, watcher, and error status
- Does NOT require authentication (for monitoring tools)

Endpoints:
- GET /api/v1/health - Comprehensive health check

Requirements:
- 8.1: Provide health check endpoint returning system status
- 8.3: Track active Watcher count and last heartbeat per Watcher
- 8.4: Track database connection status
- 8.6: Display error logs from the last 24 hours
"""

import logging
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from sqlalchemy import text, and_

from api.models.health_models import (
    HealthCheckResponse,
    DatabaseStatus,
    WatcherHealthStatus,
    ErrorSummary
)
from api.models.web_ui_models import AuditLog


logger = logging.getLogger(__name__)
router = APIRouter()


# Dependencies
def get_db():
    """Database dependency - will be overridden in tests."""
    from api.main import SessionLocal
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_watcher_registry():
    """
    Get the global WatcherRegistry instance.
    
    Returns:
        WatcherRegistry instance
    """
    from api.main import watcher_registry
    return watcher_registry


@router.get("/health", response_model=HealthCheckResponse, status_code=status.HTTP_200_OK)
async def health_check(
    db: Session = Depends(get_db),
    registry = Depends(get_watcher_registry)
):
    """
    Comprehensive health check endpoint.
    
    Returns system health information including:
    - Database connection status
    - Active watcher count and heartbeats
    - Error count from last 24 hours
    - Recent error messages
    
    This endpoint does NOT require authentication to allow monitoring
    tools to check system health.
    
    Args:
        db: Database session
        registry: WatcherRegistry instance
        
    Returns:
        HealthCheckResponse with comprehensive system status
        
    Requirements:
        - 8.1: Provide health check endpoint returning system status
        - 8.3: Track active Watcher count and last heartbeat per Watcher
        - 8.4: Track database connection status
        - 8.6: Display error logs from the last 24 hours
    """
    # Check database connection
    db_status = DatabaseStatus(connected=False, message=None)
    try:
        db.execute(text("SELECT 1"))
        db_status.connected = True
        db_status.message = "Database connection active"
    except Exception as e:
        logger.error(f"Database health check failed: {str(e)}", exc_info=True)
        db_status.connected = False
        db_status.message = f"Database connection failed: {str(e)}"
    
    # Get watcher status
    watcher_statuses = await registry.get_all_statuses()
    
    # Count active watchers and collect heartbeats
    active_count = 0
    heartbeats = {}
    
    for agent_id, watcher_info in watcher_statuses.items():
        if watcher_info["status"] == "running":
            active_count += 1
        
        # Add heartbeat timestamp
        heartbeats[agent_id] = watcher_info["last_heartbeat"]
    
    watcher_health = WatcherHealthStatus(
        active_count=active_count,
        heartbeats=heartbeats
    )
    
    # Get error count from last 24 hours
    # We'll use audit_logs with action containing "error" or "failed"
    # as a proxy for error tracking since there's no dedicated error_logs table
    error_count = 0
    recent_errors = []
    
    try:
        # Calculate 24 hours ago
        twenty_four_hours_ago = datetime.utcnow() - timedelta(hours=24)
        
        # Query audit logs for error-related actions
        error_logs = db.query(AuditLog).filter(
            and_(
                AuditLog.timestamp >= twenty_four_hours_ago,
                AuditLog.action.like('%error%') | AuditLog.action.like('%failed%')
            )
        ).order_by(AuditLog.timestamp.desc()).limit(10).all()
        
        error_count = db.query(AuditLog).filter(
            and_(
                AuditLog.timestamp >= twenty_four_hours_ago,
                AuditLog.action.like('%error%') | AuditLog.action.like('%failed%')
            )
        ).count()
        
        # Collect recent error messages
        recent_errors = [
            f"{log.action}: {log.details}" if log.details else log.action
            for log in error_logs
        ]
    
    except Exception as e:
        logger.error(f"Error querying audit logs for health check: {str(e)}", exc_info=True)
        # Continue with empty error data
    
    error_summary = ErrorSummary(
        count_24h=error_count,
        recent_errors=recent_errors
    )
    
    # Determine overall status
    overall_status = "healthy"
    
    if not db_status.connected:
        overall_status = "unhealthy"
    elif error_count > 50:  # More than 50 errors in 24 hours
        overall_status = "degraded"
    elif active_count == 0 and len(watcher_statuses) > 0:
        # Watchers exist but none are running
        overall_status = "degraded"
    
    # Check for failed watchers
    failed_watchers = sum(
        1 for info in watcher_statuses.values()
        if info["status"] == "failed"
    )
    if failed_watchers > 0:
        overall_status = "degraded"
    
    # Build response
    timestamp = datetime.utcnow().isoformat() + "Z"
    
    return HealthCheckResponse(
        status=overall_status,
        timestamp=timestamp,
        database=db_status,
        watchers=watcher_health,
        errors=error_summary
    )
