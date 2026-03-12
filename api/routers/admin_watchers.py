"""
Watcher control API endpoints.

This module provides REST API endpoints for controlling watcher processes:
- Starting watchers for agents
- Stopping watchers
- Triggering manual sync operations
- Getting watcher status for all agents

All endpoints require authentication and integrate with the WatcherRegistry
service for background task management.

Endpoints:
- POST /api/v1/watchers/{agent_id}/start - Start watcher
- POST /api/v1/watchers/{agent_id}/stop - Stop watcher
- POST /api/v1/watchers/{agent_id}/sync - Trigger manual sync
- GET /api/v1/watchers/status - Get all watcher statuses

Requirements:
- 4.1: Provide endpoints for starting, stopping, and triggering sync operations
- 4.5: Execute single sync operation when manual sync is triggered
- 4.6: Display real-time Watcher status for each Agent
- 21.1: Use existing gmail_lead_sync modules
- 21.2: Maintain idempotent processing guarantees
"""

from datetime import datetime
from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.orm import Session

from gmail_lead_sync.models import Credentials
from api.models.web_ui_models import User
from api.models.watcher_models import (
    WatcherStartResponse,
    WatcherStopResponse,
    WatcherSyncResponse,
    WatcherStatusResponse,
    WatcherStatusListResponse
)
from api.models.error_models import ErrorCode
from api.exceptions import (
    NotFoundException,
    ConflictException,
    ValidationException
)
from api.services.audit_log import record_audit_log


router = APIRouter()


# Dependencies that will be injected by FastAPI
def get_db():
    """Database dependency - will be overridden in tests."""
    from api.main import SessionLocal
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    """Authentication dependency - will be overridden in tests."""
    from api.auth import get_current_user as auth_get_current_user
    return auth_get_current_user(request, db)


def get_watcher_registry():
    """
    Get the global WatcherRegistry instance.
    
    This dependency will be initialized in main.py and injected here.
    For now, we'll import it directly.
    
    Returns:
        WatcherRegistry instance
    """
    from api.main import watcher_registry
    return watcher_registry


@router.post("/watchers/{agent_id}/start", response_model=WatcherStartResponse, status_code=status.HTTP_200_OK)
async def start_watcher(
    agent_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    registry = Depends(get_watcher_registry)
):
    """
    Start a watcher background task for the specified agent.
    
    Creates a background task that monitors the agent's Gmail inbox for
    new lead emails. Prevents starting multiple concurrent watchers for
    the same agent.
    
    Args:
        agent_id: Agent identifier
        db: Database session
        current_user: Authenticated user
        registry: WatcherRegistry instance
        
    Returns:
        Watcher start confirmation with status
        
    Raises:
        NotFoundException: If agent not found
        ConflictException: If watcher already running
        
    Requirements:
        - 4.1: Provide endpoints for starting watcher
        - 4.2: Create background task for agent when watcher is started
        - 4.4: Prevent multiple concurrent watchers for same agent
        - 4.8: Record all watcher start operations
    """
    # Verify agent exists
    credentials = db.query(Credentials).filter(Credentials.agent_id == agent_id).first()
    if not credentials:
        raise NotFoundException(
            message=f"Agent '{agent_id}' not found",
            code=ErrorCode.NOT_FOUND_RESOURCE
        )
    
    # Attempt to start watcher
    started = await registry.start_watcher(agent_id)
    
    if not started:
        raise ConflictException(
            message=f"Watcher for agent '{agent_id}' is already running",
            code=ErrorCode.CONFLICT_RESOURCE_EXISTS
        )
    
    # Record audit log
    record_audit_log(
        db_session=db,
        user_id=current_user.id,
        action="watcher_started",
        resource_type="watcher",
        resource_id=credentials.id,
        details=f"Started watcher for agent {agent_id}"
    )
    
    # Get current status
    watcher_status = await registry.get_status(agent_id)
    
    return WatcherStartResponse(
        agent_id=agent_id,
        status=watcher_status["status"],
        started_at=watcher_status["started_at"],
        message=f"Watcher started successfully for agent '{agent_id}'"
    )


@router.post("/watchers/{agent_id}/stop", response_model=WatcherStopResponse, status_code=status.HTTP_200_OK)
async def stop_watcher(
    agent_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    registry = Depends(get_watcher_registry)
):
    """
    Gracefully stop the watcher task for the specified agent.
    
    Cancels the background task and waits for it to complete gracefully.
    
    Args:
        agent_id: Agent identifier
        db: Database session
        current_user: Authenticated user
        registry: WatcherRegistry instance
        
    Returns:
        Watcher stop confirmation
        
    Raises:
        NotFoundException: If agent or watcher not found
        
    Requirements:
        - 4.1: Provide endpoints for stopping watcher
        - 4.3: Gracefully terminate background task when watcher is stopped
        - 4.8: Record all watcher stop operations
    """
    # Verify agent exists
    credentials = db.query(Credentials).filter(Credentials.agent_id == agent_id).first()
    if not credentials:
        raise NotFoundException(
            message=f"Agent '{agent_id}' not found",
            code=ErrorCode.NOT_FOUND_RESOURCE
        )
    
    # Attempt to stop watcher
    stopped = await registry.stop_watcher(agent_id)
    
    if not stopped:
        raise NotFoundException(
            message=f"No running watcher found for agent '{agent_id}'",
            code=ErrorCode.NOT_FOUND_RESOURCE
        )
    
    # Record audit log
    record_audit_log(
        db_session=db,
        user_id=current_user.id,
        action="watcher_stopped",
        resource_type="watcher",
        resource_id=credentials.id,
        details=f"Stopped watcher for agent {agent_id}"
    )
    
    return WatcherStopResponse(
        agent_id=agent_id,
        status="stopped",
        message=f"Watcher stopped successfully for agent '{agent_id}'"
    )


@router.post("/watchers/{agent_id}/sync", response_model=WatcherSyncResponse, status_code=status.HTTP_200_OK)
async def trigger_sync(
    agent_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    registry = Depends(get_watcher_registry)
):
    """
    Trigger a manual sync operation for the specified agent.
    
    Signals the watcher to perform an immediate sync operation outside
    of its normal schedule.
    
    Args:
        agent_id: Agent identifier
        db: Database session
        current_user: Authenticated user
        registry: WatcherRegistry instance
        
    Returns:
        Sync trigger confirmation
        
    Raises:
        NotFoundException: If agent or watcher not found
        ValidationException: If watcher not running
        
    Requirements:
        - 4.1: Provide endpoints for triggering sync operations
        - 4.5: Execute single sync operation when manual sync is triggered
        - 4.8: Record all watcher sync operations
    """
    # Verify agent exists
    credentials = db.query(Credentials).filter(Credentials.agent_id == agent_id).first()
    if not credentials:
        raise NotFoundException(
            message=f"Agent '{agent_id}' not found",
            code=ErrorCode.NOT_FOUND_RESOURCE
        )
    
    # Attempt to trigger sync
    triggered = await registry.trigger_sync(agent_id)
    
    if not triggered:
        raise ValidationException(
            message=f"Cannot trigger sync: watcher for agent '{agent_id}' is not running",
            code=ErrorCode.VALIDATION_ERROR
        )
    
    # Record audit log
    record_audit_log(
        db_session=db,
        user_id=current_user.id,
        action="watcher_sync_triggered",
        resource_type="watcher",
        resource_id=credentials.id,
        details=f"Triggered manual sync for agent {agent_id}"
    )
    
    timestamp = datetime.utcnow().isoformat() + "Z"
    
    return WatcherSyncResponse(
        agent_id=agent_id,
        sync_triggered=True,
        timestamp=timestamp,
        message=f"Manual sync triggered successfully for agent '{agent_id}'"
    )


@router.get("/watchers/status", response_model=WatcherStatusListResponse, status_code=status.HTTP_200_OK)
async def get_all_watcher_statuses(
    current_user: User = Depends(get_current_user),
    registry = Depends(get_watcher_registry)
):
    """
    Get the status of all watchers.
    
    Returns real-time status information for all registered watchers
    including heartbeat timestamps, last sync times, and error states.
    
    Args:
        current_user: Authenticated user
        registry: WatcherRegistry instance
        
    Returns:
        List of all watcher statuses
        
    Requirements:
        - 4.6: Display real-time Watcher status for each Agent
        - 4.7: Track Watcher heartbeats and last sync timestamps
    """
    # Get all watcher statuses from registry
    all_statuses = await registry.get_all_statuses()
    
    # Convert to response models
    watchers = [
        WatcherStatusResponse(
            agent_id=status_data["agent_id"],
            status=status_data["status"],
            last_heartbeat=status_data["last_heartbeat"],
            last_sync=status_data["last_sync"],
            error=status_data["error"],
            started_at=status_data["started_at"]
        )
        for status_data in all_statuses.values()
    ]
    
    return WatcherStatusListResponse(watchers=watchers)
